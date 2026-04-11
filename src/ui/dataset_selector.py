"""
dataset_selector.py
-------------------
Sidebar widget that lets the user pick one of the loaded datasets
(which may be a pd.DataFrame or an ImageDataset) as the active one.
"""

from __future__ import annotations

from typing import Optional, Union

import pandas as pd
import streamlit as st

from src.sources.image_source import ImageDataset


AnyDataset = Union[pd.DataFrame, ImageDataset]


def _icon(value: AnyDataset) -> str:
    return "🖼️" if isinstance(value, ImageDataset) else "📊"


def render_dataset_selector() -> None:
    """Render the dataset picker in the sidebar."""
    datasets: dict = st.session_state.get("datasets", {})

    if not datasets:
        return

    st.divider()
    st.markdown("#### 🗂️ Loaded Datasets")

    options = list(datasets.keys())
    labels = [f"{_icon(datasets[k])} {k}" for k in options]

    # Determine default index
    current = st.session_state.get("active_dataset")
    default_idx = options.index(current) if current in options else 0

    chosen_label = st.radio(
        "Select active dataset",
        options=labels,
        index=default_idx,
        key="dataset_selector_radio",
        label_visibility="collapsed",
    )

    # Map label back to key
    chosen_idx = labels.index(chosen_label)
    st.session_state["active_dataset"] = options[chosen_idx]


def get_active_dataset() -> tuple[Optional[AnyDataset], Optional[str]]:
    """
    Return (dataset, name) for the currently selected dataset.
    Dataset may be a pd.DataFrame or an ImageDataset.
    Returns (None, None) if nothing is loaded/selected.
    """
    datasets: dict = st.session_state.get("datasets", {})
    active_name: Optional[str] = st.session_state.get("active_dataset")

    if not datasets:
        return None, None

    # Auto-select first available
    if active_name not in datasets:
        active_name = next(iter(datasets), None)
        st.session_state["active_dataset"] = active_name

    if active_name is None:
        return None, None

    return datasets[active_name], active_name


def get_active_dataframe() -> tuple[Optional[pd.DataFrame], Optional[str]]:
    """
    Backwards-compatible helper — returns (DataFrame, name) only if the
    active dataset is a DataFrame. Returns (None, name) for ImageDatasets.
    """
    dataset, name = get_active_dataset()
    if isinstance(dataset, pd.DataFrame):
        return dataset, name
    return None, name
