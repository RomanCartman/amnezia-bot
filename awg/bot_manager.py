import logging
import asyncio
from zoneinfo import ZoneInfo
from aiogram import Router, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from handlers import payment, user_actions, start_help
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

# dp.message.middleware(AdminMessageDeletionMiddleware(admins=ADMINS))


# 🚀 Запуск
async def main():
    dp.include_router(start_help.router)
    dp.include_router(payment.router)
    dp.include_router(user_actions.router)
    scheduler.start()
    await dp.start_polling(BOT)


if __name__ == "__main__":
    asyncio.run(main())
