import datetime
import logging
import re
import humanize
from typing import cast
from zoneinfo import ZoneInfo
import db
from aiogram import Bot
from aiogram import Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
)
from aiogram.enums import ParseMode
from aiogram.utils.chat_action import ChatActionSender
from aiogram.fsm.context import FSMContext
from admin_service.admin import is_privileged
from service.send_backup_admin import create_db_backup
from utils import parse_relative_time, parse_transfer
from fsm.callback_data import ClientCallbackFactory
from keyboard.menu import get_client_profile_keyboard, get_home_keyboard
from fsm.admin_state import AdminState
from settings import BOT, DB_FILE

logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "add_user")
async def adimin_add_user_callback_handler(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает нажатие кнопки 'Добавить пользователя' и переводит в состояние ожидания данных."""
    user_id = callback.from_user.id
    if not is_privileged(user_id):
        await callback.answer("У вас нет прав для этого действия.", show_alert=True)
        return

    await callback.answer()  # Отвечаем на callback, чтобы кнопка не оставалась "нажатой"

    if callback.message is None:
        await callback.answer("Ошибка: бот недоступен.")
        return

    await callback.message.answer("Пожалуйста, введите данные для нового пользоваля:")
    await state.set_state(AdminState.waiting_for_user_name)
    logger.info(f"Admin {user_id} entered state waiting_for_user_name")


@router.callback_query(F.data == "add_admin")
async def add_admin_callback_handler(callback: CallbackQuery, state: FSMContext):
    """Обрабатывает нажатие кнопки 'Добавить админа' и переводит в состояние ожидания ID."""
    user_id = callback.from_user.id
    if not is_privileged(user_id):
        await callback.answer("У вас нет прав для этого действия.", show_alert=True)
        return

    await callback.answer()

    if callback.message is None:
        await callback.answer("Ошибка: бот недоступен.")
        return

    await callback.message.answer(
        "Пожалуйста, введите Telegram ID нового администратора:"
    )
    await state.set_state(AdminState.waiting_for_admin_id)
    logger.info(f"Admin {user_id} entered state waiting_for_admin_id")


@router.callback_query(F.data == "list_users")
async def admin_list_users_callback(callback: CallbackQuery):
    """Обрабатывает нажатие кнопки 'Список клиентов' и показывает список."""
    user_id = callback.from_user.id
    if callback.message is None:
        await callback.answer("Ошибка: бот недоступен.")
        return
    logger.info(f"User {user_id} requested client list.")

    if not is_privileged(user_id):
        logger.warning(
            f"User {user_id} attempted to access client list without permissions."
        )
        await callback.answer("Нет прав.", show_alert=True)
        return

    try:
        logger.info("Fetching client list...")
        clients = db.get_client_list()
        logger.info(f"Found {len(clients)} clients.")

        if not clients:
            logger.info("Client list is empty.")
            if isinstance(callback.message, Message):
                await callback.message.edit_text(
                    text="Список слиентов пуст",
                    reply_markup=get_home_keyboard(),
                )
            await callback.answer()
            return

        activ_clients = db.get_active_list()
        logger.info(f"Fetched active clients data.")

        keyboard_buttons: list = []

        for client_data in clients:
            username = client_data[0]

            activ_client = activ_clients.get(username)
            logger.debug(
                f"Processing client: {username}, last_handshke: {activ_client}"
            )

            status = "❌"  # По умолчанию неактивен

            if not activ_client:
                continue

            if activ_client.last_time and activ_client.last_time.lower() not in [
                "never",
                "нет данных",
                "-",
            ]:
                status = "🟢"  # Упрощенно ставим 🟢 если строка рукопожатия не пуста и не Never/Нет данных/

            button_text = f"{status} {username}"
            keyboard_buttons.append(
                InlineKeyboardButton(
                    text=button_text,
                    callback_data=ClientCallbackFactory(username=username).pack(),
                )
            )

        # Сборка клавиатуры
        keyboard_buttons_pairs = []

        # Формируем клавишу по парам, если кнопок нечетное количество, последняя будет одиночной
        for i in range(0, len(keyboard_buttons), 2):
            pair = [keyboard_buttons[i]]
            if i + 1 < len(keyboard_buttons):  # Если есть вторая кнопка для пары
                pair.append(keyboard_buttons[i + 1])
            keyboard_buttons_pairs.append(pair)

        # Добавляем кнопку "🏠 Домой" внизу
        keyboard_buttons_pairs.append(
            [InlineKeyboardButton(text="🏠 Домой", callback_data="home")]
        )

        # Создаем клавиатуру
        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons_pairs)

        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                text="Выберите пользователя:",
                reply_markup=keyboard,
            )
        logger.info(f"Displayed client list to user {user_id}")
        await callback.answer()

    except Exception as e:
        logger.error(
            f"Error in admin_list_users_callback for user {user_id}: {str(e)}",
            exc_info=True,
        )
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                text=f"Произошла ошибка при получении списка клиентов:\n{str(e)}",
                reply_markup=get_home_keyboard(),
            )
        # Отвечаем на callback с оповещением
        await callback.answer(
            "Ошибка на сервере при получении списка.", show_alert=True
        )


@router.callback_query(ClientCallbackFactory.filter())
async def client_selected_callback(
    callback: CallbackQuery, callback_data: ClientCallbackFactory
):
    user_id = callback.from_user.id

    if (
        callback.from_user is None
        or callback.message is None
        or not isinstance(callback.message, Message)
    ):
        await callback.answer(
            "Ошибка: пользователь или сообщение не определены.", show_alert=True
        )
        return

    if not is_privileged(user_id):
        await callback.answer("Нет прав.", show_allert=True)
        return

    username = callback_data.username
    logger.info(f"Выбран клиент: {username}")

    try:
        clients = db.get_client_list()
        client_info = next((c for c in clients if c[0] == username), None)
        if not client_info:
            await callback.answer("Пользователь не найден.", show_alert=True)
            return

        # Значения по умолчанию
        status = "🔴 Офлайн"
        incoming_traffic = "↓—"
        outgoing_traffic = "↑—"
        ipv4_address = "—"

        if (
            isinstance(client_info, (tuple, list))
            and len(client_info) > 2
            and client_info[2]
        ):
            ip_match = re.search(r"(\d{1,3}\.){3}\d{1,3}/\d+", str(client_info[2]))
            ipv4_address = ip_match.group(0) if ip_match else "—"

        # Проверка активности
        active_clients = db.get_active_list()
        active_info = active_clients.get(username)

        if active_info and active_info.last_time.lower() not in [
            "never",
            "нет данных",
            "-",
        ]:
            try:
                last_handshake = parse_relative_time(active_info.last_time)
                if (
                    last_handshake
                    and (
                        datetime.datetime.now(ZoneInfo("Europe/Moscow"))
                        - last_handshake
                    ).total_seconds()
                    <= 60
                ):
                    status = "🟢 Онлайн"
                else:
                    status = "❌ Офлайн"

                transfer_result = parse_transfer(active_info.transfer)
                if transfer_result:
                    incoming_bytes, outgoing_bytes = transfer_result
                    incoming_traffic = f"↓{humanize.naturalsize(incoming_bytes)}"
                    outgoing_traffic = f"↑{humanize.naturalsize(outgoing_bytes)}"

            except Exception as e:
                logger.error(
                    f"Ошибка при анализе активности клиента: {e}", exc_info=True
                )

        # Текст профиля
        text = (
            f"📧 *Имя:* {username}\n"
            f"🌐 *IPv4:* {ipv4_address}\n"
            f"🌐 *Статус:* {status}\n"
            f"🔼 *Исходящий:* {outgoing_traffic}\n"
            f"🔽 *Входящий:* {incoming_traffic}"
        )

        # Отправка редактированного сообщения
        await callback.message.edit_text(
            text=text,
            parse_mode="Markdown",
            reply_markup=get_client_profile_keyboard(username),
        )
        await callback.answer()

    except Exception as e:
        logger.error(f"Ошибка в client_selected_callback: {e}", exc_info=True)
        await callback.message.edit_text(
            text=f"Ошибка при загрузке профиля: {str(e)}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="⬅️ Назад", callback_data="list_users")],
                    [InlineKeyboardButton(text="🏠 Домой", callback_data="home")],
                ]
            ),
        )
        await callback.answer("Ошибка на сервере.", show_alert=True)


@router.callback_query(F.data == "create_backup")
async def create_backup_callback(callback: CallbackQuery):
    """Отправка бекапа админу"""
    user_id = callback.from_user.id
    if callback.message is None and callback.bot is None:
        await callback.answer("Ошибка: бот недоступен.")
        return
    logger.info(f"Create backup for {user_id}")

    if not is_privileged(user_id):
        logger.warning(
            f"User {user_id} attempted to access client list without permissions."
        )
        await callback.answer("Нет прав.", show_alert=True)
        return

    await callback.answer("Создаю бэкап...")

    try:
        bot = cast(Bot, callback.bot)
        async with ChatActionSender.upload_document(bot=bot, chat_id=user_id):
            backup_bytes = create_db_backup(DB_FILE)
            await bot.send_document(
                chat_id=user_id,
                document=BufferedInputFile(file=backup_bytes, filename="backup.zip"),
                caption="Бэкап успешно создан и отправлен.",
                parse_mode=ParseMode.HTML,
            )
        logging.info(f"Бэкап отправлен администратору: {user_id}")
    except Exception as e:
        logging.error(f"Ошибка при создании/отправке бэкапа: {e}")
        await callback.answer("Ошибка при создании бэкапа.", show_alert=True)
