"""Immutable, atomic storage for original ticket PDFs."""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path

from app.application.contracts import ArchivedPdf, ArchiveError


def _safe_component(value: str, *, fallback: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", Path(value).name).strip("._")
    return safe[:120] or fallback


class PdfArchive:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def find_by_sha256(self, sha256: str) -> ArchivedPdf | None:
        for candidate in self.root.rglob(f"*_{sha256}.pdf"):
            if candidate.is_file():
                return ArchivedPdf(sha256, candidate.stat().st_size, candidate.relative_to(self.root).as_posix(), True)
        return None

    def write(
        self,
        *,
        message_id: str,
        attachment_id: str,
        original_filename: str,
        pdf_bytes: bytes,
        received_at: datetime | None = None,
    ) -> ArchivedPdf:
        if not pdf_bytes.startswith(b"%PDF"):
            raise ArchiveError("PDF_INVALID")
        sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        existing = self.find_by_sha256(sha256)
        if existing:
            return existing
        year_month = received_at.strftime("%Y-%m") if received_at else "unknown"
        safe_name = _safe_component(original_filename, fallback="ticket.pdf")
        if safe_name.lower().endswith(".pdf"):
            stem = safe_name[:-4]
        else:
            stem = safe_name
        safe_message = _safe_component(message_id, fallback="message")
        safe_attachment = _safe_component(attachment_id, fallback="attachment")
        target_dir = self.root / year_month
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{stem}_{safe_message}_{safe_attachment}_{sha256}.pdf"
        if target.exists():
            return ArchivedPdf(sha256, target.stat().st_size, target.relative_to(self.root).as_posix(), True)

        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=target_dir, prefix=".partial-", suffix=".pdf", delete=False) as temporary:
                temporary_path = temporary.name
                temporary.write(pdf_bytes)
                temporary.flush()
                os.fsync(temporary.fileno())
            written = Path(temporary_path).read_bytes()
            if len(written) != len(pdf_bytes) or hashlib.sha256(written).hexdigest() != sha256:
                raise ArchiveError("ARCHIVE_VERIFY_FAILED")
            try:
                os.link(temporary_path, target)
                os.unlink(temporary_path)
            except FileExistsError:
                os.unlink(temporary_path)
                return ArchivedPdf(sha256, target.stat().st_size, target.relative_to(self.root).as_posix(), True)
            return ArchivedPdf(sha256, len(pdf_bytes), target.relative_to(self.root).as_posix())
        except Exception:
            if temporary_path:
                try:
                    os.unlink(temporary_path)
                except FileNotFoundError:
                    pass
            raise
