"""Gmail API client for sending transactional emails."""

from __future__ import annotations

import base64
import logging
import os
from email.message import EmailMessage
from email.utils import formataddr
from typing import Optional, Sequence

import httpx

LOGGER = logging.getLogger(__name__)

TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/{user_id}/messages/send"
DEFAULT_TIMEOUT = httpx.Timeout(20.0, connect=10.0, read=20.0)


class GmailConfigError(RuntimeError):
    """Raised when required Gmail API environment variables are missing."""


def _first_nonempty_env(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value.strip()
    return None


def _get_sender_info() -> tuple[str, str]:
    username = _first_nonempty_env("GMAIL_USER")
    from_name = _first_nonempty_env("GMAIL_FROM_NAME") or "EduVision"

    if not username:
        raise GmailConfigError("GMAIL_USER є обов'язковим для Gmail API")

    return username, from_name


def _get_oauth_credentials() -> tuple[str, str, str]:
    client_id = _first_nonempty_env("GMAIL_CLIENT_ID", "GOOGLE_CLIENT_ID", "GOOGLE_Client_ID")
    client_secret = _first_nonempty_env(
        "GMAIL_CLIENT_SECRET",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_Client_SEC",
    )
    refresh_token = _first_nonempty_env("GMAIL_REFRESH_TOKEN", "GOOGLE_REFRESH_TOKEN", "API_GOOGLE")

    if not client_id or not client_secret or not refresh_token:
        raise GmailConfigError(
            "Потрібні GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET та GMAIL_REFRESH_TOKEN для Gmail API"
        )

    return client_id, client_secret, refresh_token


def _fetch_access_token() -> str:
    client_id, client_secret, refresh_token = _get_oauth_credentials()
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    try:
        response = httpx.post(TOKEN_URL, data=data, timeout=DEFAULT_TIMEOUT)
    except httpx.HTTPError as exc:  # pragma: no cover - network
        raise RuntimeError(f"Gmail token request failed: {exc}") from exc

    if response.status_code != 200:
        raise RuntimeError(
            f"Gmail token request failed ({response.status_code}): {response.text}"
        )

    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Gmail token response did not contain access_token")
    return token


def _normalize_recipients(targets: Sequence[str] | str) -> list[str]:
    if isinstance(targets, str):
        targets = [targets]
    return [email.strip() for email in targets if email and email.strip()]

def _build_message(
    recipients: list[str], subject: str, html_body: str, text_body: Optional[str],
) -> EmailMessage:
    username, from_name = _get_sender_info()

    # Не шлемо випадкових копій самому собі
    recipients = [r for r in recipients if r.strip().lower() != username.lower()]
    if not recipients:
        raise ValueError("Немає одержувачів після фільтрації (вказано лише адресу відправника)")

    # Перший адресат у To, решта — в Bcc (щоб не світити адреси між собою)
    to_addr = recipients[0]
    bcc_list = recipients[1:]

    message = EmailMessage()
    message["From"] = formataddr((from_name, username))
    message["To"] = to_addr
    if bcc_list:
        message["Bcc"] = ", ".join(bcc_list)
    message["Subject"] = subject

    if text_body:
        message.set_content(text_body)
    else:
        message.set_content("")
    message.add_alternative(html_body, subtype="html")
    return message

def _send_raw_message(raw_message: str) -> None:
    access_token = _fetch_access_token()
    user_id = _first_nonempty_env("GMAIL_API_USER", "GMAIL_USER") or "me"
    url = SEND_URL.format(user_id=user_id if user_id != "me" else "me")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    payload = {"raw": raw_message}

    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:  # pragma: no cover - depends on API
        error_text = exc.response.text
        raise RuntimeError(f"Gmail API responded with error: {error_text}") from exc
    except httpx.HTTPError as exc:  # pragma: no cover - network
        raise RuntimeError(f"Gmail API request failed: {exc}") from exc


def send_email(
    recipients: Sequence[str] | str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
) -> None:
    """Send email to recipients via Gmail API."""

    to_list = _normalize_recipients(recipients)
    if not to_list:
        raise ValueError("Не вказано жодного отримувача")

    message = _build_message(to_list, subject, html_body, text_body)
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    _send_raw_message(raw_message)
    LOGGER.info("Gmail API email sent to %s (subject=%s)", to_list, subject)
