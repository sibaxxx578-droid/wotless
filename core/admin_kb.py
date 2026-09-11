# -*- coding: utf-8 -*-
"""لوحات الأدمن / admin keyboards."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from . import emojis, texts
from .callbacks import CB
from .config import OWNER_ID


def _b(label: str, action: str, item: str = "") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=label, callback_data=CB(a=action, i=item).pack())


def _small(label: str, action: str, item: str = "") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=label, callback_data=CB(a=action, i=item).pack())


def admin_main(lang: str, uid: int) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    is_owner = uid == OWNER_ID
    rows = [
        [
            _b(f"{emojis.char('category')} {d['am_cats']}", "a_cat"),
            _b(f"{emojis.char('box')} {d['am_prods']}", "a_prods"),
        ],
        [
            _b(f"{emojis.char('key')} {d['am_keys']}", "a_keys"),
            _b(f"{emojis.char('stats')} {d['am_stats']}", "a_stats"),
        ],
        [
            _b(f"{emojis.char('referral')} {d['am_ref']}", "a_ref"),
            _b(f"{emojis.char('settings')} {d['am_emoji']}", "a_emoji"),
        ],
        [
            _b(f"{emojis.char('channel')} {d['am_chan']}", "a_chan"),
            _b(f"{emojis.char('users')} {d['am_users']}", "a_users"),
        ],
        [
            _b(f"{emojis.char('send')} {d['am_bcast']}", "a_bcast"),
        ],
    ]
    if is_owner:
        rows.append([_b(f"{emojis.char('admin')} {d['am_admins']}", "a_admins")])
        rows.append([_b(f"{emojis.char('box')} {d['am_backup']}", "a_backup")])
    rows.append([_b(f"{emojis.char('back')} {d['am_exit']}", "menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cats_kb(lang: str, cats: list) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    add_label = f"{emojis.char('add')} إضافة قسم" if lang == "ar" else f"{emojis.char('add')} Add category"
    rows = [[_b(add_label, "a_cata")]]
    for c in cats:
        rows.append([
            InlineKeyboardButton(
                text=f"{emojis.char('edit')} {c['name_ar'] if lang == 'ar' else c['name_en']}",
                callback_data=CB(a="a_cren1", i=str(c["id"])).pack()),
            _small(f"{emojis.char('delete')}", "a_cdel1", str(c["id"])),
        ])
    rows.append([_b(f"{emojis.char('back')} {d['btn_back_admin']}", "am")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cat_rename_kb(lang: str, cid: int) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [_b("العربية / Arabic", "a_cren_ar", str(cid)), _b("English / الإنجليزية", "a_cren_en", str(cid))],
        [_b(f"{emojis.char('back')} {d['btn_back_admin']}", "a_cat")],
    ])


def prods_kb(lang: str, prods: list) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    rows = [[_b(f"{emojis.char('add')} إضافة منتج" if lang == "ar" else f"{emojis.char('add')} Add product", "a_proda")]]
    for p in prods:
        name = p["name_ar"] if lang == "ar" else p["name_en"]
        rows.append([InlineKeyboardButton(
            text=f"{emojis.char('edit')} {name} — {p['price']}⭐",
            callback_data=CB(a="a_prod", i=str(p["id"])).pack())])
    rows.append([_b(f"{emojis.char('back')} {d['btn_back_admin']}", "am")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def prod_ops_kb(lang: str, pid: int) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            _b(f"{emojis.char('edit')} {d['prod_edit_ar']}", "a_pname", f"{pid}_ar"),
            _b(f"{emojis.char('edit')} {d['prod_edit_en']}", "a_pname", f"{pid}_en"),
        ],
        [
            _b(f"{emojis.char('money')} {d['prod_edit_price']}", "a_pprice", str(pid)),
            _b(f"{emojis.char('category')} {d['prod_edit_move']}", "a_pmove", str(pid)),
        ],
        [
            _b(f"{emojis.char('add')} {d['am_keys']}", "a_kadd", str(pid)),
            _b(f"{emojis.char('delete')} {d['prod_edit_delete']}", "a_pdel1", str(pid)),
        ],
        [_b(f"{emojis.char('back')} {d['btn_back_admin']}", "a_prods")],
    ])


def cats_pick_kb(lang: str, cats: list, action: str, pid: int) -> InlineKeyboardMarkup:
    """اختيار قسم (لنقل منتج)."""
    d = texts.tr(lang)
    rows = []
    for c in cats:
        name = c["name_ar"] if lang == "ar" else c["name_en"]
        rows.append([_b(f"{emojis.char('category')} {name}", action, f"{pid}_{c['id']}")])
    rows.append([_b(f"{emojis.char('back')} {d['btn_back_admin']}", "a_prods")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def keys_kb(lang: str, prods: list) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    rows = []
    for p in prods:
        name = p["name_ar"] if lang == "ar" else p["name_en"]
        rows.append([InlineKeyboardButton(
            text=f"{emojis.char('key')} {name}",
            callback_data=CB(a="a_kinfo", i=str(p["id"])).pack())])
    rows.append([_b(f"{emojis.char('back')} {d['btn_back_admin']}", "am")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def keys_ops_kb(lang: str, pid: int) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            _b(f"{emojis.char('add')} إضافة مفاتيح" if lang == "ar" else f"{emojis.char('add')} Add keys", "a_kadd", str(pid)),
            _b(f"{emojis.char('box')} تصدير" if lang == "ar" else f"{emojis.char('box')} Export", "a_kexp", str(pid)),
        ],
        [_b(f"{emojis.char('delete')} تصفير المخزون" if lang == "ar" else f"{emojis.char('delete')} Clear stock", "a_kclr1", str(pid))],
        [_b(f"{emojis.char('back')} {d['btn_back_admin']}", "a_keys")],
    ])


def ref_kb(lang: str, reward: int, penalty: int, support: str) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [_b(d["ref_reward_btn"].format(v=reward), "a_refset", "referral_reward"),
         _b(d["ref_penalty_btn"].format(v=penalty), "a_refset", "referral_penalty")],
        [_b(d["ref_support_btn"].format(v=support), "a_refset", "support")],
        [_b(f"{emojis.char('back')} {d['btn_back_admin']}", "am")],
    ])


def emoji_slots_kb(lang: str) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    rows = []
    row = []
    for slot in emojis.slots():
        row.append(InlineKeyboardButton(
            text=f"{emojis.char(slot)} {emojis.label(slot, lang)}",
            callback_data=CB(a="a_eslot", i=slot).pack()))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([_b(f"{emojis.char('back')} {d['btn_back_admin']}", "am")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def emoji_slot_kb(lang: str, slot: str) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [_b(f"{emojis.char('id')} ضبط آيدي بريميوم" if lang == "ar" else f"{emojis.char('id')} Set premium ID", "a_ecid", slot)],
        [_b(f"{emojis.char('edit')} تغيير الحرف" if lang == "ar" else f"{emojis.char('edit')} Change char", "a_echar", slot),
         _b(f"{emojis.char('settings')} افتراضي" if lang == "ar" else f"{emojis.char('settings')} Default", "a_ereset", slot)],
        [_b(f"🧪 {'معاينة' if lang == 'ar' else 'Preview'}", "a_etest", slot)],
        [_b(f"{emojis.char('back')} {d['btn_back_admin']}", "a_emoji")],
    ])


def chans_kb(lang: str, chans: list) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    rows = []
    for c in chans:
        rows.append([_b(f"{emojis.char('delete')} {c['title'] or c['chat_id']}", "a_chdel", str(c["chat_id"]))])
    rows.append([_b(f"{emojis.char('add')} إضافة قناة" if lang == "ar" else f"{emojis.char('add')} Add channel", "a_chana")])
    rows.append([_b(f"{emojis.char('back')} {d['btn_back_admin']}", "am")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def users_recent_kb(lang: str, users: list) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    rows = [[_b(f"{emojis.char('id')} بحث بالآيدي" if lang == "ar" else f"{emojis.char('id')} Search by ID", "a_ufind")]]
    for u in users:
        label = (u["first_name"] or str(u["user_id"]))[:20]
        rows.append([InlineKeyboardButton(
            text=f"{emojis.char('account')} {label} ({u['user_id']})",
            callback_data=CB(a="a_user", i=str(u["user_id"])).pack())])
    rows.append([_b(f"{emojis.char('back')} {d['btn_back_admin']}", "am")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def user_card_kb(lang: str, uid: int, banned: bool, is_admin: bool, caller_is_owner: bool) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    rows = [
        [_b(f"{emojis.char('add')} نقاط" if lang == "ar" else f"{emojis.char('add')} Points", "a_upadd", str(uid)),
         _b(f"{emojis.char('delete')} نقاط" if lang == "ar" else f"{emojis.char('delete')} Points", "a_upsub", str(uid))],
        [_b(f"{emojis.char('send')} رسالة" if lang == "ar" else f"{emojis.char('send')} Message", "a_umsg", str(uid))],
    ]
    if banned:
        rows.append([_b(f"{emojis.char('success')} فك الحظر" if lang == "ar" else f"{emojis.char('success')} Unban", "a_uunban", str(uid))])
    else:
        rows.append([_b(f"{emojis.char('ban')} حظر" if lang == "ar" else f"{emojis.char('ban')} Ban", "a_uban", str(uid))])
    if caller_is_owner and uid != OWNER_ID:
        rows.append([_b(f"{emojis.char('admin')} {'إزالة الأدمن' if is_admin else 'ترقية لأدمن'}"
                         if lang == "ar" else
                         f"{emojis.char('admin')} {'Demote admin' if is_admin else 'Promote to admin'}",
                         "a_uadmin", str(uid))])
    rows.append([_b(f"{emojis.char('back')} {d['btn_back_admin']}", "a_users")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admins_kb(lang: str, admins: list) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    rows = [[_b(f"{emojis.char('add')} إضافة أدمن" if lang == "ar" else f"{emojis.char('add')} Add admin", "a_adadd")]]
    for a in admins:
        label = (a["first_name"] or str(a["user_id"]))[:20]
        rows.append([_b(f"{emojis.char('delete')} {label} ({a['user_id']})", "a_addel", str(a["user_id"]))])
    rows.append([_b(f"{emojis.char('back')} {d['btn_back_admin']}", "am")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
