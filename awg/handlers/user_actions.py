from datetime import datetime
import logging
from aiogram import Router, F

from service.db_instance import user_db
from keyboard.menu import get_user_main_menu
from aiogram.types import CallbackQuery, Message

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
    )  # предполагаем, что у тебя есть объект `db` с методом

    if not user:
        await message.answer(
            "❌ Пользователь не найден. Пожалуйста, зарегистрируйтесь или свяжитесь с поддержкой."
        )
        await callback.answer()
        return

    # Форматируем дату окончания подписки
    if user.is_unlimited:
        subscription_text = "♾️ Безлимитная"
    elif user.end_date:
        try:
            end_date = datetime.strptime(user.end_date, "%Y-%m-%d").strftime("%d.%m.%Y")
        except Exception:
            end_date = user.end_date  # если дата уже в нормальном виде
        subscription_text = f"📅 Активна до {end_date}"
    else:
        subscription_text = "❌ Нет активной подписки"

    profile_text = (
        f"👤 *Ваш профиль*\n\n"
        f"🆔 ID: `{user.telegram_id}`\n"
        f"👥 Имя: *{user.name}*\n"
        f"{subscription_text}\n"
        f"🧪 Пробный период: {'использован' if user.has_used_trial else 'доступен'}"
    )

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
