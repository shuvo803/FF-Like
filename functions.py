from datetime import datetime, timezone

from api import name_check, send_likes
from config import admin_ids, envv, h, is_admin, sc
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
from includes.telegram import answer_cb, delete_message, edit_text, send_log, send_text, tg


def menu() -> list:
    return [
        [{"text": f"❤️ {sc('Free Fire Like')}", "callback_data": "like"}],
        [{"text": f"📊 {sc('My Statistics')}", "callback_data": "stats"}, {"text": f"ℹ️ {sc('Help')}", "callback_data": "help"}],
        [{"text": f"📞 {sc('Contact Admin')}", "callback_data": "contact"}],
    ]


def back() -> list:
    return [[{"text": f"🔙 {sc('Back to Main Menu')}", "callback_data": "home"}]]


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
            f"🆕 <b>{sc('NEW USER STARTED BOT')}</b>\n\n"
            f"👤 {sc('Name')}: {h(name)}\n"
            f"🔹 {sc('Username')}: @{h(str(u.get('username') or 'N/A'))}\n"
            f"🆔 {sc('Telegram ID')}: <code>{tg_id}</code>\n"
            f"🌐 {sc('Language')}: {h(str(u.get('language_code') or 'unknown'))}\n"
            f"⏰ {datetime.now().strftime('%d %b %Y, %I:%M %p')}"
        )


def welcome() -> str:
    return (
        f"🎮 <b>{sc('FREE FIRE AUTO LIKE')}</b>\n\n"
        f"⚡ দ্রুত {sc('Like')} নেওয়া যাবে\n"
        f"🆔 {sc('UID')} ভিত্তিক সিস্টেম\n"
        f"😊 সহজে ব্যবহারযোগ্য\n"
        f"🕐 24/7 {sc('Service')}\n\n"
        f"🔒 শুধুমাত্র বৈধ/অনুমোদিত {sc('Like API')} ব্যবহার করা হয়।"
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
        send_text(chat, f"🎮 আপনার {sc('Free Fire UID')} পাঠান:", back())
        return
    if is_admin(tg_id) and handle_admin_text(m):
        return
    if session_get(tg_id, "state") == "uid":
        handle_uid(chat, tg_id, text.strip())
        return
    if session_get(tg_id, "state") == "broadcast":
        admin_broadcast_receive(chat, tg_id, m)
        return
    send_text(chat, "📋 মেনু থেকে একটি অপশন নির্বাচন করুন।", menu())


def handle_uid(chat: int, tg_id: int, uid: str) -> None:
    if not valid_uid(uid):
        send_text(chat, f"❌ <b>ভুল {sc('UID')}</b>\n🔢 শুধু 5–15 সংখ্যার {sc('UID')} পাঠান।", back())
        return
    if is_blocked(tg_id):
        send_text(chat, "🚫 আপনার অ্যাকাউন্ট ব্লক করা হয়েছে।", back())
        return
    if bool(get_setting("maintenance", False)) and not is_admin(tg_id):
        send_text(chat, f"🔧 বর্তমানে {sc('Like Service Maintenance Mode')}-এ রয়েছে।", back())
        return
    left = user_cooldown(tg_id)
    if left > 0:
        send_text(chat, f"⏳ আপনার {sc('cooldown active')}। আরও <b>{left}</b> সেকেন্ড পরে চেষ্টা করুন।", back())
        return

    checking = send_text(chat, f"🔍 <b>{sc('Player information checking...')}</b>")
    r = name_check(uid)

    # Auto-remove the "checking" status message now that we have a result
    checking_result = checking.get("result") if isinstance(checking, dict) else None
    if isinstance(checking_result, dict) and checking_result.get("message_id"):
        delete_message(chat, checking_result["message_id"])

    if not r["ok"]:
        send_text(chat, f"❌ <b>{sc('Player Not Found')}</b>\n\n🗒️ কারণ: {h(r['error'])}", back())
        return

    session_set(tg_id, "uid", uid)
    session_set(tg_id, "name", r["name"])
    session_set(tg_id, "state", "package")
    send_text(
        chat,
        f"👤 <b>{sc('Player')}:</b> {h(r['name'])}\n🆔 <b>{sc('UID')}:</b> <code>{h(uid)}</code>\n\n"
        f"<b>আপনি কত {sc('Like')} নিতে চান?</b>",
        [
            [
                {"text": f"❤️ 100 {sc('Likes')}", "callback_data": "pkg:100"},
                {"text": f"❤️ 500 {sc('Likes')}", "callback_data": "pkg:500"},
            ],
            [
                {"text": f"❤️ 1000 {sc('Likes')}", "callback_data": "pkg:1000"},
                {"text": f"❤️ 2500 {sc('Likes')}", "callback_data": "pkg:2500"},
            ],
            [{"text": f"🔙 {sc('Back to Main Menu')}", "callback_data": "home"}],
        ],
    )


def process_like(chat: int, tg_id: int, mid: int, amount: int) -> None:
    if amount not in packages():
        return
    if is_blocked(tg_id):
        edit_text(chat, mid, "🚫 আপনার অ্যাকাউন্ট ব্লক করা হয়েছে।", back())
        return
    if bool(get_setting("maintenance", False)) and not is_admin(tg_id):
        edit_text(chat, mid, f"🔧 {sc('Like Service Maintenance Mode')}-এ রয়েছে।", back())
        return

    uid = str(session_get(tg_id, "uid", ""))
    name = str(session_get(tg_id, "name", "Unknown"))
    if not valid_uid(uid):
        edit_text(chat, mid, f"❌ {sc('UID session expired')}. আবার চেষ্টা করুন।", back())
        return

    left = user_cooldown(tg_id)
    if left > 0:
        edit_text(chat, mid, f"⏳ আরও {left} সেকেন্ড অপেক্ষা করুন।", back())
        return
    ul = uid_cooldown(uid)
    if ul > 0:
        edit_text(chat, mid, f"⏳ এই {sc('UID')}-তে {sc('cooldown active')}। আরও {ul} সেকেন্ড অপেক্ষা করুন।", back())
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
        f"⏳ <b>আপনার {sc('Like Request Processing')} হচ্ছে...</b>\n\n"
        f"👤 {h(name)}\n🆔 <code>{h(uid)}</code>\n❤️ {sc('Likes')}: <b>{amount:,}</b>",
    )
    send_log(
        f"❤️ <b>{sc('NEW LIKE REQUEST')}</b>\n\n"
        f"👤 {sc('User ID')}: <code>{tg_id}</code>\n🎮 {sc('UID')}: <code>{h(uid)}</code>\n👤 {sc('Player')}: {h(name)}\n"
        f"❤️ {sc('Likes')}: {amount:,}\n⏳ {sc('Status')}: {sc('Processing')}"
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
            f"✅ <b>{sc('LIKE SENT SUCCESSFULLY')}</b>\n\n👤 {sc('Player')}: {h(name)}\n🆔 {sc('UID')}: <code>{h(uid)}</code>\n"
            f"❤️ {sc('Likes')}: {amount:,}\n📊 {sc('Status')}: {sc('Success')}",
            back(),
        )
        send_log(
            f"✅ <b>{sc('LIKE REQUEST SUCCESS')}</b>\n\n"
            f"👤 {sc('User ID')}: <code>{tg_id}</code>\n🎮 {sc('UID')}: <code>{h(uid)}</code>\n"
            f"❤️ {sc('Likes')}: {amount:,}\n📊 {sc('Status')}: {sc('Success')}"
        )
    else:
        error = r.get("error") or "API Error"
        edit_text(
            chat,
            mid,
            f"❌ <b>{sc('LIKE REQUEST FAILED')}</b>\n\n👤 {sc('Player')}: {h(name)}\n🆔 {sc('UID')}: <code>{h(uid)}</code>\n\n"
            f"❗ {sc('Reason')}: {h(error)}",
            back(),
        )
        send_log(
            f"❌ <b>{sc('LIKE REQUEST FAILED')}</b>\n\n"
            f"👤 {sc('User ID')}: <code>{tg_id}</code>\n🎮 {sc('UID')}: <code>{h(uid)}</code>\n"
            f"❤️ {sc('Likes')}: {amount:,}\n❗ {sc('Reason')}: {h(error)}"
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
        edit_text(chat, mid, f"🎮 <b>আপনার {sc('Free Fire UID')} পাঠান:</b>\n\n📝 উদাহরণ: <code>58392019</code>", back())
        return
    if d == "stats":
        answer_cb(cb_id)
        t = db().requests.count_documents({"telegram_id": tg_id})
        s = db().requests.count_documents({"telegram_id": tg_id, "status": "success"})
        f = db().requests.count_documents({"telegram_id": tg_id, "status": "failed"})
        edit_text(
            chat,
            mid,
            f"📊 <b>{sc('My Statistics')}</b>\n\n❤️ {sc('Total')}: {t}\n✅ {sc('Success')}: {s}\n❌ {sc('Failed')}: {f}",
            back(),
        )
        return
    if d == "help":
        answer_cb(cb_id)
        edit_text(
            chat,
            mid,
            f"ℹ️ <b>{sc('Help')}</b>\n\n"
            f"❤️ {sc('Like')} নির্বাচন করুন → {sc('UID')} দিন → {sc('Player Name')} যাচাই করুন → {sc('Package')} নির্বাচন করুন।\n\n"
            f"⚠️ শুধু বৈধ {sc('API integration')} ব্যবহার করুন।",
            back(),
        )
        return
    if d == "contact":
        answer_cb(cb_id)
        ids = admin_ids()
        target_admin = ids[0] if ids else ""
        if target_admin:
            kb = [[{"text": f"💬 {sc('Message Admin')}", "url": f"tg://user?id={target_admin}"}], *back()]
            edit_text(
                chat,
                mid,
                f"📞 <b>{sc('Contact Admin')}</b>\n\n👇 নিচের বাটনে চাপ দিয়ে সরাসরি {sc('Admin')}-কে মেসেজ করুন।",
                kb,
            )
        else:
            edit_text(chat, mid, f"📞 <b>{sc('Contact Admin')}</b>\n\n⚠️ {sc('Admin')} এখনো কনফিগার করা হয়নি।", back())
        return
    if d.startswith("pkg:"):
        answer_cb(cb_id, f"⏳ {sc('Processing...')}")
        process_like(chat, tg_id, mid, int(d[4:]))
        return
    if is_admin(tg_id):
        admin_callback(c)


def admin_home(chat: int, tg_id: int) -> None:
    if not is_admin(tg_id):
        send_text(chat, f"🚫 <b>{sc('Unauthorized')}</b>")
        return
    send_text(chat, f"🔐 <b>{sc('ADMIN CONTROL')}</b>\n\n⚙️ সব {sc('Admin control')} এই {sc('Bot')}-এর ভিতরেই থাকবে।", admin_keyboard())


def admin_keyboard() -> list:
    return [
        [{"text": f"📊 {sc('Dashboard')}", "callback_data": "adm:dash"}, {"text": f"👥 {sc('Users')}", "callback_data": "adm:users"}],
        [{"text": f"❤️ {sc('Requests')}", "callback_data": "adm:req"}, {"text": f"📈 {sc('Statistics')}", "callback_data": "adm:stats"}],
        [
            {"text": f"🔧 {sc('Maintenance')}", "callback_data": "adm:maint"},
            {"text": f"🚫 {sc('Block User')}", "callback_data": "adm:block"},
        ],
        [{"text": f"📢 {sc('Broadcast')}", "callback_data": "adm:broadcast"}],
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
        maint = sc("ON") if bool(get_setting("maintenance", False)) else sc("OFF")
        edit_text(
            chat,
            mid,
            f"📊 <b>{sc('Dashboard')}</b>\n\n👥 {sc('Users')}: {u}\n❤️ {sc('Requests')}: {r}\n"
            f"✅ {sc('Success')}: {s}\n❌ {sc('Failed')}: {f}\n🔧 {sc('Maintenance')}: {maint}",
            admin_keyboard(),
        )
        return
    if d == "adm:stats":
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        r = db().requests.count_documents({"created_at": {"$gte": today}})
        cutoff = datetime.now(timezone.utc).timestamp() - 86400
        active = db().users.count_documents({"last_activity": {"$gte": datetime.fromtimestamp(cutoff, tz=timezone.utc)}})
        today_label = sc("Today's Requests")
        edit_text(
            chat,
            mid,
            f"📈 <b>{sc('Statistics')}</b>\n\n📅 {today_label}: {r}\n⚡ {sc('Active 24h Users')}: {active}",
            admin_keyboard(),
        )
        return
    if d == "adm:maint":
        new = not bool(get_setting("maintenance", False))
        set_setting("maintenance", new)
        edit_text(chat, mid, f"🔧 {sc('Maintenance')}: <b>{sc('ON') if new else sc('OFF')}</b>", admin_keyboard())
        return
    if d == "adm:users":
        rows = db().users.find({}, sort=[("last_activity", -1)], limit=10)
        out = f"👥 <b>{sc('Recent Users')}</b>\n\n"
        for x in rows:
            mark = "🚫" if x.get("blocked", False) else "✅"
            out += f"• <code>{h(str(x['telegram_id']))}</code> {h(str(x.get('first_name') or ''))} {mark}\n"
        edit_text(chat, mid, out, admin_keyboard())
        return
    if d == "adm:req":
        rows = db().requests.find({}, sort=[("created_at", -1)], limit=10)
        out = f"❤️ <b>{sc('Recent Requests')}</b>\n\n"
        for x in rows:
            out += f"• {h(x['uid'])} | {int(x['like_amount']):,} | {sc(h(x['status']))}\n"
        edit_text(chat, mid, out, admin_keyboard())
        return
    if d == "adm:block":
        session_set(tg_id, "state", "admin_block")
        edit_text(
            chat,
            mid,
            f"🚫 যে {sc('Telegram ID')} block/unblock করতে চান সেটি পাঠান:",
            [[{"text": f"🔙 {sc('Admin Menu')}", "callback_data": "adm:menu"}]],
        )
        return
    if d == "adm:broadcast":
        session_set(tg_id, "state", "broadcast")
        edit_text(
            chat,
            mid,
            f"📢 <b>{sc('Broadcast Mode')}</b>\n\n📝 এখন {sc('Text/Image/Video/Document')} পাঠান।\n"
            f"🚫 {sc('Cancel')} করতে /cancel পাঠান।",
            [[{"text": f"🔙 {sc('Admin Menu')}", "callback_data": "adm:menu"}]],
        )
        return
    if d == "adm:menu":
        edit_text(chat, mid, f"🔐 <b>{sc('ADMIN CONTROL')}</b>", admin_keyboard())


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
            send_text(chat, f"❌ {sc('Invalid Telegram ID')}")
            return True
        u = db().users.find_one({"telegram_id": target_id})
        if not u:
            send_text(chat, f"❌ {sc('User not found.')}")
            session_clear(tg_id)
            return True
        blocked = not u.get("blocked", False)
        db().users.update_one({"telegram_id": target_id}, {"$set": {"blocked": blocked}})
        session_clear(tg_id)
        send_text(chat, f"🚫 {sc('User blocked.')}" if blocked else f"✅ {sc('User unblocked.')}", admin_keyboard())
        return True

    return False


def admin_broadcast_receive(chat: int, tg_id: int, m: dict) -> None:
    if (m.get("text") or "") == "/cancel":
        session_clear(tg_id)
        send_text(chat, f"❌ {sc('Broadcast cancelled.')}", admin_keyboard())
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
    send_text(chat, f"📢 <b>{sc('Broadcast Finished')}</b>\n\n✅ {sc('Sent')}: {sent}\n❌ {sc('Failed')}: {failed}", admin_keyboard())
