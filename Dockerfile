# صورة تشغيل البوت / production image
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# قاعدة البيانات بتتخزن هنا — اربط Volume على هذا المسار
# (اختياري: البيئة بتحدد المجلد عبر DATA_DIR)
ENV DATA_DIR=/app/data

CMD ["python", "bot.py"]
