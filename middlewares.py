from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from typing import Callable, Dict, Any, Awaitable

from config import ADMIN_ID
import keyboards as kb

BLOCKED_TEXT = (
    "Siz botdan butunlay blocklandingiz. Sababini bilmoqchi bo'lsangiz "
    "Yordam bo'limidan adminga murojaat qiling."
)


def blocked_kb():
    from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Yordam")]], resize_keyboard=True)


class BlockCheckMiddleware(BaseMiddleware):
    def __init__(self, db):
        self.db = db
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user and user.id != ADMIN_ID:
            if await self.db.is_blocked(user.id):
                if isinstance(event, Message):
                    if event.text == "Yordam" or (event.text and event.text.startswith("/start")):
                        return await handler(event, data)
                    await event.answer(BLOCKED_TEXT, reply_markup=blocked_kb())
                    return
                elif isinstance(event, CallbackQuery):
                    if event.data == "main_menu":
                        await event.answer()
                        await event.message.answer(BLOCKED_TEXT, reply_markup=blocked_kb())
                        return
                    await event.answer(BLOCKED_TEXT, show_alert=True)
                    return

        return await handler(event, data)
