import hashlib
import json

import requests

from config import app_url, envv, log_channel

# A shared session reuses TCP/TLS connections across requests instead of
# renegotiating a new HTTPS connection on every Telegram API call — this
# alone typically saves 100-300ms per call once the pool is warm.
_session = requests.Session()

_webhook_registered = False


def tg(method: str, data: dict | None = None) -> dict:
    data = data or {}
    token = envv("BOT_TOKEN")
    if not token:
        return {"ok": False, "description": "BOT_TOKEN missing"}
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        resp = _session.post(url, data=data, timeout=(5, 15))
    except requests.RequestException as e:
        return {"ok": False, "description": str(e) or "Telegram request failed"}
    try:
        j = resp.json()
    except ValueError:
        return {"ok": False, "description": "Invalid Telegram response"}
    return j if isinstance(j, dict) else {"ok": False, "description": "Invalid Telegram response"}


def send_text(chat, text: str, kb: list | None = None) -> dict:
    d = {"chat_id": chat, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if kb is not None:
        d["reply_markup"] = json.dumps({"inline_keyboard": kb}, ensure_ascii=False)
    return tg("sendMessage", d)


def edit_text(chat, mid: int, text: str, kb: list | None = None) -> dict:
    d = {"chat_id": chat, "message_id": mid, "text": text, "parse_mode": "HTML"}
    if kb is not None:
        d["reply_markup"] = json.dumps({"inline_keyboard": kb}, ensure_ascii=False)
    return tg("editMessageText", d)


def delete_message(chat, mid: int) -> dict:
    return tg("deleteMessage", {"chat_id": chat, "message_id": mid})


def answer_cb(cb_id: str, text: str = "", alert: bool = False) -> None:
    tg("answerCallbackQuery", {"callback_query_id": cb_id, "text": text, "show_alert": alert})


def send_log(text: str) -> None:
    ch = log_channel()
    if not ch:
        return
    send_text(ch, text)


def webhook_secret() -> str:
    return hashlib.sha256(f"{envv('BOT_TOKEN')}|webhook-secret".encode("utf-8")).hexdigest()


def set_webhook_if_possible() -> None:
    global _webhook_registered
    if _webhook_registered:
        return
    url = app_url()
    if not url:
        return
    r = tg(
        "setWebhook",
        {
            "url": f"{url}/webhook",
            "secret_token": webhook_secret(),
            "allowed_updates": json.dumps(["message", "callback_query"]),
        },
    )
    if r.get("ok"):
        _webhook_registered = True
