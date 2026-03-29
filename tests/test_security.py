import hashlib
import hmac
import time

from app.core.security import validate_telegram_init_data


def sign_payload(token: str, payload: dict[str, str]) -> str:
    data_check = payload.copy()
    data_check.pop("hash", None)
    sorted_items = sorted(data_check.items())
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_items)

    secret_key = hmac.new(
        key=b"WebAppData",
        msg=token.encode(),
        digestmod=hashlib.sha256,
    ).digest()
    return hmac.new(
        key=secret_key,
        msg=data_check_string.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()


def test_validate_telegram_init_data_accepts_signature_field() -> None:
    bot_token = "token"
    payload = {
        "auth_date": str(int(time.time())),
        "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
        "signature": "telegram-signature",
        "user": '{"id":1,"first_name":"Test","username":"tester"}',
        "hash": "",
    }
    payload["hash"] = sign_payload(bot_token, payload)

    init_data = "&".join(f"{key}={value}" for key, value in payload.items())

    parsed = validate_telegram_init_data(init_data, bot_token)

    assert parsed["signature"] == "telegram-signature"
    assert parsed["user"] == payload["user"]
