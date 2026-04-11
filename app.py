"""
app.py
------
Data Cleanliness Checker — Main Streamlit Application (Production Build)

Sections
--------
1.  Page config & custom CSS
2.  Session-state initialisation
3.  Sidebar  — data source + dataset selector
4.  Analysis tabs
    Tab 1  Overview        — 5-column metrics + dtype table + raw-data expander
    Tab 2  Missing Values  — summary table + Plotly bar (columns with >0 missing)
    Tab 3  Duplicates      — count + duplicate-row preview
    Tab 4  Full Report     — ydata-profiling (gate behind a button)
5.  Quick Clean
    — working_df session-state, smart imputation, dedup w/ before/after,
      cached CSV export via @st.cache_data
"""

from __future__ import annotations

import io
from typing import Optional

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.sources.local_source import render_local_uploader
from src.sources.drive_source import render_drive_browser
from src.ui.dataset_selector import render_dataset_selector, get_active_dataframe

# ── 1. Page Config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Data Cleanliness Checker",
    page_icon="🧹",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 2. Custom CSS ──────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
        /* ── Google font ── */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

        /* ── Sidebar header ── */
        [data-testid="stSidebar"] h1 {
            font-size: 1.1rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }

        /* ── Metric cards ── */
        [data-testid="stMetric"] {
            background: linear-gradient(135deg, #f8f9fa 0%, #eef2ff 100%);
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 14px 18px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        }
        [data-testid="stMetricLabel"] { font-weight: 600; color: #475569; }
        [data-testid="stMetricValue"] { font-weight: 700; color: #1e293b; }

        /* ── Tab headers ── */
        .stTabs [data-baseweb="tab"] {
            font-weight: 600;
            letter-spacing: 0.01em;
        }
        .stTabs [data-baseweb="tab-list"] {
            border-bottom: 2px solid #e2e8f0;
        }

        /* ── Section card ── */
        .section-card {
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 16px;
        }

        /* ── Quick-clean action buttons ── */
        div[data-testid="stHorizontalBlock"] .stButton > button {
            width: 100%;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── 3. Session-State Initialisation ───────────────────────────────────────────

_DEFAULTS: dict = {
    "datasets": {},                     # dict[str, pd.DataFrame]
    "active_dataset": None,             # str | None
    "drive_folder_stack": [],           # list[{id, title}]
    "drive_current_folder_id": "root",  # str
    "drive_items": [],                  # list[dict]
    "gauth": None,
    "gdrive": None,
    # ── Working copy for incremental cleaning ──
    "working_df": None,                 # pd.DataFrame | None
    "working_df_source": None,          # str | None  — tracks which dataset it belongs to
}

for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── 4. Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🧹 Data Cleanliness Checker")
    st.caption("Upload or browse CSV files and inspect their quality.")
    st.divider()

    source = st.radio(
        "**Data Source**",
        options=["Local Upload", "Google Drive"],
        index=0,
        horizontal=True,
        key="data_source_radio",
    )

    st.markdown("")

    if source == "Local Upload":
        render_local_uploader()
    else:
        render_drive_browser()

    render_dataset_selector()

# ── 5. Main Panel ──────────────────────────────────────────────────────────────

df: Optional[pd.DataFrame]
df, active_name = get_active_dataframe()

if df is None:
    st.markdown("## 👋 Welcome to Data Cleanliness Checker")
    st.markdown(
        """
        Get an instant quality report on any CSV file:

        - 📂 **Upload** a local `.csv` or `.zip` file using the sidebar
        - 🌐 **Browse** your Google Drive and load a CSV with one click
        - 📊 View the **Overview**, **Missing Values**, **Duplicates** tabs
        - 📄 Generate a full **ydata-profiling HTML report**
        - ✨ **Quick-clean** and **download** — changes persist within your session

        _Use the sidebar on the left to get started._
        """
    )
    st.stop()

# Guard against empty DataFrames
if df.empty:
    st.error("⚠️ The selected file is empty. Please upload a valid dataset.")
    st.stop()

# ── Sync working_df when a new dataset is loaded ───────────────────────────────

if st.session_state["working_df_source"] != active_name:
    st.session_state["working_df"] = df.copy()
    st.session_state["working_df_source"] = active_name

# Convenience alias — analysis tabs always read from the *original* df
# Quick-clean tab always reads/writes st.session_state["working_df"]

# ── 6. Analysis Header ─────────────────────────────────────────────────────────

st.markdown(f"## 📊 Analysing: `{active_name}`")

tab_overview, tab_missing, tab_duplicates, tab_report, tab_clean = st.tabs(
    ["🗂️ Overview", "❓ Missing Values", "👥 Duplicates", "📄 Full Report", "✨ Quick Clean"]
)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 1 — OVERVIEW                                                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

with tab_overview:
    st.markdown("### Dataset Overview")

    try:
        rows, cols = df.shape
        total_cells = rows * cols

        n_missing = int(df.isnull().sum().sum())
        pct_missing = round(n_missing / total_cells * 100, 2) if total_cells > 0 else 0.0
        n_duplicates = int(df.duplicated().sum())
        memory_bytes = df.memory_usage(deep=True).sum()
        memory_mb = round(memory_bytes / 1_048_576, 3)

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Rows", f"{rows:,}")
        m2.metric("Columns", f"{cols:,}")
        m3.metric("Missing Cells", f"{n_missing:,}", f"{pct_missing} %")
        m4.metric("Duplicate Rows", f"{n_duplicates:,}")
        m5.metric("Memory Usage", f"{memory_mb} MB")

        st.divider()

        # ── Column-level summary ───────────────────────────────────────────────
        st.markdown("#### Column Statistics")

        null_counts = df.isnull().sum()
        dtype_df = pd.DataFrame(
            {
                "Column": df.columns,
                "Data Type": df.dtypes.astype(str).values,
                "Non-Null Count": df.count().values,
                "Null Count": null_counts.values,
                "Null %": (null_counts / len(df) * 100).round(2).values,
                "Unique Values": df.nunique().values,
            }
        )
        st.dataframe(dtype_df, use_container_width=True, hide_index=True)

        st.divider()

        # ── Raw data expander ──────────────────────────────────────────────────
        with st.expander("🔍 Raw Data Preview (first 100 rows)", expanded=False):
            st.dataframe(df.head(100), use_container_width=True)

    except Exception as exc:
        st.error(f"❌ Overview could not be rendered: {exc}")

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 2 — MISSING VALUES                                                    ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

with tab_missing:
    st.markdown("### Missing Values Analysis")

    try:
        if df.empty or len(df.columns) == 0:
            st.warning("No columns available for missing-value analysis.")
        else:
            missing_counts = df.isnull().sum()
            missing_pct = (missing_counts / len(df) * 100).round(2)

            # Full summary table (all columns, sorted by missing desc)
            summary_df = (
                pd.DataFrame(
                    {
                        "Column": df.columns,
                        "Data Type": df.dtypes.astype(str).values,
                        "Missing Count": missing_counts.values,
                        "Missing %": missing_pct.values,
                    }
                )
                .sort_values("Missing Count", ascending=False)
                .reset_index(drop=True)
            )

            total_missing = int(summary_df["Missing Count"].sum())
            cols_with_missing = int((summary_df["Missing Count"] > 0).sum())

            if total_missing == 0:
                st.success("✅ No missing values detected in this dataset!")
            else:
                st.markdown(
                    f"**{cols_with_missing}** column(s) have missing values "
                    f"({total_missing:,} missing cells in total)."
                )

                # ── Plotly bar — only columns with >0 missing ──────────────────
                chart_df = summary_df[summary_df["Missing Count"] > 0].copy()

                fig = px.bar(
                    chart_df,
                    x="Column",
                    y="Missing %",
                    color="Missing %",
                    color_continuous_scale="Reds",
                    title="Missing Value Rate by Column (columns with > 0 missing only)",
                    text="Missing %",
                    hover_data={"Missing Count": True},
                )
                fig.update_traces(
                    texttemplate="%{text:.1f}%",
                    textposition="outside",
                    marker_line_width=0,
                )
                fig.update_layout(
                    coloraxis_showscale=False,
                    height=420,
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(tickangle=-35),
                    yaxis=dict(title="Missing %", gridcolor="#e2e8f0"),
                    title_font_size=14,
                    margin=dict(t=50, b=60),
                )
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("#### Full Column Summary")
            st.dataframe(summary_df, use_container_width=True, hide_index=True)

    except Exception as exc:
        st.error(f"❌ Missing-value analysis failed: {exc}")

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 3 — DUPLICATES                                                        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

with tab_duplicates:
    st.markdown("### Duplicate Rows Analysis")

    try:
        dup_count = int(df.duplicated().sum())

        col_d1, col_d2 = st.columns(2)
        col_d1.metric("Total Rows", f"{len(df):,}")
        col_d2.metric("Duplicate Rows", f"{dup_count:,}")

        if dup_count == 0:
            st.success("✅ No duplicate rows found in this dataset!")
        else:
            pct_dup = round(dup_count / len(df) * 100, 2)
            st.warning(
                f"⚠️ Found **{dup_count:,}** duplicate row(s) "
                f"(**{pct_dup}%** of total rows)."
            )
            st.markdown("#### Preview of Duplicated Rows")
            st.caption(
                "Showing rows identified as duplicates (using `df[df.duplicated()]`). "
                "Preview capped at 200 rows."
            )
            # df.duplicated() marks only the *non-first* occurrence
            dup_preview = df[df.duplicated()].head(200)
            st.dataframe(dup_preview, use_container_width=True)

    except Exception as exc:
        st.error(f"❌ Duplicate analysis failed: {exc}")

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 4 — FULL REPORT (ydata-profiling)                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

with tab_report:
    st.markdown("### Full Profiling Report")
    st.info(
        "Generates an interactive HTML report using **ydata-profiling**. "
        "This may take a moment for large datasets. "
        "Click the button once — the report is not regenerated on every rerun."
    )

    if st.button("🔍 Generate Report", key="generate_report_btn"):
        with st.spinner("Generating profiling report… please wait."):
            try:
                from ydata_profiling import ProfileReport  # lazy import

                profile = ProfileReport(
                    df,
                    title=f"Profiling — {active_name}",
                    explorative=True,
                    minimal=False,
                    progress_bar=False,
                )
                report_html = profile.to_html()

                # Persist so the download button survives a rerun
                st.session_state["_report_html"] = report_html
                st.session_state["_report_name"] = active_name
                st.success("✅ Report generated successfully!")

            except ImportError:
                st.error(
                    "❌ **ydata-profiling** is not installed. "
                    "Run `pip install ydata-profiling` to enable this feature."
                )
            except Exception as exc:
                st.error(f"❌ Report generation failed: {exc}")

    # Render cached report outside the button block so it survives reruns
    if st.session_state.get("_report_html") and st.session_state.get("_report_name") == active_name:
        report_html = st.session_state["_report_html"]
        stem = active_name.rsplit(".", 1)[0]

        st.download_button(
            label="⬇️ Download HTML Report",
            data=report_html,
            file_name=f"{stem}_profile_report.html",
            mime="text/html",
            key="download_report_btn",
        )
        st.components.v1.html(report_html, height=850, scrolling=True)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  TAB 5 — QUICK CLEAN                                                       ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

# ── Helper: cached CSV serialisation ──────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _df_to_csv_bytes(df_hash_key: str, data: bytes) -> bytes:
    """
    Wrapper so Streamlit caches by content hash.
    We pass pre-serialised bytes in and return them — the real work is done
    before calling this function; the point is to memoize the result.
    """
    return data


def build_csv_bytes(frame: pd.DataFrame) -> bytes:
    """Convert DataFrame → UTF-8 CSV bytes, cached via content hash."""
    raw = frame.to_csv(index=False).encode("utf-8")
    # Use the length + first 512 bytes as a cheap hash key for cache lookup
    cache_key = f"{len(raw)}_{raw[:512]}"
    return _df_to_csv_bytes(cache_key, raw)


# ── Smart imputation logic ────────────────────────────────────────────────────

def smart_impute(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Fill missing values:
      - Numeric columns  → median  (skips all-NaN columns gracefully)
      - Object / string columns → first mode (skips all-NaN columns gracefully)

    Returns (cleaned_frame, cells_filled).
    Raises no exceptions — problem columns are silently skipped.
    """
    filled_cells = 0
    out = frame.copy()

    for col in out.columns:
        n_null = int(out[col].isnull().sum())
        if n_null == 0:
            continue

        try:
            if out[col].dtype.kind in ("i", "u", "f"):          # numeric kinds
                median_val = out[col].median()
                if pd.isna(median_val):                          # all-NaN column
                    continue
                out[col] = out[col].fillna(median_val)

            else:                                                # categorical
                mode_series = out[col].mode(dropna=True)
                if mode_series.empty:                            # all-NaN column
                    continue
                out[col] = out[col].fillna(mode_series.iloc[0])

            filled_cells += n_null

        except (TypeError, ValueError):
            # Incompatible dtype — skip silently
            continue

    return out, filled_cells


# ── Tab rendering ─────────────────────────────────────────────────────────────

with tab_clean:
    st.markdown("### ✨ Quick Clean Actions")
    st.caption(
        "Changes are applied **cumulatively** within your session. "
        "Switching to a different dataset resets the working copy."
    )

    # Always reference the mutable working copy
    wdf: pd.DataFrame = st.session_state["working_df"]

    # ── Working-copy stats ─────────────────────────────────────────────────────
    wrows, wcols = wdf.shape
    wn_missing = int(wdf.isnull().sum().sum())
    wn_dup = int(wdf.duplicated().sum())

    st.markdown("#### Current Working Dataset")
    cw1, cw2, cw3 = st.columns(3)
    cw1.metric("Rows", f"{wrows:,}", f"{wrows - len(df):+,} vs original")
    cw2.metric("Missing Cells", f"{wn_missing:,}")
    cw3.metric("Duplicate Rows", f"{wn_dup:,}")

    st.divider()

    # ── Action: Deduplication ─────────────────────────────────────────────────
    st.markdown("#### 🔁 Deduplication")

    if wn_dup == 0:
        st.success("✅ No duplicate rows in the current working dataset.")
    else:
        st.warning(f"⚠️ **{wn_dup:,}** duplicate row(s) found in the working dataset.")

    if st.button("🗑️ Drop Duplicate Rows", key="drop_dups_btn", disabled=(wn_dup == 0)):
        before_rows = len(wdf)
        wdf = wdf.drop_duplicates().reset_index(drop=True)
        after_rows = len(wdf)
        removed = before_rows - after_rows

        st.session_state["working_df"] = wdf
        st.success(
            f"✅ Deduplication complete — removed **{removed:,}** row(s).  \n"
            f"**Before:** {before_rows:,} rows → **After:** {after_rows:,} rows."
        )
        st.rerun()

    st.divider()

    # ── Action: Smart Imputation ───────────────────────────────────────────────
    st.markdown("#### 🧠 Smart Imputation")
    st.caption(
        "Numeric columns → **median**  |  Categorical / text columns → **mode**  \n"
        "All-NaN columns are skipped automatically."
    )

    wn_missing_now = int(wdf.isnull().sum().sum())

    if wn_missing_now == 0:
        st.success("✅ No missing values in the current working dataset.")
    else:
        st.info(f"ℹ️ **{wn_missing_now:,}** missing cell(s) will be filled.")

    if st.button(
        "🧹 Apply Smart Imputation",
        key="smart_impute_btn",
        disabled=(wn_missing_now == 0),
    ):
        try:
            wdf_imputed, cells_filled = smart_impute(wdf)
            st.session_state["working_df"] = wdf_imputed
            wdf = wdf_imputed
            if cells_filled > 0:
                st.success(f"✅ Filled **{cells_filled:,}** missing cell(s) using smart imputation.")
            else:
                st.info("ℹ️ No cells were filled — all columns may be all-NaN or unsupported types.")
            st.rerun()
        except Exception as exc:
            st.error(f"❌ Imputation failed: {exc}")

    st.divider()

    # ── Reset button ───────────────────────────────────────────────────────────
    st.markdown("#### ↩️ Reset Working Copy")

    if st.button("↩️ Reset to Original (discard all changes)", key="reset_wdf_btn"):
        st.session_state["working_df"] = df.copy()
        st.success("✅ Working dataset has been reset to the original uploaded file.")
        st.rerun()

    st.divider()

    # ── Export ─────────────────────────────────────────────────────────────────
    st.markdown("#### ⬇️ Export Cleaned CSV")

    try:
        csv_bytes = build_csv_bytes(st.session_state["working_df"])
        stem = active_name.rsplit(".", 1)[0]
        out_filename = f"{stem}_cleaned.csv"

        st.download_button(
            label=f"⬇️ Download `{out_filename}`",
            data=csv_bytes,
            file_name=out_filename,
            mime="text/csv",
            key="download_clean_btn",
        )
    except Exception as exc:
        st.error(f"❌ CSV export failed: {exc}")

    # ── Cleaned data preview ───────────────────────────────────────────────────
    st.markdown("#### Cleaned Data Preview (first 100 rows)")
    st.dataframe(st.session_state["working_df"].head(100), use_container_width=True)
