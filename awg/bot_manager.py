import logging
import asyncio
from time import timezone
from zoneinfo import ZoneInfo
from aiogram import Router, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from service.user_vpn_check import update_vpn_state
from service.notifier import daily_check_end_date_and_notify
from handlers import payment, user_actions, start_help, admin_actions
from middlewares.admin_delete import AdminMessageDeletionMiddleware
from settings import (
    BOT,
    ADMINS,
    MODERATORS,
    WG_CONFIG_FILE,
    DOCKER_CONTAINER,
    ISP_CACHE_FILE,
    CACHE_TTL,
)


# ⚙️ Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 📦 Инициализация
dp = Dispatcher(storage=MemoryStorage())
router = Router()
scheduler = AsyncIOScheduler(timezone=ZoneInfo("UTC"))


# 🚀 Запуск
async def main():
    dp.include_router(start_help.router)
    dp.include_router(payment.router)
    dp.include_router(user_actions.router)
    dp.include_router(admin_actions.router)

    dp.message.middleware(AdminMessageDeletionMiddleware(admins=ADMINS))

    scheduler.add_job(
        daily_check_end_date_and_notify,
        trigger="cron",
        hour=10,  # каждый день в 10:00 утра
        minute=0,
        timezone=ZoneInfo("Europe/Moscow"),
    )

    scheduler.add_job(
        update_vpn_state,
        trigger="cron",
        hour=9,  # каждый день в 9:00 утра
        minute=30,
        timezone=ZoneInfo("Europe/Moscow"),
    )

    scheduler.start()
    await dp.start_polling(BOT)


if __name__ == "__main__":
    asyncio.run(main())
