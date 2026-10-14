"""Validation and safe storage for user-submitted child photographs."""

from __future__ import annotations

import uuid
import warnings
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from storage import UPLOAD_ROOT, _restrict_permissions


Image.MAX_IMAGE_PIXELS = 12_000_000
warnings.simplefilter("error", Image.DecompressionBombWarning)

_ALLOWED_FORMATS = {
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".png": "PNG",
    ".webp": "WEBP",
}


def save_child_photo(photo: FileStorage, category: str) -> str:
    """Decode and re-encode a bounded image, dropping metadata and extra payloads."""
    if category not in {"missing_children", "found_children"}:
        raise ValueError("Unsupported upload category.")

    safe_name = secure_filename(photo.filename or "")
    extension = Path(safe_name).suffix.lower()
    expected_format = _ALLOWED_FORMATS.get(extension)
    if not safe_name or not expected_format:
        raise ValueError("Upload a JPG, PNG, or WEBP image.")

    try:
        photo.stream.seek(0)
        with Image.open(photo.stream) as image:
            if image.format != expected_format:
                raise ValueError("The image content does not match its file type.")
            image.verify()
        photo.stream.seek(0)
        with Image.open(photo.stream) as image:
            if image.width < 32 or image.height < 32:
                raise ValueError("The image must be at least 32 by 32 pixels.")
            if image.width > 6000 or image.height > 6000:
                raise ValueError("The image dimensions are too large.")
            clean_image = ImageOps.exif_transpose(image)
            if expected_format == "JPEG":
                if clean_image.mode not in {"RGB", "L"}:
                    rgba = clean_image.convert("RGBA")
                    background = Image.new("RGB", rgba.size, "white")
                    background.paste(rgba, mask=rgba.getchannel("A"))
                    clean_image = background
                elif clean_image.mode == "L":
                    clean_image = clean_image.convert("RGB")
            elif expected_format == "PNG" and clean_image.mode == "P":
                clean_image = clean_image.convert("RGBA")
            elif expected_format == "PNG" and clean_image.mode not in {
                "1", "L", "LA", "RGB", "RGBA"
            }:
                clean_image = clean_image.convert("RGBA")
            elif expected_format == "WEBP" and clean_image.mode not in {
                "RGB", "RGBA"
            }:
                clean_image = clean_image.convert("RGBA")
            clean_image.load()
            # Create a fresh pixel-only image so EXIF, ICC, and other metadata
            # from the untrusted upload cannot be carried into the stored file.
            pixel_only = Image.new(clean_image.mode, clean_image.size)
            pixel_only.paste(clean_image)
            clean_image.close()
            clean_image = pixel_only
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
        OSError,
    ) as exc:
        raise ValueError("The uploaded file is not a valid image.") from exc

    filename = f"{uuid.uuid4().hex}{extension}"
    category_dir = UPLOAD_ROOT / category
    category_dir.mkdir(parents=True, exist_ok=True)
    _restrict_permissions(category_dir, 0o700)
    destination = category_dir / filename
    try:
        save_options = {"format": expected_format}
        if expected_format == "JPEG":
            save_options.update(quality=88, optimize=True, progressive=True)
        elif expected_format == "PNG":
            save_options.update(optimize=True)
        else:
            save_options.update(quality=88, method=4)
        clean_image.save(destination, **save_options)
        _restrict_permissions(destination, 0o600)
    except (OSError, ValueError) as exc:
        destination.unlink(missing_ok=True)
        raise ValueError("The uploaded image could not be safely stored.") from exc
    finally:
        clean_image.close()

    return f"static/uploads/{category}/{filename}"
