# -*- coding: utf-8 -*-
"""اختبار تكاملي كامل عبر الـ dispatcher بدون شبكة (FakeBot)."""
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (CallbackQuery, Chat, ChatMemberLeft, ChatMemberMember,
                           ChatMemberUpdated, Contact, Message, Update, User)

from core import config, db, emojis
from core.mw import BanGate
from handlers import admin as ah
from handlers import user as uh

PASS = 0
FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✓ {name}")
    else:
        FAIL += 1
        print(f"  ✗ FAIL: {name} {extra}")


BOT_TG = User(id=777000, is_bot=True, first_name="StoreBot", username="keys_store_bot")
NOW = datetime.now(timezone.utc)


class FakeBot(Bot):
    """يعترض كل نداءات API عبر __call__ (هكذا تعمل اختصارات aiogram فعلياً)."""

    def __init__(self):
        super().__init__(token="123456:TESTFAKE")
        self.sent = []
        self.answers = []
        self.docs = []
        self.member_status = "member"

    async def __call__(self, method, request_timeout=None):
        name = type(method).__name__
        if name == "SendMessage":
            self.sent.append(("msg", method.chat_id, method.text))
            return Message.model_construct(message_id=len(self.sent) + 10,
                                           chat=Chat(id=method.chat_id, type="private"), date=NOW)
        if name == "EditMessageText":
            self.sent.append(("edit", method.chat_id, method.text))
            return True
        if name == "AnswerCallbackQuery":
            self.answers.append((method.callback_query_id, method.text, method.show_alert))
            return True
        if name == "GetChatMember":
            return SimpleNamespace(status=self.member_status, user=SimpleNamespace(id=method.user_id))
        if name == "GetChat":
            return SimpleNamespace(id=-100555, title="قناة تجريبية", username="testchan", invite_link=None)
        if name == "CopyMessage":
            self.sent.append(("copy", method.chat_id, f"m{method.message_id}"))
            return Message.model_construct(message_id=99, chat=Chat(id=method.chat_id, type="private"), date=NOW)
        if name == "SendDocument":
            self.docs.append((method.chat_id, method.caption))
            return True
        if name == "GetMe":
            return BOT_TG
        return True  # DeleteWebhook / SetMyCommands / إلخ


_uq = [100]


def mk_user(uid, first, lang="ar", username=None):
    return User(id=uid, is_bot=False, first_name=first, language_code=lang, username=username)


_owner = mk_user(config.OWNER_ID, "Owner", username="owner")
_ref = mk_user(222, "Rami", username="rami")
_jr = mk_user(333, "Jo", username="jo")


async def feed_msg(dp, bot, user, text=None, contact=None):
    _uq[0] += 1
    msg = Message.model_construct(
        message_id=_uq[0], date=NOW,
        chat=Chat(id=user.id, type="private"),
        from_user=user, text=text,
        contact=contact, forward_origin=None, photo=None)
    await dp.feed_update(bot, Update.model_construct(update_id=_uq[0], message=msg))


async def feed_cb(dp, bot, user, data):
    _uq[0] += 1
    carrier = Message.model_construct(
        message_id=555, date=NOW, chat=Chat(id=user.id, type="private"),
        from_user=BOT_TG, text="old")
    cb = CallbackQuery.model_construct(
        id=str(_uq[0]), from_user=user, chat_instance="ci", data=data, message=carrier)
    await dp.feed_update(bot, Update.model_construct(update_id=_uq[0], callback_query=cb))


async def feed_chat_member(dp, bot, chat_id, user, old_status, new_status):
    _uq[0] += 1
    old_m = ChatMemberMember(user=user) if old_status == "member" else ChatMemberLeft(user=user)
    new_m = ChatMemberMember(user=user) if new_status == "member" else ChatMemberLeft(user=user)
    upd = Update.model_construct(
        update_id=_uq[0],
        chat_member=ChatMemberUpdated(
            chat=Chat(id=chat_id, type="channel"),
            from_user=user, date=NOW,
            old_chat_member=old_m, new_chat_member=new_m))
    await dp.feed_update(bot, upd)


def sent_to(bot, chat_id):
    return [t for (kind, cid, t) in bot.sent if cid == chat_id]


def last(bot, chat_id=None):
    items = bot.sent if chat_id is None else [x for x in bot.sent if x[1] == chat_id]
    return items[-1] if items else None


async def main():
    # قاعدة نظيفة
    config.BOT_USERNAME = "keys_store_bot"
    if config.DB_PATH.exists():
        config.DB_PATH.unlink()
    db.init()
    emojis.init()

    bot = FakeBot()
    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(BanGate())
    dp.include_router(ah.r)
    dp.include_router(uh.r)

    print("== 1) الأونر: /start → طلب رقم → توثيق → قائمة ==")
    await feed_msg(dp, bot, _owner, "/start")
    m = last(bot, _owner.id)
    check("owner got phone ask", m and ("رقمك" in m[2] or "number" in m[2]), m)
    await feed_msg(dp, bot, _owner, contact=Contact(first_name="u", last_name="t", phone_number="+963900000001", user_id=_owner.id))
    m = last(bot, _owner.id)
    check("owner verified + menu", m and "أهلاً" in m[2], m)
    row = db.get_user(_owner.id)
    check("owner row saved", row and row["verified"] == 1 and row["phone"] == "+963900000001")

    print("== 2) إحالة: 333 ينضم عبر رابط 222 ==")
    await feed_msg(dp, bot, _ref, "/start")
    await feed_msg(dp, bot, _ref, contact=Contact(first_name="u", last_name="t", phone_number="+963900000002", user_id=_ref.id))
    check("referrer balance 0", db.get_user(222)["points"] == 0)
    await feed_msg(dp, bot, _jr, "/start ref222")
    m = last(bot, _jr.id)
    check("jr phone ask", m and "رقم" in m[2], m)
    await feed_msg(dp, bot, _jr, contact=Contact(first_name="u", last_name="t", phone_number="+963900000003", user_id=333))
    m = last(bot, 222)
    check("referrer got +1 notify", m and ("+1" in m[2]), m)
    check("referrer balance 1", db.get_user(222)["points"] == 1)
    check("jr bound to 222", db.get_user(333)["referred_by"] == 222)
    check("log chat received events", any(x[1] == config.LOG_CHAT_ID for x in bot.sent))

    print("== 3) بوابة القنوات + الخصم عند المغادرة ==")
    db.add_channel(-100555, "قناة تجريبية", "testchan", "https://t.me/testchan")
    bot.member_status = "left"  # jr2 غير منضم بعد
    _uq[0] += 1
    jr2 = mk_user(444, "Nour")
    await feed_msg(dp, bot, jr2, "/start ref222")
    await feed_msg(dp, bot, jr2, contact=Contact(first_name="u", last_name="t", phone_number="+963900000004", user_id=444))
    m = last(bot, jr2.id)
    check("jr2 sees gate", m and "قنوات" in m[2], m)
    check("jr2 not credited yet", db.get_user(222)["points"] == 1)

    # ضغط زر التحقق وهو ما زال غير منضم
    bot.member_status = "left"
    await feed_cb(dp, bot, jr2, "m:gate:")
    m = last(bot, jr2.id)
    check("gate still blocked", m and ("ما انضممت" in m[2] or "haven't joined" in m[2]), m)

    # انضم الآن
    bot.member_status = "member"
    await feed_cb(dp, bot, jr2, "m:gate:")
    check("jr2 credited now", db.get_user(222)["points"] == 2)

    # 444 يغادر القناة → خصم من 222 + إشعار
    await feed_chat_member(dp, bot, -100555, jr2, "member", "left")
    check("penalty applied", db.get_user(222)["points"] == 1, str(db.get_user(222)["points"]))
    m = last(bot, 222)
    check("penalty notify has details", m and "444" in m[2] and "قناة تجريبية" in m[2], m)
    m = last(bot, 444)
    check("leaver warned", m and ("قناة" in m[2]), m)

    print("== 4) المتجر: شراء بمفاتيح فعلية ==")
    cid_ = db.q("INSERT INTO categories(name_ar,name_en,created_at) VALUES(?,?,?)", ("تطبيقات", "Apps", db.now())).lastrowid
    pid = db.q("INSERT INTO products(category_id,name_ar,name_en,price,created_at) VALUES(?,?,?,?,?)",
               (cid_, "نتفليكس", "Netflix", 3, db.now())).lastrowid
    for k in ("AAA-1", "BBB-2"):
        db.q("INSERT INTO keys(product_id,key_text) VALUES(?,?)", (pid, k))
    db.set_points(222, 10)

    await feed_cb(dp, bot, _ref, "m:store:")
    m = last(bot, 222)
    check("store screen", m and "المتجر" in m[2], m)
    await feed_cb(dp, bot, _ref, f"m:cat:{cid_}")
    m = last(bot, 222)
    check("category screen", m and "اختر منتج" in m[2], m)
    await feed_cb(dp, bot, _ref, f"m:prod:{pid}")
    m = last(bot, 222)
    check("product screen", m and "3" in m[2] and "2" in m[2], m)
    await feed_cb(dp, bot, _ref, f"m:buyc:{pid}")
    m = last(bot, 222)
    check("confirm screen", m and "تأكيد" in m[2] or (m and "Confirm" in m[2]), m)
    await feed_cb(dp, bot, _ref, f"m:buyd:{pid}")
    texts_all = " ".join(sent_to(bot, 222))
    check("key delivered", "AAA-1" in texts_all, texts_all[-200:])
    check("points deducted", db.get_user(222)["points"] == 7)
    check("stock decreased", db.stock_count(pid) == 1)
    check("purchase recorded", db.user_purchases_count(222) == 1)

    print("== 5) لوحة الأدمن ==")
    await feed_msg(dp, bot, _owner, "/admin")
    m = last(bot, _owner.id)
    check("admin panel", m and "الأدمن" in m[2], m)
    await feed_cb(dp, bot, _owner, "m:a_stats:")
    m = last(bot, _owner.id)
    check("stats screen", m and "الإحصائيات" in m[2], m)

    # إضافة قسم عبر FSM
    await feed_cb(dp, bot, _owner, "m:a_cata:")
    await feed_msg(dp, bot, _owner, "ألعاب")
    await feed_msg(dp, bot, _owner, "Games")
    check("category created", any(c["name_ar"] == "ألعاب" for c in db.cats()))

    # إضافة مفاتيح عبر FSM
    await feed_cb(dp, bot, _owner, "m:a_keys:")
    await feed_cb(dp, bot, _owner, f"m:a_kinfo:{pid}")
    await feed_cb(dp, bot, _owner, f"m:a_kadd:{pid}")
    await feed_msg(dp, bot, _owner, "KEY-X1\nKEY-X2\nKEY-X3")
    check("keys added via fsm", db.stock_count(pid) == 4, str(db.stock_count(pid)))

    # حظر المستخدم 333 وفك الحظر
    await feed_cb(dp, bot, _owner, "m:a_users:")
    await feed_cb(dp, bot, _owner, "m:a_user:333")
    await feed_cb(dp, bot, _owner, "m:a_uban:333")
    await feed_msg(dp, bot, _owner, "مخالفة")
    check("user banned", db.get_user(333)["is_banned"] == 1)
    check("ban reason saved", db.get_user(333)["ban_reason"] == "مخالفة")
    await feed_msg(dp, bot, _jr, "/start")
    m = last(bot, 333)
    check("banned blocked with reason", m and "حظرك" in m[2] and "مخالفة" in m[2], m)
    # حتى الكولباك محجوب (لا رسائل جديدة، فقط تنبيه حظر)
    n_before = len(sent_to(bot, 333))
    await feed_cb(dp, bot, _jr, "m:menu:")
    check("banned cb blocked (no menu)", len(sent_to(bot, 333)) == n_before
          and any(a[1] and "Banned" in a[1] for a in bot.answers))
    await feed_cb(dp, bot, _owner, "m:a_user:333")
    await feed_cb(dp, bot, _owner, "m:a_uunban:333")
    check("user unbanned", db.get_user(333)["is_banned"] == 0)

    print("== 6) الإيموجي البريميوم من لوحة الأدمن ==")
    await feed_cb(dp, bot, _owner, "m:a_emoji:")
    await feed_cb(dp, bot, _owner, "m:a_eslot:store")
    await feed_cb(dp, bot, _owner, "m:a_ecid:store")
    await feed_msg(dp, bot, _owner, "5360481542747122286")
    check("custom id saved", emojis.cid("store") == "5360481542747122286")
    await feed_cb(dp, bot, _owner, "m:a_etest:store")
    m = last(bot, _owner.id)
    check("emoji preview sent", m and "معاينة" in m[2], m)

    print("== 7) تغيير اللغة والقائمة ==")
    await feed_cb(dp, bot, _ref, "m:set:")
    await feed_cb(dp, bot, _ref, "m:lang:en")
    check("lang saved en", db.get_user(222)["lang"] == "en")
    await feed_cb(dp, bot, _ref, "m:menu:")
    m = last(bot, 222)
    check("menu in english", m and "Hello Rami" in m[2], m)

    print()
    print(f"RESULT: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        code = asyncio.run(main())
    finally:
        pass
    sys.exit(code)
