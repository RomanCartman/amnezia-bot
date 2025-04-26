from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from typing import Callable, Dict, Any, Awaitable
import asyncio

from settings import BOT

class AdminMessageDeletionMiddleware(BaseMiddleware):
    """middleware для удаления сообщений админов"""
    def __init__(self, admins: list):
        self.admins = admins
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message):
            if event.from_user and event.from_user.id in self.admins and event.text and event.text.startswith("/"):
                asyncio.create_task(
                    delete_message_after_delay(event.chat.id, event.message_id)
                )
        return await handler(event, data)


async def delete_message_after_delay(chat_id: int, message_id: int, delay: int = 2):
    await asyncio.sleep(delay)
    try:
        await BOT.delete_message(chat_id, message_id)
    except:
        pass