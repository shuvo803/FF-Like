import re
from datetime import datetime, timezone

from database import db, get_setting

_UID_RE = re.compile(r"^[0-9]{5,15}$")


def valid_uid(uid: str) -> bool:
    return _UID_RE.match(uid) is not None


def text_clean(s: str, max_len: int = 4000) -> str:
    return (s or "").strip()[:max_len]


def session_set(tg: int, key: str, value) -> None:
    db().sessions.update_one(
        {"telegram_id": tg},
        {"$set": {"telegram_id": tg, key: value, "updated_at": datetime.now(timezone.utc)}},
        upsert=True,
    )


def session_get(tg: int, key: str, default=None):
    x = db().sessions.find_one({"telegram_id": tg})
    if not x:
        return default
    return x.get(key, default)


def session_clear(tg: int) -> None:
    db().sessions.delete_one({"telegram_id": tg})


def is_blocked(tg: int) -> bool:
    u = db().users.find_one({"telegram_id": tg})
    return bool(u.get("blocked", False)) if u else False


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def user_cooldown(tg: int) -> int:
    u = db().users.find_one({"telegram_id": tg})
    if not u or not u.get("last_request"):
        return 0
    age = int((datetime.now(timezone.utc) - _aware(u["last_request"])).total_seconds())
    return max(0, int(get_setting("cooldown_seconds", 60)) - age)


def uid_cooldown(uid: str) -> int:
    r = db().requests.find_one(
        {"uid": uid, "status": {"$in": ["processing", "success"]}},
        sort=[("created_at", -1)],
    )
    if not r:
        return 0
    age = int((datetime.now(timezone.utc) - _aware(r["created_at"])).total_seconds())
    return max(0, int(get_setting("cooldown_seconds", 60)) - age)
