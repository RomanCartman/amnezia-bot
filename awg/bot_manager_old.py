import db
import aiohttp
import logging
import asyncio
import aiofiles
import os
import re
import json
import subprocess
import sys
import pytz
import zipfile
import humanize
import shutil
from aiogram import types
from aiogram.dispatcher import Dispatcher
from aiogram.dispatcher.middlewares import BaseMiddleware
from aiogram.utils import executor
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    PreCheckoutQuery,
    LabeledPrice,
    Message,
)
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from utils import get_isp_info, load_isp_cache, parse_relative_time, parse_transfer
from service.generate_vpn_key import generate_vpn_key
from keyboard.menu import get_extend_subscription_keyboard, get_main_menu_markup, get_user_main_menu











@dp.message_handler(commands=["start", "help"])
async def help_command_handler(message: types.Message):
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
        try:
            with open("logo.png", "rb") as photo:
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


@dp.message_handler(commands=["add_admin"])
async def add_admin_command(message: types.Message):
    if message.from_user.id not in ADMINS:
        await message.answer("У вас нет прав.")
        return
    try:
        new_admin_id = int(message.text.split()[1])
        if new_admin_id not in ADMINS:
            db.add_admin(new_admin_id)
            ADMINS.append(new_admin_id)
            await message.answer(f"Админ {new_admin_id} добавлен.")
            await BOT.send_message(new_admin_id, "Вы назначены администратором!")
    except:
        await message.answer("Формат: /add_admin <user_id>")


@dp.message_handler()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    if user_id not in ADMINS and user_id not in MODERATORS:
        await message.answer("У вас нет доступа.")
        return

    user_state = user_main_messages.get(user_id, {}).get("state")
    if user_state == "waiting_for_user_name":
        user_name = message.text.strip()
        if not re.match(r"^[a-zA-Z0-9_-]+$", user_name):
            await message.reply("Имя может содержать только буквы, цифры, - и _.")
            return
        success = db.root_add(user_name, ipv6=False)
        if success:
            conf_path = os.path.join("users", user_name, f"{user_name}.conf")
            if os.path.exists(conf_path):
                vpn_key = await generate_vpn_key(conf_path)
                caption = f"Конфигурация для {user_name}:\nAmneziaVPN:\n[Google Play](https://play.google.com/store/apps/details?id=org.amnezia.vpn&hl=ru)\n[GitHub](https://github.com/amnezia-vpn/amnezia-client)\n```\n{vpn_key}\n```"
                with open(conf_path, "rb") as config:
                    # Отправляем конфиг отдельным сообщением и закрепляем его
                    config_message = await BOT.send_document(
                        user_id, config, caption=caption, parse_mode="Markdown"
                    )
                    await BOT.pin_chat_message(
                        user_id, config_message.message_id, disable_notification=True
                    )
        # Обновляем меню внизу, не закрепляя его
        await BOT.edit_message_text(
            chat_id=user_main_messages[user_id]["chat_id"],
            message_id=user_main_messages[user_id]["message_id"],
            text="Выберите действие:",
            reply_markup=get_main_menu_markup(user_id, ADMINS),
        )
        user_main_messages[user_id]["state"] = None
    elif user_state == "waiting_for_admin_id" and user_id in ADMINS:
        try:
            new_admin_id = int(message.text.strip())
            if new_admin_id not in ADMINS:
                db.add_admin(new_admin_id)
                ADMINS.append(new_admin_id)
                await message.reply(f"Админ {new_admin_id} добавлен.")
                await BOT.send_message(new_admin_id, "Вы назначены администратором!")
            await BOT.edit_message_text(
                chat_id=user_main_messages[user_id]["chat_id"],
                message_id=user_main_messages[user_id]["message_id"],
                text="Выберите действие:",
                reply_markup=get_main_menu_markup(user_id, ADMINS),
            )
            user_main_messages[user_id]["state"] = None
        except:
            await message.reply("Введите корректный Telegram ID.")


@dp.callback_query_handler(lambda c: c.data == "add_user")
async def prompt_for_user_name(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS and user_id not in MODERATORS:
        await callback_query.answer("Нет прав.", show_alert=True)
        return
    await BOT.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="Введите имя пользователя:",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🏠 Домой", callback_data="home")
        ),
    )
    user_main_messages[user_id]["state"] = "waiting_for_user_name"
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data == "add_admin")
async def prompt_for_admin_id(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS:
        await callback_query.answer("Нет прав.", show_alert=True)
        return
    await BOT.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="Введите Telegram ID нового админа:",
        reply_markup=InlineKeyboardMarkup().add(
            InlineKeyboardButton("🏠 Домой", callback_data="home")
        ),
    )
    user_main_messages[user_id]["state"] = "waiting_for_admin_id"
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("client_"))
async def client_selected_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS and user_id not in MODERATORS:
        await callback_query.answer("Нет прав.", show_alert=True)
        return

    try:
        logger.info(f"Callback data: {callback_query.data}")
        username = callback_query.data.split("client_")[1]
        logger.info(f"Выбран клиент: {username}")

        clients = db.get_client_list()
        logger.info(f"Список клиентов: {clients}")
        client_info = next((c for c in clients if c[0] == username), None)
        if not client_info:
            await callback_query.answer("Пользователь не найден.", show_alert=True)
            return
        logger.info(f"Информация о клиенте: {client_info}")

        # Базовые значения
        status = "🔴 Офлайн"
        incoming_traffic = "↓—"
        outgoing_traffic = "↑—"
        ipv4_address = "—"
        if (
            isinstance(client_info, (tuple, list))
            and len(client_info) > 2
            and client_info[2] is not None
        ):
            logger.info(f"client_info[2]: {client_info[2]}")
            ip_match = re.search(r"(\d{1,3}\.){3}\d{1,3}/\d+", str(client_info[2]))
            ipv4_address = ip_match.group(0) if ip_match else "—"
        else:
            logger.info(f"client_info некорректно: {client_info}")

        # Проверяем активность
        active_clients = db.get_active_list()
        logger.info(f"Список активных клиентов: {active_clients}")
        active_info = next((ac for ac in active_clients if ac[0] == username), None)
        logger.info(f"Активная информация: {active_info}")

        if (
            active_info is not None
            and isinstance(active_info, (tuple, list))
            and len(active_info) > 2
            and active_info[1] is not None
            and active_info[1].lower() not in ["never", "нет данных", "-"]
        ):
            logger.info(f"active_info[1]: {active_info[1]}")
            try:
                last_handshake = parse_relative_time(active_info[1])
                if last_handshake is not None:
                    logger.info(f"last_handshake: {last_handshake}")
                    status = (
                        "🟢 Онлайн"
                        if (datetime.now(pytz.UTC) - last_handshake).total_seconds()
                        <= 60
                        else "❌ Офлайн"
                    )
                if len(active_info) > 2 and active_info[2] is not None:
                    logger.info(f"active_info[2]: {active_info[2]}")
                    try:
                        transfer_result = parse_transfer(active_info[2])
                        if transfer_result is not None:
                            incoming_bytes, outgoing_bytes = transfer_result
                            incoming_traffic = (
                                f"↓{humanize.naturalsize(incoming_bytes)}"
                            )
                            outgoing_traffic = (
                                f"↑{humanize.naturalsize(outgoing_bytes)}"
                            )
                        else:
                            logger.info("parse_transfer вернул None")
                    except Exception as e:
                        logger.error(f"Ошибка в parse_transfer: {str(e)}")
            except Exception as e:
                logger.error(f"Ошибка в parse_relative_time: {str(e)}")

        # Формируем текст профиля
        text = (
            f"📧 *Имя:* {username}\n"
            f"🌐 *IPv4:* {ipv4_address}\n"
            f"🌐 *Статус:* {status}\n"
            f"🔼 *Исходящий:* {incoming_traffic}\n"
            f"🔽 *Входящий:* {outgoing_traffic}"
        )

        # Создаём клавиатуру
        keyboard = InlineKeyboardMarkup(row_width=2).add(
            InlineKeyboardButton("ℹ️ IP info", callback_data=f"ip_info_{username}"),
            InlineKeyboardButton(
                "🔗 Подключения", callback_data=f"connections_{username}"
            ),
            InlineKeyboardButton("🗑️ Удалить", callback_data=f"delete_user_{username}"),
            InlineKeyboardButton("⬅️ Назад", callback_data="list_users"),
            InlineKeyboardButton("🏠 Домой", callback_data="home"),
        )

        logger.info(f"Редактирование сообщения для {username}")
        await BOT.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=text,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
        await callback_query.answer()

    except Exception as e:
        logger.error(f"Ошибка в client_selected_callback: {str(e)}")
        await BOT.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=f"Ошибка при загрузке профиля: {str(e)}",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("⬅️ Назад", callback_data="list_users"),
                InlineKeyboardButton("🏠 Домой", callback_data="home"),
            ),
        )
        await callback_query.answer("Ошибка на сервере.", show_alert=True)


@dp.callback_query_handler(lambda c: c.data == "list_users")
async def list_users_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS and user_id not in MODERATORS:
        await callback_query.answer("Нет прав.", show_alert=True)
        return

    try:
        logger.info("Запуск list_users_callback")
        clients = db.get_client_list()
        logger.info(f"Клиенты: {clients}")
        if not clients:
            await BOT.edit_message_text(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id,
                text="Список клиентов пуст.",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("🏠 Домой", callback_data="home")
                ),
            )
            await callback_query.answer()
            return

        keyboard = InlineKeyboardMarkup(row_width=2)
        active_clients = {client[0]: client[1] for client in db.get_active_list()}
        logger.info(f"Активные клиенты: {active_clients}")
        now = datetime.now(pytz.UTC)

        for client in clients:
            username = client[0]
            last_handshake = active_clients.get(username)
            logger.info(f"Клиент: {username}, last_handshake: {last_handshake}")
            # Упрощённая логика статуса для теста
            status = (
                "❌"
                if not last_handshake
                or last_handshake.lower() in ["never", "нет данных", "-"]
                else "🟢"
            )
            button_text = f"{status} {username}"
            keyboard.insert(
                InlineKeyboardButton(button_text, callback_data=f"client_{username}")
            )

        keyboard.add(InlineKeyboardButton("🏠 Домой", callback_data="home"))

        await BOT.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text="Выберите пользователя:",
            reply_markup=keyboard,
        )
        await callback_query.answer()

    except Exception as e:
        logger.error(f"Ошибка в list_users_callback: {str(e)}")
        await BOT.edit_message_text(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id,
            text=f"Ошибка: {str(e)}",
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🏠 Домой", callback_data="home")
            ),
        )
        await callback_query.answer("Ошибка на сервере.", show_alert=True)


@dp.callback_query_handler(lambda c: c.data == "list_admins")
async def list_admins_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS:
        await callback_query.answer("Нет прав.", show_alert=True)
        return
    keyboard = InlineKeyboardMarkup(row_width=2)
    for admin_id in ADMINS:
        keyboard.insert(
            InlineKeyboardButton(
                f"🗑️ Удалить {admin_id}", callback_data=f"remove_admin_{admin_id}"
            )
        )
    keyboard.add(InlineKeyboardButton("🏠 Домой", callback_data="home"))
    await BOT.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=f"Администраторы:\n" + "\n".join(f"- {admin_id}" for admin_id in ADMINS),
        reply_markup=keyboard,
    )
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("remove_admin_"))
async def remove_admin_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS:
        await callback_query.answer("Нет прав.", show_alert=True)
        return
    admin_id = int(callback_query.data.split("_")[2])
    if admin_id not in ADMINS or len(ADMINS) <= 1:
        await callback_query.answer(
            "Нельзя удалить последнего админа или несуществующего.", show_alert=True
        )
        return
    db.remove_admin(admin_id)
    ADMINS.remove(admin_id)
    await BOT.send_message(admin_id, "Вы удалены из администраторов.")
    await list_admins_callback(callback_query)


@dp.callback_query_handler(lambda c: c.data.startswith("connections_"))
async def client_connections_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS and user_id not in MODERATORS:
        await callback_query.answer("Нет прав.", show_alert=True)
        return
    username = callback_query.data.split("connections_")[1]
    file_path = os.path.join("files", "connections", f"{username}_ip.json")
    if not os.path.exists(file_path):
        await callback_query.answer("Нет данных о подключениях.", show_alert=True)
        return

    async with aiofiles.open(file_path, "r") as f:
        data = json.loads(await f.read())
    last_connections = sorted(
        data.items(),
        key=lambda x: datetime.strptime(x[1], "%d.%m.%Y %H:%M"),
        reverse=True,
    )[:5]
    isp_results = await asyncio.gather(
        *(get_isp_info(ip) for ip, _ in last_connections)
    )

    text = f"*Последние подключения {username}:*\n" + "\n".join(
        f"{ip} ({isp}) - {time}"
        for (ip, time), isp in zip(last_connections, isp_results)
    )
    keyboard = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("⬅️ Назад", callback_data=f"client_{username}"),
        InlineKeyboardButton("🏠 Домой", callback_data="home"),
    )
    await BOT.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("ip_info_"))
async def ip_info_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS and user_id not in MODERATORS:
        await callback_query.answer("Нет прав.", show_alert=True)
        return
    username = callback_query.data.split("ip_info_")[1]
    active_info = next((ac for ac in db.get_active_list() if ac[0] == username), None)
    if not active_info:
        await callback_query.answer("Нет данных о подключении.", show_alert=True)
        return

    ip_address = active_info[3].split(":")[0]
    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://ip-api.com/json/{ip_address}") as resp:
            data = await resp.json() if resp.status == 200 else {}

    text = f"*IP info {username}:*\n" + "\n".join(
        f"{k.capitalize()}: {v}" for k, v in data.items()
    )
    keyboard = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("⬅️ Назад", callback_data=f"client_{username}"),
        InlineKeyboardButton("🏠 Домой", callback_data="home"),
    )
    await BOT.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("delete_user_"))
async def client_delete_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS and user_id not in MODERATORS:
        await callback_query.answer("Нет прав.", show_alert=True)
        return
    username = callback_query.data.split("delete_user_")[1]
    if db.deactive_user_db(username):
        shutil.rmtree(os.path.join("users", username), ignore_errors=True)
        text = f"Пользователь **{username}** удален."
    else:
        text = f"Не удалось удалить **{username}**."
    await BOT.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_markup(user_id, ADMINS),
    )
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data == "home")
async def return_home(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS and user_id not in MODERATORS:
        await callback_query.answer("Нет прав.", show_alert=True)
        return
    user_main_messages[user_id]["state"] = None
    await BOT.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="Выберите действие:",
        reply_markup=get_main_menu_markup(user_id, ADMINS),
    )
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data == "get_config")
async def list_users_for_config(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS and user_id not in MODERATORS:
        await callback_query.answer("Нет прав.", show_alert=True)
        return
    clients = db.get_client_list()
    if not clients:
        await callback_query.answer("Список пуст.", show_alert=True)
        return

    keyboard = InlineKeyboardMarkup(row_width=2)
    for client in clients:
        keyboard.insert(
            InlineKeyboardButton(client[0], callback_data=f"send_config_{client[0]}")
        )
    keyboard.add(InlineKeyboardButton("🏠 Домой", callback_data="home"))
    await BOT.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="Выберите пользователя:",
        reply_markup=keyboard,
    )
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("send_config_"))
async def send_user_config(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS and user_id not in MODERATORS:
        await callback_query.answer("Нет прав.", show_alert=True)
        return
    username = callback_query.data.split("send_config_")[1]
    conf_path = os.path.join("users", username, f"{username}.conf")
    if os.path.exists(conf_path):
        vpn_key = await generate_vpn_key(conf_path)
        caption = f"Конфигурация для {username}:\nAmneziaVPN:\n[Google Play](https://play.google.com/store/apps/details?id=org.amnezia.vpn&hl=ru)\n[GitHub](https://github.com/amnezia-vpn/amnezia-client)\n```\n{vpn_key}\n```"
        with open(conf_path, "rb") as config:
            # Отправляем конфиг отдельным сообщением и закрепляем его
            config_message = await BOT.send_document(
                user_id, config, caption=caption, parse_mode="Markdown"
            )
            await BOT.pin_chat_message(
                user_id, config_message.message_id, disable_notification=True
            )
    else:
        await BOT.send_message(
            user_id,
            f"Конфигурация для **{username}** не найдена.",
            parse_mode="Markdown",
        )
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data == "create_backup")
async def create_backup_callback(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS:
        await callback_query.answer("Нет прав.", show_alert=True)
        return
    backup_filename = f"backup_{datetime.now().strftime('%Y-%m-%d')}.zip"
    with zipfile.ZipFile(backup_filename, "w") as zipf:
        for file in ["awg-decode.py", "newclient.sh", "removeclient.sh"]:
            if os.path.exists(file):
                zipf.write(file)
        for root, _, files in os.walk("files"):
            for file in files:
                zipf.write(
                    os.path.join(root, file),
                    os.path.relpath(os.path.join(root, file), os.getcwd()),
                )
        for root, _, files in os.walk("users"):
            for file in files:
                zipf.write(
                    os.path.join(root, file),
                    os.path.relpath(os.path.join(root, file), os.getcwd()),
                )
    with open(backup_filename, "rb") as f:
        await BOT.send_document(user_id, f, caption=backup_filename)
    os.remove(backup_filename)
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data == "instructions")
async def show_instructions(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS and user_id not in MODERATORS:
        await callback_query.answer("Нет прав.", show_alert=True)
        return
    keyboard = InlineKeyboardMarkup(row_width=2).add(
        InlineKeyboardButton("📱 Для мобильных", callback_data="mobile_instructions"),
        InlineKeyboardButton("💻 Для компьютеров", callback_data="pc_instructions"),
        InlineKeyboardButton("🏠 Домой", callback_data="home"),
    )
    await BOT.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text="Выберите тип устройства для инструкции:",
        reply_markup=keyboard,
    )
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data == "mobile_instructions")
async def mobile_instructions(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS and user_id not in MODERATORS:
        await callback_query.answer("Нет прав.", show_alert=True)
        return
    instruction_text = (
        "📱 *Инструкция для мобильных устройств:*\n\n"
        "1. Скачайте приложение AmneziaVPN:\n"
        "   - [Google Play](https://play.google.com/store/apps/details?id=org.amnezia.vpn&hl=ru)\n"
        "   - Или через [GitHub](https://github.com/amnezia-vpn/amnezia-client)\n"
        "2. Откройте приложение и выберите 'Добавить конфигурацию'.\n"
        "3. Скопируйте VPN ключ из сообщения с файлом .conf.\n"
        "4. Вставьте ключ в приложение и нажмите 'Подключить'.\n"
        "5. Готово! Вы подключены к VPN."
    )
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("⬅️ Назад", callback_data="instructions"),
        InlineKeyboardButton("🏠 Домой", callback_data="home"),
    )
    await BOT.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=instruction_text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    await callback_query.answer()


@dp.callback_query_handler(lambda c: c.data == "pc_instructions")
async def pc_instructions(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in ADMINS and user_id not in MODERATORS:
        await callback_query.answer("Нет прав.", show_alert=True)
        return
    instruction_text = (
        "💻 *Инструкция для компьютеров:*\n\n"
        "1. Скачайте клиент AmneziaVPN с [GitHub](https://github.com/amnezia-vpn/amnezia-client).\n"
        "2. Установите программу на ваш компьютер.\n"
        "3. Откройте AmneziaVPN и выберите 'Импорт конфигурации'.\n"
        "4. Укажите путь к скачанному файлу .conf.\n"
        "5. Нажмите 'Подключить' для активации VPN.\n"
        "6. Готово! VPN активен."
    )
    keyboard = InlineKeyboardMarkup().add(
        InlineKeyboardButton("⬅️ Назад", callback_data="instructions"),
        InlineKeyboardButton("🏠 Домой", callback_data="home"),
    )
    await BOT.edit_message_text(
        chat_id=callback_query.message.chat.id,
        message_id=callback_query.message.message_id,
        text=instruction_text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    await callback_query.answer()


async def check_environment():
    if DOCKER_CONTAINER not in subprocess.check_output(
        f"docker ps --filter 'name={DOCKER_CONTAINER}' --format '{{{{.Names}}}}'",
        shell=True,
    ).decode().strip().split("\n"):
        logger.error(f"Контейнер '{DOCKER_CONTAINER}' не найден.")
        return False
    subprocess.check_call(
        f"docker exec {DOCKER_CONTAINER} test -f {WG_CONFIG_FILE}", shell=True
    )
    return True


async def on_startup(dp):
    os.makedirs("files/connections", exist_ok=True)
    os.makedirs("users", exist_ok=True)
    await load_isp_cache()
    if not await check_environment():
        for admin_id in ADMINS:
            await BOT.send_message(admin_id, "Ошибка инициализации AmneziaVPN.")
        await BOT.close()
        sys.exit(1)
    if not db.get_admins():
        logger.error("Список админов пуст.")
        sys.exit(1)
    scheduler.add_job(db.ensure_peer_names, IntervalTrigger(minutes=1))


async def on_shutdown(dp):
    scheduler.shutdown()


if __name__ == "__main__":
    # payment_handlers(dp)
    executor.start_polling(dp, on_startup=on_startup, on_shutdown=on_shutdown)
