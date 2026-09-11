# -*- coding: utf-8 -*-
"""حاجز الحظر / ban gate middleware."""
import logging

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from . import db, texts
from .rich import render
from .utils import send

log = logging.getLogger("mw")


class BanGate(BaseMiddleware):
    """يمنع المحظورين من استخدام البوت (عدا تحديثات عضوية القنوات)."""

    async def __call__(self, handler, event: TelegramObject, data: dict):
        # تحديثات العضوية/القنوات تمر دائماً (مهم لخصم نقاط المغادرة)
        if (getattr(event, "chat_member", None) is not None
                or getattr(event, "my_chat_member", None) is not None
                or getattr(event, "channel_post", None) is not None
                or getattr(event, "edited_channel_post", None) is not None):
            return await handler(event, data)

        msg = getattr(event, "message", None) or getattr(event, "edited_message", None)
        cb = getattr(event, "callback_query", None)
        user = None
        if msg is not None and msg.from_user and not msg.from_user.is_bot:
            user = msg.from_user
        elif cb is not None and cb.from_user and not cb.from_user.is_bot:
            user = cb.from_user

        if user is None:
            return await handler(event, data)

        row = db.get_user(user.id)
        if row and row["is_banned"] and not db.is_admin(user.id):
            d = texts.tr(row["lang"])
            extra = d["ban_reason_line"] if row["ban_reason"] else ""
            bot = data.get("bot")
            try:
                if msg is not None and bot is not None:
                    txt, ents = render(d["banned"] + extra, reason=row["ban_reason"])
                    await send(bot, msg.chat.id, (txt, ents))
                elif cb is not None:
                    await cb.answer("🚫 Banned / محظور", show_alert=True)
            except Exception:
                pass
            return  # لا تمرّر للمعالج
        return await handler(event, data)
