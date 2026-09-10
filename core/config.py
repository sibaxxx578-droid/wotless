"""إعدادات البوت المركزية / Central bot configuration."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data")))
DB_PATH = DATA_DIR / "bot.db"

# ─── بيانات حساسة: يمكن تجاوزها بمتغيرات البيئة ───
# يمكن تشغيل البوت هكذا:  BOT_TOKEN=xxx OWNER_ID=xxx python bot.py
BOT_TOKEN = os.getenv("BOT_TOKEN", "8567784767:AAE78VMtT8xP5br8ijALHgwwqVMEuTiRrh8")
OWNER_ID = int(os.getenv("OWNER_ID", "7337091751"))            # آيدي الأونر
LOG_CHAT_ID = int(os.getenv("LOG_CHAT_ID", "-1004291296496"))  # شات سجل كل التعاملات
DEFAULT_SUPPORT = os.getenv("SUPPORT_USERNAME", "GIKSSEM16")   # حساب الدعم الافتراضي (بدون @)

# يُضبط تلقائياً بعد تشغيل البوت (get_me) — لا تعدّله يدوياً
BOT_USERNAME = ""
