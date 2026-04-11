"""
local_source.py
---------------
Handles local file uploads via Streamlit's file_uploader.

Supported types:
  - CSV / ZIP-of-CSVs  → stored as pd.DataFrame in session_state["datasets"]
  - Image / ZIP-of-images → stored as ImageDataset in session_state["datasets"]

Loaded objects are stored in st.session_state["datasets"][filename].
"""

import io
import zipfile
from pathlib import PurePosixPath

import pandas as pd
import streamlit as st

from src.sources.image_source import IMAGE_EXTS, handle_image_upload


# ── Accepted CSV extensions ────────────────────────────────────────────────────
_CSV_EXTS = {".csv", ".tsv"}

# ── Accepted file types for the uploader ─────────────────────────────────────
_UPLOADER_TYPES = ["csv", "zip", "jpg", "jpeg", "png", "bmp", "webp"]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _register_df(name: str, df: pd.DataFrame) -> None:
    """Store a DataFrame in session state, handling duplicate filename collisions."""
    key = name
    if key in st.session_state["datasets"]:
        base = PurePosixPath(name).stem
        ext = PurePosixPath(name).suffix
        counter = 1
        while key in st.session_state["datasets"]:
            key = f"{base}_local_{counter}{ext}"
            counter += 1
    st.session_state["datasets"][key] = df


def _load_csv_bytes(name: str, raw_bytes: bytes) -> pd.DataFrame | None:
    """Parse CSV bytes into a DataFrame, returning None on failure."""
    try:
        sep = "\t" if name.lower().endswith(".tsv") else ","
        df = pd.read_csv(io.BytesIO(raw_bytes), sep=sep)
        return df
    except Exception as exc:
        st.warning(f"⚠️ Could not parse `{name}`: {exc}")
        return None


def _handle_single_csv(uploaded_file) -> None:
    """Load a single .csv upload into session state."""
    raw = uploaded_file.read()
    df = _load_csv_bytes(uploaded_file.name, raw)
    if df is not None:
        _register_df(uploaded_file.name, df)
        st.success(
            f"✅ Loaded **{uploaded_file.name}** — "
            f"{df.shape[0]:,} rows × {df.shape[1]} columns"
        )


def _handle_zip(uploaded_file) -> None:
    """
    Detect ZIP content and route appropriately:
      - Contains CSVs → load each as a DataFrame.
      - Contains images → delegate to image_source.handle_image_upload.
      - Mixed → handle CSVs first, then images.
    """
    raw = uploaded_file.read()

    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            members = zf.namelist()
    except zipfile.BadZipFile:
        st.error("❌ The uploaded file is not a valid ZIP archive.")
        return

    csv_members = [m for m in members if PurePosixPath(m).suffix.lower() in _CSV_EXTS]
    img_members = [
        m for m in members
        if PurePosixPath(m).suffix.lower() in IMAGE_EXTS
        and not PurePosixPath(m).name.startswith(".")
        and not m.startswith("__MACOSX")
    ]

    if not csv_members and not img_members:
        st.warning("⚠️ The ZIP contains no recognised CSV or image files.")
        return

    # ── Load CSV members ────────────────────────────────────────────────────
    csv_loaded = 0
    if csv_members:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            for member in csv_members:
                base_name = PurePosixPath(member).name
                member_bytes = zf.read(member)
                df = _load_csv_bytes(base_name, member_bytes)
                if df is not None:
                    _register_df(base_name, df)
                    csv_loaded += 1
        if csv_loaded:
            st.success(f"✅ Extracted **{csv_loaded}** CSV file(s) from `{uploaded_file.name}`")

    # ── Load image members (route to image handler) ─────────────────────────
    if img_members:
        # Re-wrap the raw bytes as a file-like object with the required .name attribute
        class _FakFile:
            def __init__(self, n, b):
                self.name = n
                self._b = b
            def read(self):
                return self._b

        handle_image_upload(_FakFile(uploaded_file.name, raw))


# ── Public entry point ─────────────────────────────────────────────────────────

def render_local_uploader() -> None:
    """
    Render the local file upload UI panel.
    Call this inside the sidebar or main body as needed.
    """
    st.markdown("#### 📂 Upload Local File")
    uploaded = st.file_uploader(
        label="Choose a CSV, ZIP or image file",
        type=_UPLOADER_TYPES,
        accept_multiple_files=False,
        help=(
            "Upload a CSV, a ZIP archive (CSVs or images), "
            "or a single image (JPG, PNG, BMP, WEBP)."
        ),
        key="local_file_uploader",
    )

    if uploaded is not None:
        ext = PurePosixPath(uploaded.name).suffix.lower()

        if ext in _CSV_EXTS:
            _handle_single_csv(uploaded)

        elif ext == ".zip":
            _handle_zip(uploaded)

        elif ext in IMAGE_EXTS:
            handle_image_upload(uploaded)

        else:
            st.error(
                f"❌ Unsupported file type `{ext}`. "
                "Please upload a .csv, .zip, or image file."
            )
