import html
import os
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Dhaka")
except Exception:  # pragma: no cover
    TZ = None


def _load_env_file(path: Path) -> None:
    """Minimal .env loader (mirrors the original PHP loadEnvFile)."""
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
            v = v[1:-1]
        os.environ.setdefault(k, v)


_load_env_file(Path(__file__).resolve().parent / ".env")


def envv(key: str, default: str = "") -> str:
    v = os.environ.get(key)
    return default if v is None else v


def admin_ids() -> list:
    raw = envv("ADMIN_IDS")
    return [x.strip() for x in raw.split(",") if x.strip().isdigit()]


def is_admin(uid) -> bool:
    return str(uid) in admin_ids()


def app_url() -> str:
    u = envv("RENDER_EXTERNAL_URL")
    if u:
        return u.rstrip("/")
    return envv("APP_URL").rstrip("/")


def log_channel() -> str:
    return envv("LOG_CHANNEL_ID")


def h(s: str) -> str:
    """HTML-escape, matching PHP's htmlspecialchars(ENT_QUOTES)."""
    return html.escape(s or "", quote=True)
