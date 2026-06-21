from datetime import UTC, datetime, timedelta
from hashlib import sha256
import hmac
from urllib.parse import urlencode

from paperfirst.services.telegram_auth import validate_telegram_init_data


def signed_init_data(bot_token: str, payload: dict[str, str]) -> str:
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(payload.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), sha256).digest()
    payload["hash"] = hmac.new(secret_key, data_check_string.encode(), sha256).hexdigest()
    return urlencode(payload)


def test_telegram_init_data_rejects_future_auth_date():
    bot_token = "token"
    payload = {
        "auth_date": str(int((datetime.now(UTC) + timedelta(hours=1)).timestamp())),
        "user": '{"id":1}',
    }

    assert not validate_telegram_init_data(signed_init_data(bot_token, payload), bot_token)
