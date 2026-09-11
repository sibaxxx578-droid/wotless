# -*- coding: utf-8 -*-
"""إيموجيات الواجهة (عادية + بريميوم عبر custom_emoji_id) / UI emoji slots.

مهم / Important:
- الحرف (char): إيموجي عادي يظهر للأزرار وكمظهر بديل دائماً.
- custom_id: آيدي إيموجي تلغرام بريميوم. تظهر الإيموجي البريميوم في نصوص
  الرسائل فقط إذا كان صاحب البوت مشترك Telegram Premium أو يملك اسم Fragment،
  وفي حال عدم توفر ذلك يرجع البوت تلقائياً للحرف العادي.
"""
from . import db

# slot -> الحرف الافتراضي
DEFAULTS = {
    "wave": "👋", "store": "🛍️", "account": "👤", "purchases": "🧾", "settings": "⚙️",
    "support": "💬", "points": "⭐", "referral": "🎁", "key": "🔑", "category": "📂",
    "back": "↪️", "success": "✅", "error": "❌", "warning": "⚠️", "ban": "🚫",
    "channel": "📢", "phone": "📱", "admin": "🛡️", "stats": "📊", "lang": "🌐",
    "edit": "✏️", "add": "➕", "delete": "🗑", "money": "💰", "box": "📦",
    "users": "👥", "id": "🪪", "fire": "🔥", "send": "📨",
}

LABELS_AR = {
    "wave": "الترحيب", "store": "المتجر", "account": "حسابي", "purchases": "مشترياتي",
    "settings": "الإعدادات", "support": "الدعم", "points": "النقاط", "referral": "الإحالة",
    "key": "المفتاح", "category": "الأقسام", "back": "رجوع", "success": "نجاح",
    "error": "خطأ", "warning": "تحذير", "ban": "حظر", "channel": "القنوات",
    "phone": "الهاتف", "admin": "الأدمن", "stats": "الإحصائيات", "lang": "اللغة",
    "edit": "تعديل", "add": "إضافة", "delete": "حذف", "money": "المال", "box": "الصندوق",
    "users": "المستخدمون", "id": "الآيدي", "fire": "النار", "send": "إرسال",
}
LABELS_EN = {
    "wave": "Welcome", "store": "Store", "account": "Account", "purchases": "Purchases",
    "settings": "Settings", "support": "Support", "points": "Points", "referral": "Referral",
    "key": "Key", "category": "Categories", "back": "Back", "success": "Success",
    "error": "Error", "warning": "Warning", "ban": "Ban", "channel": "Channels",
    "phone": "Phone", "admin": "Admin", "stats": "Statistics", "lang": "Language",
    "edit": "Edit", "add": "Add", "delete": "Delete", "money": "Money", "box": "Box",
    "users": "Users", "id": "ID", "fire": "Fire", "send": "Send",
}

_cache: dict = {}          # slot -> (char, custom_id)
custom_allowed: bool = True  # يُطفأ تلقائياً إذا رفض تلغرام الإيموجي البريميوم


def init():
    _cache.clear()
    for slot, ch in DEFAULTS.items():
        db.q("INSERT OR IGNORE INTO emojis(slot, char, custom_id) VALUES(?,?,?)", (slot, ch, None))
    for row in db.q("SELECT * FROM emojis", fetch="all"):
        _cache[row["slot"]] = (row["char"] or DEFAULTS.get(row["slot"], "⭐"), row["custom_id"])


def char(slot: str) -> str:
    if slot in _cache:
        return _cache[slot][0]
    return DEFAULTS.get(slot, "⭐")


def cid(slot: str) -> str:
    return (_cache.get(slot) or (None, None))[1] or ""


def label(slot: str, lang: str) -> str:
    return (LABELS_AR if lang == "ar" else LABELS_EN).get(slot, slot)


def slots():
    return list(DEFAULTS.keys())


def set_char(slot: str, ch: str):
    db.q("INSERT INTO emojis(slot, char, custom_id) VALUES(?,?,?) "
         "ON CONFLICT(slot) DO UPDATE SET char=excluded.char", (slot, ch, cid(slot)))
    _cache[slot] = (ch, _cache.get(slot, (None, None))[1])


def set_cid(slot: str, custom_id: str):
    db.q("INSERT INTO emojis(slot, char, custom_id) VALUES(?,?,?) "
         "ON CONFLICT(slot) DO UPDATE SET custom_id=excluded.custom_id", (slot, char(slot), custom_id))
    _cache[slot] = (char(slot), custom_id or None)


def reset(slot: str):
    ch = DEFAULTS.get(slot, "⭐")
    set_char(slot, ch)
    set_cid(slot, "")


def disable_custom():
    global custom_allowed
    custom_allowed = False
