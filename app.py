import logging

from flask import Flask, jsonify, request

from database import init_db
from functions import callback, handle_message
from includes.telegram import set_webhook_if_possible, webhook_secret

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("freefire-bot")

app = Flask(__name__)


@app.get("/")
def index():
    try:
        init_db()
        set_webhook_if_possible()
    except Exception as e:  # noqa: BLE001
        logger.error(e)
    return "Free Fire Auto Like Bot is running.", 200


@app.get("/health")
def health():
    try:
        init_db()
        set_webhook_if_possible()
        return jsonify(ok=True, database="connected", webhook="configured")
    except Exception as e:  # noqa: BLE001
        logger.error(e)
        return jsonify(ok=False, error="service_unavailable"), 503


@app.post("/webhook")
def webhook():
    expected = webhook_secret()
    got = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not got or not _secure_compare(expected, got):
        return "Forbidden", 403

    update = request.get_json(silent=True)
    if not isinstance(update, dict):
        return "Bad Request", 400

    try:
        init_db()
        if "message" in update:
            handle_message(update["message"])
        elif "callback_query" in update:
            callback(update["callback_query"])
    except Exception as e:  # noqa: BLE001
        logger.error("bot: %s", e)

    return "OK", 200


def _secure_compare(a: str, b: str) -> bool:
    import hmac

    return hmac.compare_digest(a, b)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
