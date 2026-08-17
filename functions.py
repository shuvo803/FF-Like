from datetime import datetime, timezone

from api import name_check, send_likes
from config import envv, h, is_admin
from database import db, get_setting, set_setting
from includes.security import (
    is_blocked,
    session_clear,
    session_get,
    session_set,
    text_clean,
    uid_cooldown,
    user_cooldown,
    valid_uid,
)
from includes.telegram import answer_cb, edit_text, send_log, send_text, tg


def menu() -> list:
    return [
        [{"text": "❤️ Free Fire Like", "callback_data": "like"}],
        [{"text": "📊 My Statistics", "callback_data": "stats"}, {"text": "ℹ️ Help", "callback_data": "help"}],
        [{"text": "📞 Contact Admin", "callback_data": "contact"}],
    ]


def back() -> list:
    return [[{"text": "🔙 Back to Main Menu", "callback_data": "home"}]]


def packages() -> list:
    return [100, 500, 1000, 2500]


def upsert_user(u: dict) -> None:
    tg_id = int(u.get("id") or 0)
    if tg_id <= 0:
        return
    now = datetime.now(timezone.utc)
    result = db().users.update_one(
        {"telegram_id": tg_id},
        {
            "$set": {
                "telegram_id": tg_id,
                "username": text_clean(str(u.get("username") or ""), 100),
                "first_name": text_clean(str(u.get("first_name") or ""), 100),
                "last_name": text_clean(str(u.get("last_name") or ""), 100),
                "last_activity": now,
            },
            "$setOnInsert": {"created_at": now, "blocked": False},
        },
        upsert=True,
    )
    if result.upserted_id is not None:
        name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
        send_log(
            "🆕 <b>NEW USER STARTED BOT</b>\n\n"
            f"👤 Name: {h(name)}\n"
            f"🔹 Username: @{h(str(u.get('username') or 'N/A'))}\n"
            f"🆔 Telegram ID: <code>{tg_id}</code>\n"
            f"🌐 Language: {h(str(u.get('language_code') or 'unknown'))}\n"
            f"⏰ {datetime.now().strftime('%d %b %Y, %I:%M %p')}"
        )


def welcome() -> str:
    return (
        "🎮 <b>FREE FIRE AUTO LIKE</b>\n\n"
        "• দ্রুত Like নেওয়া যাবে\n"
        "• UID ভিত্তিক সিস্টেম\n"
        "• সহজে ব্যবহারযোগ্য\n"
        "• 24/7 Service\n\n"
        "⚡ শুধুমাত্র বৈধ/অনুমোদিত Like API ব্যবহার করা হয়।"
    )


def handle_message(m: dict) -> None:
    chat = int((m.get("chat") or {}).get("id") or 0)
    u = m.get("from") or {}
    tg_id = int(u.get("id") or 0)
    if tg_id <= 0:
        return
    upsert_user(u)

    text = str(m.get("text") or "")
    if text.strip().startswith("/start"):
        session_clear(tg_id)
        send_text(chat, welcome(), menu())
        return
    if text.strip().startswith("/admin"):
        admin_home(chat, tg_id)
        return
    if text.strip().startswith("/id"):
        session_set(tg_id, "state", "uid")
        send_text(chat, "🎮 আপনার Free Fire UID পাঠান:", back())
        return
    if is_admin(tg_id) and handle_admin_text(m):
        return
    if session_get(tg_id, "state") == "uid":
        handle_uid(chat, tg_id, text.strip())
        return
    if session_get(tg_id, "state") == "broadcast":
        admin_broadcast_receive(chat, tg_id, m)
        return
    send_text(chat, "মেনু থেকে একটি অপশন নির্বাচন করুন।", menu())


def handle_uid(chat: int, tg_id: int, uid: str) -> None:
    if not valid_uid(uid):
        send_text(chat, "❌ <b>ভুল UID</b>\nশুধু 5–15 সংখ্যার UID পাঠান।", back())
        return
    if is_blocked(tg_id):
        send_text(chat, "🚫 আপনার অ্যাকাউন্ট ব্লক করা হয়েছে।", back())
        return
    if bool(get_setting("maintenance", False)) and not is_admin(tg_id):
        send_text(chat, "🔧 বর্তমানে Like Service Maintenance Mode-এ রয়েছে।", back())
        return
    left = user_cooldown(tg_id)
    if left > 0:
        send_text(chat, f"⏳ আপনার cooldown active। আরও <b>{left}</b> সেকেন্ড পরে চেষ্টা করুন।", back())
        return

    send_text(chat, "⏳ <b>Player information checking...</b>")
    r = name_check(uid)
    if not r["ok"]:
        send_text(chat, f"❌ <b>Player Not Found</b>\n\nকারণ: {h(r['error'])}", back())
        return

    session_set(tg_id, "uid", uid)
    session_set(tg_id, "name", r["name"])
    session_set(tg_id, "state", "package")
    send_text(
        chat,
        f"👤 <b>Player:</b> {h(r['name'])}\n🆔 <b>UID:</b> <code>{h(uid)}</code>\n\n<b>আপনি কত Like নিতে চান?</b>",
        [
            [{"text": "❤️ 100 Likes", "callback_data": "pkg:100"}, {"text": "❤️ 500 Likes", "callback_data": "pkg:500"}],
            [{"text": "❤️ 1000 Likes", "callback_data": "pkg:1000"}, {"text": "❤️ 2500 Likes", "callback_data": "pkg:2500"}],
            [{"text": "🔙 Back to Main Menu", "callback_data": "home"}],
        ],
    )


def process_like(chat: int, tg_id: int, mid: int, amount: int) -> None:
    if amount not in packages():
        return
    if is_blocked(tg_id):
        edit_text(chat, mid, "🚫 আপনার অ্যাকাউন্ট ব্লক করা হয়েছে।", back())
        return
    if bool(get_setting("maintenance", False)) and not is_admin(tg_id):
        edit_text(chat, mid, "🔧 Like Service Maintenance Mode-এ রয়েছে।", back())
        return

    uid = str(session_get(tg_id, "uid", ""))
    name = str(session_get(tg_id, "name", "Unknown"))
    if not valid_uid(uid):
        edit_text(chat, mid, "❌ UID session expired. আবার চেষ্টা করুন।", back())
        return

    left = user_cooldown(tg_id)
    if left > 0:
        edit_text(chat, mid, f"⏳ আরও {left} সেকেন্ড অপেক্ষা করুন।", back())
        return
    ul = uid_cooldown(uid)
    if ul > 0:
        edit_text(chat, mid, f"⏳ এই UID-তে cooldown active। আরও {ul} সেকেন্ড অপেক্ষা করুন।", back())
        return

    now = datetime.now(timezone.utc)
    ins = db().requests.insert_one(
        {
            "telegram_id": tg_id,
            "uid": uid,
            "player_name": name,
            "like_amount": amount,
            "status": "processing",
            "api_response": "",
            "created_at": now,
        }
    )
    db().users.update_one({"telegram_id": tg_id}, {"$set": {"last_request": now}})

    edit_text(
        chat,
        mid,
        f"⏳ <b>আপনার Like Request Processing হচ্ছে...</b>\n\n👤 {h(name)}\n🆔 <code>{h(uid)}</code>\n❤️ Likes: <b>{amount:,}</b>",
    )
    send_log(
        "❤️ <b>NEW LIKE REQUEST</b>\n\n"
        f"👤 User ID: <code>{tg_id}</code>\n🎮 UID: <code>{h(uid)}</code>\n👤 Player: {h(name)}\n"
        f"❤️ Likes: {amount:,}\n⏳ Status: Processing"
    )

    r = send_likes(uid, amount)
    status = "success" if r["ok"] else "failed"
    db().requests.update_one(
        {"_id": ins.inserted_id},
        {"$set": {"status": status, "api_response": r.get("raw", ""), "completed_at": datetime.now(timezone.utc)}},
    )

    if r["ok"]:
        edit_text(
            chat,
            mid,
            f"✅ <b>LIKE SENT SUCCESSFULLY</b>\n\n👤 Player: {h(name)}\n🆔 UID: <code>{h(uid)}</code>\n"
            f"❤️ Likes: {amount:,}\n📊 Status: Success",
            back(),
        )
        send_log(
            "✅ <b>LIKE REQUEST SUCCESS</b>\n\n"
            f"👤 User ID: <code>{tg_id}</code>\n🎮 UID: <code>{h(uid)}</code>\n❤️ Likes: {amount:,}\n📊 Status: Success"
        )
    else:
        error = r.get("error") or "API Error"
        edit_text(
            chat,
            mid,
            f"❌ <b>LIKE REQUEST FAILED</b>\n\n👤 Player: {h(name)}\n🆔 UID: <code>{h(uid)}</code>\n\n❗ কারণ: {h(error)}",
            back(),
        )
        send_log(
            "❌ <b>LIKE REQUEST FAILED</b>\n\n"
            f"👤 User ID: <code>{tg_id}</code>\n🎮 UID: <code>{h(uid)}</code>\n❤️ Likes: {amount:,}\n❗ Reason: {h(error)}"
        )

    session_clear(tg_id)


def callback(c: dict) -> None:
    cb_id = c["id"]
    u = c["from"]
    tg_id = int(u["id"])
    chat = int(c["message"]["chat"]["id"])
    mid = int(c["message"]["message_id"])
    d = str(c["data"])
    upsert_user(u)

    if d == "home":
        answer_cb(cb_id)
        session_clear(tg_id)
        edit_text(chat, mid, welcome(), menu())
        return
    if d == "like":
        answer_cb(cb_id)
        session_set(tg_id, "state", "uid")
        edit_text(chat, mid, "🎮 <b>আপনার Free Fire UID পাঠান:</b>\n\nউদাহরণ: <code>58392019</code>", back())
        return
    if d == "stats":
        answer_cb(cb_id)
        t = db().requests.count_documents({"telegram_id": tg_id})
        s = db().requests.count_documents({"telegram_id": tg_id, "status": "success"})
        f = db().requests.count_documents({"telegram_id": tg_id, "status": "failed"})
        edit_text(chat, mid, f"📊 <b>My Statistics</b>\n\n❤️ Total: {t}\n✅ Success: {s}\n❌ Failed: {f}", back())
        return
    if d == "help":
        answer_cb(cb_id)
        edit_text(
            chat,
            mid,
            "ℹ️ <b>Help</b>\n\n❤️ Like নির্বাচন করুন → UID দিন → Player Name যাচাই করুন → Package নির্বাচন করুন।\n\n"
            "⚠️ শুধু বৈধ API integration ব্যবহার করুন।",
            back(),
        )
        return
    if d == "contact":
        answer_cb(cb_id)
        send_text(
            chat,
            "📞 Contact Admin\n\nAdmin-এর সাথে যোগাযোগের জন্য নিচের username ব্যবহার করুন:\n"
            f"{h(str(get_setting('contact_username', 'Not configured')))}",
            back(),
        )
        return
    if d.startswith("pkg:"):
        answer_cb(cb_id, "Processing...")
        process_like(chat, tg_id, mid, int(d[4:]))
        return
    if is_admin(tg_id):
        admin_callback(c)


def admin_home(chat: int, tg_id: int) -> None:
    if not is_admin(tg_id):
        send_text(chat, "🚫 <b>Unauthorized</b>")
        return
    send_text(chat, "🔐 <b>ADMIN CONTROL</b>\n\nসব Admin control এই Bot-এর ভিতরেই থাকবে।", admin_keyboard())


def admin_keyboard() -> list:
    return [
        [{"text": "📊 Dashboard", "callback_data": "adm:dash"}, {"text": "👥 Users", "callback_data": "adm:users"}],
        [{"text": "❤️ Requests", "callback_data": "adm:req"}, {"text": "📈 Statistics", "callback_data": "adm:stats"}],
        [{"text": "🔧 Maintenance", "callback_data": "adm:maint"}, {"text": "🚫 Block User", "callback_data": "adm:block"}],
        [{"text": "📢 Broadcast", "callback_data": "adm:broadcast"}],
    ]


def admin_callback(c: dict) -> None:
    cb_id = c["id"]
    tg_id = int(c["from"]["id"])
    chat = int(c["message"]["chat"]["id"])
    mid = int(c["message"]["message_id"])
    d = str(c["data"])
    answer_cb(cb_id)

    if d == "adm:dash":
        u = db().users.count_documents({})
        r = db().requests.count_documents({})
        s = db().requests.count_documents({"status": "success"})
        f = db().requests.count_documents({"status": "failed"})
        maint = "ON" if bool(get_setting("maintenance", False)) else "OFF"
        edit_text(
            chat,
            mid,
            f"📊 <b>Dashboard</b>\n\n👥 Users: {u}\n❤️ Requests: {r}\n✅ Success: {s}\n❌ Failed: {f}\n🔧 Maintenance: {maint}",
            admin_keyboard(),
        )
        return
    if d == "adm:stats":
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        r = db().requests.count_documents({"created_at": {"$gte": today}})
        cutoff = datetime.now(timezone.utc).timestamp() - 86400
        active = db().users.count_documents({"last_activity": {"$gte": datetime.fromtimestamp(cutoff, tz=timezone.utc)}})
        edit_text(chat, mid, f"📈 <b>Statistics</b>\n\n📅 Today's Requests: {r}\n⚡ Active 24h Users: {active}", admin_keyboard())
        return
    if d == "adm:maint":
        new = not bool(get_setting("maintenance", False))
        set_setting("maintenance", new)
        edit_text(chat, mid, f"🔧 Maintenance: <b>{'ON' if new else 'OFF'}</b>", admin_keyboard())
        return
    if d == "adm:users":
        rows = db().users.find({}, sort=[("last_activity", -1)], limit=10)
        out = "👥 <b>Recent Users</b>\n\n"
        for x in rows:
            mark = "🚫" if x.get("blocked", False) else "✅"
            out += f"• <code>{h(str(x['telegram_id']))}</code> {h(str(x.get('first_name') or ''))} {mark}\n"
        edit_text(chat, mid, out, admin_keyboard())
        return
    if d == "adm:req":
        rows = db().requests.find({}, sort=[("created_at", -1)], limit=10)
        out = "❤️ <b>Recent Requests</b>\n\n"
        for x in rows:
            out += f"• {h(x['uid'])} | {int(x['like_amount']):,} | {h(x['status'])}\n"
        edit_text(chat, mid, out, admin_keyboard())
        return
    if d == "adm:block":
        session_set(tg_id, "state", "admin_block")
        edit_text(
            chat,
            mid,
            "🚫 যে Telegram ID block/unblock করতে চান সেটি পাঠান:",
            [[{"text": "🔙 Admin Menu", "callback_data": "adm:menu"}]],
        )
        return
    if d == "adm:broadcast":
        session_set(tg_id, "state", "broadcast")
        edit_text(
            chat,
            mid,
            "📢 <b>Broadcast Mode</b>\n\nএখন Text/Image/Video/Document পাঠান।\nCancel করতে /cancel পাঠান।",
            [[{"text": "🔙 Admin Menu", "callback_data": "adm:menu"}]],
        )
        return
    if d == "adm:menu":
        edit_text(chat, mid, "🔐 <b>ADMIN CONTROL</b>", admin_keyboard())


def handle_admin_text(m: dict) -> bool:
    tg_id = int(m["from"]["id"])
    state = session_get(tg_id, "state")
    chat = int(m["chat"]["id"])

    if state == "admin_block":
        raw = str(m.get("text") or "").strip()
        try:
            target_id = int(raw)
        except ValueError:
            target_id = 0
        if target_id <= 0:
            send_text(chat, "❌ Invalid Telegram ID")
            return True
        u = db().users.find_one({"telegram_id": target_id})
        if not u:
            send_text(chat, "❌ User not found.")
            session_clear(tg_id)
            return True
        blocked = not u.get("blocked", False)
        db().users.update_one({"telegram_id": target_id}, {"$set": {"blocked": blocked}})
        session_clear(tg_id)
        send_text(chat, "🚫 User blocked." if blocked else "✅ User unblocked.", admin_keyboard())
        return True

    return False


def admin_broadcast_receive(chat: int, tg_id: int, m: dict) -> None:
    if (m.get("text") or "") == "/cancel":
        session_clear(tg_id)
        send_text(chat, "❌ Broadcast cancelled.", admin_keyboard())
        return

    users = db().users.find({"blocked": {"$ne": True}}, projection={"telegram_id": 1})
    sent = 0
    failed = 0
    for u in users:
        target_id = int(u["telegram_id"])
        if "text" in m:
            r = send_text(target_id, text_clean(m["text"]))
        elif "photo" in m:
            photo = m["photo"][-1]
            r = tg(
                "sendPhoto",
                {
                    "chat_id": target_id,
                    "photo": photo["file_id"],
                    "caption": text_clean(str(m.get("caption") or "")),
                    "parse_mode": "HTML",
                },
            )
        elif "video" in m:
            r = tg(
                "sendVideo",
                {
                    "chat_id": target_id,
                    "video": m["video"]["file_id"],
                    "caption": text_clean(str(m.get("caption") or "")),
                    "parse_mode": "HTML",
                },
            )
        elif "document" in m:
            r = tg(
                "sendDocument",
                {
                    "chat_id": target_id,
                    "document": m["document"]["file_id"],
                    "caption": text_clean(str(m.get("caption") or "")),
                    "parse_mode": "HTML",
                },
            )
        else:
            failed += 1
            continue

        if r.get("ok"):
            sent += 1
        else:
            failed += 1
        import time

        time.sleep(0.07)

    session_clear(tg_id)
    send_text(chat, f"📢 <b>Broadcast Finished</b>\n\n✅ Sent: {sent}\n❌ Failed: {failed}", admin_keyboard())
