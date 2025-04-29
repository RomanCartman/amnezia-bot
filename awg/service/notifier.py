import logging
import time
from typing import List

from service.db_instance import user_db
from service.base_model import UserData
from settings import BOT

logger = logging.getLogger(__name__)


async def daily_check_end_date_and_notify():
    start_time = time.time()
    logger.info("📬 Начинаю ежедневную проверку рассылки подписок...")


    try:
        days_before_end = [10, 5, 2]
        users = user_db.get_users_expiring_in_days(days_before_end)
        await notify_users(users)
    except Exception as e:
        logger.error(f"❌ Ошибка в daily_check_end_date_and_notify: {e}")
    finally:
        logger.info(f"✅ Завершена проверка. Заняло {time.time() - start_time:.2f} сек.")


async def notify_users(users: List[UserData]):
    for user in users:
        try:
            await BOT.send_message(
                user.telegram_id,
                f"Привет, {user.name}! Ваша подписка заканчивается {user.end_date}. Пожалуйста, продлите её вовремя!",
            )
        except Exception as e:
            logger.error(
                f"Ошибка отправки сообщения пользователю {user.telegram_id}: {e}"
            )
