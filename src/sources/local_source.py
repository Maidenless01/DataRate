"""
local_source.py
---------------
Handles local CSV and ZIP file uploads via Streamlit's file_uploader.
Loaded DataFrames are stored in st.session_state["datasets"].
"""

import io
import zipfile
from pathlib import PurePosixPath

import pandas as pd
import streamlit as st


def _register_df(name: str, df: pd.DataFrame) -> None:
    """Store a DataFrame in session state, handling duplicate filename collisions."""
    key = name
    # If a key already exists from a different source, suffix with a counter
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
        df = pd.read_csv(io.BytesIO(raw_bytes))
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
        st.success(f"✅ Loaded **{uploaded_file.name}** — {df.shape[0]:,} rows × {df.shape[1]} columns")


def _handle_zip(uploaded_file) -> None:
    """Extract all CSV files from a ZIP upload and load each into session state."""
    raw = uploaded_file.read()
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            csv_members = [m for m in zf.namelist() if m.lower().endswith(".csv")]
            if not csv_members:
                st.warning("⚠️ The ZIP file contains no CSV files.")
                return

            loaded = 0
            for member in csv_members:
                # Use only the basename to avoid path clutter
                base_name = PurePosixPath(member).name
                member_bytes = zf.read(member)
                df = _load_csv_bytes(base_name, member_bytes)
                if df is not None:
                    _register_df(base_name, df)
                    loaded += 1

            st.success(f"✅ Extracted **{loaded}** CSV file(s) from `{uploaded_file.name}`")
    except zipfile.BadZipFile:
        st.error("❌ The uploaded file is not a valid ZIP archive.")


def render_local_uploader() -> None:
    """
    Render the local file upload UI panel.
    Call this inside the sidebar or main body as needed.
    """
    st.markdown("#### 📂 Upload Local File")
    uploaded = st.file_uploader(
        label="Choose a CSV or ZIP file",
        type=["csv", "zip"],
        accept_multiple_files=False,
        help="Upload a single CSV or a ZIP archive containing multiple CSVs.",
        key="local_file_uploader",
    )

    if uploaded is not None:
        file_ext = uploaded.name.rsplit(".", 1)[-1].lower()
        if file_ext == "csv":
            _handle_single_csv(uploaded)
        elif file_ext == "zip":
            _handle_zip(uploaded)
        else:
            st.error("❌ Unsupported file type. Please upload a .csv or .zip file.")
