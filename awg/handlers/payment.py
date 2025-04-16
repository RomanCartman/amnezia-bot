import logging
import uuid
from aiogram import Router, F
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message
from aiogram.enums import ContentType
from aiogram.types import CallbackQuery
from keyboard.menu import get_extend_subscription_keyboard
from service.db_instance import user_db
from settings import YOOKASSA_PROVIDER_TOKEN


logger = logging.getLogger(__name__)
router = Router()


@router.callback_query(F.data == "buy_vpn")
async def buy_vpn(callback: CallbackQuery):
    logger.info(f"🔔 buy_vpn triggered by {callback.from_user.id}")
    if callback.message is None:
        await callback.answer("Ошибка: бот недоступен.")
        return
    await callback.message.answer(
        "💰 Выберите срок подписки:", reply_markup=get_extend_subscription_keyboard()
    )
    await callback.answer()


# 👉 Обработка кнопок "Купить VPN"
@router.callback_query(F.data.endswith("_extend"))
async def handle_extend_subscription(callback: CallbackQuery):
    if (
        callback.bot is None
        or callback.data is None
        or callback.message is None
        or callback.message.bot is None
    ):
        await callback.answer("Ошибка: бот недоступен.")
        return

    telegram_id = callback.from_user.id

    try:
        month = int(callback.data.split("_")[0])
    except (IndexError, ValueError):
        await callback.answer("Неверный формат выбораю")
        return

    prices_by_month = {
        1: 80,
        2: 150,
        3: 210,
    }

    price_per_month = prices_by_month.get(month)
    if not price_per_month:
        await callback.answer("Выбранный срок недоступен.")
        return

    amount = price_per_month * 100  # копейки
    logger.info(f"{telegram_id} - {month} mec. - {price_per_month}₽")
    unique_payload = str(uuid.uuid4())

    await callback.message.bot.send_invoice(
        chat_id=telegram_id,
        title=f"Покупка VPN на {month} mec.",
        description="Мы предоставляем удобные VPN услуги",
        payload=f"{unique_payload}-{telegram_id}-{month}-{price_per_month}",
        provider_token=YOOKASSA_PROVIDER_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label="RUB", amount=amount)],
        start_parameter="vpn-subscription",
    )

    user_db.add_payment(
        user_id=telegram_id,
        amount=amount / 100,
        months=month,
        provider_payment_id=None,
        raw_payload=f"{unique_payload}-{telegram_id}-{month}-{price_per_month}",
        status="pending",
        unique_payload=unique_payload,
    )
    await callback.answer()


# 👉 Pre-checkout обработка
@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery):
    logger.info(f"💳 PreCheckout: {pre_checkout_query.id}")
    await pre_checkout_query.answer(ok=True)


# 👉 Успешная оплата
@router.message(F.content_type == ContentType.SUCCESSFUL_PAYMENT)
async def successful_payment(message: Message):
    payment = message.successful_payment
    if payment is None or payment.invoice_payload is None:
        await message.answer("Ошибка оплаты")
        return
    logger.info(f"💰 Успешная оплата {payment.invoice_payload}")
    await message.answer("✅ Спасибо за покупку! Подписка активирована.")
