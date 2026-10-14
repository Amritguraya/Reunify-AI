"""Persistent paths used by the Flask app and its background matching code."""

from __future__ import annotations

import os
import sqlite3
import shutil
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
STORAGE_APP_ENV = os.environ.get("APP_ENV", "development").strip().lower()
if STORAGE_APP_ENV not in {"development", "test", "production"}:
    raise RuntimeError("APP_ENV must be development, test, or production.")
IS_PRODUCTION = STORAGE_APP_ENV == "production"
if IS_PRODUCTION and not os.environ.get("DATA_DIR", "").strip():
    raise RuntimeError(
        "Production requires DATA_DIR to point to a persistent directory outside the source tree."
    )
DATA_DIR = Path(os.environ.get("DATA_DIR", str(PROJECT_DIR))).expanduser().resolve()
DATABASE = Path(
    os.environ.get("DATABASE_PATH", str(DATA_DIR / "database.db"))
).expanduser().resolve()
UPLOAD_ROOT = Path(
    os.environ.get("UPLOAD_ROOT", str(DATA_DIR / "uploads"))
).expanduser().resolve()

LEGACY_DATABASE = PROJECT_DIR / "database.db"
LEGACY_UPLOAD_ROOT = PROJECT_DIR / "static" / "uploads"
PREVIOUS_VOLUME_UPLOAD_ROOT = DATA_DIR / "static" / "uploads"
STATIC_ROOT = (PROJECT_DIR / "static").resolve()
if IS_PRODUCTION and DATA_DIR == Path(DATA_DIR.anchor):
    raise RuntimeError("DATA_DIR must be a dedicated data directory, not a filesystem root.")
if IS_PRODUCTION and DATA_DIR.is_relative_to(PROJECT_DIR):
    raise RuntimeError("Production DATA_DIR must be outside the project source tree.")
if IS_PRODUCTION and DATABASE.is_relative_to(PROJECT_DIR):
    raise RuntimeError("Production DATABASE_PATH must be outside the project source tree.")
if IS_PRODUCTION and UPLOAD_ROOT.is_relative_to(PROJECT_DIR):
    raise RuntimeError("Production UPLOAD_ROOT must be outside the project source tree.")
if DATABASE == STATIC_ROOT or DATABASE.is_relative_to(STATIC_ROOT):
    raise RuntimeError("DATABASE_PATH must be outside the public static directory.")
if UPLOAD_ROOT == STATIC_ROOT or UPLOAD_ROOT.is_relative_to(STATIC_ROOT):
    raise RuntimeError("UPLOAD_ROOT must be outside the public static directory.")


def _restrict_permissions(path: Path, mode: int) -> None:
    """Limit Unix permissions for sensitive storage; Windows uses inherited ACLs."""
    if os.name == "nt":
        return
    try:
        path.chmod(mode)
    except OSError:
        pass


def _copy_legacy_data_enabled() -> bool:
    """Only migrate project-local data when explicitly intended for production."""
    configured = os.environ.get("COPY_LEGACY_DATA")
    if configured is not None:
        return configured.strip().lower() in {"1", "true", "yes", "on"}
    return os.environ.get("APP_ENV", "development").strip().lower() != "production"


def connect_database(*, row_factory: bool = False) -> sqlite3.Connection:
    """Open a consistently configured SQLite connection."""
    connection = sqlite3.connect(DATABASE, timeout=10)
    _restrict_permissions(DATABASE, 0o600)
    connection.execute("PRAGMA busy_timeout = 10000")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA synchronous = NORMAL")
    if row_factory:
        connection.row_factory = sqlite3.Row
    return connection


def _copy_uploads_without_symlinks(source_root: Path) -> None:
    if source_root.is_symlink():
        return
    source_root = source_root.resolve()
    destination_root = UPLOAD_ROOT.resolve()
    for source in source_root.rglob("*"):
        if source.is_symlink() or not source.is_file():
            continue
        resolved_source = source.resolve()
        if not resolved_source.is_relative_to(source_root):
            continue
        destination = destination_root / source.relative_to(source_root)
        if not destination.resolve().is_relative_to(destination_root):
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(resolved_source, destination)
        _restrict_permissions(destination, 0o600)


def initialize_storage() -> None:
    """Create persistent directories and optionally seed them from local data."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATABASE.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    if DATA_DIR != PROJECT_DIR and DATA_DIR.parent != Path(DATA_DIR.anchor):
        _restrict_permissions(DATA_DIR, 0o700)
    if DATABASE.parent != PROJECT_DIR and DATABASE.parent.is_relative_to(DATA_DIR):
        _restrict_permissions(DATABASE.parent, 0o700)
    _restrict_permissions(UPLOAD_ROOT, 0o700)

    if not _copy_legacy_data_enabled():
        return

    if (
        DATABASE != LEGACY_DATABASE
        and not DATABASE.exists()
        and LEGACY_DATABASE.is_file()
        and not LEGACY_DATABASE.is_symlink()
    ):
        shutil.copy2(LEGACY_DATABASE, DATABASE)

    has_persistent_uploads = any(
        path.is_file() and not path.is_symlink()
        for path in UPLOAD_ROOT.rglob("*")
    )
    if (
        not has_persistent_uploads
        and PREVIOUS_VOLUME_UPLOAD_ROOT != UPLOAD_ROOT
        and PREVIOUS_VOLUME_UPLOAD_ROOT != LEGACY_UPLOAD_ROOT
        and PREVIOUS_VOLUME_UPLOAD_ROOT.is_dir()
        and not PREVIOUS_VOLUME_UPLOAD_ROOT.is_symlink()
    ):
        _copy_uploads_without_symlinks(PREVIOUS_VOLUME_UPLOAD_ROOT)
        has_persistent_uploads = any(
            path.is_file() and not path.is_symlink()
            for path in UPLOAD_ROOT.rglob("*")
        )
    if (
        UPLOAD_ROOT != LEGACY_UPLOAD_ROOT
        and not has_persistent_uploads
        and LEGACY_UPLOAD_ROOT.is_dir()
        and not LEGACY_UPLOAD_ROOT.is_symlink()
        and _copy_legacy_data_enabled()
    ):
        _copy_uploads_without_symlinks(LEGACY_UPLOAD_ROOT)

    _restrict_permissions(DATABASE, 0o600)


def resolve_upload_path(stored_path: str | os.PathLike[str] | None) -> str | None:
    """Resolve legacy DB paths and new uploads inside the configured data volume."""
    if not stored_path:
        return None

    raw = str(stored_path).strip().replace("\\", "/")
    if not raw:
        return None

    normalized = raw.lstrip("/")
    if "/static/uploads/" in f"/{normalized}":
        relative = f"/{normalized}".split("/static/uploads/", 1)[1]
    elif normalized.startswith("static/uploads/"):
        relative = normalized[len("static/uploads/"):]
    elif normalized.startswith("uploads/"):
        relative = normalized[len("uploads/"):]
    else:
        relative = normalized

    candidates: list[Path] = []
    raw_path = Path(raw)
    if raw_path.is_absolute():
        candidates.append(raw_path)
    candidates.extend((UPLOAD_ROOT / relative, LEGACY_UPLOAD_ROOT / relative))

    for candidate in candidates:
        resolved = candidate.resolve()
        allowed_roots = (UPLOAD_ROOT, LEGACY_UPLOAD_ROOT)
        if not any(resolved.is_relative_to(root.resolve()) for root in allowed_roots):
            continue
        if resolved.is_file():
            return str(resolved)

    fallback = (UPLOAD_ROOT / relative).resolve()
    if not fallback.is_relative_to(UPLOAD_ROOT.resolve()):
        return None
    return str(fallback)
