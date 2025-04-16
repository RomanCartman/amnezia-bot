import logging
from service.db_instance import user_db
import uuid
from aiogram.dispatcher import Dispatcher
from aiogram import types
from aiogram.types import LabeledPrice, PreCheckoutQuery, Message
from service.base_model import YoomoneyModel
from keyboard.menu import get_extend_subscription_keyboard

# from payment_handlers import payment_handlers
from settings import (
    BOT,
    ADMINS,
    MODERATORS,
    WG_CONFIG_FILE,
    DOCKER_CONTAINER,
    YOOKASSA_PROVIDER_TOKEN,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def buy_vpn(callback: types.CallbackQuery):
    logger.info(f"🔔 buy_vpn triggered by {callback.from_user.id}")
    await callback.message.answer(
        "💰 Выберите срок подписки:", reply_markup=get_extend_subscription_keyboard()
    )
    await callback.answer()


# 👉 Обработка callback-кнопок "N_extend"
async def handle_extend_subscription(callback: types.CallbackQuery):
    telegram_id = callback.from_user.id

    # Пример: "2_extend"
    try:
        month = int(callback.data.split("_")[0])
    except (IndexError, ValueError):
        await callback.answer("Неверный формат выбора.")
        return

    # Простой расчёт цен
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
    title = f"{month} мес."

    logger.info(f"{telegram_id} - {title} - {amount / 100}₽")
    unique_payload = str(uuid.uuid4())

    await callback.bot.send_invoice(
        chat_id=telegram_id,
        title=f"Покупка VPN на {title}",
        description="Мы предоставляем удобные VPN услуги",
        payload=f"{unique_payload}-{telegram_id}-{month}-{price_per_month}",
        provider_token=YOOKASSA_PROVIDER_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label="Подписка VPN", amount=amount)],
        start_parameter="test",
    )
    print("📤 Invoice sent!")
    user_db.add_payment(
        user_id=telegram_id,
        amount=amount / 100,
        months=month,
        provider_payment_id=None,
        raw_payload=f"{telegram_id}-{month}-{price_per_month}",
        status="pending",
        unique_payload=unique_payload,
    )
    await callback.answer()


# 👉 Обработка pre_checkout запроса
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    print(f"⚡ PreCheckout ID: {pre_checkout_query.id}")
    try:
        await pre_checkout_query.bot.answer_pre_checkout_query(
            pre_checkout_query.id, ok=True
        )
    except Exception as e:
        print(f"🔥 PreCheckout error: {e}")


# 👉 Обработка успешной оплаты
async def process_successful_payment(message: Message):
    yookassa_dict = message.successful_payment.to_python()
    for j, k in yookassa_dict.items():
        logger.info(f"{j} = {k}")

    try:
        kassa = YoomoneyModel(**yookassa_dict)
        unique_payload, t_id, month, price = kassa.invoice_payload.split("-")
        if int(t_id) == message.from_user.id:
            user = db_user.update_user_end_date(t_id, int(month))
            db_user.update_payment_status(unique_payload, "success")
            if user:
                await message.answer(f"Период активирован на {month} месяц")
                logger.info(f"SUCCESS PAY - tg_id {t_id}")
    except Exception as e:
        logger.warning(f"FAILURE PAY - tg_id {t_id} - {e}")
        await message.answer("Ошибка активации периода")


# 🔧 Регистрация всех хендлеров
def payment_handlers(dp: Dispatcher):
    # dp.register_callback_query_handler(buy_vpn, text="buy_vpn")
    # dp.register_callback_query_handler(
    #     handle_extend_subscription, text_endswith="_extend"
    # )
    # # dp.register_pre_checkout_query_handler(process_pre_checkout_query)
    # dp.register_message_handler(
    #     process_successful_payment, content_types=types.ContentType.SUCCESSFUL_PAYMENT
    # )
