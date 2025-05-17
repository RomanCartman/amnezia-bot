import logging
import time
from typing import List

from service.db_instance import user_db
from service.base_model import UserData
from settings import ADMINS, BOT

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
        logger.info(
            f"✅ Завершена проверка. Заняло {time.time() - start_time:.2f} сек."
        )


async def notify_users(users: List[UserData]):
    """Отправляет уведомления пользователям и логирует успешные отправки."""
    successful_sends = 0
    failed_sends = 0
    for user in users:
        try:
            await BOT.send_message(
                user.telegram_id,
                f"Привет, {user.name}! Ваша подписка заканчивается {user.end_date}. Пожалуйста, продлите её вовремя!",
            )

            # Логируем успешную отправку, если исключение не возникло
            logger.info(
                f"✅ Уведомление успешно отправлено пользователю ID: {user.telegram_id} (Имя: {user.name})"
            )
            successful_sends += 1
        except Exception as e:
            logger.error(
                f"Ошибка отправки сообщения пользователю {user.telegram_id}: {e}"
            )
            failed_sends += 1

    logger.info(
        f"📊 Статистика рассылки: Успешно: {successful_sends}, Ошибок: {failed_sends}"
    )


async def notify_admins(text: str):
    """Рассылает сообщение всем администраторам."""
    successful_sends = 0
    failed_sends = 0

    for admin_id in ADMINS:
        try:
            await BOT.send_message(admin_id, text)
            logger.info(f"✅ Сообщение администратору {admin_id} отправлено.")
            successful_sends += 1
        except Exception as e:
            logger.error(f"❌ Ошибка отправки админу {admin_id}: {e}")
            failed_sends += 1

    logger.info(
        f"📊 Админам отправлено: Успешно: {successful_sends}, Ошибок: {failed_sends}"
    )