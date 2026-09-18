"""Operational CLI for OAuth, synchronization, parsing and reparsing."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from pathlib import Path

from app.application.contracts import GmailError, TicketParseError
from app.application.ingestion import TicketSyncService
from app.core.config import get_settings
from app.infrastructure.archive import PdfArchive
from app.infrastructure.db import SessionFactory
from app.infrastructure.gmail import GmailApiClient, authorize_gmail
from app.infrastructure.parser import parse_pdf_bytes, parse_pdf_file
from app.infrastructure.repositories import SqlAlchemyIngestionRepository


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("gmail-auth")
    sync = subparsers.add_parser("sync")
    sync_group = sync.add_mutually_exclusive_group(required=True)
    sync_group.add_argument("--all", action="store_true")
    sync_group.add_argument("--since-last", action="store_true")
    parse_file = subparsers.add_parser("parse-file")
    parse_file.add_argument("pdf", type=Path)
    reparse = subparsers.add_parser("reparse")
    reparse.add_argument("--failed", action="store_true", required=True)
    return parser


async def _sync(mode: str) -> int:
    settings = get_settings()
    query = settings.gmail_query or f"from:({settings.gmail_sender}) has:attachment filename:pdf"
    async with SessionFactory() as session:
        repository = SqlAlchemyIngestionRepository(session)
        service = TicketSyncService(
            gmail=GmailApiClient(settings),
            repository=repository,
            archive=PdfArchive(settings.tickets_directory),
            parser=parse_pdf_bytes,
            max_attachment_bytes=settings.gmail_max_attachment_bytes,
        )
        summary = await service.sync(mode=mode, query=query)
    print(json.dumps(asdict(summary), ensure_ascii=False))
    return 0 if summary.error_count == 0 else 2


async def _reparse_failed() -> int:
    settings = get_settings()
    count = 0
    errors = 0
    async with SessionFactory() as session:
        repository = SqlAlchemyIngestionRepository(session)
        for message in await repository.failed_messages():
            try:
                parsed = parse_pdf_file(Path(settings.tickets_directory) / message.original_pdf_path)
                await repository.replace_parsed_ticket(message, parsed)
                count += 1
            except (OSError, TicketParseError):
                errors += 1
    print(json.dumps({"reparsed": count, "errors": errors}))
    return 0 if errors == 0 else 2


def _print_parsed(path: Path) -> int:
    try:
        parsed = parse_pdf_file(path)
    except TicketParseError as exc:
        print(json.dumps({"status": "failed", "errorCode": exc.code}))
        return 2
    print(
        json.dumps(
            {
                "status": parsed.status.value,
                "ticketNumber": parsed.ticket_number,
                "purchasedAt": parsed.purchased_at_utc.isoformat(),
                "totalCents": parsed.total_cents,
                "lineCount": len(parsed.lines),
                "lines": [
                    {
                        "lineIndex": line.line_index,
                        "description": line.raw_description,
                        "quantity": str(line.quantity) if line.quantity is not None else None,
                        "quantityUnit": line.quantity_unit.value,
                        "weightGrams": line.weight_grams,
                        "lineAmountCents": line.line_amount_cents,
                        "comparablePriceCents": line.comparable_price_cents,
                        "comparableBasis": line.comparable_basis.value if line.comparable_basis else None,
                    }
                    for line in parsed.lines
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "gmail-auth":
            print(json.dumps({"authorizedAccount": authorize_gmail(get_settings())}))
            return 0
        if args.command == "sync":
            return asyncio.run(_sync("backfill" if args.all else "incremental"))
        if args.command == "parse-file":
            return _print_parsed(args.pdf)
        if args.command == "reparse":
            return asyncio.run(_reparse_failed())
    except GmailError as exc:
        print(json.dumps({"errorCode": exc.code}), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
