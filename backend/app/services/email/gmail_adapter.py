import base64
import datetime as dt
import email.utils
import html
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import httpx
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import settings


@dataclass
class OAuthTokenBundle:
    access_token: str
    refresh_token: str | None
    expires_at: dt.datetime | None
    scopes: list[str]
    email_address: str | None = None


@dataclass
class FetchedEmailAttachment:
    attachment_id: str
    filename: str
    content_type: str
    size: int
    data: bytes | None = None


@dataclass
class FetchedEmailMessage:
    provider_message_id: str
    thread_id: str | None
    sender: str | None
    subject: str | None
    received_at: dt.datetime | None
    snippet_text: str | None
    body_text: str | None
    history_id: str | None
    attachments: list[FetchedEmailAttachment] = field(default_factory=list)


@dataclass
class EmailSyncFetchResult:
    message_ids: list[str]
    latest_history_id: str | None
    used_incremental_history: bool


class EmailProviderAdapter(ABC):
    provider_name: str = "abstract"

    @abstractmethod
    def is_configured(self) -> bool: ...

    @abstractmethod
    def build_authorization_url(self, *, state: str, redirect_uri: str) -> str: ...

    @abstractmethod
    def exchange_code(self, *, code: str, redirect_uri: str) -> OAuthTokenBundle: ...

    @abstractmethod
    def refresh_tokens(self, *, access_token: str | None, refresh_token: str) -> OAuthTokenBundle: ...

    @abstractmethod
    def revoke_token(self, token: str) -> bool: ...

    @abstractmethod
    def list_relevant_messages(
        self,
        *,
        access_token: str,
        refresh_token: str | None,
        query: str,
        max_results: int,
        last_history_id: str | None = None,
    ) -> EmailSyncFetchResult: ...

    @abstractmethod
    def fetch_message(
        self, *, access_token: str, refresh_token: str | None, message_id: str
    ) -> FetchedEmailMessage: ...

    @abstractmethod
    def fetch_attachment(
        self,
        *,
        access_token: str,
        refresh_token: str | None,
        message_id: str,
        attachment_id: str,
    ) -> bytes: ...


def strip_html_to_plain_text(raw_html: str) -> str:
    """Safely converts untrusted email HTML into plain text without script/HTML execution."""
    cleaned = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw_html)
    cleaned = re.sub(r"(?is)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = html.unescape(cleaned)
    lines = [" ".join(ln.split()) for ln in cleaned.splitlines()]
    return "\n".join(ln for ln in lines if ln).strip()


def _decode_b64url(data_str: str | None) -> bytes:
    if not data_str:
        return b""
    padded = data_str + "=" * ((4 - len(data_str) % 4) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


class GmailApiAdapter(EmailProviderAdapter):
    """Official Google Gmail API v1 read-only adapter using OAuth 2.0 credentials."""

    provider_name = "gmail"

    def is_configured(self) -> bool:
        return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)

    def _client_config(self, redirect_uri: str) -> dict[str, Any]:
        return {
            "web": {
                "client_id": settings.GOOGLE_OAUTH_CLIENT_ID or "",
                "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET or "",
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        }

    def build_authorization_url(self, *, state: str, redirect_uri: str) -> str:
        flow = Flow.from_client_config(
            self._client_config(redirect_uri),
            scopes=list(settings.GMAIL_SCOPES),
            redirect_uri=redirect_uri,
        )
        auth_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state,
        )
        return auth_url

    def exchange_code(self, *, code: str, redirect_uri: str) -> OAuthTokenBundle:
        flow = Flow.from_client_config(
            self._client_config(redirect_uri),
            scopes=list(settings.GMAIL_SCOPES),
            redirect_uri=redirect_uri,
        )
        flow.fetch_token(code=code)
        creds = flow.credentials
        email_addr = self._fetch_profile_email(creds)
        exp = (
            creds.expiry.replace(tzinfo=dt.UTC)
            if creds.expiry and creds.expiry.tzinfo is None
            else creds.expiry
        )
        return OAuthTokenBundle(
            access_token=creds.token,
            refresh_token=creds.refresh_token,
            expires_at=exp,
            scopes=list(creds.scopes or settings.GMAIL_SCOPES),
            email_address=email_addr,
        )

    def _credentials(self, access_token: str | None, refresh_token: str | None) -> Credentials:
        return Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_OAUTH_CLIENT_ID,
            client_secret=settings.GOOGLE_OAUTH_CLIENT_SECRET,
            scopes=list(settings.GMAIL_SCOPES),
        )

    def _fetch_profile_email(self, creds: Credentials) -> str | None:
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        profile = service.users().getProfile(userId="me").execute()
        return profile.get("emailAddress")

    def refresh_tokens(self, *, access_token: str | None, refresh_token: str) -> OAuthTokenBundle:
        creds = self._credentials(access_token, refresh_token)
        creds.refresh(GoogleAuthRequest())
        exp = (
            creds.expiry.replace(tzinfo=dt.UTC)
            if creds.expiry and creds.expiry.tzinfo is None
            else creds.expiry
        )
        return OAuthTokenBundle(
            access_token=creds.token,
            refresh_token=creds.refresh_token or refresh_token,
            expires_at=exp,
            scopes=list(creds.scopes or settings.GMAIL_SCOPES),
        )

    def revoke_token(self, token: str) -> bool:
        try:
            resp = httpx.post(
                "https://oauth2.googleapis.com/revoke",
                params={"token": token},
                headers={"content-type": "application/x-www-form-urlencoded"},
                timeout=8.0,
            )
            return resp.status_code in {200, 400}
        except Exception:
            return False

    def list_relevant_messages(
        self,
        *,
        access_token: str,
        refresh_token: str | None,
        query: str,
        max_results: int,
        last_history_id: str | None = None,
    ) -> EmailSyncFetchResult:
        service = build(
            "gmail",
            "v1",
            credentials=self._credentials(access_token, refresh_token),
            cache_discovery=False,
        )
        if last_history_id:
            try:
                hist_res = (
                    service.users()
                    .history()
                    .list(
                        userId="me",
                        startHistoryId=last_history_id,
                        historyTypes=["messageAdded"],
                        maxResults=max_results,
                    )
                    .execute()
                )
                msg_ids: list[str] = []
                for h_item in hist_res.get("history", []):
                    for added in h_item.get("messagesAdded", []):
                        mid = added.get("message", {}).get("id")
                        if mid and mid not in msg_ids:
                            msg_ids.append(mid)
                return EmailSyncFetchResult(
                    message_ids=msg_ids[:max_results],
                    latest_history_id=str(hist_res.get("historyId") or last_history_id),
                    used_incremental_history=True,
                )
            except HttpError as exc:
                # 404 from Gmail history.list means historyId expired -> fall back cleanly to query sync
                if getattr(exc.resp, "status", None) != 404:
                    raise

        profile = service.users().getProfile(userId="me").execute()
        listed = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        ids = [m["id"] for m in listed.get("messages", []) if m.get("id")]
        return EmailSyncFetchResult(
            message_ids=ids,
            latest_history_id=str(profile.get("historyId")) if profile.get("historyId") else None,
            used_incremental_history=False,
        )

    def fetch_message(
        self, *, access_token: str, refresh_token: str | None, message_id: str
    ) -> FetchedEmailMessage:
        service = build(
            "gmail",
            "v1",
            credentials=self._credentials(access_token, refresh_token),
            cache_discovery=False,
        )
        raw_msg = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        payload = raw_msg.get("payload", {})
        headers = {
            h["name"].lower(): h["value"] for h in payload.get("headers", []) if h.get("name")
        }

        received_dt: dt.datetime | None = None
        if headers.get("date"):
            try:
                parsed_dt = email.utils.parsedate_to_datetime(headers["date"])
                if parsed_dt.tzinfo is None:
                    parsed_dt = parsed_dt.replace(tzinfo=dt.UTC)
                received_dt = parsed_dt
            except Exception:
                received_dt = None

        plain_parts: list[str] = []
        html_parts: list[str] = []
        attachments: list[FetchedEmailAttachment] = []

        def _walk_parts(part: dict[str, Any]) -> None:
            mime = (part.get("mimeType") or "").lower()
            fname = part.get("filename") or ""
            body = part.get("body") or {}
            att_id = body.get("attachmentId")
            if fname and att_id:
                attachments.append(
                    FetchedEmailAttachment(
                        attachment_id=att_id,
                        filename=fname,
                        content_type=mime or "application/octet-stream",
                        size=int(body.get("size") or 0),
                    )
                )
            elif mime == "text/plain" and body.get("data"):
                plain_parts.append(_decode_b64url(body["data"]).decode("utf-8", errors="replace"))
            elif mime == "text/html" and body.get("data"):
                html_parts.append(_decode_b64url(body["data"]).decode("utf-8", errors="replace"))

            for sub in part.get("parts") or []:
                _walk_parts(sub)

        _walk_parts(payload)
        body_text = "\n".join(plain_parts).strip()
        if not body_text and html_parts:
            body_text = strip_html_to_plain_text("\n".join(html_parts))

        return FetchedEmailMessage(
            provider_message_id=raw_msg["id"],
            thread_id=raw_msg.get("threadId"),
            sender=headers.get("from"),
            subject=headers.get("subject"),
            received_at=received_dt,
            snippet_text=html.unescape(raw_msg.get("snippet") or "")[:1000] or None,
            body_text=body_text[:15000] if body_text else None,
            history_id=str(raw_msg.get("historyId")) if raw_msg.get("historyId") else None,
            attachments=attachments,
        )

    def fetch_attachment(
        self,
        *,
        access_token: str,
        refresh_token: str | None,
        message_id: str,
        attachment_id: str,
    ) -> bytes:
        service = build(
            "gmail",
            "v1",
            credentials=self._credentials(access_token, refresh_token),
            cache_discovery=False,
        )
        res = (
            service.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=message_id, id=attachment_id)
            .execute()
        )
        return _decode_b64url(res.get("data"))
