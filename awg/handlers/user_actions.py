from io import BytesIO
import logging
import os
import shutil
from utils import generate_config_text, get_profile_text, get_vpn_caption
import db
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, BufferedInputFile

from service.db_instance import user_db
from keyboard.menu import get_user_profile_menu
from settings import BOT, VPN_NAME

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

    user = user_db.get_user_by_telegram_id(telegram_id)

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
            reply_markup=get_user_profile_menu(),
        )
    else:
        await message.delete()
        await message.answer(
            profile_text,
            parse_mode="Markdown",
            reply_markup=get_user_profile_menu(),
        )

    await callback.answer()


@router.callback_query(F.data == "get_config")
async def get_vpn_config(callback: CallbackQuery):
    """Получение конфига перед получение проверка есть у пользователя активаная подписка"""
    if callback.message is None:
        await callback.answer("Невозможно получить сообщение для отправки документа.")
        return

    user_id = callback.from_user.id
    config = user_db.get_config_by_telegram_id(str(user_id))
    if not config:
        await callback.answer("Конфигурация не найдена")
        return

    # Формируем содержимое конфигурации
    config_text = generate_config_text(config)

    # Готовим файл в памяти
    file_bytes = BytesIO(config_text.encode())
    file = BufferedInputFile(
        file=file_bytes.getvalue(), filename=f"{VPN_NAME}_{user_id}.conf"
    )

    await BOT.send_document(
        chat_id=callback.message.chat.id,
        document=file,
        caption=get_vpn_caption(user_id),
    )


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
