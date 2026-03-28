import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl

import jwt

from app.core.config import Settings


class InvalidTelegramInitDataError(ValueError):
    """Raised when Telegram initData cannot be trusted."""


class InvalidAccessTokenError(ValueError):
    """Raised when JWT cannot be decoded."""


def parse_telegram_init_data(init_data: str) -> dict[str, str]:
    return {key: value for key, value in parse_qsl(init_data, keep_blank_values=True)}


def validate_telegram_init_data(init_data: str, bot_token: str) -> dict[str, str]:
    if not bot_token:
        raise InvalidTelegramInitDataError("TELEGRAM_BOT_TOKEN is not configured")

    parsed = parse_telegram_init_data(init_data)
    received_hash = parsed.get("hash")
    auth_date = parsed.get("auth_date")

    if not received_hash or not auth_date:
        raise InvalidTelegramInitDataError("Missing auth_date or hash")

    data_check = "\n".join(
        f"{key}={value}"
        for key, value in sorted((key, value) for key, value in parsed.items() if key != "hash")
    )

    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode(),
        digestmod=hashlib.sha256,
    ).digest()
    computed_hash = hmac.new(
        key=secret_key,
        msg=data_check.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise InvalidTelegramInitDataError("Invalid hash")

    if int(time.time()) - int(auth_date) > 24 * 60 * 60:
        raise InvalidTelegramInitDataError("initData expired")

    return parsed


def extract_telegram_user(init_data: dict[str, str]) -> dict[str, Any]:
    raw_user = init_data.get("user")
    if not raw_user:
        raise InvalidTelegramInitDataError("Missing Telegram user payload")

    try:
        user_payload: dict[str, Any] = json.loads(raw_user)
    except json.JSONDecodeError as exc:
        raise InvalidTelegramInitDataError("Invalid Telegram user payload") from exc

    if "id" not in user_payload:
        raise InvalidTelegramInitDataError("Telegram user id is required")

    return user_payload


def create_access_token(
    *,
    user_id: str,
    is_super_admin: bool,
    settings: Settings,
) -> str:
    expires_at = datetime.now(UTC) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": user_id,
        "is_super_admin": is_super_admin,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise InvalidAccessTokenError("Invalid access token") from exc

    if "sub" not in payload:
        raise InvalidAccessTokenError("Token subject is missing")

    return payload
