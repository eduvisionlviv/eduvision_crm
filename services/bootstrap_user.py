"""Bootstrap an emergency login user with a legacy plaintext password.

This helper inserts (or backfills) a user with a plaintext password so the
first successful login can transparently upgrade it to bcrypt via the existing
"smooth transition" logic in ``api/login/join.py``. Configuration is driven by
environment variables and the function is safe to call on every startup.
"""

import logging
import os
from typing import Optional

from api.coreapiserver import clear_cache, get_client_for_table
from api.login.join import _is_bcrypt_hash

log = logging.getLogger("bootstrap_user")

DEFAULT_EMAIL = os.getenv("BOOTSTRAP_LOGIN_EMAIL", "gammmerx@gmail.com")
DEFAULT_PASSWORD = os.getenv("BOOTSTRAP_LOGIN_PASSWORD", "gfhfif32")
DEFAULT_NAME = os.getenv("BOOTSTRAP_LOGIN_NAME", "Gammmerx")
DEFAULT_PHONE = os.getenv("BOOTSTRAP_LOGIN_PHONE", "+380000000000")
DEFAULT_TABLE = os.getenv("BOOTSTRAP_LOGIN_TABLE", "contacts")
BOOTSTRAP_ENABLED = os.getenv("BOOTSTRAP_LOGIN_ENABLED", "1") != "0"


def _log_skip(reason: str, details: Optional[str] = None) -> None:
    if details:
        log.info("Bootstrap user skipped: %s (%s)", reason, details)
    else:
        log.info("Bootstrap user skipped: %s", reason)


def ensure_bootstrap_user(
    email: str = DEFAULT_EMAIL,
    password: str = DEFAULT_PASSWORD,
    name: str = DEFAULT_NAME,
    phone: str = DEFAULT_PHONE,
    table: str = DEFAULT_TABLE,
) -> None:
    """Ensure a plaintext bootstrap user exists for smooth password migration."""

    if not email or not password:
        _log_skip("email/password not provided")
        return

    try:
        client = get_client_for_table(table)
    except Exception as exc:  # pragma: no cover - external service
        _log_skip("no database connection", str(exc))
        return

    try:
        existing = (
            client.table(table)
            .select("user_id,pass_email")
            .eq("user_email", email)
            .limit(1)
            .execute()
            .data
            or []
        )
    except Exception as exc:  # pragma: no cover - external service
        _log_skip("failed to read existing user", str(exc))
        return

    if existing:
        row = existing[0]
        stored = (row.get("pass_email") or "").strip()
        user_id = row.get("user_id")

        if _is_bcrypt_hash(stored):
            _log_skip("already hashed", f"user_id={user_id}")
            return

        if stored:
            _log_skip("legacy password kept for smooth migration", f"user_id={user_id}")
            return

        try:
            client.table(table).update({"pass_email": password}).eq("user_id", user_id).execute()
            clear_cache(table)
            log.info(
                "Bootstrap user password backfilled in plaintext for smooth migration (user_id=%s)",
                user_id,
            )
        except Exception as exc:  # pragma: no cover - external service
            log.warning("Bootstrap user update failed: %s", exc)
        return

    payload = {
        "user_email": email,
        "user_name": name,
        "user_phone": phone,
        "user_access": "def",
        "extra_access": None,
        "pass_email": password,
    }

    try:
        client.table(table).insert(payload).execute()
        clear_cache(table)
        log.info(
            "Bootstrap user created with plaintext password for first-login hashing: %s",
            email,
        )
    except Exception as exc:  # pragma: no cover - external service
        log.warning("Bootstrap user insert failed: %s", exc)

