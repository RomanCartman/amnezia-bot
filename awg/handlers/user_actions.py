import logging
import os
import shutil
from utils import get_profile_text
import db
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from service.db_instance import user_db
from keyboard.menu import get_user_main_menu

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "user_account")
async def user_profile(callback: CallbackQuery):
    message = callback.message
    # Явная проверка типа
    if not isinstance(message, Message):
        await callback.answer("Ошибка: бот недоступен.")
        return
    telegram_id = str(callback.from_user.id)
    logger.info(f"Пользователь {telegram_id} открыл профиль")

    user = user_db.get_user_by_telegram_id(
        telegram_id
    )

    if not user:
        await message.answer(
            "❌ Пользователь не найден. Пожалуйста, зарегистрируйтесь или свяжитесь с поддержкой."
        )
        await callback.answer()
        return

    # Форматируем дату окончания подписки
    profile_text = get_profile_text(user)

    # Безопасная замена: если текст редактировать нельзя — удалим и отправим заново
    if message.text:
        await message.edit_text(
            profile_text,
            parse_mode="Markdown",
            reply_markup=get_user_main_menu(),
        )
    else:
        await message.delete()
        await message.answer(
            profile_text,
            parse_mode="Markdown",
            reply_markup=get_user_main_menu(),
        )

    await callback.answer()


@router.message(Command("delete"))
async def delete_user_handler(message: Message):
    if message.from_user is None:
        await message.answer("Ошибка: бот недоступен.")
        return
    username = str(message.from_user.id)

    if db.deactive_user_db(username):
        shutil.rmtree(os.path.join("users", username), ignore_errors=True)
        await message.answer(f"Пользователь **{username}** удален.")
    else:
        await message.answer("Ошибка при удалении пользователя.")
