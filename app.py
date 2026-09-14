"""
app.py
------
Data Cleanliness Checker — Main Streamlit Application

Sections
--------
1.  Page config & custom CSS
2.  Session-state initialisation
3.  Sidebar — data source + dataset selector
4.  Router — dispatch to tabular or image analysis panels
5.  Tabular analysis
    Tab 1  Overview        — 5-column metrics + dtype table + raw-data expander
    Tab 2  Missing Values  — summary table + Plotly bar
    Tab 3  Duplicates      — count + duplicate-row preview
    Tab 4  Full Report     — custom pandas+Plotly profiling (no ydata-profiling)
    Tab 5  Score           — cleanliness gauge + breakdown
    Tab 6  Quick Clean     — imputation, dedup, export
6.  Image analysis
    Tab 1  Overview        — thumbnail grid, class counts, resolution stats
    Tab 2  Quality Issues  — corrupt, blank, low-res images
    Tab 3  Duplicates      — hash-based detection + preview
    Tab 4  Score           — cleanliness gauge + breakdown
    Tab 5  Quick Fix       — remove bad images + download cleaned ZIP
"""

from __future__ import annotations

import io
import zipfile
from collections import Counter
from typing import Optional, Union

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.sources.local_source import render_local_uploader
from src.sources.drive_source import render_drive_browser
from src.sources.image_source import ImageDataset, ImageEntry
from src.ui.dataset_selector import render_dataset_selector, get_active_dataset
from src.scoring import score_dataframe, score_image_dataset, ScoreResult

# ── 1. Page Config ─────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="DataRate — Data Cleanliness Checker",
    page_icon="🧹",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 2. Custom CSS ──────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,300;0,14..32,400;0,14..32,500;0,14..32,600;0,14..32,700;0,14..32,800;1,14..32,400&display=swap');

        /* ── Global typography ── */
        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        /* ── Hide Streamlit default header & footer ── */
        #MainMenu { visibility: hidden; }
        footer { visibility: hidden; }
        [data-testid="stHeader"] { background: transparent; }
        [data-testid="stToolbar"] [data-testid="stMainMenu"],
        [data-testid="stToolbar"] a[data-testid="stStatusWidget"],
        [data-testid="stAppDeployButton"],
        [data-testid="stToolbarActions"] { visibility: hidden; }

        /* ── Main app background ── */
        .stApp {
            background: linear-gradient(135deg, #0f0c29 0%, #1a1035 40%, #0f172a 100%);
            min-height: 100vh;
        }

        /* ── Remove default block container padding top ── */
        .block-container {
            padding-top: 1.5rem !important;
        }

        /* ── Sidebar ── */
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #13111f 0%, #0f172a 100%);
            border-right: 1px solid rgba(99, 102, 241, 0.2);
        }
        [data-testid="stSidebar"] > div:first-child {
            padding-top: 1.25rem;
        }
        [data-testid="stSidebar"] h1 {
            font-size: 1.15rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            background: linear-gradient(90deg, #a78bfa, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        [data-testid="stSidebar"] .stCaption {
            color: #64748b !important;
            font-size: 0.78rem;
        }
        [data-testid="stSidebar"] hr {
            border-color: rgba(99, 102, 241, 0.15) !important;
        }

        /* ── Radio button (data source toggle) ── */
        [data-testid="stSidebar"] .stRadio label {
            color: #94a3b8 !important;
            font-size: 0.85rem;
            font-weight: 500;
        }
        [data-testid="stSidebar"] .stRadio [data-testid="stWidgetLabel"] p {
            color: #c4b5fd !important;
            font-weight: 600;
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
        }

        /* ── Metric cards ── */
        [data-testid="stMetric"] {
            background: linear-gradient(135deg, rgba(30,27,75,0.9) 0%, rgba(15,23,42,0.95) 100%);
            border: 1px solid rgba(99, 102, 241, 0.25);
            border-radius: 16px;
            padding: 18px 22px !important;
            box-shadow: 0 4px 24px rgba(0,0,0,0.3), 0 0 0 1px rgba(99,102,241,0.08) inset;
            backdrop-filter: blur(12px);
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }
        [data-testid="stMetric"]:hover {
            border-color: rgba(139, 92, 246, 0.5);
            box-shadow: 0 8px 32px rgba(99,102,241,0.2), 0 0 0 1px rgba(99,102,241,0.12) inset;
        }
        [data-testid="stMetricLabel"] {
            font-weight: 600;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #7c86a0 !important;
        }
        [data-testid="stMetricValue"] {
            font-weight: 800;
            font-size: 1.9rem !important;
            color: #e2e8f0 !important;
            letter-spacing: -0.02em;
            line-height: 1.1;
        }
        [data-testid="stMetricDelta"] {
            font-size: 0.78rem !important;
            font-weight: 600;
        }

        /* ── Tab bar ── */
        .stTabs [data-baseweb="tab-list"] {
            gap: 4px;
            background: rgba(15, 23, 42, 0.6);
            border-radius: 14px;
            padding: 5px;
            border: 1px solid rgba(99, 102, 241, 0.15);
            border-bottom: none !important;
        }
        .stTabs [data-baseweb="tab"] {
            font-weight: 600;
            font-size: 0.82rem;
            letter-spacing: 0.01em;
            border-radius: 10px;
            color: #64748b;
            padding: 8px 18px;
            border: none !important;
            background: transparent;
            transition: all 0.2s ease;
        }
        .stTabs [data-baseweb="tab"]:hover {
            color: #a78bfa;
            background: rgba(99, 102, 241, 0.08);
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%) !important;
            color: #ffffff !important;
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
        }
        .stTabs [data-baseweb="tab-panel"] {
            padding-top: 1.5rem;
        }
        .stTabs [data-baseweb="tab-highlight"] {
            display: none;
        }

        /* ── Section headings ── */
        h1, h2, h3 {
            color: #e2e8f0 !important;
            letter-spacing: -0.02em;
        }
        h1 { font-weight: 800; }
        h2 { font-weight: 700; }
        h3 { font-weight: 700; font-size: 1.15rem !important; }
        h4 { color: #94a3b8 !important; font-weight: 600; font-size: 0.9rem !important; text-transform: uppercase; letter-spacing: 0.06em; }

        /* ── Divider ── */
        hr {
            border: none !important;
            height: 1px !important;
            background: linear-gradient(90deg, transparent, rgba(99,102,241,0.3), transparent) !important;
            margin: 1.25rem 0 !important;
        }

        /* ── Dataframe ── */
        [data-testid="stDataFrame"] {
            border-radius: 12px;
            border: 1px solid rgba(99, 102, 241, 0.15) !important;
            overflow: hidden;
        }

        /* ── Expander ── */
        [data-testid="stExpander"] {
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid rgba(99, 102, 241, 0.15) !important;
            border-radius: 12px !important;
        }
        [data-testid="stExpander"] summary {
            color: #94a3b8 !important;
            font-weight: 600;
        }

        /* ── Buttons ── */
        .stButton > button {
            background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%);
            color: white !important;
            border: none;
            border-radius: 10px;
            font-weight: 600;
            font-size: 0.85rem;
            padding: 0.55rem 1.25rem;
            box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
            transition: all 0.2s ease;
            letter-spacing: 0.01em;
        }
        .stButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 8px 20px rgba(99, 102, 241, 0.5);
        }
        .stButton > button:active {
            transform: translateY(0);
        }
        .stButton > button:disabled {
            background: rgba(30, 41, 59, 0.8) !important;
            color: #475569 !important;
            box-shadow: none;
            transform: none;
        }

        /* ── Download button ── */
        .stDownloadButton > button {
            background: linear-gradient(135deg, #059669 0%, #10b981 100%);
            color: white !important;
            border: none;
            border-radius: 10px;
            font-weight: 600;
            font-size: 0.85rem;
            padding: 0.55rem 1.25rem;
            box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35);
            transition: all 0.2s ease;
        }
        .stDownloadButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 8px 20px rgba(16, 185, 129, 0.5);
        }

        /* ── Info / Success / Warning / Error ── */
        [data-testid="stAlert"] {
            border-radius: 12px !important;
            border: 1px solid;
            font-size: 0.86rem;
            font-weight: 500;
        }
        .stSuccess { border-color: rgba(16,185,129,0.3) !important; background: rgba(16,185,129,0.07) !important; }
        .stWarning { border-color: rgba(245,158,11,0.3) !important; background: rgba(245,158,11,0.07) !important; }
        .stError   { border-color: rgba(239,68,68,0.3)  !important; background: rgba(239,68,68,0.07)  !important; }
        .stInfo    { border-color: rgba(99,102,241,0.3) !important; background: rgba(99,102,241,0.07) !important; }

        /* ── Spinner ── */
        [data-testid="stSpinner"] { color: #a78bfa !important; }

        /* ── Sidebar checkbox & selectbox ── */
        [data-testid="stSidebar"] .stCheckbox label { color: #94a3b8 !important; font-size: 0.84rem; }
        [data-testid="stSidebar"] .stSelectbox [data-testid="stWidgetLabel"] p {
            color: #94a3b8 !important; font-size: 0.8rem;
        }

        /* ── Section card ── */
        .section-card {
            background: rgba(15, 23, 42, 0.7);
            border: 1px solid rgba(99, 102, 241, 0.15);
            border-radius: 16px;
            padding: 22px 26px;
            margin-bottom: 18px;
            backdrop-filter: blur(8px);
        }

        /* ── Dataset header pill ── */
        .dataset-pill {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(99, 102, 241, 0.12);
            border: 1px solid rgba(99, 102, 241, 0.3);
            border-radius: 100px;
            padding: 5px 14px 5px 10px;
            font-size: 0.82rem;
            font-weight: 600;
            color: #a78bfa;
            margin-bottom: 1rem;
        }

        /* ── Grade badge ── */
        .grade-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 64px; height: 64px;
            border-radius: 50%;
            font-size: 2rem;
            font-weight: 800;
            color: white;
            margin-right: 16px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }

        /* ── Image thumbnail grid ── */
        .thumb-grid { display: flex; flex-wrap: wrap; gap: 8px; }
        .thumb-card {
            border: 1px solid rgba(99, 102, 241, 0.2);
            border-radius: 10px;
            overflow: hidden;
            background: rgba(15, 23, 42, 0.8);
            text-align: center;
            padding: 4px;
            font-size: 0.7rem;
            color: #64748b;
        }

        /* ── Quick-clean buttons full-width ── */
        div[data-testid="stHorizontalBlock"] .stButton > button { width: 100%; }

        /* ── Welcome page feature list ── */
        .feature-card {
            background: rgba(99, 102, 241, 0.06);
            border: 1px solid rgba(99, 102, 241, 0.2);
            border-radius: 14px;
            padding: 18px 22px;
            margin-bottom: 12px;
            transition: border-color 0.2s ease;
        }
        .feature-card:hover { border-color: rgba(139, 92, 246, 0.4); }
        .feature-card p { color: #94a3b8; margin: 0; font-size: 0.9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── 3. Session-State Initialisation ───────────────────────────────────────────

_DEFAULTS: dict = {
    "datasets": {},
    "active_dataset": None,
    "drive_folder_stack": [],
    "drive_current_folder_id": "root",
    "drive_items": [],
    "gauth": None,
    "gdrive": None,
    "working_df": None,
    "working_df_source": None,
}

for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── 4. Sidebar ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🧹 DataRate")
    st.caption("Upload CSV, image files or ZIPs and inspect their cleanliness.")
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

dataset, active_name = get_active_dataset()

if dataset is None:
    # ── Welcome screen ──────────────────────────────────────────────────────
    st.markdown(
        """
        <div style='padding: 2rem 0 1rem 0;'>
            <h1 style='font-size:2.6rem; font-weight:800; background: linear-gradient(90deg,#a78bfa,#818cf8,#6ee7b7); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; margin-bottom:0.4rem;'>
                Data Cleanliness Checker
            </h1>
            <p style='color:#64748b; font-size:1.05rem; margin-top:0;'>Instant data quality insights — for CSV datasets and image collections.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2, gap="large")
    features = [
        ("📂", "Local Upload", "Upload `.csv`, `.zip`, or image files directly from your machine."),
        ("🌐", "Google Drive", "Browse your Drive folders and load a CSV with one click."),
        ("🖼️", "Image Datasets", "Upload a ZIP of images — subfolders become class labels."),
        ("📊", "6 Analysis Tabs", "Overview, Missing Values, Duplicates, Full Report, Score & Quick Clean."),
        ("🏆", "Cleanliness Score", "Get a score from 0–100 with grade A–F across all quality checks."),
        ("✨", "Quick Clean", "Deduplicate & impute missing values, then download the cleaned file."),
    ]
    for i, (icon, title, desc) in enumerate(features):
        col = c1 if i % 2 == 0 else c2
        col.markdown(
            f"""<div class='feature-card'>
                <p style='font-size:1.5rem; margin-bottom:4px;'>{icon}</p>
                <p style='color:#e2e8f0; font-weight:700; font-size:0.95rem; margin-bottom:4px;'>{title}</p>
                <p>{desc}</p>
            </div>""",
            unsafe_allow_html=True,
        )

    st.markdown(
        "<p style='color:#475569; font-size:0.85rem; margin-top:1rem;'>👈 Use the sidebar on the left to get started.</p>",
        unsafe_allow_html=True,
    )
    st.stop()

# ── Route to tabular or image analysis ────────────────────────────────────────

if isinstance(dataset, pd.DataFrame):
    df: pd.DataFrame = dataset

    if df.empty:
        st.error("⚠️ The selected file is empty. Please upload a valid dataset.")
        st.stop()

    # Sync working copy
    if st.session_state["working_df_source"] != active_name:
        st.session_state["working_df"] = df.copy()
        st.session_state["working_df_source"] = active_name

    # ════════════════════════════════════════════════════════════════════════
    # TABULAR ANALYSIS
    # ════════════════════════════════════════════════════════════════════════

    st.markdown(
        f"<div class='dataset-pill'>📊 &nbsp;<span style='color:#e2e8f0;'>{active_name}</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"## Analysing Dataset")

    tab_overview, tab_missing, tab_duplicates, tab_report, tab_score, tab_clean = st.tabs(
        ["🗂️ Overview", "❓ Missing Values", "👥 Duplicates",
         "📄 Full Report", "🏆 Score", "✨ Quick Clean"]
    )

    # ╔═══════════════════════════════════════════════════════════════════════╗
    # ║  TAB 1 — OVERVIEW                                                   ║
    # ╚═══════════════════════════════════════════════════════════════════════╝

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
            st.markdown("#### Column Statistics")

            null_counts = df.isnull().sum()
            dtype_df = pd.DataFrame({
                "Column": df.columns,
                "Data Type": df.dtypes.astype(str).values,
                "Non-Null Count": df.count().values,
                "Null Count": null_counts.values,
                "Null %": (null_counts / len(df) * 100).round(2).values,
                "Unique Values": df.nunique().values,
            })
            st.dataframe(dtype_df, use_container_width=True, hide_index=True)

            st.divider()
            with st.expander("🔍 Raw Data Preview (first 100 rows)", expanded=False):
                st.dataframe(df.head(100), use_container_width=True)

        except Exception as exc:
            st.error(f"❌ Overview could not be rendered: {exc}")

    # ╔═══════════════════════════════════════════════════════════════════════╗
    # ║  TAB 2 — MISSING VALUES                                             ║
    # ╚═══════════════════════════════════════════════════════════════════════╝

    with tab_missing:
        st.markdown("### Missing Values Analysis")
        try:
            missing_counts = df.isnull().sum()
            missing_pct = (missing_counts / len(df) * 100).round(2)

            summary_df = (
                pd.DataFrame({
                    "Column": df.columns,
                    "Data Type": df.dtypes.astype(str).values,
                    "Missing Count": missing_counts.values,
                    "Missing %": missing_pct.values,
                })
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
                chart_df = summary_df[summary_df["Missing Count"] > 0].copy()
                fig = px.bar(
                    chart_df, x="Column", y="Missing %",
                    color="Missing %",
                    color_continuous_scale=["#312e81", "#6366f1", "#a78bfa", "#c4b5fd"],
                    title="Missing Value Rate by Column",
                    text="Missing %", hover_data={"Missing Count": True},
                )
                fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside",
                                  marker_line_width=0)
                fig.update_layout(
                    coloraxis_showscale=False, height=420,
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#94a3b8", family="Inter"),
                    xaxis=dict(tickangle=-35, gridcolor="rgba(99,102,241,0.08)", color="#64748b"),
                    yaxis=dict(title="Missing %", gridcolor="rgba(99,102,241,0.08)", color="#64748b"),
                    title_font_size=14, title_font_color="#e2e8f0",
                    margin=dict(t=50, b=60),
                )
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("#### Full Column Summary")
            st.dataframe(summary_df, use_container_width=True, hide_index=True)
        except Exception as exc:
            st.error(f"❌ Missing-value analysis failed: {exc}")

    # ╔═══════════════════════════════════════════════════════════════════════╗
    # ║  TAB 3 — DUPLICATES                                                 ║
    # ╚═══════════════════════════════════════════════════════════════════════╝

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
                st.caption("Showing rows identified as duplicates. Preview capped at 200 rows.")
                st.dataframe(df[df.duplicated()].head(200), use_container_width=True)
        except Exception as exc:
            st.error(f"❌ Duplicate analysis failed: {exc}")

    # ╔═══════════════════════════════════════════════════════════════════════╗
    # ║  TAB 4 — FULL REPORT (custom pandas + Plotly, no ydata-profiling)  ║
    # ╚═══════════════════════════════════════════════════════════════════════╝

    with tab_report:
        st.markdown("### Full Profiling Report")
        st.info(
            "Generates an interactive in-page report using **pandas + Plotly**. "
            "No external heavy dependencies — renders instantly."
        )

        if st.button("🔍 Generate Report", key="generate_report_btn"):
            with st.spinner("Building report…"):
                try:
                    st.session_state["_custom_report_ready"] = True
                    st.session_state["_custom_report_name"] = active_name
                    st.success("✅ Report ready!")
                except Exception as exc:
                    st.error(f"❌ Report generation failed: {exc}")

        if (
            st.session_state.get("_custom_report_ready")
            and st.session_state.get("_custom_report_name") == active_name
        ):
            num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            cat_cols = df.select_dtypes(include="object").columns.tolist()

            _PLOTLY_COMMON = dict(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#94a3b8", family="Inter"),
            )

            # ── Numeric distributions ────────────────────────────────────────
            if num_cols:
                st.markdown("#### 📈 Numeric Column Distributions")
                n_per_row = 3
                rows_needed = (len(num_cols) + n_per_row - 1) // n_per_row
                for row_i in range(rows_needed):
                    batch = num_cols[row_i * n_per_row: (row_i + 1) * n_per_row]
                    cols_ui = st.columns(len(batch))
                    for col_ui, col_name in zip(cols_ui, batch):
                        with col_ui:
                            series = df[col_name].dropna()
                            fig = px.histogram(
                                series, x=col_name,
                                title=col_name,
                                nbins=min(40, max(10, len(series) // 20)),
                                color_discrete_sequence=["#6366f1"],
                            )
                            fig.update_layout(
                                height=260, showlegend=False,
                                margin=dict(t=40, b=20, l=20, r=10),
                                xaxis=dict(title="", gridcolor="rgba(99,102,241,0.08)", color="#64748b"),
                                yaxis=dict(title="Count", gridcolor="rgba(99,102,241,0.08)", color="#64748b"),
                                title_font_size=12, title_font_color="#e2e8f0",
                                **_PLOTLY_COMMON,
                            )
                            st.plotly_chart(fig, use_container_width=True)

            # ── Correlation heatmap ──────────────────────────────────────────
            if len(num_cols) >= 2:
                st.markdown("#### 🔥 Correlation Heatmap")
                corr = df[num_cols].corr()
                fig_corr = px.imshow(
                    corr,
                    color_continuous_scale="RdBu_r",
                    zmin=-1, zmax=1,
                    text_auto=".2f",
                    aspect="auto",
                    title="Pearson Correlation Matrix",
                )
                fig_corr.update_layout(
                    height=max(350, len(num_cols) * 45),
                    margin=dict(t=50, b=20, l=20, r=20),
                    title_font_color="#e2e8f0",
                    **_PLOTLY_COMMON,
                )
                st.plotly_chart(fig_corr, use_container_width=True)

            # ── Categorical top-value bars ───────────────────────────────────
            if cat_cols:
                st.markdown("#### 📊 Categorical Column — Top Values")
                for col_name in cat_cols[:12]:   # cap at 12 categorical cols
                    vc = df[col_name].value_counts().head(15).reset_index()
                    vc.columns = ["Value", "Count"]
                    fig_cat = px.bar(
                        vc, x="Count", y="Value", orientation="h",
                        title=f"{col_name} — top {len(vc)} values",
                        color="Count",
                        color_continuous_scale=["#312e81", "#6366f1", "#a78bfa"],
                    )
                    fig_cat.update_layout(
                        height=max(250, len(vc) * 28),
                        showlegend=False,
                        coloraxis_showscale=False,
                        margin=dict(t=40, b=20, l=120, r=20),
                        xaxis=dict(gridcolor="rgba(99,102,241,0.08)", color="#64748b"),
                        yaxis=dict(autorange="reversed", color="#64748b"),
                        title_font_size=13, title_font_color="#e2e8f0",
                        **_PLOTLY_COMMON,
                    )
                    st.plotly_chart(fig_cat, use_container_width=True)

            # ── Download summary CSV ─────────────────────────────────────────
            st.markdown("#### ⬇️ Download Summary Statistics")
            summary_stats = df.describe(include="all").T.reset_index()
            summary_stats = summary_stats.rename(columns={"index": "Column"})
            csv_summary = summary_stats.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download Summary CSV",
                data=csv_summary,
                file_name=f"{active_name.rsplit('.', 1)[0]}_summary.csv",
                mime="text/csv",
                key="download_summary_btn",
            )

    # ╔═══════════════════════════════════════════════════════════════════════╗
    # ║  TAB 5 — CLEANLINESS SCORE                                          ║
    # ╚═══════════════════════════════════════════════════════════════════════╝

    with tab_score:
        st.markdown("### 🏆 Cleanliness Score")

        with st.spinner("Computing score…"):
            result: ScoreResult = score_dataframe(df)

        # ── Gauge chart ──────────────────────────────────────────────────────
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=result.score,
            delta={"reference": 75, "suffix": " vs B threshold"},
            title={"text": f"Cleanliness Score<br><span style='font-size:0.9em;color:{result.color}'>"
                           f"Grade {result.grade}</span>"},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#475569"},
                "bar": {"color": result.color, "thickness": 0.25},
                "bgcolor": "rgba(15,23,42,0.6)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 40],   "color": "rgba(239,68,68,0.12)"},
                    {"range": [40, 60],  "color": "rgba(245,158,11,0.12)"},
                    {"range": [60, 75],  "color": "rgba(234,179,8,0.12)"},
                    {"range": [75, 90],  "color": "rgba(34,197,94,0.12)"},
                    {"range": [90, 100], "color": "rgba(16,185,129,0.12)"},
                ],
                "threshold": {
                    "line": {"color": "#e2e8f0", "width": 3},
                    "thickness": 0.8,
                    "value": result.score,
                },
            },
            number={"suffix": "/100", "font": {"size": 52, "color": result.color}},
        ))
        fig_gauge.update_layout(
            height=320,
            margin=dict(t=60, b=10, l=30, r=30),
            paper_bgcolor="rgba(0,0,0,0)",
            font={"family": "Inter", "color": "#94a3b8"},
        )
        st.plotly_chart(fig_gauge, use_container_width=True)

        st.markdown(result.summary)
        st.divider()

        # ── Penalty breakdown ────────────────────────────────────────────────
        st.markdown("#### 📋 Score Breakdown")
        breakdown_data = []
        for item in result.breakdown:
            emoji = "✅" if item.penalty >= 0 else "⚠️" if item.penalty > -10 else "❌"
            breakdown_data.append({
                "Check": f"{emoji} {item.label}",
                "Penalty (pts)": item.penalty,
                "Detail": item.detail,
            })
        bd_df = pd.DataFrame(breakdown_data)
        st.dataframe(bd_df, use_container_width=True, hide_index=True)

        # ── Grade reference ──────────────────────────────────────────────────
        st.divider()
        st.markdown("#### 📖 Grade Reference")
        grade_cols = st.columns(5)
        for col_ui, (grade, color, label) in zip(
            grade_cols,
            [("A", "#22c55e", "≥ 90"), ("B", "#84cc16", "75–89"),
             ("C", "#f59e0b", "60–74"), ("D", "#f97316", "40–59"), ("F", "#ef4444", "< 40")]
        ):
            col_ui.markdown(
                f"<div style='text-align:center;padding:16px 12px;border-radius:14px;"
                f"background:{color}14;border:1.5px solid {color}40;'>"
                f"<div style='font-size:2.2rem;font-weight:800;color:{color};'>{grade}</div>"
                f"<div style='font-size:0.78rem;color:#64748b;font-weight:600;margin-top:4px;'>{label}</div></div>",
                unsafe_allow_html=True,
            )

    # ╔═══════════════════════════════════════════════════════════════════════╗
    # ║  TAB 6 — QUICK CLEAN                                                ║
    # ╚═══════════════════════════════════════════════════════════════════════╝

    @st.cache_data(show_spinner=False)
    def _df_to_csv_bytes(df_hash_key: str, data: bytes) -> bytes:
        return data

    def build_csv_bytes(frame: pd.DataFrame) -> bytes:
        raw = frame.to_csv(index=False).encode("utf-8")
        cache_key = f"{len(raw)}_{raw[:512]}"
        return _df_to_csv_bytes(cache_key, raw)

    def smart_impute(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        """Fill missing values: numeric → median, categorical → mode."""
        filled_cells = 0
        out = frame.copy()
        for col in out.columns:
            n_null = int(out[col].isnull().sum())
            if n_null == 0:
                continue
            try:
                if out[col].dtype.kind in ("i", "u", "f"):
                    median_val = out[col].median()
                    if pd.isna(median_val):
                        continue
                    out[col] = out[col].fillna(median_val)
                else:
                    mode_series = out[col].mode(dropna=True)
                    if mode_series.empty:
                        continue
                    out[col] = out[col].fillna(mode_series.iloc[0])
                filled_cells += n_null
            except (TypeError, ValueError):
                continue
        return out, filled_cells

    with tab_clean:
        st.markdown("### ✨ Quick Clean Actions")
        st.caption(
            "Changes are applied **cumulatively** within your session. "
            "Switching to a different dataset resets the working copy."
        )

        wdf: pd.DataFrame = st.session_state["working_df"]
        wrows, wcols = wdf.shape
        wn_missing = int(wdf.isnull().sum().sum())
        wn_dup = int(wdf.duplicated().sum())

        st.markdown("#### Current Working Dataset")
        cw1, cw2, cw3 = st.columns(3)
        cw1.metric("Rows", f"{wrows:,}", f"{wrows - len(df):+,} vs original")
        cw2.metric("Missing Cells", f"{wn_missing:,}")
        cw3.metric("Duplicate Rows", f"{wn_dup:,}")

        st.divider()

        # ── Deduplication ─────────────────────────────────────────────────
        st.markdown("#### 🔁 Deduplication")
        if wn_dup == 0:
            st.success("✅ No duplicate rows in the current working dataset.")
        else:
            st.warning(f"⚠️ **{wn_dup:,}** duplicate row(s) found.")

        if st.button("🗑️ Drop Duplicate Rows", key="drop_dups_btn", disabled=(wn_dup == 0)):
            before_rows = len(wdf)
            wdf = wdf.drop_duplicates().reset_index(drop=True)
            st.session_state["working_df"] = wdf
            st.success(
                f"✅ Removed **{before_rows - len(wdf):,}** row(s). "
                f"**Before:** {before_rows:,} → **After:** {len(wdf):,} rows."
            )
            st.rerun()

        st.divider()

        # ── Smart Imputation ──────────────────────────────────────────────
        st.markdown("#### 🧠 Smart Imputation")
        st.caption("Numeric → **median**  |  Categorical → **mode**")
        wn_missing_now = int(wdf.isnull().sum().sum())

        if wn_missing_now == 0:
            st.success("✅ No missing values in the current working dataset.")
        else:
            st.info(f"ℹ️ **{wn_missing_now:,}** missing cell(s) will be filled.")

        if st.button("🧹 Apply Smart Imputation", key="smart_impute_btn",
                     disabled=(wn_missing_now == 0)):
            try:
                wdf_imputed, cells_filled = smart_impute(wdf)
                st.session_state["working_df"] = wdf_imputed
                if cells_filled > 0:
                    st.success(f"✅ Filled **{cells_filled:,}** missing cell(s).")
                else:
                    st.info("ℹ️ No cells were filled — columns may be all-NaN or unsupported types.")
                st.rerun()
            except Exception as exc:
                st.error(f"❌ Imputation failed: {exc}")

        st.divider()

        # ── Reset ─────────────────────────────────────────────────────────
        st.markdown("#### ↩️ Reset Working Copy")
        if st.button("↩️ Reset to Original (discard all changes)", key="reset_wdf_btn"):
            st.session_state["working_df"] = df.copy()
            st.success("✅ Working dataset has been reset to the original uploaded file.")
            st.rerun()

        st.divider()

        # ── Export ────────────────────────────────────────────────────────
        st.markdown("#### ⬇️ Export Cleaned CSV")
        try:
            csv_bytes = build_csv_bytes(st.session_state["working_df"])
            stem = active_name.rsplit(".", 1)[0]
            st.download_button(
                label=f"⬇️ Download `{stem}_cleaned.csv`",
                data=csv_bytes,
                file_name=f"{stem}_cleaned.csv",
                mime="text/csv",
                key="download_clean_btn",
            )
        except Exception as exc:
            st.error(f"❌ CSV export failed: {exc}")

        st.markdown("#### Cleaned Data Preview (first 100 rows)")
        st.dataframe(st.session_state["working_df"].head(100), use_container_width=True)


elif isinstance(dataset, ImageDataset):
    img_ds: ImageDataset = dataset

    # ════════════════════════════════════════════════════════════════════════
    # IMAGE ANALYSIS
    # ════════════════════════════════════════════════════════════════════════

    st.markdown(
        f"<div class='dataset-pill'>🖼️ &nbsp;<span style='color:#e2e8f0;'>{active_name}</span></div>",
        unsafe_allow_html=True,
    )
    st.markdown("## Analysing Image Dataset")

    itab_overview, itab_quality, itab_dups, itab_score, itab_fix = st.tabs(
        ["🖼️ Overview", "🔍 Quality Issues", "👥 Duplicates",
         "🏆 Score", "✨ Quick Fix"]
    )

    # ── Helper: thumbnail bytes → base64 ──────────────────────────────────
    def _thumb_b64(entry: ImageEntry, size: int = 120) -> str:
        import base64
        if entry.pil_image is None:
            return ""
        buf = io.BytesIO()
        thumb = entry.pil_image.copy()
        thumb.thumbnail((size, size))
        thumb.save(buf, format="JPEG", quality=70)
        return base64.b64encode(buf.getvalue()).decode()

    _PLOTLY_DARK = dict(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94a3b8", family="Inter"),
    )

    # ╔═══════════════════════════════════════════════════════════════════════╗
    # ║  IMAGE TAB 1 — OVERVIEW                                             ║
    # ╚═══════════════════════════════════════════════════════════════════════╝

    with itab_overview:
        st.markdown("### Image Dataset Overview")

        valid_imgs = [img for img in img_ds.images if img.pil_image is not None]
        n_total = img_ds.n_total
        n_valid = img_ds.n_valid
        n_corrupt = img_ds.n_corrupt
        n_classes = len(img_ds.labels)

        avg_w = int(np.mean([i.width for i in valid_imgs])) if valid_imgs else 0
        avg_h = int(np.mean([i.height for i in valid_imgs])) if valid_imgs else 0
        total_mb = round(sum(i.file_size for i in img_ds.images) / 1_048_576, 2)

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total Images", f"{n_total:,}")
        m2.metric("Valid Images", f"{n_valid:,}")
        m3.metric("Corrupt Images", f"{n_corrupt:,}")
        m4.metric("Classes", f"{n_classes:,}")
        m5.metric("Total Size", f"{total_mb} MB")

        st.divider()

        # ── Class distribution ─────────────────────────────────────────────
        if n_classes > 0:
            st.markdown("#### Class Distribution")
            label_counts = Counter(img.label for img in img_ds.images)
            label_df = pd.DataFrame(
                {"Class": list(label_counts.keys()), "Count": list(label_counts.values())}
            ).sort_values("Count", ascending=False)
            fig_cls = px.bar(
                label_df, x="Class", y="Count",
                color="Count",
                color_continuous_scale=["#312e81", "#6366f1", "#a78bfa"],
                title="Images per Class",
                text="Count",
            )
            fig_cls.update_traces(textposition="outside", marker_line_width=0)
            fig_cls.update_layout(
                height=380, coloraxis_showscale=False,
                xaxis=dict(tickangle=-30, gridcolor="rgba(99,102,241,0.08)", color="#64748b"),
                yaxis=dict(gridcolor="rgba(99,102,241,0.08)", color="#64748b"),
                margin=dict(t=50, b=60), title_font_size=14, title_font_color="#e2e8f0",
                **_PLOTLY_DARK,
            )
            st.plotly_chart(fig_cls, use_container_width=True)

        # ── Resolution scatter ─────────────────────────────────────────────
        if valid_imgs:
            st.markdown("#### Resolution Distribution")
            res_df = pd.DataFrame({
                "Width": [i.width for i in valid_imgs],
                "Height": [i.height for i in valid_imgs],
                "Label": [i.label for i in valid_imgs],
                "Name": [i.name for i in valid_imgs],
            })
            fig_res = px.scatter(
                res_df, x="Width", y="Height", color="Label",
                hover_data=["Name"], opacity=0.7,
                title="Image Resolutions (W × H)",
            )
            fig_res.update_layout(
                height=380,
                xaxis=dict(gridcolor="rgba(99,102,241,0.08)", color="#64748b"),
                yaxis=dict(gridcolor="rgba(99,102,241,0.08)", color="#64748b"),
                margin=dict(t=50, b=40), title_font_size=14, title_font_color="#e2e8f0",
                **_PLOTLY_DARK,
            )
            st.plotly_chart(fig_res, use_container_width=True)

        # ── Thumbnail grid ─────────────────────────────────────────────────
        st.divider()
        st.markdown("#### Sample Thumbnails (first 25 valid images)")
        THUMB_CAP = 25
        sample = valid_imgs[:THUMB_CAP]
        if sample:
            n_cols = 5
            grid_rows = (len(sample) + n_cols - 1) // n_cols
            for r in range(grid_rows):
                row_imgs = sample[r * n_cols: (r + 1) * n_cols]
                cols_ui = st.columns(n_cols)
                for col_ui, img_entry in zip(cols_ui, row_imgs):
                    with col_ui:
                        b64 = _thumb_b64(img_entry, 150)
                        if b64:
                            st.markdown(
                                f"<div style='text-align:center;background:rgba(15,23,42,0.8);"
                                f"border:1px solid rgba(99,102,241,0.2);border-radius:10px;padding:6px;'>"
                                f"<img src='data:image/jpeg;base64,{b64}' "
                                f"style='width:100%;border-radius:6px;'/>"
                                f"<div style='font-size:0.65rem;color:#64748b;margin-top:5px;'>"
                                f"{img_entry.name[:18]}<br>{img_entry.width}×{img_entry.height}"
                                f"</div></div>",
                                unsafe_allow_html=True,
                            )
        else:
            st.info("No valid images to display.")

    # ╔═══════════════════════════════════════════════════════════════════════╗
    # ║  IMAGE TAB 2 — QUALITY ISSUES                                       ║
    # ╚═══════════════════════════════════════════════════════════════════════╝

    with itab_quality:
        st.markdown("### Quality Issues")

        # ── Corrupt ───────────────────────────────────────────────────────
        st.markdown("#### ❌ Corrupt / Unreadable Images")
        corrupt = [img for img in img_ds.images if img.pil_image is None]
        if corrupt:
            st.error(f"Found **{len(corrupt)}** corrupt image(s).")
            corrupt_df = pd.DataFrame([{"Filename": i.name, "Label": i.label} for i in corrupt])
            st.dataframe(corrupt_df, use_container_width=True, hide_index=True)
        else:
            st.success("✅ No corrupt images found.")

        st.divider()

        # ── Low-resolution ────────────────────────────────────────────────
        st.markdown("#### 🔎 Low-Resolution Images (< 64 × 64 px)")
        low_res = [img for img in valid_imgs if img.width < 64 or img.height < 64]
        if low_res:
            st.warning(f"Found **{len(low_res)}** low-resolution image(s).")
            lr_df = pd.DataFrame([
                {"Filename": i.name, "Label": i.label, "Width": i.width, "Height": i.height}
                for i in low_res
            ])
            st.dataframe(lr_df, use_container_width=True, hide_index=True)
        else:
            st.success("✅ All images meet the minimum resolution threshold.")

        st.divider()

        # ── Near-blank ────────────────────────────────────────────────────
        st.markdown("#### ⬜ Near-Blank Images (pixel std < 5)")
        blank_imgs: list[ImageEntry] = []
        for img in valid_imgs:
            try:
                arr = np.array(img.pil_image.convert("L"), dtype=np.float32)
                if arr.std() < 5.0:
                    blank_imgs.append(img)
            except Exception:
                pass
        if blank_imgs:
            st.warning(f"Found **{len(blank_imgs)}** near-blank image(s).")
            cols_ui = st.columns(min(5, len(blank_imgs)))
            for col_ui, img_entry in zip(cols_ui, blank_imgs[:10]):
                with col_ui:
                    b64 = _thumb_b64(img_entry, 120)
                    if b64:
                        st.markdown(
                            f"<img src='data:image/jpeg;base64,{b64}' "
                            f"style='width:100%;border-radius:8px;border:2px solid #f59e0b;'/>",
                            unsafe_allow_html=True,
                        )
                        st.caption(img_entry.name[:20])
        else:
            st.success("✅ No near-blank images found.")

    # ╔═══════════════════════════════════════════════════════════════════════╗
    # ║  IMAGE TAB 3 — DUPLICATES                                           ║
    # ╚═══════════════════════════════════════════════════════════════════════╝

    with itab_dups:
        st.markdown("### Image Duplicates (MD5-hash based)")

        if st.button("🔍 Detect Duplicates", key="detect_img_dups_btn"):
            import hashlib

            with st.spinner("Hashing images…"):
                hash_map: dict[str, list[ImageEntry]] = {}
                for img in valid_imgs:
                    try:
                        buf = io.BytesIO()
                        img.pil_image.save(buf, format="PNG")
                        h = hashlib.md5(buf.getvalue()).hexdigest()
                        hash_map.setdefault(h, []).append(img)
                    except Exception:
                        pass

                dup_groups = {h: v for h, v in hash_map.items() if len(v) > 1}
                st.session_state["_img_dup_groups"] = dup_groups

        dup_groups = st.session_state.get("_img_dup_groups", {})
        if dup_groups:
            n_dup_imgs = sum(len(v) - 1 for v in dup_groups.values())
            st.error(
                f"Found **{n_dup_imgs}** duplicate image(s) in "
                f"**{len(dup_groups)}** group(s)."
            )
            for i, (h, group) in enumerate(list(dup_groups.items())[:10]):
                with st.expander(f"Duplicate Group {i+1} — {len(group)} identical images"):
                    cols_ui = st.columns(min(5, len(group)))
                    for col_ui, img_entry in zip(cols_ui, group):
                        with col_ui:
                            b64 = _thumb_b64(img_entry, 130)
                            if b64:
                                st.markdown(
                                    f"<img src='data:image/jpeg;base64,{b64}' "
                                    f"style='width:100%;border-radius:8px;"
                                    f"border:2px solid #ef4444;'/>",
                                    unsafe_allow_html=True,
                                )
                                st.caption(img_entry.name[:22])
        elif "detect_img_dups_btn" in st.session_state:
            st.success("✅ No duplicate images detected.")
        else:
            st.info("Click **Detect Duplicates** above to run the check.")

    # ╔═══════════════════════════════════════════════════════════════════════╗
    # ║  IMAGE TAB 4 — SCORE                                                ║
    # ╚═══════════════════════════════════════════════════════════════════════╝

    with itab_score:
        st.markdown("### 🏆 Image Dataset Cleanliness Score")

        with st.spinner("Computing score…"):
            img_result: ScoreResult = score_image_dataset(img_ds)

        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=img_result.score,
            delta={"reference": 75, "suffix": " vs B threshold"},
            title={
                "text": (
                    f"Image Cleanliness Score<br>"
                    f"<span style='font-size:0.9em;color:{img_result.color}'>"
                    f"Grade {img_result.grade}</span>"
                )
            },
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#475569"},
                "bar": {"color": img_result.color, "thickness": 0.25},
                "bgcolor": "rgba(15,23,42,0.6)",
                "borderwidth": 0,
                "steps": [
                    {"range": [0, 40],   "color": "rgba(239,68,68,0.12)"},
                    {"range": [40, 60],  "color": "rgba(245,158,11,0.12)"},
                    {"range": [60, 75],  "color": "rgba(234,179,8,0.12)"},
                    {"range": [75, 90],  "color": "rgba(34,197,94,0.12)"},
                    {"range": [90, 100], "color": "rgba(16,185,129,0.12)"},
                ],
                "threshold": {
                    "line": {"color": "#e2e8f0", "width": 3},
                    "thickness": 0.8,
                    "value": img_result.score,
                },
            },
            number={"suffix": "/100", "font": {"size": 52, "color": img_result.color}},
        ))
        fig_gauge.update_layout(
            height=320, margin=dict(t=60, b=10, l=30, r=30),
            paper_bgcolor="rgba(0,0,0,0)", font={"family": "Inter", "color": "#94a3b8"},
        )
        st.plotly_chart(fig_gauge, use_container_width=True)

        st.markdown(img_result.summary)
        st.divider()

        st.markdown("#### 📋 Score Breakdown")
        breakdown_data = []
        for item in img_result.breakdown:
            emoji = "✅" if item.penalty >= 0 else "⚠️" if item.penalty > -10 else "❌"
            breakdown_data.append({
                "Check": f"{emoji} {item.label}",
                "Penalty (pts)": item.penalty,
                "Detail": item.detail,
            })
        st.dataframe(pd.DataFrame(breakdown_data), use_container_width=True, hide_index=True)

        st.divider()
        st.markdown("#### 📖 Grade Reference")
        grade_cols = st.columns(5)
        for col_ui, (grade, color, label) in zip(
            grade_cols,
            [("A", "#22c55e", "≥ 90"), ("B", "#84cc16", "75–89"),
             ("C", "#f59e0b", "60–74"), ("D", "#f97316", "40–59"), ("F", "#ef4444", "< 40")]
        ):
            col_ui.markdown(
                f"<div style='text-align:center;padding:16px 12px;border-radius:14px;"
                f"background:{color}14;border:1.5px solid {color}40;'>"
                f"<div style='font-size:2.2rem;font-weight:800;color:{color};'>{grade}</div>"
                f"<div style='font-size:0.78rem;color:#64748b;font-weight:600;margin-top:4px;'>{label}</div></div>",
                unsafe_allow_html=True,
            )

    # ╔═══════════════════════════════════════════════════════════════════════╗
    # ║  IMAGE TAB 5 — QUICK FIX                                            ║
    # ╚═══════════════════════════════════════════════════════════════════════╝

    with itab_fix:
        st.markdown("### ✨ Quick Fix")
        st.caption(
            "Remove problematic images from the dataset and download a cleaned ZIP. "
            "The original uploaded file is never modified."
        )

        n_corrupt_now = img_ds.n_corrupt
        low_res_now = [img for img in valid_imgs if img.width < 64 or img.height < 64]
        n_low_res_now = len(low_res_now)

        qf1, qf2, qf3 = st.columns(3)
        qf1.metric("Total Images", f"{img_ds.n_total:,}")
        qf2.metric("Corrupt", f"{n_corrupt_now:,}")
        qf3.metric("Low-Resolution", f"{n_low_res_now:,}")

        st.divider()
        st.markdown("#### Select images to remove:")
        remove_corrupt = st.checkbox(
            f"🗑️ Remove **{n_corrupt_now}** corrupt image(s)", value=n_corrupt_now > 0
        )
        remove_low_res = st.checkbox(
            f"🗑️ Remove **{n_low_res_now}** low-resolution image(s) (<64×64)",
            value=False,
        )

        if st.button("✨ Build Cleaned ZIP", key="build_clean_zip_btn"):
            with st.spinner("Building cleaned ZIP…"):
                remove_names: set[str] = set()
                if remove_corrupt:
                    remove_names.update(i.name for i in img_ds.images if i.pil_image is None)
                if remove_low_res:
                    remove_names.update(i.name for i in low_res_now)

                kept = [i for i in img_ds.images if i.name not in remove_names]

                zip_buf = io.BytesIO()
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for img_entry in kept:
                        label_dir = img_entry.label if img_entry.label != "unlabelled" else ""
                        arc_name = (
                            f"{label_dir}/{img_entry.name}" if label_dir else img_entry.name
                        )
                        if img_entry.raw_bytes:
                            zf.writestr(arc_name, img_entry.raw_bytes)
                        elif img_entry.pil_image is not None:
                            buf2 = io.BytesIO()
                            img_entry.pil_image.save(buf2, format="JPEG", quality=92)
                            zf.writestr(arc_name, buf2.getvalue())

                zip_bytes = zip_buf.getvalue()
                stem = active_name.rsplit(".", 1)[0]
                removed_count = img_ds.n_total - len(kept)
                st.success(
                    f"✅ Done! Removed **{removed_count}** image(s). "
                    f"Cleaned dataset has **{len(kept)}** image(s)."
                )
                st.download_button(
                    label=f"⬇️ Download `{stem}_cleaned.zip`",
                    data=zip_bytes,
                    file_name=f"{stem}_cleaned.zip",
                    mime="application/zip",
                    key="download_clean_zip_btn",
                )

else:
    st.error("❌ Unknown dataset type. Please re-upload your file.")
