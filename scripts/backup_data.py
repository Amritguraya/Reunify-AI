"""Create a private archive of the live database and uploaded case photos."""

from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storage import DATABASE, DATA_DIR, UPLOAD_ROOT  # noqa: E402


BACKUP_DIR = Path(
    os.environ.get("BACKUP_DIR", str(DATA_DIR / "backups"))
).expanduser().resolve()
try:
    BACKUP_RETENTION = int(os.environ.get("BACKUP_RETENTION", "7"))
except ValueError as exc:
    raise SystemExit("BACKUP_RETENTION must be an integer from 1 to 1000.") from exc
if not 1 <= BACKUP_RETENTION <= 1000:
    raise SystemExit("BACKUP_RETENTION must be an integer from 1 to 1000.")

PUBLIC_STATIC_ROOT = (Path(__file__).resolve().parents[1] / "static").resolve()
if BACKUP_DIR == PUBLIC_STATIC_ROOT or BACKUP_DIR.is_relative_to(PUBLIC_STATIC_ROOT):
    raise SystemExit("BACKUP_DIR must not be inside the public static directory.")
if BACKUP_DIR == UPLOAD_ROOT or BACKUP_DIR.is_relative_to(UPLOAD_ROOT):
    raise SystemExit("BACKUP_DIR must not be inside the uploaded-photo directory.")


def make_database_snapshot(destination: Path) -> None:
    with sqlite3.connect(DATABASE, timeout=30) as source:
        with sqlite3.connect(destination, timeout=30) as snapshot:
            source.backup(snapshot)


def add_uploads(archive: zipfile.ZipFile) -> int:
    count = 0
    if not UPLOAD_ROOT.is_dir():
        return count

    resolved_root = UPLOAD_ROOT.resolve()
    for path in UPLOAD_ROOT.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        resolved = path.resolve()
        if not resolved.is_relative_to(resolved_root):
            continue
        archive_name = Path("static") / "uploads" / path.relative_to(UPLOAD_ROOT)
        archive.write(path, arcname=archive_name.as_posix())
        count += 1
    return count


def main() -> None:
    if not DATABASE.is_file():
        raise SystemExit(f"Database not found: {DATABASE}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if os.name != "nt":
            BACKUP_DIR.chmod(0o700)
    except OSError:
        pass
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    final_path = BACKUP_DIR / f"reunify-backup-{timestamp}.zip"
    fd, snapshot_name = tempfile.mkstemp(
        prefix="reunify-db-", suffix=".sqlite3", dir=BACKUP_DIR
    )
    os.close(fd)
    snapshot_path = Path(snapshot_name)
    fd, temp_archive_name = tempfile.mkstemp(
        prefix="reunify-backup-", suffix=".zip.tmp", dir=BACKUP_DIR
    )
    os.close(fd)
    temp_archive = Path(temp_archive_name)
    for sensitive_path in (snapshot_path, temp_archive):
        try:
            sensitive_path.chmod(0o600)
        except OSError:
            pass

    try:
        make_database_snapshot(snapshot_path)
        with zipfile.ZipFile(
            temp_archive, mode="w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            archive.write(snapshot_path, arcname="database.sqlite3")
            photo_count = add_uploads(archive)
        os.replace(temp_archive, final_path)
        try:
            final_path.chmod(0o600)
        except OSError:
            pass
    finally:
        snapshot_path.unlink(missing_ok=True)
        temp_archive.unlink(missing_ok=True)

    backups = sorted(
        BACKUP_DIR.glob("reunify-backup-*.zip"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for old_backup in backups[BACKUP_RETENTION:]:
        old_backup.unlink(missing_ok=True)

    print(f"Backup created: {final_path}")
    print(f"Uploaded photo files included: {photo_count}")
    print("This archive contains sensitive child and family data.")
    print("Copy it to a separate, access-controlled backup location.")


if __name__ == "__main__":
    main()
