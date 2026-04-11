"""
image_source.py
---------------
ImageDataset dataclass + ZIP/folder loader for image datasets.

Supported upload types
  - ZIP of images (flat: all one class)
  - ZIP of subfolders-as-classes  (e.g. cats/dog.jpg, dogs/poodle.jpg)
  - Single JPG / PNG / WEBP / BMP image

Stored in st.session_state["datasets"] under the filename key.
The value is an ImageDataset object (not a pd.DataFrame).
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Optional

import streamlit as st

# PIL is optional — we show a friendly error if missing
try:
    from PIL import Image as PILImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# ── Image extensions we accept ─────────────────────────────────────────────────
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".gif", ".tiff"}


# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class ImageEntry:
    name: str                          # filename (basename)
    label: str                         # class label (subfolder name or "unlabelled")
    pil_image: Optional[object]        # PIL.Image.Image or None if corrupt
    width: int = 0
    height: int = 0
    file_size: int = 0                 # bytes
    raw_bytes: bytes = field(default=b"", repr=False)


@dataclass
class ImageDataset:
    name: str                          # display name (zip filename)
    images: list[ImageEntry]
    source: str = "local"              # "local" | "drive"

    # ── Derived helpers ────────────────────────────────────────────────────────
    @property
    def labels(self) -> list[str]:
        return sorted(set(img.label for img in self.images))

    @property
    def n_total(self) -> int:
        return len(self.images)

    @property
    def n_valid(self) -> int:
        return sum(1 for img in self.images if img.pil_image is not None)

    @property
    def n_corrupt(self) -> int:
        return self.n_total - self.n_valid


# ── Internal helpers ───────────────────────────────────────────────────────────

def _pil_from_bytes(raw: bytes) -> tuple[Optional[object], int, int]:
    """
    Load a PIL image from bytes.
    Returns (pil_image | None, width, height).
    """
    if not PIL_AVAILABLE:
        return None, 0, 0
    try:
        img = PILImage.open(io.BytesIO(raw))
        img.load()                      # force full decode so corrupt images raise
        img = img.convert("RGB")        # normalise colour mode
        w, h = img.size
        return img, w, h
    except Exception:
        return None, 0, 0


def _register_image_dataset(name: str, dataset: "ImageDataset") -> None:
    """Store an ImageDataset in session state, avoiding key collisions."""
    key = name
    if key in st.session_state["datasets"]:
        stem = PurePosixPath(name).stem
        ext = PurePosixPath(name).suffix
        counter = 1
        while key in st.session_state["datasets"]:
            key = f"{stem}_img_{counter}{ext}"
            counter += 1
    st.session_state["datasets"][key] = dataset


# ── Public loaders ─────────────────────────────────────────────────────────────

def load_single_image(name: str, raw_bytes: bytes, source: str = "local") -> ImageDataset:
    """Wrap a single image file in an ImageDataset."""
    pil_img, w, h = _pil_from_bytes(raw_bytes)
    entry = ImageEntry(
        name=name,
        label="unlabelled",
        pil_image=pil_img,
        width=w,
        height=h,
        file_size=len(raw_bytes),
        raw_bytes=raw_bytes,
    )
    return ImageDataset(name=name, images=[entry], source=source)


def load_image_zip(zip_name: str, raw_bytes: bytes, source: str = "local") -> Optional[ImageDataset]:
    """
    Parse a ZIP archive containing images.

    Folder layout detection:
      - If ANY image sits inside a subfolder, subfolders are treated as class labels.
      - If ALL images are at the root level, they get the label "unlabelled".

    Returns None if the ZIP has no recognisable image files.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            members = zf.namelist()
    except zipfile.BadZipFile:
        return None

    # Filter to image members only (skip __MACOSX, hidden files)
    image_members = [
        m for m in members
        if not PurePosixPath(m).name.startswith(".")
        and not m.startswith("__MACOSX")
        and PurePosixPath(m).suffix.lower() in IMAGE_EXTS
        and not m.endswith("/")
    ]

    if not image_members:
        return None

    # Detect subfolder layout
    has_subfolders = any(len(PurePosixPath(m).parts) > 1 for m in image_members)

    entries: list[ImageEntry] = []

    # Cap at 1000 images for memory safety
    SAMPLE_CAP = 1000
    sampled = image_members[:SAMPLE_CAP]
    if len(image_members) > SAMPLE_CAP:
        st.info(
            f"ℹ️ ZIP contains {len(image_members):,} images — "
            f"showing first {SAMPLE_CAP:,} for performance."
        )

    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
        for member in sampled:
            parts = PurePosixPath(member).parts
            basename = parts[-1]

            if has_subfolders and len(parts) >= 2:
                label = parts[-2]           # immediate parent folder = class
            else:
                label = "unlabelled"

            try:
                file_bytes = zf.read(member)
            except Exception:
                file_bytes = b""

            pil_img, w, h = _pil_from_bytes(file_bytes)
            entries.append(ImageEntry(
                name=basename,
                label=label,
                pil_image=pil_img,
                width=w,
                height=h,
                file_size=len(file_bytes),
                raw_bytes=file_bytes,
            ))

    return ImageDataset(name=zip_name, images=entries, source=source)


# ── Streamlit handler called from local_source.py ─────────────────────────────

def handle_image_upload(uploaded_file) -> None:
    """
    Called from local_source.render_local_uploader() when the uploaded file
    is an image or an image ZIP.
    """
    if not PIL_AVAILABLE:
        st.error(
            "❌ **Pillow** is not installed. "
            "Run `pip install Pillow` to enable image dataset support."
        )
        return

    raw = uploaded_file.read()
    name = uploaded_file.name
    ext = PurePosixPath(name).suffix.lower()

    if ext == ".zip":
        with st.spinner(f"Loading image ZIP: {name} …"):
            dataset = load_image_zip(name, raw)
        if dataset is None:
            st.warning(
                f"⚠️ `{name}` is either not a valid ZIP or contains no recognised image files."
            )
            return
        _register_image_dataset(name, dataset)
        st.success(
            f"✅ Loaded **{name}** — "
            f"{dataset.n_total:,} images, {len(dataset.labels)} class(es): "
            f"{', '.join(dataset.labels[:6])}{'…' if len(dataset.labels) > 6 else ''}"
        )

    elif ext in IMAGE_EXTS:
        dataset = load_single_image(name, raw)
        _register_image_dataset(name, dataset)
        img = dataset.images[0]
        status = f"{img.width}×{img.height} px" if img.pil_image else "⚠️ corrupt"
        st.success(f"✅ Loaded single image **{name}** — {status}")

    else:
        st.error(f"❌ Unsupported file type: `{ext}`")
