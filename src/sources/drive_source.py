"""
drive_source.py
---------------
Google Drive integration using PyDrive2.
Provides folder browsing (with back-navigation) and one-click CSV loading.
Loaded DataFrames are stored in st.session_state["datasets"].

Setup:
  1. Create a Google Cloud project and enable the Drive API.
  2. Create OAuth 2.0 credentials (Desktop app type).
  3. Download client_secrets.json and place it in the project root.
  On first run, a browser window will open for OAuth consent.
  Credentials are cached in mycreds.txt for subsequent runs.
"""

import io
from pathlib import Path
from pathlib import PurePosixPath

import pandas as pd
import streamlit as st

# ── PyDrive2 import guard ──────────────────────────────────────────────────────
try:
    from pydrive2.auth import GoogleAuth
    from pydrive2.drive import GoogleDrive

    PYDRIVE2_AVAILABLE = True
except ImportError:
    PYDRIVE2_AVAILABLE = False

# Google Drive MIME types
_MIME_FOLDER = "application/vnd.google-apps.folder"
_MIME_CSV = "text/csv"
_CREDS_FILE = "mycreds.txt"
_CLIENT_SECRETS_FILE = Path("client_secrets.json")


# ── Auth ───────────────────────────────────────────────────────────────────────

def _authenticate() -> tuple:
    """
    Perform OAuth2 authentication using PyDrive2's LocalWebserverAuth.
    Returns (GoogleAuth, GoogleDrive) and caches them in session state.
    """
    if not _CLIENT_SECRETS_FILE.exists():
        raise FileNotFoundError(
            "client_secrets.json is missing from the project root. "
            "Download the OAuth client secrets file from Google Cloud Console "
            "and place it next to app.py."
        )

    gauth = GoogleAuth()

    # Try loading saved credentials first
    gauth.LoadCredentialsFile(_CREDS_FILE)

    if gauth.credentials is None:
        # First-time auth: open browser for OAuth consent
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        gauth.Refresh()
    else:
        gauth.Authorize()

    # Save credentials so next session skips the browser step
    gauth.SaveCredentialsFile(_CREDS_FILE)

    drive = GoogleDrive(gauth)
    st.session_state["gauth"] = gauth
    st.session_state["gdrive"] = drive
    return gauth, drive


def _get_drive() -> "GoogleDrive | None":
    """Return the cached drive instance, or None if not authenticated."""
    return st.session_state.get("gdrive")


# ── Folder Listing ─────────────────────────────────────────────────────────────

def _list_folder(drive, folder_id: str) -> list[dict]:
    """
    List folders and CSV files inside a given Drive folder.
    Returns a list of dicts with keys: id, title, mimeType.
    Results are sorted: folders first, then CSVs — each group alphabetically.
    """
    query = (
        f"'{folder_id}' in parents and trashed=false and "
        f"(mimeType='{_MIME_FOLDER}' or mimeType='{_MIME_CSV}')"
    )
    try:
        raw = drive.ListFile({"q": query}).GetList()
    except Exception as exc:
        st.error(f"❌ Failed to list folder: {exc}")
        return []

    folders = sorted(
        [f for f in raw if f["mimeType"] == _MIME_FOLDER],
        key=lambda x: x["title"].lower(),
    )
    csvs = sorted(
        [f for f in raw if f["mimeType"] == _MIME_CSV],
        key=lambda x: x["title"].lower(),
    )
    return folders + csvs


def _refresh_listing() -> None:
    """Refresh and cache the current folder's file listing in session state."""
    drive = _get_drive()
    if drive is None:
        return
    folder_id = st.session_state["drive_current_folder_id"]
    st.session_state["drive_items"] = _list_folder(drive, folder_id)


# ── CSV Loader ─────────────────────────────────────────────────────────────────

def _load_drive_csv(drive, file_meta: dict) -> None:
    """
    Download a Drive CSV file into memory and register it in session state.
    """
    file_id = file_meta["id"]
    file_title = file_meta["title"]

    try:
        gfile = drive.CreateFile({"id": file_id})
        content_bytes = gfile.GetContentString(encoding="utf-8").encode("utf-8")
        df = pd.read_csv(io.BytesIO(content_bytes))

        # Handle filename collisions (local vs Drive)
        key = file_title
        if key in st.session_state["datasets"]:
            base = PurePosixPath(file_title).stem
            ext = PurePosixPath(file_title).suffix
            counter = 1
            while key in st.session_state["datasets"]:
                key = f"{base}_drive_{counter}{ext}"
                counter += 1

        st.session_state["datasets"][key] = df
        st.success(
            f"✅ Loaded **{key}** from Google Drive — "
            f"{df.shape[0]:,} rows × {df.shape[1]} columns"
        )
    except Exception as exc:
        st.error(f"❌ Failed to load `{file_title}`: {exc}")


# ── Breadcrumb ─────────────────────────────────────────────────────────────────

def _breadcrumb() -> str:
    """Build a readable breadcrumb string from the folder navigation stack."""
    stack: list[dict] = st.session_state.get("drive_folder_stack", [])
    parts = ["My Drive"] + [f["title"] for f in stack]
    return " / ".join(parts)


# ── Main UI ────────────────────────────────────────────────────────────────────

def render_drive_browser() -> None:
    """
    Render the Google Drive folder browser UI panel.
    Call this inside the sidebar or main body as needed.
    """
    if not PYDRIVE2_AVAILABLE:
        st.error(
            "❌ PyDrive2 is not installed. Run `pip install pydrive2` to enable "
            "Google Drive integration."
        )
        return

    st.markdown("#### 🌐 Google Drive")

    drive = _get_drive()

    # ── Connect button ─────────────────────────────────────────────────────────
    if drive is None:
        st.info("Connect to Google Drive to browse and load CSV files.")
        if st.button("🔗 Connect to Google Drive", key="drive_connect_btn"):
            with st.spinner("Opening OAuth consent window…"):
                try:
                    _, drive = _authenticate()
                    st.session_state["drive_current_folder_id"] = "root"
                    st.session_state["drive_folder_stack"] = []
                    _refresh_listing()
                    st.rerun()
                except Exception as exc:
                    st.error(f"❌ Authentication failed: {exc}")
        return

    # ── Connected — show browser ───────────────────────────────────────────────
    st.caption(f"📍 {_breadcrumb()}")

    # Back button
    stack: list[dict] = st.session_state["drive_folder_stack"]
    if stack:
        if st.button("← Back", key="drive_back_btn"):
            stack.pop()
            st.session_state["drive_folder_stack"] = stack
            if stack:
                st.session_state["drive_current_folder_id"] = stack[-1]["id"]
            else:
                st.session_state["drive_current_folder_id"] = "root"
            _refresh_listing()
            st.rerun()

    # Refresh listing if empty
    if not st.session_state.get("drive_items"):
        _refresh_listing()

    items: list[dict] = st.session_state.get("drive_items", [])

    if not items:
        st.info("📭 This folder is empty (no sub-folders or CSV files found).")
        return

    # ── Display folder/file items ──────────────────────────────────────────────
    for item in items:
        is_folder = item["mimeType"] == _MIME_FOLDER
        icon = "📁" if is_folder else "📄"
        label = f"{icon} {item['title']}"

        col1, col2 = st.columns([5, 1])
        with col1:
            st.markdown(f"**{label}**" if is_folder else label)
        with col2:
            btn_key = f"drive_item_{item['id']}"
            if is_folder:
                if st.button("Open", key=btn_key):
                    # Push the folder being entered (id + its own title) onto the stack
                    current_stack = st.session_state["drive_folder_stack"]
                    current_stack.append({"id": item["id"], "title": item["title"]})
                    st.session_state["drive_folder_stack"] = current_stack
                    st.session_state["drive_current_folder_id"] = item["id"]
                    _refresh_listing()
                    st.rerun()
            else:
                if st.button("Load", key=btn_key):
                    with st.spinner(f"Downloading {item['title']}…"):
                        _load_drive_csv(drive, item)
                    st.rerun()

    # ── Disconnect ─────────────────────────────────────────────────────────────
    st.divider()
    if st.button("🔌 Disconnect", key="drive_disconnect_btn"):
        for k in ["gauth", "gdrive", "drive_folder_stack",
                  "drive_current_folder_id", "drive_items"]:
            st.session_state[k] = None if k in ("gauth", "gdrive") else \
                                   [] if k in ("drive_folder_stack", "drive_items") else "root"
        st.rerun()
