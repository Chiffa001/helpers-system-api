import hashlib
import hmac
import json
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, unquote

import jwt

from app.core.config import Settings


class InvalidTelegramInitDataError(ValueError):
    """Raised when Telegram initData cannot be trusted."""


class InvalidAccessTokenError(ValueError):
    """Raised when JWT cannot be decoded."""


def parse_telegram_init_data(init_data: str) -> dict[str, str]:
    parsed = parse_qs(init_data)
    return {key: unquote(values[0]) for key, values in parsed.items() if values}


def _validate_telegram_webapp_data(init_data: dict[str, str], bot_token: str) -> None:
    for field in ("auth_date", "hash"):
        if field not in init_data:
            raise InvalidTelegramInitDataError(f"Missing required field: {field}")

    received_hash = init_data["hash"]

    data_check = {k: v for k, v in init_data.items() if k != "hash"}

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data_check.items()))

    secret_key = hmac.new(
        key=b"WebAppData",
        msg=bot_token.encode(),
        digestmod=hashlib.sha256,
    ).digest()
    computed_hash = hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise InvalidTelegramInitDataError("Hash comparison failed")

    if int(time.time()) - int(init_data["auth_date"]) > 86400:
        raise InvalidTelegramInitDataError("Auth expired")


def validate_telegram_init_data(init_data: str, bot_token: str) -> dict[str, str]:
    if not bot_token:
        raise InvalidTelegramInitDataError("TELEGRAM_BOT_TOKEN is not configured")

    parsed = parse_telegram_init_data(init_data)
    _validate_telegram_webapp_data(parsed, bot_token)
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
