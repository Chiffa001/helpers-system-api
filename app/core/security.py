import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, unquote

import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import Settings


class InvalidTelegramInitDataError(ValueError):
    """Raised when Telegram initData cannot be trusted."""


class InvalidAccessTokenError(ValueError):
    """Raised when JWT cannot be decoded."""


def _decode_encryption_key(key: str) -> bytes:
    if not key:
        raise ValueError("BOT_TOKEN_ENCRYPTION_KEY is not configured")

    raw_key = key.encode()
    if len(raw_key) == 32:
        return raw_key

    padding = "=" * (-len(key) % 4)
    try:
        decoded = base64.urlsafe_b64decode(key + padding)
    except binascii.Error as exc:
        raise ValueError(
            "BOT_TOKEN_ENCRYPTION_KEY must be 32 raw bytes or base64url-encoded"
        ) from exc

    if len(decoded) != 32:
        raise ValueError("BOT_TOKEN_ENCRYPTION_KEY must resolve to 32 bytes")

    return decoded


def encrypt_bot_token(token: str, key: str) -> str:
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(_decode_encryption_key(key)).encrypt(nonce, token.encode(), None)
    payload = nonce + ciphertext
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decrypt_bot_token(ciphertext: str, key: str) -> str:
    padding = "=" * (-len(ciphertext) % 4)
    try:
        payload = base64.urlsafe_b64decode(ciphertext + padding)
    except binascii.Error as exc:
        raise ValueError("Invalid encrypted bot token payload") from exc

    if len(payload) < 13:
        raise ValueError("Invalid encrypted bot token payload")

    nonce = payload[:12]
    encrypted = payload[12:]
    plaintext = AESGCM(_decode_encryption_key(key)).decrypt(nonce, encrypted, None)
    return plaintext.decode()


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
