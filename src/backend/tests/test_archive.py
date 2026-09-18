from pathlib import Path

from app.infrastructure.archive import PdfArchive


def test_archive_is_atomic_and_deduplicates_by_hash(tmp_path: Path) -> None:
    archive = PdfArchive(tmp_path)
    data = b"%PDF-1.4 fixture"
    first = archive.write(message_id="msg/1", attachment_id="att:1", original_filename="ticket?.pdf", pdf_bytes=data)
    second = archive.write(message_id="msg/2", attachment_id="att:2", original_filename="other.pdf", pdf_bytes=data)
    assert first.sha256 == second.sha256
    assert second.is_duplicate_hash
    assert list(tmp_path.rglob("*.pdf")) == [tmp_path / first.relative_path]
    assert not list(tmp_path.rglob(".partial-*"))
