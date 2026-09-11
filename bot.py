# -*- coding: utf-8 -*-
"""نقطة تشغيل البوت / bot entry point.

التشغيل:  python bot.py
أو:       BOT_TOKEN=xxx OWNER_ID=xxx python bot.py
"""
import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import (TelegramConflictError, TelegramNetworkError,
                                TelegramUnauthorizedError)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat

from core import config, db, emojis
from core.mw import BanGate
from handlers import admin as admin_handlers
from handlers import user as user_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("bot")

ALLOWED_UPDATES = ["message", "callback_query", "chat_member", "my_chat_member"]


async def setup_commands(bot: Bot):
    """قائمة الأوامر: للمستخدمين ولمدراء البوت."""
    user_cmds = [
        BotCommand(command="start", description="تشغيل البوت / Start"),
        BotCommand(command="help", description="المساعدة / Help"),
        BotCommand(command="id", description="آيديك / Your ID"),
        BotCommand(command="lang", description="اللغة / Language"),
    ]
    admin_cmds = user_cmds + [BotCommand(command="admin", description="لوحة الأدمن / Admin panel")]
    try:
        await bot.set_my_commands(user_cmds, scope=BotCommandScopeAllPrivateChats())
    except Exception as e:
        log.warning("set_my_commands failed: %s", e)
    ids = {config.OWNER_ID}
    for a in db.admins():
        ids.add(a["user_id"])
    for aid in ids:
        try:
            await bot.set_my_commands(admin_cmds, scope=BotCommandScopeChat(chat_id=aid))
        except Exception:
            pass  # الأدمن ما فتح البوت بعد


async def start_port_listener(bot: Bot):
    """بعض منصات النشر تشترط منفذ مفتوح — نشغّل سيرفر HTTP خفيف إذا كان PORT مضبوطاً."""
    port = os.getenv("PORT")
    if not port:
        return
    try:
        from aiohttp import web

        async def health(_request):
            return web.Response(text="bot is running ✅")

        app = web.Application()
        app.router.add_get("/", health)
        app.router.add_get("/health", health)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", int(port))
        await site.start()
        log.info("HTTP health listener on 0.0.0.0:%s", port)
    except Exception as e:
        log.warning("port listener failed: %s", e)


async def main() -> int:
    db.init()
    emojis.init()
    log.info("database ready: %s", config.DB_PATH)

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=None,
            link_preview_is_disabled=True,
        ),
    )

    me = None
    while me is None:
        try:
            me = await bot.get_me()
        except TelegramUnauthorizedError:
            log.critical("TOKEN غير صالح! تحقق من البوت توكن من BotFather.")
            return 2
        except TelegramNetworkError as e:
            log.warning("لا يمكن الوصول لتلغرام حالياً (%s) — إعادة محاولة بعد 10 ثوانٍ...", e)
            await asyncio.sleep(10)
    config.BOT_USERNAME = me.username
    log.info("started as @%s (id=%s) — owner=%s log_chat=%s",
             me.username, me.id, config.OWNER_ID, config.LOG_CHAT_ID)

    dp = Dispatcher(storage=MemoryStorage())
    dp.update.outer_middleware(BanGate())
    # ملاحظة: راوتر الأدمن قبل راوتر المستخدم حتى تُعالج مدخلات الأدمن أولاً
    dp.include_router(admin_handlers.r)
    dp.include_router(user_handlers.r)

    # إزالة ويبهوك قديم إن وجد (بدون حذف التحديثات المعلقة)
    try:
        await bot.delete_webhook(drop_pending_updates=False)
    except Exception as e:
        log.warning("delete_webhook failed: %s", e)

    await setup_commands(bot)
    await start_port_listener(bot)

    # حلقة إعادة المحاولة عند انقطاع الشبكة أو تعارض نسخة أخرى تعمل بنفس التوكن
    while True:
        try:
            await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES)
            break
        except TelegramNetworkError as e:
            log.warning("network error, retrying in 10s: %s", e)
            await asyncio.sleep(10)
        except TelegramConflictError:
            log.warning("يوجد نسخة ثانية شغالة بنفس التوكن (409) — إعادة محاولة بعد 30 ثانية. "
                        "إذا شغّلت البوت على سيرفر آخر وقّف النسخة القديمة.")
            await asyncio.sleep(30)
        except TelegramUnauthorizedError:
            log.critical("TOKEN revoked!")
            return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except (KeyboardInterrupt, SystemExit):
        log.info("stopped.")
