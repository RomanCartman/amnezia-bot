import os
from typing import Optional
from service.notifier import notify_admins
from service.user_vpn_check import update_vpn_state
from service.vpn_service import create_vpn_config
import db
import uuid
import logging

from aiogram import Router, F
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message
from aiogram.enums import ContentType
from aiogram.types import CallbackQuery
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from service.generate_vpn_key import generate_vpn_key
from service.db_instance import user_db
from aiogram.types import Message, FSInputFile
from settings import BOT, YOOKASSA_PROVIDER_TOKEN, ACTIVE_PAYMENT_SYSTEMS, PAYMENT_PLANS


logger = logging.getLogger(__name__)
router = Router()


# Клавиатура выбора платёжной системы

def get_payment_systems_keyboard():
    buttons = []
    if "yookassa" in ACTIVE_PAYMENT_SYSTEMS:
        buttons.append(InlineKeyboardButton(text="💳 ЮKassa", callback_data="pay_yookassa"))
    if "telegram_stars" in ACTIVE_PAYMENT_SYSTEMS:
        buttons.append(InlineKeyboardButton(text="⭐ Telegram Stars", callback_data="pay_telegram_stars"))
    return InlineKeyboardMarkup(inline_keyboard=[[b] for b in buttons])


# Клавиатура выбора плана для конкретной системы

def get_plans_keyboard(system):
    plans = PAYMENT_PLANS[system]["plans"]
    buttons = [
        [InlineKeyboardButton(text=plan["label"], callback_data=f"plan_{system}_{plan['months']}")]
        for plan in plans
    ]
    buttons.append([InlineKeyboardButton(text="◀️ Назад", callback_data="buy_vpn")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.callback_query(F.data == "buy_vpn")
async def buy_vpn(callback: CallbackQuery):
    if callback.message.text:
        await callback.message.edit_text(
            "Выберите способ оплаты:",
            reply_markup=get_payment_systems_keyboard(),
        )
    else:
        await callback.message.delete()
        await callback.message.answer(
            "Выберите способ оплаты:",
            reply_markup=get_payment_systems_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_"))
async def choose_payment_system(callback: CallbackQuery):
    system = callback.data.split("pay_")[1]
    if system not in ACTIVE_PAYMENT_SYSTEMS:
        await callback.answer("Этот способ оплаты сейчас недоступен.", show_alert=True)
        return
    await callback.message.edit_text(
        f"Выберите тариф для {system.replace('_', ' ').title()}: ",
        reply_markup=get_plans_keyboard(system),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("plan_"))
async def handle_plan_choice(callback: CallbackQuery):
    _, system, months = callback.data.split("_", 2)
    months = int(months)
    plans = PAYMENT_PLANS[system]["plans"]
    plan = next((p for p in plans if p["months"] == months), None)
    if not plan:
        await callback.answer("Тариф не найден", show_alert=True)
        return
    if system == "yookassa":
        # ЮKassa invoice
        amount = plan["price"] * 100
        await callback.message.bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"VPN на {months} мес.",
            description="Безопасное соединение",
            payload=f"yookassa-{callback.from_user.id}-{months}-{plan['price']}",
            provider_token=YOOKASSA_PROVIDER_TOKEN,
            currency="RUB",
            prices=[LabeledPrice(label="RUB", amount=amount)],
            start_parameter="vpn-subscription",
        )
        await callback.answer()
    elif system == "telegram_stars":
        # Telegram Stars invoice
        amount = plan["price"]
        await callback.message.bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"VPN на {months} мес.",
            description="Безопасное соединение",
            payload=f"telegram_stars-{callback.from_user.id}-{months}-{plan['price']}",
            provider_token="STARS",  # Telegram Stars magic token
            currency="STARS",
            prices=[LabeledPrice(label="STARS", amount=amount)],
            start_parameter="vpn-stars-subscription",
        )
        await callback.answer()
    else:
        await callback.answer("Неизвестная платёжная система", show_alert=True)


# 👉 Pre-checkout обработка
@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    logger.info(f"💳 PreCheckout: {pre_checkout_query.id}")
    await pre_checkout_query.answer(ok=True)


async def process_successful_payment(
    user_id: str, raw_payload: str, provider_payment_charge_id: str
) -> Optional[int]:
    """Обновление статуса платежа и продление подписки"""
    try:
        updated_payment = user_db.update_payment_status(
            raw_payload, provider_payment_charge_id, new_status="success"
        )
        if not updated_payment:
            return None

        user_db.update_user_end_date(user_id, months_to_add=updated_payment.months)
        return updated_payment.months
    except Exception as e:
        logger.error(f"Ошибка при обработке успешного платежа: {e}", exc_info=True)
        return None


def validate_payment(message: Message) -> Optional[tuple[str, str, str]]:
    """Валидация входных данных"""
    payment = message.successful_payment
    if payment is None or payment.invoice_payload is None or message.from_user is None:
        return None
    return (
        str(message.from_user.id),
        payment.invoice_payload,
        payment.provider_payment_charge_id,
    )


# 👉 Успешная оплата
@router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    try:
        result = validate_payment(message)
        if result is None:
            await message.answer("Ошибка оплаты")
            return
        telegram_id, payload, provider_payment_charge_id = result

        logger.info(f"💰 Успешная оплата {payload}")

        months = await process_successful_payment(
            telegram_id, payload, provider_payment_charge_id
        )
        if months is None:
            await message.answer("Не удалось обновить статус оплаты.")
            return

        logger.info(f"🔁 Подписка продлена на {months} мес. для {telegram_id}")

        # Проверяем есть конфигурация или нет
        clients = db.get_client_list()
        client_entry = next((c for c in clients if c[0] == str(telegram_id)), None)
        if client_entry is None:  # Если нет создаем
            # Проверяем есть она у нас в БД
            config = user_db.get_config_by_telegram_id(str(telegram_id))
            if not config:
                await message.answer("⚙️ Генерируем VPN-конфигурацию...")
                await create_vpn_config(telegram_id, message)
        else:
            await message.answer("🛡 У вас уже есть активная конфигурация.")
        update_vpn_state()
        await notify_admins(
            text=f"🔁 Подписка продлена на {months} мес. для {telegram_id} \n {message.from_user.username} \n {payload}"
        )
        await message.answer("✅ Спасибо за покупку! Подписка активирована.")
    except Exception as e:
        logger.error(f"❌ Ошибка при обработке успешной оплаты: {e}")
        await message.answer(
            "Произошла ошибка при активации подписки. Свяжитесь с поддержкой."
        )
