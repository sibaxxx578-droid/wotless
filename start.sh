#!/usr/bin/env bash
# ملف التشغيل لمنصات النشر (Railpack / Railway...)
set -e
cd "$(dirname "$0")"

# ثبّت المتطلبات إذا ما منصّبة (سريع لو موجودة)
python -m pip install --quiet -r requirements.txt || pip3 install --quiet -r requirements.txt || true

exec python bot.py
