"""Gmail OAuth and read-only adapter.

The Google dependencies are imported lazily so parser and domain tests never
need credentials or network access.
"""

from __future__ import annotations

import asyncio
import base64
import json
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, AsyncIterator, cast

from app.application.contracts import GmailAttachment, GmailError, GmailMessage
from app.core.config import Settings

GMAIL_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"


def _write_token_atomically(path: Path, token_json: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(token_json, encoding="utf-8")
    temporary.replace(path)


def build_gmail_service(settings: Settings) -> Any:
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]
        from googleapiclient.discovery import build  # type: ignore[import-untyped]
    except ImportError as exc:
        raise GmailError("GMAIL_DEPENDENCIES_MISSING") from exc

    token_path = Path(settings.gmail_token_path).expanduser()
    credentials = None
    if token_path.exists():
        try:
            credentials = Credentials.from_authorized_user_file(str(token_path), [GMAIL_SCOPE])  # type: ignore[no-untyped-call]
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise GmailError("GMAIL_TOKEN_INVALID", reason=type(exc).__name__) from exc
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        _write_token_atomically(token_path, credentials.to_json())
    if not credentials or not credentials.valid:
        client_path = Path(settings.gmail_client_secrets_path).expanduser()
        if not client_path.exists():
            raise GmailError("GMAIL_CLIENT_SECRET_MISSING")
        flow = InstalledAppFlow.from_client_secrets_file(str(client_path), [GMAIL_SCOPE])
        credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
        _write_token_atomically(token_path, credentials.to_json())
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def _header(payload: dict[str, Any], name: str) -> str | None:
    for header in payload.get("headers", []):
        if str(header.get("name", "")).casefold() == name.casefold():
            return str(header.get("value", ""))
    return None


def _received_at(payload: dict[str, Any]) -> datetime | None:
    value = _header(payload, "Date")
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(UTC)
    except (TypeError, ValueError, OverflowError):
        return None


def _parts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for part in payload.get("parts", []):
        result.append(part)
        result.extend(_parts(part))
    return result


class GmailApiClient:
    def __init__(self, settings: Settings, service: Any | None = None) -> None:
        self.settings = settings
        self.service = service or build_gmail_service(settings)

    def _list_page(self, query: str, page_token: str | None) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            self.service.users().messages().list(
                userId="me", q=query, pageToken=page_token, includeSpamTrash=False
            ).execute(),
        )

    def _get_message(self, message_id: str) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            self.service.users().messages().get(userId="me", id=message_id, format="full").execute(),
        )

    async def list_messages(self, query: str) -> AsyncIterator[GmailMessage]:
        page_token: str | None = None
        while True:
            response = await asyncio.to_thread(self._list_page, query, page_token)
            for summary in response.get("messages", []):
                try:
                    payload = await asyncio.to_thread(self._get_message, str(summary["id"]))
                    attachments = tuple(
                        GmailAttachment(
                            attachment_id=str(part.get("body", {}).get("attachmentId", part.get("partId", ""))),
                            filename=str(part.get("filename", "attachment.pdf")),
                            mime_type=str(part.get("mimeType", "application/pdf")),
                            size_bytes=part.get("body", {}).get("size"),
                        )
                        for part in _parts(payload.get("payload", {}))
                        if str(part.get("filename", "")).lower().endswith(".pdf")
                    )
                    yield GmailMessage(
                        provider_message_id=str(payload["id"]),
                        thread_id=payload.get("threadId"),
                        sender=_header(payload.get("payload", {}), "From") or "",
                        subject=_header(payload.get("payload", {}), "Subject"),
                        received_at_utc=_received_at(payload.get("payload", {})),
                        attachments=attachments,
                    )
                except (KeyError, TypeError, ValueError):
                    provider_message_id = str(summary.get("id", ""))
                    if provider_message_id:
                        yield GmailMessage(
                            provider_message_id=provider_message_id,
                            thread_id=None,
                            sender="",
                            subject=None,
                            received_at_utc=None,
                            attachments=(),
                        )
            page_token = response.get("nextPageToken")
            if not page_token:
                break

    async def download_attachment(self, message_id: str, attachment: GmailAttachment) -> bytes:
        try:
            response = await asyncio.to_thread(
                lambda: self.service.users().messages().attachments().get(
                    userId="me", messageId=message_id, id=attachment.attachment_id
                ).execute()
            )
            data = response.get("data")
            if not data:
                raise GmailError("GMAIL_ATTACHMENT_EMPTY")
            return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
        except GmailError:
            raise
        except Exception as exc:
            raise GmailError("GMAIL_ATTACHMENT_DOWNLOAD_FAILED", reason=type(exc).__name__) from exc


def authorize_gmail(settings: Settings) -> str:
    service = build_gmail_service(settings)
    try:
        profile = service.users().getProfile(userId="me").execute()
        return str(profile.get("emailAddress", settings.gmail_account))
    except Exception as exc:
        raise GmailError("GMAIL_PROFILE_FAILED", reason=type(exc).__name__) from exc
