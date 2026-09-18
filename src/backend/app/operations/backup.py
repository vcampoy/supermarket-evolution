"""Coherent SQLite/PDF backup and safe restore helpers.

The database is copied through SQLite's online backup API so WAL contents are
included in a consistent snapshot. PDF files and explicitly supplied,
non-secret configuration files are then written into the same archive.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote

from sqlalchemy.engine import make_url


class BackupError(RuntimeError):
    """Raised when a backup or restore cannot be completed safely."""

    code: str

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class BackupResult:
    archive_path: Path
    database_path: Path
    pdf_count: int
    config_count: int


@dataclass(frozen=True, slots=True)
class RestoreResult:
    archive_path: Path
    database_path: Path
    restored_pdf_count: int
    restored_config_count: int


def sqlite_path_from_url(database_url: str, *, base_dir: Path) -> Path:
    """Resolve a file-backed SQLite URL without accepting another backend."""

    url = make_url(database_url)
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        raise BackupError("BACKUP_REQUIRES_FILE_SQLITE")
    raw_path = unquote(url.database)
    if raw_path.startswith("/") and len(raw_path) > 2 and raw_path[2] == ":":
        raw_path = raw_path[1:]
    path = Path(raw_path).expanduser()
    return path if path.is_absolute() else (base_dir / path).resolve()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _copy_sqlite_snapshot(source_path: Path, destination_path: Path) -> None:
    if not source_path.is_file():
        raise BackupError("DATABASE_NOT_FOUND")
    source = sqlite3.connect(source_path)
    destination = sqlite3.connect(destination_path)
    try:
        source.backup(destination)
        result = destination.execute("PRAGMA integrity_check").fetchone()
        if result != ("ok",):
            raise BackupError("DATABASE_INTEGRITY_CHECK_FAILED")
    except sqlite3.Error as exc:
        raise BackupError("DATABASE_BACKUP_FAILED") from exc
    finally:
        destination.close()
        source.close()


def _safe_zip_member(member: str) -> Path:
    path = Path(member)
    if path.is_absolute() or ".." in path.parts:
        raise BackupError("ARCHIVE_PATH_UNSAFE")
    return path


def _copy_tree_contents(source: Path, destination: Path) -> int:
    count = 0
    if not source.is_dir():
        return count
    for item in source.rglob("*"):
        if not item.is_file() or item.name.startswith(".partial-"):
            continue
        relative = item.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        count += 1
    return count


def create_backup(
    *,
    database_path: Path,
    tickets_directory: Path,
    output_directory: Path,
    config_files: tuple[Path, ...] = (),
    now: datetime | None = None,
) -> BackupResult:
    """Create one archive from a consistent database snapshot and file copies."""

    database_path = database_path.expanduser().resolve()
    tickets_directory = tickets_directory.expanduser().resolve()
    output_directory = output_directory.expanduser().resolve()
    output_directory.mkdir(parents=True, exist_ok=True)
    timestamp = (now or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")
    archive_path = output_directory / f"supermarket-evolution-{timestamp}.zip"
    if archive_path.exists():
        raise BackupError("BACKUP_ALREADY_EXISTS")

    with tempfile.TemporaryDirectory(prefix="supermarket-backup-") as temporary:
        root = Path(temporary)
        snapshot = root / "database.sqlite3"
        _copy_sqlite_snapshot(database_path, snapshot)
        pdf_root = root / "tickets"
        pdf_count = _copy_tree_contents(tickets_directory, pdf_root)
        config_root = root / "config"
        config_count = 0
        for config_file in config_files:
            source = config_file.expanduser().resolve()
            if not source.is_file():
                continue
            target = config_root / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            config_count += 1

        files = sorted(path for path in root.rglob("*") if path.is_file())
        manifest = {
            "format": 1,
            "createdAtUtc": datetime.now(UTC).isoformat(),
            "database": "database.sqlite3",
            "tickets": "tickets/",
            "config": "config/",
            "files": {
                path.relative_to(root).as_posix(): _sha256(path)
                for path in files
            },
        }
        (root / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(root).as_posix())
    return BackupResult(archive_path, database_path, pdf_count, config_count)


def restore_backup(
    *,
    archive_path: Path,
    database_path: Path,
    tickets_directory: Path,
    config_directory: Path | None = None,
) -> RestoreResult:
    """Restore an archive after the caller has stopped the running service."""

    archive_path = archive_path.expanduser().resolve()
    if not archive_path.is_file():
        raise BackupError("BACKUP_NOT_FOUND")
    database_path = database_path.expanduser().resolve()
    tickets_directory = tickets_directory.expanduser().resolve()
    with tempfile.TemporaryDirectory(prefix="supermarket-restore-") as temporary:
        root = Path(temporary)
        try:
            with zipfile.ZipFile(archive_path) as archive:
                for member in archive.namelist():
                    _safe_zip_member(member)
                archive.extractall(root)
        except (zipfile.BadZipFile, OSError) as exc:
            raise BackupError("BACKUP_INVALID") from exc
        manifest_path = root / "manifest.json"
        snapshot = root / "database.sqlite3"
        if not manifest_path.is_file() or not snapshot.is_file():
            raise BackupError("BACKUP_INCOMPLETE")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            files = manifest["files"]
            expected_database_hash = files["database.sqlite3"]
        except (KeyError, TypeError, json.JSONDecodeError) as exc:
            raise BackupError("BACKUP_MANIFEST_INVALID") from exc
        for member, expected_hash in manifest.get("files", {}).items():
            path = root / _safe_zip_member(member)
            if not path.is_file() or _sha256(path) != expected_hash:
                raise BackupError("BACKUP_CHECKSUM_FAILED")
        if _sha256(snapshot) != expected_database_hash:
            raise BackupError("BACKUP_CHECKSUM_FAILED")

        database_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(snapshot, database_path)
        pdf_count = _copy_tree_contents(root / "tickets", tickets_directory)
        config_count = 0
        if config_directory:
            config_directory = config_directory.expanduser().resolve()
            config_directory.mkdir(parents=True, exist_ok=True)
            config_count = _copy_tree_contents(root / "config", config_directory)
    return RestoreResult(archive_path, database_path, pdf_count, config_count)
