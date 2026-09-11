# -*- coding: utf-8 -*-
import asyncio
"""مرافق الإرسال والتعديل وسجل التعاملات / send-edit helpers + log chat."""
import logging

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from . import config, db, emojis
from .rich import render, split_rendered

log = logging.getLogger("utils")

_owner_warned = False


def _strip_custom(ents):
    return [e for e in ents if e.type != "custom_emoji"] if ents else None


async def send(bot, chat_id: int, rendered, kb: InlineKeyboardMarkup = None, **kw) -> Message:
    """إرسال رسالة مع دعم الإيموجي البريميوم وتراجع تلقائي عند الرفض."""
    text, ents = split_rendered(rendered)
    try:
        return await bot.send_message(
            chat_id=chat_id, text=text, reply_markup=kb, entities=ents, **kw)
    except TelegramBadRequest as e:
        if ents and "custom emoji" in str(e).lower():
            emojis.disable_custom()
            return await bot.send_message(
                chat_id=chat_id, text=text, reply_markup=kb, entities=_strip_custom(ents), **kw)
        raise


async def edit(msg: Message, rendered, kb: InlineKeyboardMarkup = None) -> None:
    """تعديل رسالة موجودة (يتجاهل خطأ عدم التغيير)."""
    text, ents = split_rendered(rendered)
    try:
        await msg.edit_text(text, reply_markup=kb, entities=ents)
    except TelegramBadRequest as e:
        low = str(e).lower()
        if "message is not modified" in low:
            return
        if ents and "custom emoji" in low:
            emojis.disable_custom()
            try:
                await msg.edit_text(text, reply_markup=kb, entities=_strip_custom(ents))
            except TelegramBadRequest:
                pass
            return
        if ("there is no text" in low or "message can't be edited" in low
                or "not enough rights" in low or "message to edit not found" in low):
            return
        log.warning("edit failed: %s", e)
    except TelegramForbiddenError:
        pass


async def cb_answer(cb: CallbackQuery, text: str = None, alert: bool = False):
    try:
        await cb.answer(text, show_alert=alert) if text else await cb.answer()
    except Exception:
        pass


async def cb_show(cb: CallbackQuery, rendered, kb: InlineKeyboardMarkup = None):
    """تعديل رسالة الكولباك؛ إذا تعذر التعديل أرسل رسالة جديدة."""
    text, ents = split_rendered(rendered)
    edited = False
    if cb.message:
        try:
            await cb.message.edit_text(text, reply_markup=kb, entities=ents)
            edited = True
        except TelegramBadRequest as e:
            low = str(e).lower()
            if "message is not modified" in low:
                edited = True
            elif ents and "custom emoji" in low:
                emojis.disable_custom()
                try:
                    await cb.message.edit_text(text, reply_markup=kb, entities=_strip_custom(ents))
                    edited = True
                except TelegramBadRequest:
                    edited = False
            elif ("there is no text" in low or "message can't be edited" in low
                  or "not enough rights" in low or "message to edit not found" in low):
                edited = False
            else:
                edited = False
        except TelegramForbiddenError:
            edited = False
    if not edited:
        chat_id = cb.message.chat.id if cb.message else cb.from_user.id
        try:
            await send(cb.bot, chat_id, rendered, kb)
        except TelegramForbiddenError:
            pass
    await cb_answer(cb)


def log_action(bot, log_key: str, **kw):
    """إرسال كل تعاملات البوت إلى شات السجل (fire-and-forget، صفر إزعاج لو فشل)."""
    global _owner_warned
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(_send_log(bot, log_key, kw))


async def _send_log(bot, log_key: str, kw: dict):
    global _owner_warned
    try:
        text, ents = render(_log_default(log_key), **kw)
        await bot.send_message(config.LOG_CHAT_ID, text, entities=ents)
    except Exception as e:
        log.warning("log_action failed for %s: %s", log_key, e)
        if not _owner_warned:
            _owner_warned = True
            try:
                t, en = render(
                    "⚠️ البوت ما يقدر يرسل لشات السجل!\nتأكد إنو البوت عضو/أدمن بالشات: {cid}\n\n"
                    "⚠️ Bot cannot post to the log chat!\nMake sure the bot is a member/admin of: {cid}",
                    cid=config.LOG_CHAT_ID)
                await bot.send_message(config.OWNER_ID, t, entities=en)
            except Exception:
                pass


def _log_default(key: str) -> str:
    from .texts import t
    return t("ar", key)


def full_name(u) -> str:
    n = (u.first_name or "").strip()
    if (u.last_name or "").strip():
        n += " " + u.last_name.strip()
    return n or "User"


def uname(u) -> str:
    return ("@" + u.username) if getattr(u, "username", None) else "—"


def ref_link(uid: int) -> str:
    return f"https://t.me/{config.BOT_USERNAME}?start=ref{uid}"
