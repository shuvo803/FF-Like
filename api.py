"""
HL Gaming Official adapter.

Likes API:
POST https://proapis.hlgamingofficial.com/main/games/freefire/likes/api
{
  "useruid": "...",
  "api": "...",
  "region": "BD",
  "ff_uid": 123456789
}

Account API:
POST https://proapis.hlgamingofficial.com/main/games/freefire/account/api
{
  "sectionName": "AllData",
  "PlayerUid": "123456789",
  "region": "bd",
  "useruid": "...",
  "api": "..."
}

Credentials are sent server-to-server and never exposed to Telegram users.
"""

import requests

from config import envv


def hl_post(url: str, payload: dict) -> dict:
    if not url:
        return {"ok": False, "error": "API URL is not configured", "raw": ""}
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=(8, 20),
            allow_redirects=False,
        )
    except requests.RequestException as e:
        return {"ok": False, "http": 0, "error": str(e) or "API network/timeout error", "raw": ""}

    raw = resp.text[:8000]
    try:
        j = resp.json()
        if not isinstance(j, dict):
            j = {}
    except ValueError:
        j = {}

    ok = 200 <= resp.status_code < 300
    return {
        "ok": ok,
        "http": resp.status_code,
        "json": j,
        "raw": raw,
        "error": "" if ok else f"HTTP {resp.status_code}",
    }


def hl_error(r: dict) -> str:
    j = r.get("json") or {}
    if isinstance(j.get("error"), (str, int, float)):
        return str(j["error"])
    if isinstance(j.get("message"), (str, int, float)):
        return str(j["message"])
    result = j.get("result") or {}
    if isinstance(result.get("message"), (str, int, float)):
        return str(result["message"])
    return str(r.get("error") or "API request failed")


def name_check(uid: str) -> dict:
    # HL Gaming endpoint and Bangladesh region are automatic.
    url = "https://proapis.hlgamingofficial.com/main/games/freefire/account/api"
    user_uid = envv("HL_GAMING_USERUID")
    key = envv("NAME_CHECK_API_KEY")
    region = "bd"

    if not user_uid or not key:
        return {"ok": False, "error": "Name Check API credentials are not configured", "raw": ""}

    payload = {
        "sectionName": "AllData",
        "PlayerUid": uid,
        "region": region,
        "useruid": user_uid,
        "api": key,
    }
    r = hl_post(url, payload)
    if not r["ok"]:
        return {"ok": False, "error": hl_error(r), "raw": r["raw"]}

    j = r["json"]
    name = ((j.get("result") or {}).get("AccountInfo") or {}).get("AccountName")
    if name is None:
        name = (j.get("AccountInfo") or {}).get("AccountName")
    if name is None or str(name).strip() == "":
        err = hl_error(r)
        msg = "Player name not found in HL Gaming response" if err == "API request failed" else err
        return {"ok": False, "error": msg, "raw": r["raw"]}
    return {"ok": True, "name": str(name), "raw": r["raw"]}


def send_likes(uid: str, amount: int) -> dict:
    # HL Gaming endpoint and Bangladesh region are automatic.
    url = "https://proapis.hlgamingofficial.com/main/games/freefire/likes/api"
    user_uid = envv("HL_GAMING_USERUID")
    key = envv("LIKE_API_KEY")
    region = "BD"

    if not user_uid or not key:
        return {"ok": False, "error": "Like API credentials are not configured", "raw": ""}

    # HL Gaming Likes API accepts ff_uid as the target Free Fire UID.
    # NOTE: HL Gaming documents a per-UID like limit; "amount" is kept in the
    # bot's UI/log only and is not sent as an undocumented parameter.
    payload = {"useruid": user_uid, "api": key, "region": region, "ff_uid": int(uid)}

    r = hl_post(url, payload)
    j = r.get("json") or {}

    if not r["ok"]:
        return {"ok": False, "error": hl_error(r), "raw": r["raw"]}

    # Treat explicit API error/rejection as failure even if provider returns HTTP 200.
    if "error" in j:
        return {"ok": False, "error": hl_error(r), "raw": r["raw"]}

    result = j.get("result") or {}
    status = result.get("status", j.get("status"))
    message = result.get("message", j.get("message", ""))

    if isinstance(status, str) and status.lower() in {"failed", "failure", "error", "rejected", "denied"}:
        return {"ok": False, "error": str(message) or "Like request rejected", "raw": r["raw"]}

    # HL Gaming's success response is accepted when there is no explicit error
    # and the HTTP response is successful.
    return {"ok": True, "raw": r["raw"]}
