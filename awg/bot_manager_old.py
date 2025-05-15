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
