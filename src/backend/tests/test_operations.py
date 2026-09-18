from __future__ import annotations

import os
import platform
import shutil
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.api.main import _allowed_bind_host
from app.operations.backup import create_backup, restore_backup


def _powershell() -> str | None:
    if platform.system() != "Windows":
        return None
    return shutil.which("pwsh") or shutil.which("powershell")


def _run_script(script: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    executable = _powershell()
    assert executable is not None
    return subprocess.run(
        [executable, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *arguments],
        capture_output=True,
        text=True,
        check=False,
    )


def test_bind_host_only_allows_loopback_or_tailscale() -> None:
    assert _allowed_bind_host("127.0.0.1")
    assert _allowed_bind_host("100.101.102.103")
    assert not _allowed_bind_host("0.0.0.0")
    assert not _allowed_bind_host("192.168.1.10")


def test_backup_restore_round_trip_with_sqlite_wal_and_pdf(tmp_path: Path) -> None:
    database = tmp_path / "source" / "supermarket-evolution.db"
    database.parent.mkdir()
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample VALUES ('synthetic ticket')")
        connection.commit()
    tickets = tmp_path / "tickets"
    tickets.mkdir()
    pdf = tickets / "2026-09" / "ticket.pdf"
    pdf.parent.mkdir()
    pdf.write_bytes(b"%PDF synthetic ticket")
    (pdf.parent / ".partial-ticket.pdf").write_bytes(b"incomplete")
    config = tmp_path / "alembic.ini"
    config.write_text("[alembic]\n", encoding="utf-8")

    backup = create_backup(
        database_path=database,
        tickets_directory=tickets,
        output_directory=tmp_path / "backups",
        config_files=(config,),
        now=datetime(2026, 9, 18, 1, 0, tzinfo=UTC),
    )
    restored_database = tmp_path / "restored" / "supermarket-evolution.db"
    restored_tickets = tmp_path / "restored" / "tickets"
    restored_config = tmp_path / "restored" / "config"
    restored = restore_backup(
        archive_path=backup.archive_path,
        database_path=restored_database,
        tickets_directory=restored_tickets,
        config_directory=restored_config,
    )

    assert restored.restored_pdf_count == 1
    assert (restored_tickets / "2026-09" / "ticket.pdf").read_bytes() == pdf.read_bytes()
    assert not (restored_tickets / "2026-09" / ".partial-ticket.pdf").exists()
    assert (restored_config / "alembic.ini").read_text(encoding="utf-8") == config.read_text(encoding="utf-8")
    with sqlite3.connect(restored_database) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("SELECT value FROM sample").fetchone() == ("synthetic ticket",)


@pytest.mark.skipif(_powershell() is None, reason="PowerShell is required for operational script tests")
def test_scheduled_execution_simulation_retries_without_logging_output(tmp_path: Path) -> None:
    script = Path(__file__).parents[2] / "scripts" / "sync-tickets.ps1"
    fake_python = tmp_path / "fake-python.cmd"
    fake_python.write_text(
        "@echo off\n"
        'if "%~1"=="-c" (\n'
        "  echo 3.13\n"
        "  exit /b 0\n"
        ")\n"
        "if exist \"%~dp0called\" exit /b 0\n"
        "echo called>\"%~dp0called\"\n"
        "exit /b 1\n",
        encoding="ascii",
    )
    log_directory = tmp_path / "logs"
    result = _run_script(
        script,
        "-BackendDirectory",
        str(tmp_path),
        "-PythonExecutable",
        str(fake_python),
        "-LogDirectory",
        str(log_directory),
        "-MaxRetries",
        "2",
        "-RetryDelaySeconds",
        "0",
        "-MutexName",
        f"Local\\SupermarketEvolution-Test-{os.getpid()}",
    )

    assert result.returncode == 0, result.stderr
    log = (log_directory / "sync-tickets.log").read_text(encoding="utf-8-sig")
    assert "failed" in log and "succeeded" in log
    assert "synthetic ticket" not in log
    assert "token" not in log.lower()


@pytest.mark.skipif(_powershell() is None, reason="PowerShell is required for operational script tests")
def test_two_synchronizations_do_not_overlap(tmp_path: Path) -> None:
    script = Path(__file__).parents[2] / "scripts" / "sync-tickets.ps1"
    fake_python = tmp_path / "slow-python.cmd"
    fake_python.write_text(
        "@echo off\n"
        'if "%~1"=="-c" (\n'
        "  echo 3.13\n"
        "  exit /b 0\n"
        ")\n"
        "ping -n 3 127.0.0.1 >nul\n"
        "exit /b 0\n",
        encoding="ascii",
    )
    log_directory = tmp_path / "logs"
    mutex = f"Local\\SupermarketEvolution-Overlap-{os.getpid()}"
    executable = _powershell()
    assert executable is not None
    arguments = [
        executable,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "-BackendDirectory",
        str(tmp_path),
        "-PythonExecutable",
        str(fake_python),
        "-LogDirectory",
        str(log_directory),
        "-RetryDelaySeconds",
        "0",
        "-MutexName",
        mutex,
    ]
    first = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        import time

        time.sleep(0.25)
        second = subprocess.run(arguments, capture_output=True, text=True, check=False)
        assert second.returncode == 0, second.stderr
    finally:
        first.wait(timeout=10)
    log = (log_directory / "sync-tickets.log").read_text(encoding="utf-8-sig")
    assert "skipped" in log
