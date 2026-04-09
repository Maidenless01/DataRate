"""
dataset_selector.py
--------------------
Renders the unified dataset selector widget in the sidebar.
Reads from st.session_state["datasets"] and sets st.session_state["active_dataset"].
"""

import streamlit as st


def render_dataset_selector() -> None:
    """
    Display the loaded datasets selectbox and shape info.
    Should be called after all data source panels have rendered.
    """
    datasets: dict = st.session_state.get("datasets", {})

    st.divider()
    st.markdown("#### 📋 Loaded Datasets")

    if not datasets:
        st.info("Upload a CSV or connect to Drive to get started.")
        return

    names = list(datasets.keys())

    # Auto-select if only one dataset is loaded
    current_active = st.session_state.get("active_dataset")
    if current_active not in names:
        st.session_state["active_dataset"] = names[0]

    selected = st.selectbox(
        label="Select dataset to analyse",
        options=names,
        index=names.index(st.session_state["active_dataset"]),
        key="dataset_selectbox",
    )
    st.session_state["active_dataset"] = selected

    # Shape metadata
    df = datasets[selected]
    rows, cols = df.shape
    st.caption(f"ℹ️ Shape: **{rows:,} rows × {cols} columns**")

    # Optional: show a remove button for each dataset
    with st.expander("🗑️ Remove a dataset", expanded=False):
        to_remove = st.selectbox(
            "Select dataset to remove",
            options=names,
            key="dataset_remove_selectbox",
        )
        if st.button("Remove", key="dataset_remove_btn"):
            del st.session_state["datasets"][to_remove]
            # Reset active dataset
            remaining = list(st.session_state["datasets"].keys())
            st.session_state["active_dataset"] = remaining[0] if remaining else None
            st.rerun()


def get_active_dataframe():
    """
    Convenience helper: returns the currently selected DataFrame, or None.
    Use this in analysis tabs to get the active data.
    """
    datasets: dict = st.session_state.get("datasets", {})
    active: str = st.session_state.get("active_dataset")
    if active and active in datasets:
        return datasets[active], active
    return None, None
