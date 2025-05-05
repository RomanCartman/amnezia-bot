import logging
from aiogram import Router, F

from service.db_instance import user_db
from utils import get_short_name
from keyboard.menu import get_main_menu_markup, get_user_main_menu
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, CallbackQuery
from admin_service.admin import is_privileged
from settings import ADMINS

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command(commands=["start", "help"]))
async def help_command_handler(message: Message):
    if message.from_user is None:
        await message.answer("Ошибка: невозможно получить данные пользователя.")
        return
    user_id = message.from_user.id

    if is_privileged(user_id):
        await message.answer(
            "Выберите действие:", reply_markup=get_main_menu_markup(user_id, ADMINS)
        )
    else:
        name = get_short_name(message.from_user)
        user_db.add_user(str(user_id), name)
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


@router.callback_query(F.data == "home")
async def home_callback_handler(callback: CallbackQuery):
    user = callback.from_user
    if user is None:
        await callback.answer("Ошибка: пользователь не определён.", show_alert=True)
        return

    user_id = user.id

    if not isinstance(callback.message, Message):
        await callback.answer("Ошибка: сообщение недоступно.", show_alert=True)
        return

    if is_privileged(user_id):
        await callback.message.edit_text(
            text="Выберите действие:",
            reply_markup=get_main_menu_markup(user_id, ADMINS),
        )
    else:
        try:
            photo = FSInputFile("logo.png")
            await callback.message.answer_photo(
                photo=photo,
                caption="👋 Добро пожаловать в *VPN Бот!*\n\nВыберите действие:",
                parse_mode="Markdown",
                reply_markup=get_user_main_menu(),
            )
        except Exception as e:
            logger.error(f"Ошибка при отображении главного меню: {e}", exc_info=True)
            await callback.message.edit_text(
                text="👋 Добро пожаловать!\n\nВыберите действие:",
                reply_markup=get_user_main_menu(),
            )

    await callback.answer()
