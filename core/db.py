# -*- coding: utf-8 -*-
"""التعريفات العامة لقواعد البيانات / DB schema + helpers (SQLite ملف واحد)."""
import sqlite3
from datetime import datetime, timezone

from . import config

_conn: sqlite3.Connection = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id      INTEGER PRIMARY KEY,
    first_name   TEXT DEFAULT '',
    last_name    TEXT DEFAULT '',
    username     TEXT DEFAULT '',
    phone        TEXT DEFAULT '',
    lang         TEXT DEFAULT 'ar',
    points       INTEGER NOT NULL DEFAULT 0,
    is_admin     INTEGER NOT NULL DEFAULT 0,
    is_banned    INTEGER NOT NULL DEFAULT 0,
    ban_reason   TEXT DEFAULT '',
    verified     INTEGER NOT NULL DEFAULT 0,
    referred_by  INTEGER,
    ref_credited INTEGER NOT NULL DEFAULT 0,
    joined_at    TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS categories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name_ar    TEXT NOT NULL,
    name_en    TEXT NOT NULL,
    created_at TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL,
    name_ar     TEXT NOT NULL,
    name_en     TEXT NOT NULL,
    price       INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS keys (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    key_text   TEXT NOT NULL,
    sold_to    INTEGER,
    sold_at    TEXT
);
CREATE TABLE IF NOT EXISTS purchases (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    product_id   INTEGER,
    product_name TEXT,
    key_text     TEXT,
    price        INTEGER,
    created_at   TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS channels (
    chat_id  INTEGER PRIMARY KEY,
    title    TEXT DEFAULT '',
    username TEXT DEFAULT '',
    link     TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS settings (
    k TEXT PRIMARY KEY,
    v TEXT
);
CREATE TABLE IF NOT EXISTS emojis (
    slot      TEXT PRIMARY KEY,
    char      TEXT,
    custom_id TEXT
);
"""


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")


def init() -> None:
    global _conn
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(config.DB_PATH)
    _conn.row_factory = sqlite3.Row
    _conn.execute("PRAGMA journal_mode=WAL")
    _conn.executescript(SCHEMA)
    _conn.commit()
    # الإعدادات الافتراضية / default settings
    defaults = {
        "referral_reward": "1",          # نقاط لكل إحالة ناجحة
        "referral_penalty": "1",         # نقاط تُخصم عند مغادرة قناة إجبارية
        "support": config.DEFAULT_SUPPORT,
    }
    for k, v in defaults.items():
        q("INSERT OR IGNORE INTO settings(k, v) VALUES(?, ?)", (k, v))


def q(sql: str, params=(), fetch: str = None):
    """تنفيذ استعلام. fetch: None | 'one' | 'all'."""
    cur = _conn.execute(sql, params)
    if not sql.lstrip().lower().startswith("select"):
        _conn.commit()
    if fetch == "one":
        return cur.fetchone()
    if fetch == "all":
        return cur.fetchall()
    return cur


# ─── المستخدمون ───
def get_user(uid: int):
    return q("SELECT * FROM users WHERE user_id=?", (uid,), fetch="one")


def create_user(uid: int, first: str, last: str, username: str, lang: str, referred_by=None):
    q(
        "INSERT OR IGNORE INTO users(user_id, first_name, last_name, username, lang, referred_by, joined_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (uid, first or "", last or "", username or "", lang, referred_by, now()),
    )
    return get_user(uid)


def update_profile(uid: int, first: str, last: str, username: str):
    q("UPDATE users SET first_name=?, last_name=?, username=? WHERE user_id=?",
      (first or "", last or "", username or "", uid))


def set_phone_verified(uid: int, phone: str):
    q("UPDATE users SET phone=?, verified=1 WHERE user_id=?", (phone, uid))


def set_lang(uid: int, lang: str):
    q("UPDATE users SET lang=? WHERE user_id=?", (lang, uid))


def add_points(uid: int, delta: int) -> int:
    q("UPDATE users SET points = points + ? WHERE user_id=?", (delta, uid))
    return get_user(uid)["points"]


def set_points(uid: int, value: int):
    q("UPDATE users SET points=? WHERE user_id=?", (value, uid))


def set_referred_by(uid: int, rid: int):
    q("UPDATE users SET referred_by=? WHERE user_id=? AND referred_by IS NULL", (rid, uid))


def set_ban(uid: int, banned: bool, reason: str = ""):
    q("UPDATE users SET is_banned=?, ban_reason=? WHERE user_id=?", (1 if banned else 0, reason, uid))


def set_admin(uid: int, admin: bool):
    q("UPDATE users SET is_admin=? WHERE user_id=?", (1 if admin else 0, uid))


def is_admin(uid: int) -> bool:
    if uid == config.OWNER_ID:
        return True
    row = get_user(uid)
    return bool(row and row["is_admin"])


def admins() -> list:
    return q("SELECT * FROM users WHERE is_admin=1 ORDER BY user_id", fetch="all")


# ─── الإعدادات ───
def get_setting(key: str, default: str = "") -> str:
    row = q("SELECT v FROM settings WHERE k=?", (key,), fetch="one")
    return row["v"] if row else default


def set_setting(key: str, value: str):
    q("INSERT INTO settings(k, v) VALUES(?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (key, str(value)))


def get_setting_int(key: str, default: int = 0) -> int:
    try:
        return int(get_setting(key, str(default)))
    except (TypeError, ValueError):
        return default


# ─── الأقسام والمنتجات والمفاتيح ───
def cats():
    return q("SELECT * FROM categories ORDER BY id", fetch="all")


def cat_by_id(cid: int):
    return q("SELECT * FROM categories WHERE id=?", (cid,), fetch="one")


def products_of(cid: int):
    return q("SELECT * FROM products WHERE category_id=? ORDER BY id", (cid,), fetch="all")


def all_products():
    return q("SELECT * FROM products ORDER BY category_id, id", fetch="all")


def product_by_id(pid: int):
    return q("SELECT * FROM products WHERE id=?", (pid,), fetch="one")


def stock_count(pid: int) -> int:
    row = q("SELECT COUNT(*) c FROM keys WHERE product_id=? AND sold_to IS NULL", (pid,), fetch="one")
    return row["c"]


def pop_key(pid: int):
    return q("SELECT * FROM keys WHERE product_id=? AND sold_to IS NULL ORDER BY id LIMIT 1",
             (pid,), fetch="one")


def sold_count(pid: int) -> int:
    row = q("SELECT COUNT(*) c FROM keys WHERE product_id=? AND sold_to IS NOT NULL", (pid,), fetch="one")
    return row["c"]


# ─── المشتريات ───
def add_purchase(uid: int, product_id: int, product_name: str, key_text: str, price: int):
    q("INSERT INTO purchases(user_id, product_id, product_name, key_text, price, created_at) VALUES(?,?,?,?,?,?)",
      (uid, product_id, product_name, key_text, price, now()))


def user_purchases(uid: int, limit: int = 10):
    return q("SELECT * FROM purchases WHERE user_id=? ORDER BY id DESC LIMIT ?", (uid, limit), fetch="all")


def user_purchases_count(uid: int) -> int:
    row = q("SELECT COUNT(*) c FROM purchases WHERE user_id=?", (uid,), fetch="one")
    return row["c"]


def user_spent(uid: int) -> int:
    row = q("SELECT COALESCE(SUM(price),0) s FROM purchases WHERE user_id=?", (uid,), fetch="one")
    return row["s"]


# ─── القنوات الإجبارية ───
def channels():
    return q("SELECT * FROM channels ORDER BY chat_id", fetch="all")


def channel_by_id(chat_id: int):
    return q("SELECT * FROM channels WHERE chat_id=?", (chat_id,), fetch="one")


def add_channel(chat_id: int, title: str, username: str, link: str):
    q("INSERT INTO channels(chat_id, title, username, link) VALUES(?,?,?,?) "
      "ON CONFLICT(chat_id) DO UPDATE SET title=excluded.title, username=excluded.username, link=excluded.link",
      (chat_id, title or "", username or "", link or ""))


def del_channel(chat_id: int):
    q("DELETE FROM channels WHERE chat_id=?", (chat_id,))


# ─── إحصائيات ───
def stats() -> dict:
    def one(sql, params=()):
        return q(sql, params, fetch="one")
    today = now()[:10]
    s = {
        "users": one("SELECT COUNT(*) c FROM users")["c"],
        "users_today": one("SELECT COUNT(*) c FROM users WHERE joined_at LIKE ?", (today + "%",))["c"],
        "verified": one("SELECT COUNT(*) c FROM users WHERE verified=1")["c"],
        "banned": one("SELECT COUNT(*) c FROM users WHERE is_banned=1")["c"],
        "refs": one("SELECT COUNT(*) c FROM users WHERE referred_by IS NOT NULL")["c"],
        "points": one("SELECT COALESCE(SUM(points),0) s FROM users")["s"],
        "purchases": one("SELECT COUNT(*) c FROM purchases")["c"],
        "revenue": one("SELECT COALESCE(SUM(price),0) s FROM purchases")["s"],
        "keys_stock": one("SELECT COUNT(*) c FROM keys WHERE sold_to IS NULL")["c"],
        "channels": one("SELECT COUNT(*) c FROM channels")["c"],
        "admins": one("SELECT COUNT(*) c FROM users WHERE is_admin=1")["c"] + (1 if get_user(config.OWNER_ID) else 0),
        "cats": one("SELECT COUNT(*) c FROM categories")["c"],
        "prods": one("SELECT COUNT(*) c FROM products")["c"],
    }
    s["top"] = q(
        "SELECT product_name, COUNT(*) c, COALESCE(SUM(price),0) s FROM purchases "
        "GROUP BY product_name ORDER BY c DESC LIMIT 5", fetch="all")
    return s


# ─── نسخة احتياطية ───
def backup_to(path: str):
    dest = sqlite3.connect(path)
    try:
        _conn.backup(dest)
    finally:
        dest.close()
