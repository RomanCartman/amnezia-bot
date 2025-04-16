import logging
from aiogram import Router

from service.db_instance import user_db
from utils import get_short_name
from keyboard.menu import get_main_menu_markup, get_user_main_menu
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from settings import ADMINS, MODERATORS, user_main_messages

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command(commands=["start", "help"]))
async def help_command_handler(message: Message):
    if message.from_user is None:
        await message.answer("Ошибка: невозможно получить данные пользователя.")
        return
    user_id = message.from_user.id

    if user_id in ADMINS or user_id in MODERATORS:
        sent_message = await message.answer(
            "Выберите действие:", reply_markup=get_main_menu_markup(user_id, ADMINS)
        )
        user_main_messages[user_id] = {
            "chat_id": sent_message.chat.id,
            "message_id": sent_message.message_id,
            "state": None,  # Инициализируем state явно
        }
    else:
        name = get_short_name(message.from_user)
        user_db.add_user(user_id, name)
        try:
            photo = FSInputFile("logo.png")
            await message.answer_photo(
                photo=photo,
                caption="👋 Добро пожаловать в *VPN Бот!*\n\nВыберите действие:",
                parse_mode="Markdown",
                reply_markup=get_user_main_menu(),
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке приветствия: {e}")
            await message.answer(
                "👋 Добро пожаловать!\n\nВыберите действие:",
                reply_markup=get_user_main_menu(),
            )
