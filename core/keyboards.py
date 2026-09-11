# -*- coding: utf-8 -*-
"""الكولباكات وشاشات المستخدم / user keyboards."""
from aiogram.types import (CopyTextButton, InlineKeyboardButton, InlineKeyboardMarkup,
                           KeyboardButton, ReplyKeyboardMarkup)

from . import emojis, texts
from .callbacks import CB
from .config import OWNER_ID


def _b(label: str, action: str, item: str = "") -> InlineKeyboardButton:
    return InlineKeyboardButton(text=label, callback_data=CB(a=action, i=item).pack())


def main_menu(lang: str, is_admin: bool) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    rows = [
        [InlineKeyboardButton(text=f"{emojis.char('store')} {d['btn_store']}", callback_data=CB(a="store").pack())],
        [
            InlineKeyboardButton(text=f"{emojis.char('account')} {d['btn_account']}", callback_data=CB(a="acc").pack()),
            InlineKeyboardButton(text=f"{emojis.char('purchases')} {d['btn_purchases']}", callback_data=CB(a="pur").pack()),
        ],
        [
            InlineKeyboardButton(text=f"{emojis.char('settings')} {d['btn_settings']}", callback_data=CB(a="set").pack()),
            InlineKeyboardButton(text=f"{emojis.char('support')} {d['btn_support']}", callback_data=CB(a="sup").pack()),
        ],
    ]
    if is_admin:
        rows.append([InlineKeyboardButton(
            text=f"{emojis.char('admin')} {d['btn_admin']}", callback_data=CB(a="am").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def settings_kb(lang: str) -> InlineKeyboardMarkup:
    mark_ar = "✔️ " if lang == "ar" else ""
    mark_en = "✔️ " if lang == "en" else ""
    d = texts.tr(lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"{mark_ar}{d['btn_lang_ar']}", callback_data=CB(a="lang", i="ar").pack()),
            InlineKeyboardButton(text=f"{mark_en}{d['btn_lang_en']}", callback_data=CB(a="lang", i="en").pack()),
        ],
        [_b(f"{emojis.char('back')} {d['btn_back']}", "menu")],
    ])


def gate_kb(lang: str, channels: list) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    rows = []
    for ch in channels:
        url = ch["link"] or (f"https://t.me/{ch['username']}" if ch["username"] else None)
        if url:
            rows.append([InlineKeyboardButton(text=f"{emojis.char('channel')} {ch['title'] or 'Channel'}", url=url)])
    rows.append([InlineKeyboardButton(
        text=f"{emojis.char('success')} {d['btn_check']}", callback_data=CB(a="gate").pack())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def back_kb(lang: str, action: str = "menu", item: str = "") -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    label = d["btn_back_admin"] if action == "am" else d["btn_back"]
    return InlineKeyboardMarkup(inline_keyboard=[[_b(f"{emojis.char('back')} {label}", action, item)]])


def store_cats_kb(lang: str, cats: list) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    rows = []
    row = []
    for c in cats:
        name = c["name_ar"] if lang == "ar" else c["name_en"]
        row.append(InlineKeyboardButton(
            text=f"{emojis.char('category')} {name}", callback_data=CB(a="cat", i=str(c["id"])).pack()))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([_b(f"{emojis.char('back')} {d['btn_back']}", "menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cat_products_kb(lang: str, cat_id: int, prods: list) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    rows = []
    for p in prods:
        name = p["name_ar"] if lang == "ar" else p["name_en"]
        rows.append([InlineKeyboardButton(
            text=d["prod_btn"].format(name=name, price=p["price"]),
            callback_data=CB(a="prod", i=str(p["id"])).pack())])
    rows.append([_b(f"{emojis.char('back')} {d['btn_back']}", "store")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_kb(lang: str, product_id: int, cat_id: int, in_stock: bool) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    rows = []
    if in_stock:
        rows.append([InlineKeyboardButton(
            text=f"{emojis.char('money')} {d['btn_buy']}",
            callback_data=CB(a="buyc", i=str(product_id)).pack())])
    rows.append([_b(f"{emojis.char('back')} {d['btn_back']}", "cat", str(cat_id))])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_buy_kb(lang: str, product_id: int) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=f"{emojis.char('success')} {d['btn_yes']}",
                                 callback_data=CB(a="buyd", i=str(product_id)).pack()),
            InlineKeyboardButton(text=f"{emojis.char('error')} {d['btn_no']}",
                                 callback_data=CB(a="cat", i="").pack()),
        ],
        [_b(f"{emojis.char('back')} {d['btn_back']}", "store")],
    ])


def account_kb(lang: str, link: str) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{emojis.char('referral')} {d['btn_copy_link']}", copy_text=CopyTextButton(text=link))],
        [_b(f"{emojis.char('back')} {d['btn_back']}", "menu")],
    ])


def purchases_kb(lang: str, purchases: list) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    rows = []
    row = []
    for p in purchases:
        key = p["key_text"] or ""
        if len(key) <= 64:  # حد تلغرام لزر النسخ
            row.append(InlineKeyboardButton(
                text=f"{emojis.char('key')} {(p['product_name'] or '')[:18]}",
                copy_text=CopyTextButton(text=key)))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([_b(f"{emojis.char('back')} {d['btn_back']}", "menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def support_kb(lang: str, username: str) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"{emojis.char('support')} @{username}", url=f"https://t.me/{username}")],
        [_b(f"{emojis.char('back')} {d['btn_back']}", "menu")],
    ])


def contact_kb(lang: str) -> ReplyKeyboardMarkup:
    d = texts.tr(lang)
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=f"{emojis.char('phone')} {d['btn_send_contact']}", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True)


def cancel_kb(lang: str) -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    return InlineKeyboardMarkup(inline_keyboard=[[_b(f"{emojis.char('error')} {d['btn_cancel']}", "cancel")]])


def confirm_kb(lang: str, yes: str, no: str, item: str = "") -> InlineKeyboardMarkup:
    d = texts.tr(lang)
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{emojis.char('success')} {d['btn_yes']}", callback_data=CB(a=yes, i=item).pack()),
        InlineKeyboardButton(text=f"{emojis.char('error')} {d['btn_no']}", callback_data=CB(a=no, i=item).pack()),
    ]])
