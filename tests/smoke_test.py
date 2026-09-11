# -*- coding: utf-8 -*-
"""اختبار سريع لكل منطق البوت بدون شبكة / offline smoke test."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config, db, emojis  # noqa: E402
from core.rich import render, u16  # noqa: E402
from core import texts  # noqa: E402
from core import keyboards as kb  # noqa: E402
from core import admin_kb as akb  # noqa: E402

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


print("== init db ==")
db.init()
emojis.init()

print("== texts coverage (ar vs en) ==")
ar_keys = set(texts.T["ar"].keys())
en_keys = set(texts.T["en"].keys())
missing_en = ar_keys - en_keys
missing_ar = en_keys - ar_keys
check("en has all ar keys", not missing_en, str(missing_en))
check("ar has all en keys", not missing_ar, str(missing_ar))

# كل قوالب النصوص تُصيَّر بدون أخطاء (بقيم تجريبية)
kw = dict(name="أحمد", points="5", uid="123", phone="+963900000000", lang="العربية",
          joined="2026-01-01 00:00", refs="2", buys="1", spent="10", reward=1,
          link="https://t.me/x", list="• q", channels="c", btn_send_contact="x",
          reason="test", amount=1, channel="ch", cat="قسم", price="9", stock="3",
          key="KEY-1", balance="4", need="2", n="1", i="1", date="x", username="u",
          v="1", slot="store", char="⭐", cid="—", label="متجر", top="t", users=1,
          sold=2, penalty=1, ban_reason="", support="GIKSSEM16", admin="نعم", value="1",
          today=1, verified=1, banned=0, refs2=0, purchases=1, revenue=1, keys=1,
          cats=1, prods=1, admins=1, s=1, c=1, t="x", total=3, ok=1, fail=0, delta="+1",
          title="chan", cid2=1)
for lang in ("ar", "en"):
    bad = []
    for k in texts.T[lang]:
        if k.startswith("btn_") or k in ("yes", "no"):
            continue
        tpl = texts.T[lang][k].replace("__SLOT__", "store")
        try:
            render(tpl, **kw, ref="x", ref_line="", product="p")
        except Exception as e:
            bad.append((k, repr(e)))
    check(f"render all {lang} templates", not bad, str(bad[:4]))

print("== utf16 entity offsets ==")
txt, ents = render("{e:store} <b>عربي text</b> {e:points} النهاية")
check("text has emoji chars", txt.startswith("🛍️") and "⭐" in txt)
for e in ents:
    seg = txt.encode("utf-16-le")[e.offset * 2:(e.offset + e.length) * 2].decode("utf-16-le")
    if e.type == "bold":
        check("bold entity covers exact text", seg == "عربي text", repr(seg))
    if e.type == "custom_emoji":
        check("custom emoji offset", seg in ("🛍️", "🛍", "⭐", "⭐️"), repr(seg))

# محاكاة آيدي بريميوم
emojis.set_cid("store", "5360481542747122286")
txt2, ents2 = render("{e:store} hi")
ces = [e for e in ents2 if e.type == "custom_emoji"]
check("premium entity emitted", len(ces) == 1 and ces[0].custom_emoji_id == "5360481542747122286")
emojis.reset("store")

print("== users / referral / penalty ==")
db.q("DELETE FROM users")
u1 = db.create_user(111, "Owner", "", "owner", "ar", None)
u2 = db.create_user(222, "Referrer", "", "ref", "ar", None)
u3 = db.create_user(333, "Joined", "", "j", "en", 222)
check("created 3 users", db.get_user(111) and db.get_user(222) and db.get_user(333))
check("referred_by set", db.get_user(333)["referred_by"] == 222)
db.set_phone_verified(333, "+963900000001")
check("verified", db.get_user(333)["verified"] == 1)
pts = db.add_points(222, db.get_setting_int("referral_reward", 1))
check("reward credited", pts == 1, str(pts))
pts = db.add_points(222, -db.get_setting_int("referral_penalty", 1))
check("penalty deducted", pts == 0, str(pts))
db.q("UPDATE users SET ref_credited=1 WHERE user_id=333")
db.set_ban(333, True, "تجربة")
check("banned", db.get_user(333)["is_banned"] == 1)
db.set_ban(333, False, "")
check("unbanned", db.get_user(333)["is_banned"] == 0)
check("is_admin owner", db.is_admin(config.OWNER_ID))
db.set_admin(111, True)
check("admin flag", db.is_admin(111))
db.set_admin(111, False)

print("== store flow ==")
cid_ = db.q("INSERT INTO categories(name_ar, name_en, created_at) VALUES(?,?,?)",
            ("تطبيقات", "Apps", db.now())).lastrowid
pid = db.q("INSERT INTO products(category_id, name_ar, name_en, price, created_at) VALUES(?,?,?,?,?)",
           (cid_, "نتفليكس", "Netflix", 5, db.now())).lastrowid
for k in ("K1", "K2", "K3"):
    db.q("INSERT INTO keys(product_id, key_text) VALUES(?,?)", (pid, k))
check("stock=3", db.stock_count(pid) == 3)
db.set_points(222, 10)
u = db.get_user(222)
check("balance=10", u["points"] == 10)
key = db.pop_key(pid)
check("pop key", key["key_text"] == "K1")
db.add_points(222, -5)
db.q("UPDATE keys SET sold_to=?, sold_at=? WHERE id=?", (222, db.now(), key["id"]))
db.add_purchase(222, pid, "نتفليكس", key["key_text"], 5)
check("stock=2 after sale", db.stock_count(pid) == 2)
check("balance=5 after sale", db.get_user(222)["points"] == 5)
check("purchase saved", db.user_purchases_count(222) == 1 and db.user_purchases(222)[0]["key_text"] == "K1")
check("spent=5", db.user_spent(222) == 5)
check("sold=1", db.sold_count(pid) == 1)

print("== stats ==")
s = db.stats()
check("stats users>=3", s["users"] >= 3)
check("stats revenue>=5", s["revenue"] >= 5)
check("stats keys_stock>=2", s["keys_stock"] >= 2)

print("== settings ==")
db.set_setting("referral_reward", "7")
check("setting updated", db.get_setting_int("referral_reward", 1) == 7)
db.set_setting("referral_reward", "1")
check("support default", db.get_setting("support") == config.DEFAULT_SUPPORT)

print("== channels ==")
db.add_channel(-1001234567890, "قناة الاختبار", "testchannel", "https://t.me/testchannel")
check("channel added", len(db.channels()) == 1)
check("channel by id", db.channel_by_id(-1001234567890)["title"] == "قناة الاختبار")
db.del_channel(-1001234567890)
check("channel deleted", len(db.channels()) == 0)

print("== backup ==")
bpath = str(config.DATA_DIR / "smoke_backup.db")
db.backup_to(bpath)
check("backup file", os.path.exists(bpath) and os.path.getsize(bpath) > 0)
os.unlink(bpath)

print("== keyboards build ==")
chans = [{"chat_id": -100, "title": "C", "username": "c", "link": ""}]
cats_rows = db.cats()
prods_rows = db.all_products()
prow = db.product_by_id(pid)
for lang in ("ar", "en"):
    kb.main_menu(lang, True)
    kb.settings_kb(lang)
    kb.gate_kb(lang, chans)
    kb.store_cats_kb(lang, cats_rows)
    kb.cat_products_kb(lang, cid_, prods_rows)
    kb.product_kb(lang, pid, cid_, True)
    kb.confirm_buy_kb(lang, pid)
    kb.account_kb(lang, "https://t.me/b?start=ref1")
    kb.purchases_kb(lang, db.user_purchases(222))
    kb.support_kb(lang, "GIKSSEM16")
    kb.contact_kb(lang)
    kb.cancel_kb(lang)
    kb.confirm_kb(lang, "a", "b", "1")
    akb.admin_main(lang, config.OWNER_ID)
    akb.admin_main(lang, 999)
    akb.cats_kb(lang, cats_rows)
    akb.cat_rename_kb(lang, cid_)
    akb.prods_kb(lang, prods_rows)
    akb.prod_ops_kb(lang, pid)
    akb.cats_pick_kb(lang, cats_rows, "a_pmove2", pid)
    akb.keys_kb(lang, prods_rows)
    akb.keys_ops_kb(lang, pid)
    akb.ref_kb(lang, 1, 1, "GIKSSEM16")
    akb.emoji_slots_kb(lang)
    akb.emoji_slot_kb(lang, "store")
    akb.chans_kb(lang, db.channels())
    akb.users_recent_kb(lang, db.q("SELECT * FROM users LIMIT 5", fetch="all"))
    akb.user_card_kb(lang, 222, False, False, True)
    akb.admins_kb(lang, db.admins())
check("all keyboards built for ar+en", True)

print("== callback pack/unpack roundtrip ==")
from core.callbacks import CB  # noqa: E402
data = CB(a="a_eslot", i="store").pack()
un = CB.unpack(data)
check("cb roundtrip", un.a == "a_eslot" and un.i == "store" and len(data) <= 64)

print()
print(f"RESULT: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
