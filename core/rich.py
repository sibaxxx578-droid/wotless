# -*- coding: utf-8 -*-
"""مُحرّك عرض النصوص: يدعم <b> <i> <u> <code> + {e:slot} للإيموجي (عادي/بريميوم).

يرجع (نص, قائمة MessageEntity) جاهزة للإرسال بدون parse_mode، مع حساب
الإزاحات بصيغة UTF-16 كما يطلب تلغرام تماماً.
"""
import re

from aiogram.types import MessageEntity

from . import emojis

_TOKEN_RE = re.compile(r"(\x00[a-z_]+\x01|</?b>|</?i>|</?u>|</?s>|</?code>)")
_E_RE = re.compile(r"\{e:([a-z_]+)\}")

_TAGMAP = {"b": "bold", "i": "italic", "u": "underline", "s": "strikethrough", "code": "code"}


def u16(s: str) -> int:
    """طول النص بوحدات UTF-16 (هكذا يحسب تلغرام الإزاحات)."""
    return len(s.encode("utf-16-le")) // 2


def render(template: str, **kw):
    """حوّل قالب النص إلى (text, entities)."""
    s = _E_RE.sub(lambda m: "\x00" + m.group(1) + "\x01", template)
    if kw:
        s = s.format(**kw)

    out = []
    ents = []
    pos = 0
    flags = {t: 0 for t in _TAGMAP}
    for part in _TOKEN_RE.split(s):
        if not part:
            continue
        m = _TOKEN_RE.fullmatch(part)
        if m:
            if part.startswith("\x00"):
                slot = part.strip("\x00\x01")
                ch = emojis.char(slot)
                start = pos
                out.append(ch)
                pos += u16(ch)
                if emojis.custom_allowed:
                    c = emojis.cid(slot)
                    if c:
                        ents.append(MessageEntity(
                            type="custom_emoji", offset=start, length=pos - start, custom_emoji_id=c))
            else:
                closing = part.startswith("</")
                tag = part.strip("</>")
                flags[tag] = 0 if closing else 1
            continue
        # نص عادي
        start = pos
        out.append(part)
        pos += u16(part)
        for tag, etype in _TAGMAP.items():
            if flags[tag]:
                ents.append(MessageEntity(type=etype, offset=start, length=pos - start))
    return "".join(out), ents


def split_rendered(rendered):
    """يقبل (text, entities) أو نص صريح ويرجع (text, entities)."""
    if isinstance(rendered, tuple):
        return rendered
    return rendered, None
