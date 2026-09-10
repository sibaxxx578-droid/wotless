# -*- coding: utf-8 -*-
"""تعريف موحّد لكولباكات الأزرار / single callback factory."""
from aiogram.filters.callback_data import CallbackData


class CB(CallbackData, prefix="m"):
    a: str          # action
    i: str = ""     # id / extra payload
