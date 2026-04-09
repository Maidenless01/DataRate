"""
app.py
------
Data Cleanliness Checker — Main Streamlit Application
Assembles the sidebar (data sources + dataset selector) and the
main analysis panel (tabs: Overview, Missing Values, Duplicates, Full Report).
"""

import io

import pandas as pd
import plotly.express as px
import streamlit as st

from src.sources.local_source import render_local_uploader
from src.sources.drive_source import render_drive_browser
from src.ui.dataset_selector import render_dataset_selector, get_active_dataframe

# ── Page Config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Data Cleanliness Checker",
    page_icon="🧹",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
        /* Sidebar header */
        [data-testid="stSidebar"] h1 {
            font-size: 1.1rem;
            font-weight: 700;
        }
        /* Metric cards */
        [data-testid="stMetric"] {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 12px 16px;
        }
        /* Tab headers */
        .stTabs [data-baseweb="tab"] {
            font-weight: 600;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Session State Initialisation ───────────────────────────────────────────────

_DEFAULTS = {
    "datasets": {},                      # dict[str, pd.DataFrame]
    "active_dataset": None,              # str | None
    "drive_folder_stack": [],            # list[{id, title}]
    "drive_current_folder_id": "root",  # str
    "drive_items": [],                   # list[dict]
    "gauth": None,
    "gdrive": None,
}

for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🧹 Data Cleanliness Checker")
    st.caption("Upload or browse CSV files and inspect their quality.")
    st.divider()

    # Data source selector
    source = st.radio(
        "**Data Source**",
        options=["Local Upload", "Google Drive"],
        index=0,
        horizontal=True,
        key="data_source_radio",
    )

    st.markdown("")  # spacing

    if source == "Local Upload":
        render_local_uploader()
    else:
        render_drive_browser()

    # Dataset selector (always visible at the bottom of sidebar)
    render_dataset_selector()

# ── Main Panel ─────────────────────────────────────────────────────────────────

df, active_name = get_active_dataframe()

if df is None:
    # Landing / empty state
    st.markdown("## 👋 Welcome to Data Cleanliness Checker")
    st.markdown(
        """
        Get an instant quality report on any CSV file:

        - 📂 **Upload** a local `.csv` or `.zip` file using the sidebar
        - 🌐 **Browse** your Google Drive and load a CSV with one click
        - 📊 View the **Overview**, **Missing Values**, **Duplicates** tabs
        - 📄 Generate a full **ydata-profiling HTML report**
        - ✨ **Quick-clean** and **download** the fixed file

        _Use the sidebar on the left to get started._
        """
    )
    st.stop()

# ── Analysis Tabs ──────────────────────────────────────────────────────────────

st.markdown(f"## 📊 Analysing: `{active_name}`")

tab_overview, tab_missing, tab_duplicates, tab_report, tab_clean = st.tabs(
    ["🗂️ Overview", "❓ Missing Values", "👥 Duplicates", "📄 Full Report", "✨ Quick Clean"]
)

# ── Tab 1: Overview ────────────────────────────────────────────────────────────

with tab_overview:
    st.markdown("### Dataset Overview")

    rows, cols = df.shape
    n_missing = int(df.isnull().sum().sum())
    pct_missing = round(n_missing / (rows * cols) * 100, 2) if rows * cols > 0 else 0
    n_duplicates = int(df.duplicated().sum())
    memory_mb = round(df.memory_usage(deep=True).sum() / 1024 / 1024, 3)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Rows", f"{rows:,}")
    m2.metric("Columns", f"{cols}")
    m3.metric("Missing Cells", f"{n_missing:,}", f"{pct_missing}%")
    m4.metric("Duplicate Rows", f"{n_duplicates:,}")
    m5.metric("Memory", f"{memory_mb} MB")

    st.divider()
    st.markdown("#### Column Data Types")
    dtype_df = pd.DataFrame({
        "Column": df.columns,
        "Type": df.dtypes.astype(str).values,
        "Non-Null Count": df.count().values,
        "Null Count": df.isnull().sum().values,
        "Null %": (df.isnull().sum() / len(df) * 100).round(2).values,
    })
    st.dataframe(dtype_df, use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### Preview (first 50 rows)")
    st.dataframe(df.head(50), use_container_width=True)

# ── Tab 2: Missing Values ──────────────────────────────────────────────────────

with tab_missing:
    st.markdown("### Missing Values Analysis")

    missing_series = df.isnull().sum()
    missing_pct = (missing_series / len(df) * 100).round(2)
    missing_df = pd.DataFrame({
        "Column": df.columns,
        "Missing Count": missing_series.values,
        "Missing %": missing_pct.values,
    }).sort_values("Missing Count", ascending=False)

    total_missing = missing_df["Missing Count"].sum()
    if total_missing == 0:
        st.success("✅ No missing values detected in this dataset!")
    else:
        cols_with_missing = (missing_df["Missing Count"] > 0).sum()
        st.markdown(
            f"**{cols_with_missing}** column(s) have missing values "
            f"({total_missing:,} total missing cells)."
        )

        # Bar chart
        chart_df = missing_df[missing_df["Missing Count"] > 0]
        fig = px.bar(
            chart_df,
            x="Column",
            y="Missing %",
            color="Missing %",
            color_continuous_scale="Reds",
            title="Missing % per Column",
            text="Missing %",
        )
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(showlegend=False, height=400)
        st.plotly_chart(fig, use_container_width=True)

        st.dataframe(missing_df, use_container_width=True, hide_index=True)

# ── Tab 3: Duplicates ──────────────────────────────────────────────────────────

with tab_duplicates:
    st.markdown("### Duplicate Rows Analysis")

    dup_mask = df.duplicated(keep=False)
    dup_count = df.duplicated().sum()

    if dup_count == 0:
        st.success("✅ No duplicate rows found in this dataset!")
    else:
        st.warning(f"⚠️ Found **{dup_count:,}** duplicate row(s).")
        st.markdown("#### Preview of Duplicate Rows")
        st.dataframe(df[dup_mask].head(100), use_container_width=True)

# ── Tab 4: Full Report ─────────────────────────────────────────────────────────

with tab_report:
    st.markdown("### Full Profiling Report")
    st.info(
        "Generates an interactive HTML report using **ydata-profiling**. "
        "This may take a moment for large datasets."
    )

    if st.button("🔍 Generate Report", key="generate_report_btn"):
        with st.spinner("Generating profiling report…"):
            try:
                from ydata_profiling import ProfileReport

                profile = ProfileReport(
                    df,
                    title=f"Profiling — {active_name}",
                    explorative=True,
                    minimal=False,
                )
                report_html = profile.to_html()
                st.download_button(
                    label="⬇️ Download HTML Report",
                    data=report_html,
                    file_name=f"{active_name.rsplit('.', 1)[0]}_report.html",
                    mime="text/html",
                    key="download_report_btn",
                )
                st.components.v1.html(report_html, height=800, scrolling=True)
            except ImportError:
                st.error(
                    "❌ ydata-profiling is not installed. "
                    "Run `pip install ydata-profiling` to enable this feature."
                )
            except Exception as exc:
                st.error(f"❌ Report generation failed: {exc}")

# ── Tab 5: Quick Clean ─────────────────────────────────────────────────────────

with tab_clean:
    st.markdown("### ✨ Quick Clean Actions")

    col_a, col_b = st.columns(2)

    with col_a:
        remove_dups = st.checkbox("Remove duplicate rows", value=True, key="clean_dups")
    with col_b:
        fill_missing = st.checkbox(
            "Fill missing values (median / mode)", value=True, key="clean_fill"
        )

    if st.button("🧹 Apply & Download Cleaned CSV", key="apply_clean_btn"):
        cleaned = df.copy()

        if remove_dups:
            before = len(cleaned)
            cleaned = cleaned.drop_duplicates()
            after = len(cleaned)
            st.success(f"Removed **{before - after:,}** duplicate rows.")

        if fill_missing:
            filled = 0
            for col in cleaned.columns:
                n = cleaned[col].isnull().sum()
                if n == 0:
                    continue
                if cleaned[col].dtype.kind in ("i", "u", "f"):  # numeric
                    cleaned[col] = cleaned[col].fillna(cleaned[col].median())
                else:
                    mode_vals = cleaned[col].mode()
                    if not mode_vals.empty:
                        cleaned[col] = cleaned[col].fillna(mode_vals[0])
                filled += n
            st.success(f"Filled **{filled:,}** missing cells.")

        # Build download
        csv_bytes = cleaned.to_csv(index=False).encode("utf-8")
        out_name = f"{active_name.rsplit('.', 1)[0]}_cleaned.csv"
        st.download_button(
            label=f"⬇️ Download `{out_name}`",
            data=csv_bytes,
            file_name=out_name,
            mime="text/csv",
            key="download_clean_btn",
        )

        st.markdown("#### Cleaned Data Preview")
        st.dataframe(cleaned.head(50), use_container_width=True)
