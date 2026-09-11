# -*- coding: utf-8 -*-
"""واجهة المستخدم: التسجيل والتحقق والإحالات والمتجر / user-side handlers."""
import logging
import re

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, ChatMemberUpdated, Message, ReplyKeyboardRemove

from core import config, db, texts, utils
from core.callbacks import CB
from core.keyboards import (account_kb, back_kb, cat_products_kb, confirm_buy_kb, contact_kb,
                            gate_kb, main_menu, product_kb, purchases_kb, settings_kb,
                            store_cats_kb, support_kb)
from core.rich import render
from core.utils import cb_answer, cb_show, full_name, log_action, send

log = logging.getLogger("user")

r = Router(name="user")
r.message.filter(F.chat.type == "private")


class UsrSt(StatesGroup):
    phone = State()


# ═══════════════ أدوات مشتركة / shared helpers ═══════════════

def db_name(row) -> str:
    n = (row["first_name"] or "").strip()
    if (row["last_name"] or "").strip():
        n += " " + row["last_name"].strip()
    return n or f"#{row['user_id']}"


async def missing_channels(bot: Bot, uid: int) -> list:
    out = []
    for ch in db.channels():
        try:
            m = await bot.get_chat_member(ch["chat_id"], uid)
            if m.status not in ("member", "administrator", "creator"):
                out.append(ch)
        except Exception as e:
            low = str(e).lower()
            if "member" in low or "participant" in low or "not found" in low:
                out.append(ch)
            else:
                # البوت مو أدمن بالقناة — ما نحبس المستخدمين، بس نسجّل تحذير
                log.warning("channel check failed for %s: %s", ch["chat_id"], e)
    return out


async def complete_registration(bot: Bot, uid: int) -> bool:
    """منح نقاط الإحالة عند أول اكتمال تسجيل (مرة وحدة فقط)."""
    row = db.get_user(uid)
    if not row or not row["referred_by"] or row["ref_credited"]:
        return False
    rid = row["referred_by"]
    if rid == uid:
        return False
    reward = db.get_setting_int("referral_reward", 1)
    db.q("UPDATE users SET ref_credited=1 WHERE user_id=?", (uid,))
    pts = db.add_points(rid, reward)
    rrow = db.get_user(rid)
    if rrow and not rrow["is_banned"]:
        d = texts.tr(rrow["lang"])
        txt, ents = render(d["ref_join"], name=db_name(row), reward=reward, points=pts)
        try:
            await send(bot, rid, (txt, ents))
        except Exception:
            pass
    log_action(bot, "log_ref_credit", name=db_name(row),
               ref=(db_name(rrow) if rrow else str(rid)), amount=reward, points=pts)
    return True


async def to_menu(target, state: FSMContext, first_time: bool = False):
    """الانتقال للقائمة الرئيسية بعد تجاوز بوابة القنوات."""
    bot = target.bot
    await state.clear()
    uid = target.from_user.id
    row = db.get_user(uid)
    lang = row["lang"] if row else "ar"
    d = texts.tr(lang)
    missing = await missing_channels(bot, uid)
    if missing:
        names = "\n".join(f"• {c['title'] or c['chat_id']}" for c in missing)
        txt, ents = render(d["gate_hdr"] + "\n\n{list}" + d["gate_after"], list=names)
        kb = gate_kb(lang, missing)
        if isinstance(target, CallbackQuery):
            await cb_show(target, (txt, ents), kb)
        else:
            await send(bot, target.chat.id, (txt, ents), kb)
        return
    first = await complete_registration(bot, uid)
    header = d["gate_passed"] + "\n\n" if (first_time or first) else ""
    name = full_name(target.from_user)
    points = row["points"] if row else 0
    txt, ents = render(header + d["menu_txt"], name=name, points=points)
    kb = main_menu(lang, db.is_admin(uid))
    if isinstance(target, CallbackQuery):
        await cb_show(target, (txt, ents), kb)
    else:
        await send(bot, target.chat.id, (txt, ents), kb)


async def ask_gate_again(cb: CallbackQuery, lang: str, missing: list):
    d = texts.tr(lang)
    names = "\n".join(f"• {c['title'] or c['chat_id']}" for c in missing)
    txt, ents = render(d["gate_still"] + "\n" + d["gate_after"], list=names)
    await cb_show(cb, (txt, ents), gate_kb(lang, missing))


# ═══════════════ /start والتسجيل ═══════════════

@r.message(CommandStart())
async def start_handler(message: Message, command: CommandObject, state: FSMContext, bot: Bot):
    u = message.from_user
    uid = u.id
    args = (command.args or "").strip()
    m = re.fullmatch(r"ref_?(\d{1,15})", args)
    ref_id = int(m.group(1)) if m else None
    if ref_id == uid:
        ref_id = None

    row = db.get_user(uid)
    if row is None:
        lang = "ar" if (u.language_code or "").lower().startswith("ar") else "en"
        referrer = None
        if ref_id is not None and db.get_user(ref_id):
            referrer = ref_id
        row = db.create_user(uid, u.first_name, u.last_name, u.username, lang, referrer)
        ref_line = ""
        if referrer:
            rr = db.get_user(referrer)
            ref_line = texts.t(lang, "log_ref_line").format(ref=f"{db_name(rr)} ({referrer})")
        log_action(bot, "log_new_user", name=full_name(u), uid=uid,
                   username=u.username or "—", phone="—", ref_line=ref_line)
    else:
        db.update_profile(uid, u.first_name, u.last_name, u.username)
        # ربط الإحالة إذا ضغط الرابط قبل إكمال التحقق
        if ref_id and not row["referred_by"] and not row["verified"] and db.get_user(ref_id):
            db.set_referred_by(uid, ref_id)
            row = db.get_user(uid)

    if row["is_banned"]:
        d = texts.tr(row["lang"])
        extra = d["ban_reason_line"] if row["ban_reason"] else ""
        txt, ents = render(d["banned"] + extra, reason=row["ban_reason"])
        await send(bot, message.chat.id, (txt, ents))
        return

    if not row["verified"]:
        d = texts.tr(row["lang"])
        await state.set_state(UsrSt.phone)
        txt, ents = render(d["ask_phone"])
        await send(bot, message.chat.id, (txt, ents), contact_kb(row["lang"]))
        return

    await to_menu(message, state)


@r.message(UsrSt.phone)
async def phone_handler(message: Message, state: FSMContext, bot: Bot):
    uid = message.from_user.id
    row = db.get_user(uid)
    lang = row["lang"] if row else "ar"
    d = texts.tr(lang)

    phone = None
    if message.contact:
        if message.contact.user_id and message.contact.user_id != uid:
            txt, ents = render(d["phone_other"])
            await send(bot, message.chat.id, (txt, ents), contact_kb(lang))
            return
        phone = message.contact.phone_number
    elif message.text:
        cleaned = re.sub(r"[\s\-()]", "", message.text.strip())
        if re.fullmatch(r"\+?\d{7,15}", cleaned):
            phone = cleaned if cleaned.startswith("+") else "+" + cleaned

    if not phone:
        txt, ents = render(d["phone_bad"], btn_send_contact=d["btn_send_contact"])
        await send(bot, message.chat.id, (txt, ents), contact_kb(lang))
        return

    db.set_phone_verified(uid, phone)
    row = db.get_user(uid)
    log_action(bot, "log_verified", name=db_name(row), uid=uid, phone=phone)
    await state.clear()
    txt, ents = render(d["phone_ok"])
    await send(bot, message.chat.id, (txt, ents), ReplyKeyboardRemove())
    await to_menu(message, state, first_time=True)


@r.callback_query(CB.filter(F.a == "gate"))
async def gate_check(cb: CallbackQuery, state: FSMContext, bot: Bot):
    await cb.answer()
    row = db.get_user(cb.from_user.id)
    if not row:
        return
    if not row["verified"]:
        d = texts.tr(row["lang"])
        await state.set_state(UsrSt.phone)
        txt, ents = render(d["ask_phone"])
        await send(bot, cb.from_user.id, (txt, ents), contact_kb(row["lang"]))
        return
    missing = await missing_channels(bot, cb.from_user.id)
    if missing:
        await ask_gate_again(cb, row["lang"], missing)
        return
    await to_menu(cb, state)


# ═══════════════ مراقب القنوات: خصم نقاط المغادرة ═══════════════

@r.chat_member()
async def on_membership(event: ChatMemberUpdated, bot: Bot):
    ch = db.channel_by_id(event.chat.id)
    if not ch:
        return
    new, old = event.new_chat_member, event.old_chat_member
    u = new.user
    if u.is_bot:
        return
    if new.status not in ("left", "kicked"):
        return
    if old.status not in ("member", "administrator", "creator", "restricted"):
        return

    row = db.get_user(u.id)
    if not row:
        return
    if not row["is_banned"]:
        d = texts.tr(row["lang"])
        txt, ents = render(d["left_warn"])
        try:
            await send(bot, u.id, (txt, ents))
        except Exception:
            pass
    if not row["verified"] or not row["referred_by"]:
        return

    rid = row["referred_by"]
    penalty = db.get_setting_int("referral_penalty", 1)
    pts = db.add_points(rid, -penalty)
    rrow = db.get_user(rid)
    if rrow and not rrow["is_banned"]:
        rd = texts.tr(rrow["lang"])
        tpl = rd["penalty"] if penalty > 0 else rd["penalty_zero"]
        txt, ents = render(tpl, name=db_name(row), uid=u.id,
                           channel=ch["title"] or str(ch["chat_id"]),
                           amount=abs(penalty), points=pts)
        try:
            await send(bot, rid, (txt, ents))
        except Exception:
            pass
    log_action(bot, "log_penalty", name=db_name(row),
               channel=ch["title"] or str(ch["chat_id"]),
               amount=penalty, ref=(db_name(rrow) if rrow else str(rid)), points=pts)


# ═══════════════ القائمة الرئيسية والمتجر ═══════════════

def _ulang(cb: CallbackQuery) -> str:
    row = db.get_user(cb.from_user.id)
    return row["lang"] if row else "ar"


@r.callback_query(CB.filter(F.a == "menu"))
async def menu_cb(cb: CallbackQuery, state: FSMContext):
    await to_menu(cb, state)


@r.callback_query(CB.filter(F.a == "store"))
async def store_cb(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    lang = _ulang(cb)
    d = texts.tr(lang)
    cats = db.cats()
    if not cats:
        txt, ents = render(d["store_empty"])
        await cb_show(cb, (txt, ents), back_kb(lang))
        return
    txt, ents = render(d["store_hdr"])
    await cb_show(cb, (txt, ents), store_cats_kb(lang, cats))


@r.callback_query(CB.filter(F.a == "cat"))
async def cat_cb(cb: CallbackQuery, callback_data: CB):
    lang = _ulang(cb)
    d = texts.tr(lang)
    if not callback_data.i:
        cats = db.cats()
        if not cats:
            txt, ents = render(d["store_empty"])
            await cb_show(cb, (txt, ents), back_kb(lang))
        else:
            txt, ents = render(d["store_hdr"])
            await cb_show(cb, (txt, ents), store_cats_kb(lang, cats))
        return
    cat = db.cat_by_id(int(callback_data.i))
    if not cat:
        await cb_answer(cb, "❌")
        return
    cname = cat["name_ar"] if lang == "ar" else cat["name_en"]
    prods = db.products_of(cat["id"])
    if not prods:
        txt, ents = render(d["cat_empty"], cat=cname)
        await cb_show(cb, (txt, ents), back_kb(lang, "store"))
        return
    txt, ents = render(d["cat_hdr"], cat=cname)
    await cb_show(cb, (txt, ents), cat_products_kb(lang, cat["id"], prods))


@r.callback_query(CB.filter(F.a == "prod"))
async def prod_cb(cb: CallbackQuery, callback_data: CB):
    lang = _ulang(cb)
    d = texts.tr(lang)
    p = db.product_by_id(int(callback_data.i)) if callback_data.i else None
    if not p:
        await cb_answer(cb, "❌")
        return
    stock = db.stock_count(p["id"])
    txt, ents = render(d["product_txt"], name=p["name_ar"] if lang == "ar" else p["name_en"],
                       price=p["price"], stock=stock)
    await cb_show(cb, (txt, ents), product_kb(lang, p["id"], p["category_id"], stock > 0))


@r.callback_query(CB.filter(F.a == "buyc"))
async def buy_confirm_cb(cb: CallbackQuery, callback_data: CB):
    lang = _ulang(cb)
    d = texts.tr(lang)
    p = db.product_by_id(int(callback_data.i)) if callback_data.i else None
    if not p:
        await cb_answer(cb, "❌")
        return
    u = db.get_user(cb.from_user.id)
    stock = db.stock_count(p["id"])
    if stock <= 0:
        txt, ents = render(d["no_stock_buy"])
        await cb_show(cb, (txt, ents), back_kb(lang, "cat", str(p["category_id"])))
        return
    txt, ents = render(d["confirm_buy"], name=p["name_ar"] if lang == "ar" else p["name_en"],
                       price=p["price"], balance=u["points"] if u else 0)
    await cb_show(cb, (txt, ents), confirm_buy_kb(lang, p["id"]))


@r.callback_query(CB.filter(F.a == "buyd"))
async def buy_do_cb(cb: CallbackQuery, callback_data: CB, bot: Bot):
    uid = cb.from_user.id
    lang = _ulang(cb)
    d = texts.tr(lang)
    p = db.product_by_id(int(callback_data.i)) if callback_data.i else None
    u = db.get_user(uid)
    if not p or not u:
        await cb_answer(cb, "❌")
        return
    if u["points"] < p["price"]:
        need = p["price"] - u["points"]
        txt, ents = render(d["no_points"], need=need)
        try:
            await send(bot, uid, (txt, ents))
        except Exception:
            pass
        await cb_answer(cb)
        return
    key = db.pop_key(p["id"])
    if key is None:
        txt, ents = render(d["no_stock_buy"])
        await cb_show(cb, (txt, ents), back_kb(lang, "cat", str(p["category_id"])))
        return
    # منطقة ذرّية: بدون awaits بين الفحص والتنفيذ
    balance = db.add_points(uid, -p["price"])
    db.q("UPDATE keys SET sold_to=?, sold_at=? WHERE id=?", (uid, db.now(), key["id"]))
    pname = p["name_ar"] if lang == "ar" else p["name_en"]
    db.add_purchase(uid, p["id"], p["name_ar"], key["key_text"], p["price"])
    txt, ents = render(d["buy_ok"], key=key["key_text"], balance=balance)
    try:
        await send(bot, uid, (txt, ents))
    except Exception:
        pass
    await cb_answer(cb, "✅")
    log_action(bot, "log_purchase", name=db_name(u), uid=uid,
               product=p["name_ar"], price=p["price"], key=key["key_text"])


# ═══════════════ حسابي / مشترياتي / الإعدادات / الدعم ═══════════════

@r.callback_query(CB.filter(F.a == "acc"))
async def acc_cb(cb: CallbackQuery):
    uid = cb.from_user.id
    lang = _ulang(cb)
    d = texts.tr(lang)
    row = db.get_user(uid)
    if not row:
        await cb_answer(cb, "❌")
        return
    reward = db.get_setting_int("referral_reward", 1)
    refs = db.q("SELECT COUNT(*) c FROM users WHERE referred_by=?", (uid,), fetch="one")["c"]
    buys = db.user_purchases_count(uid)
    spent = db.user_spent(uid)
    link = utils.ref_link(uid)
    txt, ents = render(
        d["account_txt"] + d["ref_link_hint"],
        name=full_name(cb.from_user), uid=uid,
        phone=row["phone"] or d["no_phone"],
        lang=("العربية" if row["lang"] == "ar" else "English"),
        joined=row["joined_at"] or "—",
        points=row["points"], refs=refs, buys=buys, spent=spent,
        reward=reward, link=link)
    await cb_show(cb, (txt, ents), account_kb(lang, link))


@r.callback_query(CB.filter(F.a == "pur"))
async def pur_cb(cb: CallbackQuery):
    uid = cb.from_user.id
    lang = _ulang(cb)
    d = texts.tr(lang)
    rows = db.user_purchases(uid)
    if not rows:
        txt, ents = render(d["purchases_empty"])
        await cb_show(cb, (txt, ents), back_kb(lang))
        return
    body = "".join(
        d["purchases_row"].format(i=i, name=x["product_name"] or "—", date=x["created_at"] or "", key=x["key_text"] or "")
        for i, x in enumerate(rows, 1))
    txt, ents = render(d["purchases_hdr"] + body, n=len(rows))
    await cb_show(cb, (txt, ents), purchases_kb(lang, rows))


@r.callback_query(CB.filter(F.a == "set"))
async def set_cb(cb: CallbackQuery):
    lang = _ulang(cb)
    d = texts.tr(lang)
    txt, ents = render(d["settings_txt"])
    await cb_show(cb, (txt, ents), settings_kb(lang))


@r.callback_query(CB.filter(F.a == "lang"))
async def lang_cb(cb: CallbackQuery, callback_data: CB):
    lang = callback_data.i if callback_data.i in ("ar", "en") else "ar"
    db.set_lang(cb.from_user.id, lang)
    d = texts.tr(lang)
    txt, ents = render(d["settings_txt"])
    await cb_show(cb, (txt, ents), settings_kb(lang))
    await cb_answer(cb, d["lang_set"])


@r.callback_query(CB.filter(F.a == "sup"))
async def sup_cb(cb: CallbackQuery):
    lang = _ulang(cb)
    d = texts.tr(lang)
    support = db.get_setting("support", config.DEFAULT_SUPPORT)
    txt, ents = render(d["support_txt"])
    await cb_show(cb, (txt, ents), support_kb(lang, support))


# ═══════════════ أوامر سريعة ═══════════════

@r.message(Command("id"))
async def id_cmd(message: Message):
    txt, ents = render("{e:id} <code>{uid}</code>", uid=message.from_user.id)
    await send(message.bot, message.chat.id, (txt, ents))


@r.message(Command("help"))
async def help_cmd(message: Message):
    row = db.get_user(message.from_user.id)
    lang = row["lang"] if row else "ar"
    d = texts.tr(lang)
    txt, ents = render(d["help_txt"])
    await send(message.bot, message.chat.id, (txt, ents))


@r.message(Command("lang"))
async def lang_cmd(message: Message):
    row = db.get_user(message.from_user.id)
    if not row:
        txt, ents = render("{e:warning} /start")
        await send(message.bot, message.chat.id, (txt, ents))
        return
    d = texts.tr(row["lang"])
    txt, ents = render(d["settings_txt"])
    await send(message.bot, message.chat.id, (txt, ents), settings_kb(row["lang"]))


@r.message(Command("admin"))
async def admin_denied(message: Message):
    row = db.get_user(message.from_user.id)
    lang = row["lang"] if row else "ar"
    d = texts.tr(lang)
    txt, ents = render(d["no_access"])
    await send(message.bot, message.chat.id, (txt, ents))


# ═══════════════ نص عشوائي بدون حالة ═══════════════

@r.message(StateFilter(None))
async def fallback(message: Message):
    row = db.get_user(message.from_user.id)
    if not row or not row["verified"]:
        return
    d = texts.tr(row["lang"])
    txt, ents = render(d["menu_txt"], name=full_name(message.from_user), points=row["points"])
    await send(message.bot, message.chat.id, (txt, ents),
               main_menu(row["lang"], db.is_admin(row["user_id"])))
