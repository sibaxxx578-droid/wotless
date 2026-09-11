# -*- coding: utf-8 -*-
"""لوحة الأدمن الكاملة / full admin panel."""
import asyncio
import logging
import re
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, Message

from core import config, db, emojis, texts
from core import admin_kb as akb
from core.callbacks import CB
from core.keyboards import back_kb, cancel_kb, confirm_kb
from core.rich import render
from core.utils import cb_answer, cb_show, full_name, log_action, send

log = logging.getLogger("admin")

r = Router(name="admin")


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery) -> bool:
        return db.is_admin(event.from_user.id)


r.message.filter(IsAdmin())
r.callback_query.filter(IsAdmin())
r.message.filter(F.chat.type == "private")


class AdmSt(StatesGroup):
    cat_add_ar = State()
    cat_add_en = State()
    cat_ren = State()
    prod_name_ar = State()
    prod_name_en = State()
    prod_price = State()
    prod_rename = State()
    keys_paste = State()
    emoji_cid = State()
    emoji_char = State()
    chan_add = State()
    user_find = State()
    pts_add = State()
    pts_sub = State()
    msg_user = State()
    ban_reason = State()
    admin_add = State()
    bcast = State()
    ref_set = State()


def _ulang(uid: int) -> str:
    row = db.get_user(uid)
    return row["lang"] if row else "ar"


def _d(uid: int) -> dict:
    return texts.tr(_ulang(uid))


def db_name(row) -> str:
    n = (row["first_name"] or "").strip()
    if (row["last_name"] or "").strip():
        n += " " + row["last_name"].strip()
    return n or f"#{row['user_id']}"


def cb_chat(cb: CallbackQuery) -> int:
    return cb.message.chat.id if cb.message else cb.from_user.id


async def owner_guard(cb: CallbackQuery) -> bool:
    if cb.from_user.id != config.OWNER_ID:
        d = _d(cb.from_user.id)
        await cb_answer(cb, d["only_owner"], alert=True)
        return False
    return True


def prod_name(p, lang: str) -> str:
    return p["name_ar"] if lang == "ar" else p["name_en"]


# ═══════════════ /admin + القائمة الرئيسية ═══════════════

@r.message(Command("admin"))
async def admin_cmd(message: Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id
    d = _d(uid)
    txt, ents = render(d["am_hdr"], name=full_name(message.from_user))
    await send(message.bot, message.chat.id, (txt, ents), akb.admin_main(_ulang(uid), uid))


@r.callback_query(CB.filter(F.a == "am"))
async def am_cb(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    d = _d(uid)
    txt, ents = render(d["am_hdr"], name=full_name(cb.from_user))
    await cb_show(cb, (txt, ents), akb.admin_main(_ulang(uid), uid))


@r.callback_query(CB.filter(F.a == "cancel"))
async def cancel_cb(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    d = _d(uid)
    txt, ents = render(d["am_hdr"], name=full_name(cb.from_user))
    await cb_show(cb, (txt, ents), akb.admin_main(_ulang(uid), uid))


# ═══════════════ الأقسام ═══════════════

@r.callback_query(CB.filter(F.a == "a_cat"))
async def a_cat_cb(cb: CallbackQuery):
    uid = cb.from_user.id
    lang = _ulang(uid)
    cats = db.cats()
    kb = akb.cats_kb(lang, cats)
    if not cats:
        d = texts.tr(lang)
        txt, ents = render(d["no_cats"])
    else:
        d = texts.tr(lang)
        txt, ents = render(d["am_hdr"], name=full_name(cb.from_user))
    await cb_show(cb, (txt, ents), kb)


@r.callback_query(CB.filter(F.a == "a_cata"))
async def a_cata_cb(cb: CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    d = _d(uid)
    await state.set_state(AdmSt.cat_add_ar)
    txt, ents = render(d["cat_add_prompt"])
    await cb_show(cb, (txt, ents), cancel_kb(_ulang(uid)))


@r.message(AdmSt.cat_add_ar, F.text)
async def cat_add_ar_msg(message: Message, state: FSMContext):
    uid = message.from_user.id
    d = _d(uid)
    await state.update_data(ar=message.text.strip()[:64])
    await state.set_state(AdmSt.cat_add_en)
    txt, ents = render(d["cat_add_en_prompt"])
    await send(message.bot, message.chat.id, (txt, ents), cancel_kb(_ulang(uid)))


@r.message(AdmSt.cat_add_en, F.text)
async def cat_add_en_msg(message: Message, state: FSMContext):
    data = await state.get_data()
    uid = message.from_user.id
    ar = data.get("ar", "")
    en = message.text.strip()[:64]
    if en == "-":
        en = ar
    db.q("INSERT INTO categories(name_ar, name_en, created_at) VALUES(?,?,?)", (ar, en, db.now()))
    await state.clear()
    d = _d(uid)
    log_action(message.bot, "log_cat_add", name=ar)
    txt, ents = render(d["cat_added"], name=ar)
    await send(message.bot, message.chat.id, (txt, ents), akb.cats_kb(_ulang(uid), db.cats()))


@r.callback_query(CB.filter(F.a == "a_cren1"))
async def a_cren1_cb(cb: CallbackQuery, callback_data: CB):
    uid = cb.from_user.id
    lang = _ulang(uid)
    cat = db.cat_by_id(int(callback_data.i))
    if not cat:
        await cb_answer(cb, "❌")
        return
    txt, ents = render("{e:category} {name}", name=prod_name(cat, lang))
    await cb_show(cb, (txt, ents), akb.cat_rename_kb(lang, cat["id"]))


@r.callback_query(CB.filter(F.a == "a_cren_ar"))
async def a_cren_ar_cb(cb: CallbackQuery, callback_data: CB, state: FSMContext):
    cat = db.cat_by_id(int(callback_data.i))
    if not cat:
        await cb_answer(cb, "❌")
        return
    uid = cb.from_user.id
    d = _d(uid)
    await state.set_state(AdmSt.cat_ren)
    await state.update_data(cid=cat["id"], field="ar")
    txt, ents = render(d["cat_ren_prompt"], name=cat["name_ar"])
    await cb_show(cb, (txt, ents), cancel_kb(_ulang(uid)))


@r.callback_query(CB.filter(F.a == "a_cren_en"))
async def a_cren_en_cb(cb: CallbackQuery, callback_data: CB, state: FSMContext):
    cat = db.cat_by_id(int(callback_data.i))
    if not cat:
        await cb_answer(cb, "❌")
        return
    uid = cb.from_user.id
    d = _d(uid)
    await state.set_state(AdmSt.cat_ren)
    await state.update_data(cid=cat["id"], field="en")
    txt, ents = render(d["cat_ren_en_prompt"], name=cat["name_en"])
    await cb_show(cb, (txt, ents), cancel_kb(_ulang(uid)))


@r.message(AdmSt.cat_ren, F.text)
async def cat_ren_msg(message: Message, state: FSMContext):
    data = await state.get_data()
    uid = message.from_user.id
    field = data.get("field", "ar")
    new_name = message.text.strip()[:64]
    db.q(f"UPDATE categories SET name_{field}=? WHERE id=?", (new_name, data["cid"]))
    await state.clear()
    d = _d(uid)
    log_action(message.bot, "log_cat_edit", name=new_name)
    txt, ents = render(d["cat_updated"])
    await send(message.bot, message.chat.id, (txt, ents), akb.cats_kb(_ulang(uid), db.cats()))


@r.callback_query(CB.filter(F.a == "a_cdel1"))
async def a_cdel1_cb(cb: CallbackQuery, callback_data: CB):
    uid = cb.from_user.id
    lang = _ulang(uid)
    cat = db.cat_by_id(int(callback_data.i))
    if not cat:
        await cb_answer(cb, "❌")
        return
    d = texts.tr(lang)
    txt, ents = render(d["cat_del_confirm"], name=cat["name_ar"] if lang == "ar" else cat["name_en"])
    await cb_show(cb, (txt, ents), confirm_kb(lang, "a_cdel2", "a_cat", str(cat["id"])))


@r.callback_query(CB.filter(F.a == "a_cdel2"))
async def a_cdel2_cb(cb: CallbackQuery, callback_data: CB):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    cid = int(callback_data.i)
    cat = db.cat_by_id(cid)
    for p in db.products_of(cid):
        db.q("DELETE FROM keys WHERE product_id=?", (p["id"],))
    db.q("DELETE FROM products WHERE category_id=?", (cid,))
    db.q("DELETE FROM categories WHERE id=?", (cid,))
    log_action(cb.bot, "log_cat_del", name=(cat["name_ar"] if cat else str(cid)))
    txt, ents = render(d["cat_deleted"])
    await cb_show(cb, (txt, ents), akb.cats_kb(lang, db.cats()))


# ═══════════════ المنتجات ═══════════════

@r.callback_query(CB.filter(F.a == "a_prods"))
async def a_prods_cb(cb: CallbackQuery):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    txt, ents = render("{e:box} {t}", t=d["am_prods"])
    await cb_show(cb, (txt, ents), akb.prods_kb(lang, db.all_products()))


@r.callback_query(CB.filter(F.a == "a_proda"))
async def a_proda_cb(cb: CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    if not db.cats():
        txt, ents = render(d["no_cats"])
        await cb_show(cb, (txt, ents), akb.cats_kb(lang, []))
        return
    await state.set_state(AdmSt.prod_name_ar)
    txt, ents = render(d["prod_name_ar_prompt"])
    await cb_show(cb, (txt, ents), cancel_kb(lang))


@r.message(AdmSt.prod_name_ar, F.text)
async def prod_name_ar_msg(message: Message, state: FSMContext):
    uid = message.from_user.id
    d = _d(uid)
    await state.update_data(ar=message.text.strip()[:64])
    await state.set_state(AdmSt.prod_name_en)
    txt, ents = render(d["prod_name_en_prompt"])
    await send(message.bot, message.chat.id, (txt, ents), cancel_kb(_ulang(uid)))


@r.message(AdmSt.prod_name_en, F.text)
async def prod_name_en_msg(message: Message, state: FSMContext):
    uid = message.from_user.id
    d = _d(uid)
    await state.update_data(en=message.text.strip()[:64])
    await state.set_state(AdmSt.prod_price)
    txt, ents = render(d["prod_price_prompt"])
    await send(message.bot, message.chat.id, (txt, ents), cancel_kb(_ulang(uid)))


@r.message(AdmSt.prod_price, F.text)
async def prod_price_msg(message: Message, state: FSMContext):
    data = await state.get_data()
    uid = message.from_user.id
    lang = _ulang(uid)
    d = _d(uid)
    if not re.fullmatch(r"\d{1,7}", message.text.strip()):
        txt, ents = render(d["num_bad"])
        await send(message.bot, message.chat.id, (txt, ents), cancel_kb(lang))
        return
    price = int(message.text.strip())

    # هل نحن بوضع تعديل سعر منتج موجود؟
    edit_pid = data.get("edit_pid")
    if edit_pid:
        db.q("UPDATE products SET price=? WHERE id=?", (price, int(edit_pid)))
        await state.clear()
        p = db.product_by_id(int(edit_pid))
        if p:
            log_action(message.bot, "log_prod_edit", name=p["name_ar"])
            cat = db.cat_by_id(p["category_id"])
            txt, ents = render(d["prod_updated"] + "\n\n" + d["prod_card"],
                               name=prod_name(p, lang), cat=(prod_name(cat, lang) if cat else "—"),
                               price=p["price"], stock=db.stock_count(p["id"]), sold=db.sold_count(p["id"]))
            await send(message.bot, message.chat.id, (txt, ents), akb.prod_ops_kb(lang, p["id"]))
        return

    ar = data.get("ar", "Product")
    en = data.get("en", ar)
    if en == "-":
        en = ar
    cats = db.cats()
    cat_id = cats[0]["id"] if cats else 0
    cur = db.q("INSERT INTO products(category_id, name_ar, name_en, price, created_at) VALUES(?,?,?,?,?)",
               (cat_id, ar, en, price, db.now()))
    await state.clear()
    log_action(message.bot, "log_prod_add", name=ar, price=price)
    txt, ents = render(d["prod_added"], name=ar, price=price)
    await send(message.bot, message.chat.id, (txt, ents), akb.prods_kb(lang, db.all_products()))


@r.callback_query(CB.filter(F.a == "a_prod"))
async def a_prod_cb(cb: CallbackQuery, callback_data: CB):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    p = db.product_by_id(int(callback_data.i))
    if not p:
        await cb_answer(cb, "❌")
        return
    cat = db.cat_by_id(p["category_id"])
    txt, ents = render(d["prod_card"], name=prod_name(p, lang),
                       cat=(prod_name(cat, lang) if cat else "—"),
                       price=p["price"], stock=db.stock_count(p["id"]), sold=db.sold_count(p["id"]))
    await cb_show(cb, (txt, ents), akb.prod_ops_kb(lang, p["id"]))


@r.callback_query(CB.filter(F.a == "a_pname"))
async def a_pname_cb(cb: CallbackQuery, callback_data: CB, state: FSMContext):
    pid, field = callback_data.i.split("_")
    p = db.product_by_id(int(pid))
    if not p:
        await cb_answer(cb, "❌")
        return
    uid = cb.from_user.id
    d = _d(uid)
    await state.set_state(AdmSt.prod_rename)
    await state.update_data(pid=int(pid), field=field)
    txt, ents = render(d["prod_new_name_prompt"])
    await cb_show(cb, (txt, ents), cancel_kb(_ulang(uid)))


@r.message(AdmSt.prod_rename, F.text)
async def prod_rename_msg(message: Message, state: FSMContext):
    data = await state.get_data()
    uid = message.from_user.id
    lang = _ulang(uid)
    field = data.get("field", "ar")
    pid = int(data.get("pid", 0))
    new_name = message.text.strip()[:64]
    db.q(f"UPDATE products SET name_{field}=? WHERE id=?", (new_name, pid))
    await state.clear()
    d = _d(uid)
    p = db.product_by_id(pid)
    log_action(message.bot, "log_prod_edit", name=(p["name_ar"] if p else new_name))
    txt, ents = render(d["prod_updated"])
    if p:
        cat = db.cat_by_id(p["category_id"])
        txt, ents = render(d["prod_updated"] + "\n\n" + d["prod_card"],
                           name=prod_name(p, lang), cat=(prod_name(cat, lang) if cat else "—"),
                           price=p["price"], stock=db.stock_count(p["id"]), sold=db.sold_count(p["id"]))
    await send(message.bot, message.chat.id, (txt, ents), akb.prod_ops_kb(lang, pid))


@r.callback_query(CB.filter(F.a == "a_pprice"))
async def a_pprice_cb(cb: CallbackQuery, callback_data: CB, state: FSMContext):
    uid = cb.from_user.id
    d = _d(uid)
    await state.set_state(AdmSt.prod_price)
    await state.update_data(edit_pid=int(callback_data.i))
    txt, ents = render(d["prod_price_prompt"])
    await cb_show(cb, (txt, ents), cancel_kb(_ulang(uid)))


@r.callback_query(CB.filter(F.a == "a_pmove"))
async def a_pmove_cb(cb: CallbackQuery, callback_data: CB):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    p = db.product_by_id(int(callback_data.i))
    if not p:
        await cb_answer(cb, "❌")
        return
    txt, ents = render(d["prod_move_pick"], name=prod_name(p, lang))
    await cb_show(cb, (txt, ents), akb.cats_pick_kb(lang, db.cats(), "a_pmove2", p["id"]))


@r.callback_query(CB.filter(F.a == "a_pmove2"))
async def a_pmove2_cb(cb: CallbackQuery, callback_data: CB):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    pid, cid = callback_data.i.split("_")
    db.q("UPDATE products SET category_id=? WHERE id=?", (int(cid), int(pid)))
    p = db.product_by_id(int(pid))
    cat = db.cat_by_id(int(cid))
    if p:
        log_action(cb.bot, "log_prod_edit", name=p["name_ar"])
    txt, ents = render(d["prod_moved"], cat=(prod_name(cat, lang) if cat else "—"))
    await cb_show(cb, (txt, ents), akb.prods_kb(lang, db.all_products()))


@r.callback_query(CB.filter(F.a == "a_pdel1"))
async def a_pdel1_cb(cb: CallbackQuery, callback_data: CB):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    p = db.product_by_id(int(callback_data.i))
    if not p:
        await cb_answer(cb, "❌")
        return
    txt, ents = render(d["prod_del_confirm"], name=prod_name(p, lang))
    await cb_show(cb, (txt, ents), confirm_kb(lang, "a_pdel2", "a_prods", str(p["id"])))


@r.callback_query(CB.filter(F.a == "a_pdel2"))
async def a_pdel2_cb(cb: CallbackQuery, callback_data: CB):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    pid = int(callback_data.i)
    p = db.product_by_id(pid)
    db.q("DELETE FROM keys WHERE product_id=?", (pid,))
    db.q("DELETE FROM products WHERE id=?", (pid,))
    if p:
        log_action(cb.bot, "log_prod_del", name=p["name_ar"])
    txt, ents = render(d["prod_deleted"])
    await cb_show(cb, (txt, ents), akb.prods_kb(lang, db.all_products()))


# ═══════════════ مخزون المفاتيح ═══════════════

@r.callback_query(CB.filter(F.a == "a_keys"))
async def a_keys_cb(cb: CallbackQuery):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    prods = db.all_products()
    if not prods:
        txt, ents = render(d["no_prods"])
        await cb_show(cb, (txt, ents), back_kb(lang, "am"))
        return
    txt, ents = render(d["keys_pick"])
    await cb_show(cb, (txt, ents), akb.keys_kb(lang, prods))


@r.callback_query(CB.filter(F.a == "a_kinfo"))
async def a_kinfo_cb(cb: CallbackQuery, callback_data: CB):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    p = db.product_by_id(int(callback_data.i))
    if not p:
        await cb_answer(cb, "❌")
        return
    txt, ents = render(d["keys_card"], name=prod_name(p, lang),
                       stock=db.stock_count(p["id"]), sold=db.sold_count(p["id"]))
    await cb_show(cb, (txt, ents), akb.keys_ops_kb(lang, p["id"]))


@r.callback_query(CB.filter(F.a == "a_kadd"))
async def a_kadd_cb(cb: CallbackQuery, callback_data: CB, state: FSMContext):
    uid = cb.from_user.id
    d = _d(uid)
    await state.set_state(AdmSt.keys_paste)
    await state.update_data(pid=int(callback_data.i))
    txt, ents = render(d["keys_prompt"])
    await cb_show(cb, (txt, ents), cancel_kb(_ulang(uid)))


@r.message(AdmSt.keys_paste, F.text)
async def keys_paste_msg(message: Message, state: FSMContext):
    data = await state.get_data()
    uid = message.from_user.id
    lang = _ulang(uid)
    pid = int(data.get("pid", 0))
    p = db.product_by_id(pid)
    d = _d(uid)
    if not p:
        await state.clear()
        txt, ents = render(d["no_prods"])
        await send(message.bot, message.chat.id, (txt, ents), akb.keys_kb(lang, db.all_products()))
        return
    lines = [ln.strip() for ln in message.text.splitlines() if ln.strip()][:2000]
    for ln in lines:
        db.q("INSERT INTO keys(product_id, key_text) VALUES(?,?)", (pid, ln[:256]))
    total = db.stock_count(pid)
    await state.clear()
    log_action(message.bot, "log_keys", n=len(lines), name=p["name_ar"], total=total)
    txt, ents = render(d["keys_added"], n=len(lines), name=prod_name(p, lang), total=total)
    await send(message.bot, message.chat.id, (txt, ents), akb.keys_ops_kb(lang, pid))


@r.callback_query(CB.filter(F.a == "a_kexp"))
async def a_kexp_cb(cb: CallbackQuery, callback_data: CB):
    uid = cb.from_user.id
    d = _d(uid)
    pid = int(callback_data.i)
    p = db.product_by_id(pid)
    if not p:
        await cb_answer(cb, "❌")
        return
    rows = db.q("SELECT key_text FROM keys WHERE product_id=? AND sold_to IS NULL ORDER BY id", (pid,), fetch="all")
    if not rows:
        txt, ents = render(d["keys_no_stock"])
        await cb_answer(cb, txt, alert=True)
        return
    path = config.DATA_DIR / f"export_keys_{pid}.txt"
    path.write_text("\n".join(x["key_text"] for x in rows), encoding="utf-8")
    cap, cents = render(d["keys_export_caption"], name=p["name_ar"], n=len(rows))
    try:
        if cb.message:
            await cb.message.answer_document(FSInputFile(str(path)), caption=cap, caption_entities=cents)
        else:
            await cb.bot.send_document(cb.from_user.id, FSInputFile(str(path)), caption=cap, caption_entities=cents)
    finally:
        try:
            path.unlink()
        except OSError:
            pass
    await cb_answer(cb)


@r.callback_query(CB.filter(F.a == "a_kclr1"))
async def a_kclr1_cb(cb: CallbackQuery, callback_data: CB):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    p = db.product_by_id(int(callback_data.i))
    if not p:
        await cb_answer(cb, "❌")
        return
    txt, ents = render(d["keys_clear_confirm"], name=prod_name(p, lang), stock=db.stock_count(p["id"]))
    await cb_show(cb, (txt, ents), confirm_kb(lang, "a_kclr2", "a_keys", str(p["id"])))


@r.callback_query(CB.filter(F.a == "a_kclr2"))
async def a_kclr2_cb(cb: CallbackQuery, callback_data: CB):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    pid = int(callback_data.i)
    n = db.stock_count(pid)
    db.q("DELETE FROM keys WHERE product_id=? AND sold_to IS NULL", (pid,))
    p = db.product_by_id(pid)
    log_action(cb.bot, "log_keys_clear", n=n, name=(p["name_ar"] if p else str(pid)))
    txt, ents = render(d["keys_cleared"], n=n)
    await cb_show(cb, (txt, ents), akb.keys_kb(lang, db.all_products()))


# ═══════════════ الإحصائيات ═══════════════

@r.callback_query(CB.filter(F.a == "a_stats"))
async def a_stats_cb(cb: CallbackQuery):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    s = db.stats()
    if s["top"]:
        top = "".join(d["stats_top_row"].format(i=i, name=x["product_name"], c=x["c"], s=x["s"])
                      for i, x in enumerate(s["top"], 1))
    else:
        top = d["stats_top_empty"]
    txt, ents = render(d["stats_txt"], users=s["users"], today=s["users_today"],
                       verified=s["verified"], banned=s["banned"], refs=s["refs"],
                       points=s["points"], purchases=s["purchases"], revenue=s["revenue"],
                       keys=s["keys_stock"], cats=s["cats"], prods=s["prods"],
                       channels=s["channels"], admins=s["admins"], top=top)
    await cb_show(cb, (txt, ents), back_kb(lang, "am"))


# ═══════════════ إعدادات نقاط الإحالة ═══════════════

@r.callback_query(CB.filter(F.a == "a_ref"))
async def a_ref_cb(cb: CallbackQuery):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    reward = db.get_setting_int("referral_reward", 1)
    penalty = db.get_setting_int("referral_penalty", 1)
    support = db.get_setting("support", config.DEFAULT_SUPPORT)
    txt, ents = render(d["ref_txt"], reward=reward, penalty=penalty, support=support)
    await cb_show(cb, (txt, ents), akb.ref_kb(lang, reward, penalty, support))


@r.callback_query(CB.filter(F.a == "a_refset"))
async def a_refset_cb(cb: CallbackQuery, callback_data: CB, state: FSMContext):
    uid = cb.from_user.id
    d = _d(uid)
    field = callback_data.i
    await state.set_state(AdmSt.ref_set)
    await state.update_data(field=field)
    if field == "support":
        prompt = ("{e:support} أرسل معرف الدعم الجديد بدون @:"
                  if _ulang(uid) == "ar" else
                  "{e:support} Send the new support username without @:")
        txt, ents = render(prompt)
    else:
        txt, ents = render(d["ref_num_prompt"])
    await cb_show(cb, (txt, ents), cancel_kb(_ulang(uid)))


@r.message(AdmSt.ref_set, F.text)
async def ref_set_msg(message: Message, state: FSMContext):
    data = await state.get_data()
    uid = message.from_user.id
    lang = _ulang(uid)
    field = data.get("field", "referral_reward")
    d = _d(uid)
    if field == "support":
        val = message.text.strip().lstrip("@")
        if not re.fullmatch(r"[A-Za-z0-9_]{4,32}", val):
            txt, ents = render(d["text_bad"])
            await send(message.bot, message.chat.id, (txt, ents), cancel_kb(lang))
            return
    else:
        if not re.fullmatch(r"\d{1,5}", message.text.strip()):
            txt, ents = render(d["num_bad"])
            await send(message.bot, message.chat.id, (txt, ents), cancel_kb(lang))
            return
        val = str(int(message.text.strip()))
    db.set_setting(field, val)
    await state.clear()
    log_action(message.bot, "log_setting", key=field, value=val)
    reward = db.get_setting_int("referral_reward", 1)
    penalty = db.get_setting_int("referral_penalty", 1)
    support = db.get_setting("support", config.DEFAULT_SUPPORT)
    txt, ents = render(d["ref_txt"], reward=reward, penalty=penalty, support=support)
    await send(message.bot, message.chat.id, (txt, ents), akb.ref_kb(lang, reward, penalty, support))


# ═══════════════ الإيموجيات ═══════════════

@r.callback_query(CB.filter(F.a == "a_emoji"))
async def a_emoji_cb(cb: CallbackQuery):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    txt, ents = render(d["emoji_txt"])
    await cb_show(cb, (txt, ents), akb.emoji_slots_kb(lang))


@r.callback_query(CB.filter(F.a == "a_eslot"))
async def a_eslot_cb(cb: CallbackQuery, callback_data: CB):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    slot = callback_data.i
    if slot not in emojis.slots():
        await cb_answer(cb, "❌")
        return
    txt, ents = render(d["emoji_slot_txt"], label=emojis.label(slot, lang),
                       slot=slot, char=emojis.char(slot), cid=emojis.cid(slot) or d["emoji_no_cid"])
    await cb_show(cb, (txt, ents), akb.emoji_slot_kb(lang, slot))


@r.callback_query(CB.filter(F.a == "a_ecid"))
async def a_ecid_cb(cb: CallbackQuery, callback_data: CB, state: FSMContext):
    uid = cb.from_user.id
    d = _d(uid)
    await state.set_state(AdmSt.emoji_cid)
    await state.update_data(slot=callback_data.i)
    txt, ents = render(d["emoji_cid_prompt"])
    await cb_show(cb, (txt, ents), cancel_kb(_ulang(uid)))


@r.message(AdmSt.emoji_cid, F.text)
async def emoji_cid_msg(message: Message, state: FSMContext):
    data = await state.get_data()
    uid = message.from_user.id
    lang = _ulang(uid)
    slot = data.get("slot", "")
    d = _d(uid)
    val = message.text.strip()
    if val == "-":
        emojis.set_cid(slot, "")
        done = d["emoji_cid_cleared"]
    elif not re.fullmatch(r"\d{8,25}", val):
        txt, ents = render(d["emoji_cid_bad"])
        await send(message.bot, message.chat.id, (txt, ents), cancel_kb(lang))
        return
    else:
        emojis.set_cid(slot, val)
        done = d["emoji_cid_set"]
    await state.clear()
    log_action(message.bot, "log_emoji", slot=slot, value=val[:40])
    txt, ents = render(done + "\n\n" + d["emoji_slot_txt"], label=emojis.label(slot, lang),
                       slot=slot, char=emojis.char(slot), cid=emojis.cid(slot) or d["emoji_no_cid"])
    await send(message.bot, message.chat.id, (txt, ents), akb.emoji_slot_kb(lang, slot))


@r.callback_query(CB.filter(F.a == "a_echar"))
async def a_echar_cb(cb: CallbackQuery, callback_data: CB, state: FSMContext):
    uid = cb.from_user.id
    d = _d(uid)
    await state.set_state(AdmSt.emoji_char)
    await state.update_data(slot=callback_data.i)
    txt, ents = render(d["emoji_char_prompt"])
    await cb_show(cb, (txt, ents), cancel_kb(_ulang(uid)))


@r.message(AdmSt.emoji_char, F.text)
async def emoji_char_msg(message: Message, state: FSMContext):
    data = await state.get_data()
    uid = message.from_user.id
    lang = _ulang(uid)
    slot = data.get("slot", "")
    d = _d(uid)
    val = message.text.strip()[:8]
    if not val:
        txt, ents = render(d["text_bad"])
        await send(message.bot, message.chat.id, (txt, ents), cancel_kb(lang))
        return
    emojis.set_char(slot, val)
    await state.clear()
    log_action(message.bot, "log_emoji", slot=slot, value=val)
    txt, ents = render(d["emoji_char_set"] + "\n\n" + d["emoji_slot_txt"],
                       label=emojis.label(slot, lang), slot=slot, char=emojis.char(slot),
                       cid=emojis.cid(slot) or d["emoji_no_cid"])
    await send(message.bot, message.chat.id, (txt, ents), akb.emoji_slot_kb(lang, slot))


@r.callback_query(CB.filter(F.a == "a_ereset"))
async def a_ereset_cb(cb: CallbackQuery, callback_data: CB):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    slot = callback_data.i
    emojis.reset(slot)
    log_action(cb.bot, "log_emoji", slot=slot, value="default")
    txt, ents = render(d["emoji_reset"] + "\n\n" + d["emoji_slot_txt"],
                       label=emojis.label(slot, lang), slot=slot, char=emojis.char(slot),
                       cid=emojis.cid(slot) or d["emoji_no_cid"])
    await cb_show(cb, (txt, ents), akb.emoji_slot_kb(lang, slot))


@r.callback_query(CB.filter(F.a == "a_etest"))
async def a_etest_cb(cb: CallbackQuery, callback_data: CB):
    slot = callback_data.i
    await cb_answer(cb)
    tpl = texts.t(_ulang(cb.from_user.id), "emoji_test").replace("__SLOT__", slot)
    txt, ents = render(tpl)
    try:
        await cb.bot.send_message(cb.from_user.id, txt, entities=ents)
    except TelegramBadRequest as e:
        if "custom emoji" in str(e).lower():
            emojis.disable_custom()
            txt, ents = render(tpl)
            await cb.bot.send_message(cb.from_user.id, txt, entities=ents)
        else:
            raise


# ═══════════════ القنوات الإجبارية ═══════════════

@r.callback_query(CB.filter(F.a == "a_chan"))
async def a_chan_cb(cb: CallbackQuery):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    chans = db.channels()
    listing = "\n".join(f"• {c['title'] or c['chat_id']} (<code>{c['chat_id']}</code>)" for c in chans) or d["chan_empty_list"]
    txt, ents = render(d["chan_txt"], list=listing)
    await cb_show(cb, (txt, ents), akb.chans_kb(lang, chans))


@r.callback_query(CB.filter(F.a == "a_chana"))
async def a_chana_cb(cb: CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    d = _d(uid)
    await state.set_state(AdmSt.chan_add)
    txt, ents = render(d["chan_add_prompt"])
    await cb_show(cb, (txt, ents), cancel_kb(_ulang(uid)))


def _extract_chat_ref(message: Message) -> str:
    """يستخرج مرجع القناة من نص أو رسالة محوّلة."""
    fo = message.forward_origin
    if fo is not None and getattr(fo, "chat", None) is not None:
        return str(fo.chat.id)
    if not message.text:
        return ""
    t = message.text.strip()
    m = re.search(r"t\.me/([A-Za-z0-9_]{4,64})", t)
    if m:
        return "@" + m.group(1)
    if re.fullmatch(r"-?\d{5,25}", t):
        return t
    if re.fullmatch(r"@[A-Za-z0-9_]{4,64}", t):
        return t
    return ""


@r.message(AdmSt.chan_add)
async def chan_add_msg(message: Message, state: FSMContext):
    uid = message.from_user.id
    lang = _ulang(uid)
    d = _d(uid)
    ref = _extract_chat_ref(message)
    chat = None
    if ref:
        try:
            chat = await message.bot.get_chat(ref)
        except Exception as e:
            log.warning("get_chat failed for %s: %s", ref, e)
    if chat is None:
        txt, ents = render(d["chan_bad"])
        await send(message.bot, message.chat.id, (txt, ents), cancel_kb(lang))
        return
    username = chat.username or ""
    link = getattr(chat, "invite_link", None) or (f"https://t.me/{username}" if username else "")
    db.add_channel(chat.id, chat.title or str(chat.id), username, link)
    await state.clear()
    log_action(message.bot, "log_chan_add", title=chat.title or str(chat.id), cid=chat.id)
    txt, ents = render(d["chan_added"], title=chat.title or str(chat.id))
    await send(message.bot, message.chat.id, (txt, ents), akb.chans_kb(lang, db.channels()))


@r.callback_query(CB.filter(F.a == "a_chdel"))
async def a_chdel_cb(cb: CallbackQuery, callback_data: CB):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    cid = int(callback_data.i)
    ch = db.channel_by_id(cid)
    db.del_channel(cid)
    log_action(cb.bot, "log_chan_del", title=(ch["title"] if ch else str(cid)), cid=cid)
    txt, ents = render(d["chan_deleted"])
    await cb_show(cb, (txt, ents), akb.chans_kb(lang, db.channels()))


# ═══════════════ المستخدمون ═══════════════

def _recent_users():
    return db.q("SELECT * FROM users ORDER BY joined_at DESC, user_id DESC LIMIT 12", fetch="all")


@r.callback_query(CB.filter(F.a == "a_users"))
async def a_users_cb(cb: CallbackQuery):
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    txt, ents = render(d["users_pick"])
    await cb_show(cb, (txt, ents), akb.users_recent_kb(lang, _recent_users()))


@r.callback_query(CB.filter(F.a == "a_ufind"))
async def a_ufind_cb(cb: CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    d = _d(uid)
    await state.set_state(AdmSt.user_find)
    txt, ents = render(d["user_find_prompt"])
    await cb_show(cb, (txt, ents), cancel_kb(_ulang(uid)))


def _extract_uid(message: Message):
    fo = message.forward_origin
    if fo is not None and getattr(fo, "sender_user", None) is not None:
        return fo.sender_user.id
    if message.text and re.fullmatch(r"\d{3,15}", message.text.strip()):
        return int(message.text.strip())
    return None


@r.message(AdmSt.user_find)
async def user_find_msg(message: Message, state: FSMContext):
    uid = message.from_user.id
    lang = _ulang(uid)
    d = _d(uid)
    target_uid = _extract_uid(message)
    row = db.get_user(target_uid) if target_uid else None
    await state.clear()
    if not row:
        txt, ents = render(d["user_nf"])
        await send(message.bot, message.chat.id, (txt, ents), akb.users_recent_kb(lang, _recent_users()))
        return
    await _send_user_card(message.bot, message.chat.id, uid, row)


async def _send_user_card(bot, chat_id: int, caller_id: int, row):
    lang = _ulang(caller_id)
    d = texts.tr(lang)
    refs = db.q("SELECT COUNT(*) c FROM users WHERE referred_by=?", (row["user_id"],), fetch="one")["c"]
    reason = d["ban_reason_line"] if row["ban_reason"] else ""
    txt, ents = render(
        d["user_card"],
        name=db_name(row), uid=row["user_id"],
        username=("@" + row["username"]) if row["username"] else "—",
        phone=row["phone"] or d["no_phone"],
        lang=("العربية" if row["lang"] == "ar" else "English"),
        points=row["points"], refs=refs, buys=db.user_purchases_count(row["user_id"]),
        spent=db.user_spent(row["user_id"]), joined=row["joined_at"] or "—",
        verified=(d["yes"] if row["verified"] else d["no"]),
        banned=(d["yes"] if row["is_banned"] else d["no"]),
        admin=(d["yes"] if db.is_admin(row["user_id"]) else d["no"]),
        ban_reason=reason, reason=row["ban_reason"] or "—")
    kb = akb.user_card_kb(lang, row["user_id"], bool(row["is_banned"]), bool(row["is_admin"]),
                          caller_id == config.OWNER_ID)
    await send(bot, chat_id, (txt, ents), kb)


@r.callback_query(CB.filter(F.a == "a_user"))
async def a_user_cb(cb: CallbackQuery, callback_data: CB):
    row = db.get_user(int(callback_data.i))
    if not row:
        await cb_answer(cb, "❌")
        return
    await _send_user_card(cb.bot, cb_chat(cb), cb.from_user.id, row)
    await cb_answer(cb)


@r.callback_query(CB.filter(F.a == "a_upadd"))
async def a_upadd_cb(cb: CallbackQuery, callback_data: CB, state: FSMContext):
    uid = cb.from_user.id
    d = _d(uid)
    await state.set_state(AdmSt.pts_add)
    await state.update_data(uid=int(callback_data.i))
    txt, ents = render(d["pts_add_prompt"])
    await cb_show(cb, (txt, ents), cancel_kb(_ulang(uid)))


@r.callback_query(CB.filter(F.a == "a_upsub"))
async def a_upsub_cb(cb: CallbackQuery, callback_data: CB, state: FSMContext):
    uid = cb.from_user.id
    d = _d(uid)
    await state.set_state(AdmSt.pts_sub)
    await state.update_data(uid=int(callback_data.i))
    txt, ents = render(d["pts_sub_prompt"])
    await cb_show(cb, (txt, ents), cancel_kb(_ulang(uid)))


async def _pts_input(message: Message, state: FSMContext, sign: int):
    data = await state.get_data()
    uid = int(data.get("uid", 0))
    target = db.get_user(uid)
    lang = _ulang(message.from_user.id)
    d = _d(message.from_user.id)
    if not re.fullmatch(r"\d{1,7}", message.text.strip()):
        txt, ents = render(d["num_bad"])
        await send(message.bot, message.chat.id, (txt, ents), cancel_kb(lang))
        return
    amount = int(message.text.strip())
    if not target:
        await state.clear()
        txt, ents = render(d["user_nf"])
        await send(message.bot, message.chat.id, (txt, ents))
        return
    pts = db.add_points(uid, sign * amount)
    await state.clear()
    log_action(message.bot, "log_points", name=db_name(target),
               delta=(f"+{amount}" if sign > 0 else f"-{amount}"), points=pts)
    txt, ents = render(d["pts_done"], points=pts)
    await send(message.bot, message.chat.id, (txt, ents))
    await _send_user_card(message.bot, message.chat.id, message.from_user.id, db.get_user(uid))


@r.message(AdmSt.pts_add, F.text)
async def pts_add_msg(message: Message, state: FSMContext):
    await _pts_input(message, state, +1)


@r.message(AdmSt.pts_sub, F.text)
async def pts_sub_msg(message: Message, state: FSMContext):
    await _pts_input(message, state, -1)


@r.callback_query(CB.filter(F.a == "a_umsg"))
async def a_umsg_cb(cb: CallbackQuery, callback_data: CB, state: FSMContext):
    uid = cb.from_user.id
    d = _d(uid)
    await state.set_state(AdmSt.msg_user)
    await state.update_data(uid=int(callback_data.i))
    txt, ents = render(d["msg_prompt"])
    await cb_show(cb, (txt, ents), cancel_kb(_ulang(uid)))


@r.message(AdmSt.msg_user)
async def msg_user_msg(message: Message, state: FSMContext):
    data = await state.get_data()
    uid = int(data.get("uid", 0))
    await state.clear()
    d = _d(message.from_user.id)
    try:
        await message.send_copy(uid)
        txt, ents = render(d["msg_sent"])
    except Exception:
        txt, ents = render(d["msg_fail"])
    await send(message.bot, message.chat.id, (txt, ents))


@r.callback_query(CB.filter(F.a == "a_uban"))
async def a_uban_cb(cb: CallbackQuery, callback_data: CB, state: FSMContext):
    uid = cb.from_user.id
    d = _d(uid)
    await state.set_state(AdmSt.ban_reason)
    await state.update_data(uid=int(callback_data.i))
    txt, ents = render(d["ban_prompt"])
    await cb_show(cb, (txt, ents), cancel_kb(_ulang(uid)))


@r.message(AdmSt.ban_reason, F.text)
async def ban_reason_msg(message: Message, state: FSMContext):
    data = await state.get_data()
    uid = int(data.get("uid", 0))
    caller = message.from_user.id
    await state.clear()
    lang = _ulang(caller)
    d = _d(caller)
    row = db.get_user(uid)
    if not row:
        txt, ents = render(d["user_nf"])
        await send(message.bot, message.chat.id, (txt, ents))
        return
    if uid == config.OWNER_ID:
        txt, ents = render(d["only_owner"])
        await send(message.bot, message.chat.id, (txt, ents))
        return
    reason = "" if message.text.strip() == "-" else message.text.strip()[:200]
    db.set_ban(uid, True, reason)
    log_action(message.bot, "log_ban", name=db_name(row), uid=uid, reason=reason or "—")
    try:
        t2, e2 = render(texts.tr(row["lang"])["user_banned_notify"], reason=reason or "—")
        await message.bot.send_message(uid, t2, entities=e2)
    except Exception:
        pass
    txt, ents = render(d["ban_done"])
    await send(message.bot, message.chat.id, (txt, ents))
    await _send_user_card(message.bot, message.chat.id, caller, db.get_user(uid))


@r.callback_query(CB.filter(F.a == "a_uunban"))
async def a_uunban_cb(cb: CallbackQuery, callback_data: CB):
    uid = int(callback_data.i)
    caller = cb.from_user.id
    d = _d(caller)
    row = db.get_user(uid)
    if not row:
        await cb_answer(cb, "❌")
        return
    db.set_ban(uid, False, "")
    log_action(cb.bot, "log_unban", name=db_name(row), uid=uid)
    try:
        t2, e2 = render(texts.tr(row["lang"])["user_unban_notify"])
        await cb.bot.send_message(uid, t2, entities=e2)
    except Exception:
        pass
    txt, ents = render(d["unban_done"])
    await cb_show(cb, (txt, ents))
    await _send_user_card(cb.bot, cb_chat(cb), caller, db.get_user(uid))


@r.callback_query(CB.filter(F.a == "a_uadmin"))
async def a_uadmin_cb(cb: CallbackQuery, callback_data: CB):
    if not await owner_guard(cb):
        return
    uid = int(callback_data.i)
    caller = cb.from_user.id
    d = _d(caller)
    row = db.get_user(uid)
    if not row:
        await cb_answer(cb, "❌")
        return
    new_val = 0 if row["is_admin"] else 1
    db.set_admin(uid, bool(new_val))
    if new_val:
        log_action(cb.bot, "log_admin_add", name=db_name(row), uid=uid)
        try:
            t2, e2 = render(texts.tr(row["lang"])["admin_new_notify"])
            await cb.bot.send_message(uid, t2, entities=e2)
        except Exception:
            pass
        txt, ents = render(d["admin_added"], name=db_name(row))
    else:
        log_action(cb.bot, "log_admin_del", name=db_name(row), uid=uid)
        try:
            t2, e2 = render(texts.tr(row["lang"])["admin_del_notify"])
            await cb.bot.send_message(uid, t2, entities=e2)
        except Exception:
            pass
        txt, ents = render(d["admin_removed"])
    await cb_show(cb, (txt, ents))
    await _send_user_card(cb.bot, cb_chat(cb), caller, db.get_user(uid))


# ═══════════════ الأدمنز (أونر فقط) ═══════════════

@r.callback_query(CB.filter(F.a == "a_admins"))
async def a_admins_cb(cb: CallbackQuery):
    if not await owner_guard(cb):
        return
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = texts.tr(lang)
    admins = db.admins()
    txt, ents = render(d["admins_txt"], n=len(admins))
    await cb_show(cb, (txt, ents), akb.admins_kb(lang, admins))


@r.callback_query(CB.filter(F.a == "a_adadd"))
async def a_adadd_cb(cb: CallbackQuery, state: FSMContext):
    if not await owner_guard(cb):
        return
    uid = cb.from_user.id
    d = _d(uid)
    await state.set_state(AdmSt.admin_add)
    txt, ents = render(d["admin_add_prompt"])
    await cb_show(cb, (txt, ents), cancel_kb(_ulang(uid)))


@r.message(AdmSt.admin_add)
async def admin_add_msg(message: Message, state: FSMContext):
    if message.from_user.id != config.OWNER_ID:
        await state.clear()
        return
    uid_target = _extract_uid(message)
    await state.clear()
    d = _d(message.from_user.id)
    lang = _ulang(message.from_user.id)
    if not uid_target:
        txt, ents = render(d["text_bad"])
        await send(message.bot, message.chat.id, (txt, ents), akb.admins_kb(lang, db.admins()))
        return
    row = db.get_user(uid_target)
    if row:
        db.set_admin(uid_target, True)
        name = db_name(row)
        tlang = row["lang"]
    else:
        db.q("INSERT OR IGNORE INTO users(user_id, lang, is_admin, joined_at) VALUES(?,?,1,?)",
             (uid_target, "ar", db.now()))
        name = f"#{uid_target}"
        tlang = "ar"
    log_action(message.bot, "log_admin_add", name=name, uid=uid_target)
    try:
        t2, e2 = render(texts.tr(tlang)["admin_new_notify"])
        await message.bot.send_message(uid_target, t2, entities=e2)
    except Exception:
        pass
    txt, ents = render(d["admin_added"], name=name)
    await send(message.bot, message.chat.id, (txt, ents), akb.admins_kb(lang, db.admins()))


@r.callback_query(CB.filter(F.a == "a_addel"))
async def a_addel_cb(cb: CallbackQuery, callback_data: CB):
    if not await owner_guard(cb):
        return
    uid_target = int(callback_data.i)
    caller = cb.from_user.id
    d = _d(caller)
    row = db.get_user(uid_target)
    if not row or uid_target == config.OWNER_ID:
        await cb_answer(cb, d["admin_is_you"], alert=True)
        return
    db.set_admin(uid_target, False)
    log_action(cb.bot, "log_admin_del", name=db_name(row), uid=uid_target)
    try:
        t2, e2 = render(texts.tr(row["lang"])["admin_del_notify"])
        await cb.bot.send_message(uid_target, t2, entities=e2)
    except Exception:
        pass
    txt, ents = render(d["admin_removed"])
    await cb_show(cb, (txt, ents), akb.admins_kb(_ulang(caller), db.admins()))


# ═══════════════ الإذاعة العامة ═══════════════

@r.callback_query(CB.filter(F.a == "a_bcast"))
async def a_bcast_cb(cb: CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    d = _d(uid)
    await state.set_state(AdmSt.bcast)
    txt, ents = render(d["bcast_prompt"])
    await cb_show(cb, (txt, ents), cancel_kb(_ulang(uid)))


@r.message(AdmSt.bcast)
async def bcast_msg(message: Message, state: FSMContext):
    uid = message.from_user.id
    lang = _ulang(uid)
    d = _d(uid)
    targets = db.q("SELECT user_id FROM users WHERE is_banned=0", fetch="all")
    await state.update_data(bchat=message.chat.id, bmsg=message.message_id)
    txt, ents = render(d["bcast_confirm"], n=len(targets))
    await send(message.bot, message.chat.id, (txt, ents),
               confirm_kb(lang, "a_bgo", "a_bcancel"))


@r.callback_query(CB.filter(F.a == "a_bcancel"))
async def a_bcancel_cb(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cb.from_user.id
    d = _d(uid)
    txt, ents = render(d["bcast_cancelled"])
    await cb_show(cb, (txt, ents), back_kb(_ulang(uid), "am"))


@r.callback_query(CB.filter(F.a == "a_bgo"))
async def a_bgo_cb(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    uid = cb.from_user.id
    lang = _ulang(uid)
    d = _d(uid)
    bchat, bmsg = data.get("bchat"), data.get("bmsg")
    if not bchat or not bmsg:
        await cb_answer(cb, "❌")
        return
    await cb_answer(cb)
    txt, ents = render(d["bcast_going"])
    await send(cb.bot, cb_chat(cb), (txt, ents))
    targets = db.q("SELECT user_id FROM users WHERE is_banned=0", fetch="all")
    ok = fail = 0
    for t in targets:
        try:
            await cb.bot.copy_message(chat_id=t["user_id"], from_chat_id=bchat, message_id=bmsg)
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    log_action(cb.bot, "log_bcast", ok=ok, fail=fail)
    txt, ents = render(d["bcast_done"], ok=ok, fail=fail)
    await send(cb.bot, cb_chat(cb), (txt, ents), back_kb(lang, "am"))


# ═══════════════ النسخة الاحتياطية (أونر فقط) ═══════════════

@r.callback_query(CB.filter(F.a == "a_backup"))
async def a_backup_cb(cb: CallbackQuery):
    if not await owner_guard(cb):
        return
    uid = cb.from_user.id
    d = _d(uid)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = config.DATA_DIR / f"bot_backup_{stamp}.db"
    db.backup_to(str(path))
    log_action(cb.bot, "log_backup")
    try:
        if cb.message:
            await cb.message.answer_document(FSInputFile(str(path)), caption=d["backup_sent"])
        else:
            await cb.bot.send_document(uid, FSInputFile(str(path)), caption=d["backup_sent"])
    finally:
        try:
            path.unlink()
        except OSError:
            pass
    await cb_answer(cb)
