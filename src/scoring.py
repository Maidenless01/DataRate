"""
scoring.py
----------
Cleanliness Score engine for the Data Cleanliness Checker.

Produces a ScoreResult (score 0-100, letter grade, penalty breakdown)
for both tabular (pd.DataFrame) and image (ImageDataset) datasets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from src.sources.image_source import ImageDataset


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class PenaltyItem:
    label: str
    penalty: float          # negative = bad, positive = bonus
    detail: str = ""        # human-readable explanation


@dataclass
class ScoreResult:
    score: int              # 0-100
    grade: str              # A / B / C / D / F
    color: str              # hex colour matching grade
    breakdown: list[PenaltyItem] = field(default_factory=list)
    summary: str = ""


# ── Grade helpers ──────────────────────────────────────────────────────────────

def _grade(score: int) -> tuple[str, str]:
    """Return (letter, hex-color) for a 0-100 score."""
    if score >= 90:
        return "A", "#22c55e"   # green
    if score >= 75:
        return "B", "#84cc16"   # lime
    if score >= 60:
        return "C", "#f59e0b"   # amber
    if score >= 40:
        return "D", "#f97316"   # orange
    return "F", "#ef4444"       # red


# ══════════════════════════════════════════════════════════════════════════════
# TABULAR SCORING
# ══════════════════════════════════════════════════════════════════════════════

def score_dataframe(df: pd.DataFrame) -> ScoreResult:
    """
    Compute a cleanliness score for a tabular DataFrame.

    Penalty model (max 90 pts deducted from a 100 base):
      - Missing values          – up to 30 pts
      - Duplicate rows          – up to 20 pts
      - Constant columns        – up to 10 pts
      - Mixed-type columns      – up to 10 pts
      - Outlier-heavy columns   – up to 15 pts   (IQR method)
      - High-cardinality text   – up to  5 pts
    """
    breakdown: list[PenaltyItem] = []
    total_penalty = 0.0

    rows, cols = df.shape
    total_cells = rows * cols

    # ── 1. Missing values ─────────────────────────────────────────────────────
    n_missing = int(df.isnull().sum().sum())
    if total_cells > 0:
        missing_pct = n_missing / total_cells
    else:
        missing_pct = 0.0
    # Logarithmic scale: 1% → ~3 pts, 10% → ~15 pts, 50% → 30 pts
    if missing_pct > 0:
        penalty_missing = min(30.0, 30.0 * (missing_pct ** 0.5))
        detail = f"{n_missing:,} missing cells ({missing_pct*100:.1f}% of all cells)"
    else:
        penalty_missing = 0.0
        detail = "No missing values ✅"
    breakdown.append(PenaltyItem("Missing Values", -round(penalty_missing, 1), detail))
    total_penalty += penalty_missing

    # ── 2. Duplicate rows ────────────────────────────────────────────────────
    n_dups = int(df.duplicated().sum())
    if rows > 0:
        dup_pct = n_dups / rows
    else:
        dup_pct = 0.0
    if dup_pct > 0:
        penalty_dups = min(20.0, 20.0 * (dup_pct ** 0.5))
        detail = f"{n_dups:,} duplicate rows ({dup_pct*100:.1f}%)"
    else:
        penalty_dups = 0.0
        detail = "No duplicate rows ✅"
    breakdown.append(PenaltyItem("Duplicate Rows", -round(penalty_dups, 1), detail))
    total_penalty += penalty_dups

    # ── 3. Constant columns ───────────────────────────────────────────────────
    if cols > 0:
        constant_cols = [c for c in df.columns if df[c].nunique(dropna=True) <= 1]
        n_constant = len(constant_cols)
        penalty_const = min(10.0, (n_constant / cols) * 10.0)
        if n_constant:
            detail = f"{n_constant} constant column(s): {', '.join(constant_cols[:5])}"
        else:
            detail = "No constant columns ✅"
    else:
        penalty_const = 0.0
        detail = "N/A"
    breakdown.append(PenaltyItem("Constant Columns", -round(penalty_const, 1), detail))
    total_penalty += penalty_const

    # ── 4. Mixed-type columns ─────────────────────────────────────────────────
    mixed_cols: list[str] = []
    for col in df.select_dtypes(include="object").columns:
        series = df[col].dropna()
        if len(series) == 0:
            continue
        # Check if the column contains a mix of numeric-looking and non-numeric values
        numeric_count = pd.to_numeric(series, errors="coerce").notna().sum()
        if 0 < numeric_count < len(series):
            mixed_cols.append(col)
    n_mixed = len(mixed_cols)
    if cols > 0 and n_mixed > 0:
        penalty_mixed = min(10.0, (n_mixed / cols) * 10.0)
        detail = f"{n_mixed} mixed-type column(s): {', '.join(mixed_cols[:5])}"
    else:
        penalty_mixed = 0.0
        detail = "No mixed-type columns ✅"
    breakdown.append(PenaltyItem("Mixed-Type Columns", -round(penalty_mixed, 1), detail))
    total_penalty += penalty_mixed

    # ── 5. Outlier-heavy columns (IQR method) ─────────────────────────────────
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    n_outlier_cols = 0
    total_outlier_cells = 0
    total_numeric_cells = 0
    for col in num_cols:
        series = df[col].dropna()
        if len(series) < 4:
            continue
        q1, q3 = series.quantile(0.25), series.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        outliers = ((series < (q1 - 1.5 * iqr)) | (series > (q3 + 1.5 * iqr))).sum()
        total_outlier_cells += int(outliers)
        total_numeric_cells += len(series)
        if outliers / len(series) > 0.10:   # >10% outliers in that column
            n_outlier_cols += 1

    if total_numeric_cells > 0 and total_outlier_cells > 0:
        outlier_pct = total_outlier_cells / total_numeric_cells
        penalty_outliers = min(15.0, 15.0 * (outlier_pct ** 0.5))
        detail = (
            f"{total_outlier_cells:,} outlier values across {n_outlier_cols} column(s) "
            f"({outlier_pct*100:.1f}% of numeric cells)"
        )
    else:
        penalty_outliers = 0.0
        detail = "No significant outliers ✅"
    breakdown.append(PenaltyItem("Outlier-Heavy Columns", -round(penalty_outliers, 1), detail))
    total_penalty += penalty_outliers

    # ── 6. High-cardinality text columns ─────────────────────────────────────
    text_cols = df.select_dtypes(include="object").columns.tolist()
    high_card_cols: list[str] = []
    for col in text_cols:
        if rows > 0 and df[col].nunique() / rows > 0.95 and len(df[col]) > 50:
            high_card_cols.append(col)
    n_hc = len(high_card_cols)
    if n_hc > 0:
        penalty_hc = min(5.0, n_hc * 1.5)
        detail = f"{n_hc} high-cardinality column(s): {', '.join(high_card_cols[:5])}"
    else:
        penalty_hc = 0.0
        detail = "No high-cardinality issues ✅"
    breakdown.append(PenaltyItem("High-Cardinality Text", -round(penalty_hc, 1), detail))
    total_penalty += penalty_hc

    # ── Final score ───────────────────────────────────────────────────────────
    raw_score = max(0.0, 100.0 - total_penalty)
    score = int(round(raw_score))
    grade, color = _grade(score)

    summary = (
        f"Dataset has {rows:,} rows × {cols} columns. "
        f"Total penalty: {total_penalty:.1f} pts. "
        f"Cleanliness grade: **{grade}** ({score}/100)."
    )

    return ScoreResult(score=score, grade=grade, color=color, breakdown=breakdown, summary=summary)


# ══════════════════════════════════════════════════════════════════════════════
# IMAGE SCORING
# ══════════════════════════════════════════════════════════════════════════════

def score_image_dataset(dataset: "ImageDataset") -> ScoreResult:
    """
    Compute a cleanliness score for an ImageDataset.

    Penalty model:
      - Corrupt / unreadable images  – up to 30 pts
      - Duplicate images (md5 hash)  – up to 25 pts
      - Low-resolution (<64×64)      – up to 15 pts
      - Near-blank images            – up to 15 pts
      - Class imbalance              – up to 15 pts
    """
    import hashlib
    from collections import Counter

    breakdown: list[PenaltyItem] = []
    total_penalty = 0.0

    images = dataset.images
    n_total = len(images)

    if n_total == 0:
        return ScoreResult(
            score=0, grade="F", color="#ef4444",
            breakdown=[PenaltyItem("No Images", -100, "Dataset is empty")],
            summary="Empty image dataset."
        )

    # ── 1. Corrupt images ────────────────────────────────────────────────────
    n_corrupt = sum(1 for img in images if img.pil_image is None)
    if n_corrupt > 0:
        corrupt_pct = n_corrupt / n_total
        penalty_corrupt = min(30.0, 30.0 * (corrupt_pct ** 0.5))
        detail = f"{n_corrupt}/{n_total} images are corrupt or unreadable"
    else:
        penalty_corrupt = 0.0
        detail = "No corrupt images ✅"
    breakdown.append(PenaltyItem("Corrupt Images", -round(penalty_corrupt, 1), detail))
    total_penalty += penalty_corrupt

    # Only work with valid images from here on
    valid = [img for img in images if img.pil_image is not None]
    n_valid = len(valid)

    # ── 2. Duplicate images (MD5 hash of raw bytes) ──────────────────────────
    hashes: dict[str, list[str]] = {}
    for img in valid:
        try:
            import io as _io
            buf = _io.BytesIO()
            img.pil_image.save(buf, format="PNG")
            h = hashlib.md5(buf.getvalue()).hexdigest()
            hashes.setdefault(h, []).append(img.name)
        except Exception:
            pass
    n_dup_groups = sum(1 for v in hashes.values() if len(v) > 1)
    n_dup_images = sum(len(v) - 1 for v in hashes.values() if len(v) > 1)
    if n_valid > 0 and n_dup_images > 0:
        dup_pct = n_dup_images / n_valid
        penalty_dups = min(25.0, 25.0 * (dup_pct ** 0.5))
        detail = f"{n_dup_images} duplicate image(s) in {n_dup_groups} group(s)"
    else:
        penalty_dups = 0.0
        detail = "No duplicate images ✅"
    breakdown.append(PenaltyItem("Duplicate Images", -round(penalty_dups, 1), detail))
    total_penalty += penalty_dups

    # ── 3. Low-resolution images (<64×64) ────────────────────────────────────
    low_res = [img for img in valid if img.width < 64 or img.height < 64]
    n_low_res = len(low_res)
    if n_valid > 0 and n_low_res > 0:
        lr_pct = n_low_res / n_valid
        penalty_lr = min(15.0, 15.0 * (lr_pct ** 0.5))
        detail = f"{n_low_res}/{n_valid} images are low-resolution (<64×64 px)"
    else:
        penalty_lr = 0.0
        detail = "All images meet minimum resolution ✅"
    breakdown.append(PenaltyItem("Low-Resolution Images", -round(penalty_lr, 1), detail))
    total_penalty += penalty_lr

    # ── 4. Near-blank images (very low pixel variance) ────────────────────────
    blank_count = 0
    for img in valid:
        try:
            arr = np.array(img.pil_image.convert("L"), dtype=np.float32)
            if arr.std() < 5.0:
                blank_count += 1
        except Exception:
            pass
    if n_valid > 0 and blank_count > 0:
        blank_pct = blank_count / n_valid
        penalty_blank = min(15.0, 15.0 * (blank_pct ** 0.5))
        detail = f"{blank_count}/{n_valid} images appear near-blank (low pixel variance)"
    else:
        penalty_blank = 0.0
        detail = "No near-blank images ✅"
    breakdown.append(PenaltyItem("Near-Blank Images", -round(penalty_blank, 1), detail))
    total_penalty += penalty_blank

    # ── 5. Class imbalance ────────────────────────────────────────────────────
    labels = [img.label for img in valid]
    label_counts = Counter(labels)
    n_classes = len(label_counts)
    if n_classes > 1 and n_valid > 0:
        counts = list(label_counts.values())
        max_c, min_c = max(counts), min(counts)
        imbalance_ratio = 1.0 - (min_c / max_c)   # 0 = perfect, 1 = extreme
        penalty_imbal = min(15.0, 15.0 * imbalance_ratio)
        detail = (
            f"{n_classes} classes detected. "
            f"Largest: {max_c}, Smallest: {min_c} "
            f"(imbalance ratio: {imbalance_ratio*100:.0f}%)"
        )
    else:
        penalty_imbal = 0.0
        detail = "Single class or perfectly balanced ✅" if n_classes <= 1 else "Balanced classes ✅"
    breakdown.append(PenaltyItem("Class Imbalance", -round(penalty_imbal, 1), detail))
    total_penalty += penalty_imbal

    # ── Final score ───────────────────────────────────────────────────────────
    raw_score = max(0.0, 100.0 - total_penalty)
    score = int(round(raw_score))
    grade, color = _grade(score)

    summary = (
        f"Image dataset has {n_total} image(s), {n_valid} valid. "
        f"Total penalty: {total_penalty:.1f} pts. "
        f"Cleanliness grade: **{grade}** ({score}/100)."
    )

    return ScoreResult(score=score, grade=grade, color=color, breakdown=breakdown, summary=summary)
