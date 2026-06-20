from datetime import UTC, datetime
from hashlib import sha256
import hmac
from urllib.parse import parse_qsl


def validate_telegram_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86_400) -> bool:
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return False

    auth_date = parsed.get("auth_date")
    if auth_date is None:
        return False
    try:
        auth_timestamp = int(auth_date)
    except ValueError:
        return False

    now_timestamp = int(datetime.now(UTC).timestamp())
    age_seconds = now_timestamp - auth_timestamp
    if age_seconds < 0 or age_seconds > max_age_seconds:
        return False

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), sha256).hexdigest()
    return hmac.compare_digest(calculated_hash, received_hash)
