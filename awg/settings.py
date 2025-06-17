import subprocess
import sys
import logging
import db
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

logger = logging.getLogger(__name__)

# Загрузка конфигурации
setting = db.get_config()
bot_token = setting.get("bot_token")
admin_ids = setting.get("admin_ids", [])
moderator_ids = setting.get("moderator_ids", [])
wg_config_file = setting.get("wg_config_file")
docker_container = setting.get("docker_container")
endpoint = setting.get("endpoint")
yookassa_provider_token = setting.get("yookassa_provider_token").strip()
vpn_name = setting.get("vpn_name")
fast_api_url = setting.get("fast_api_url")

if not all([bot_token, admin_ids, wg_config_file, docker_container, endpoint]):
    logger.error("Некоторые обязательные настройки отсутствуют.")
    sys.exit(1)

# Настройки и объекты
BOT = Bot(bot_token, default=DefaultBotProperties(parse_mode="HTML"))
ADMINS = [int(admin_id) for admin_id in admin_ids]
MODERATORS = [int(mod_id) for mod_id in moderator_ids]
WG_CONFIG_FILE = wg_config_file
DOCKER_CONTAINER = docker_container
ENDPOINT = endpoint
YOOKASSA_PROVIDER_TOKEN = yookassa_provider_token
VPN_NAME = vpn_name
FAST_API_URL = fast_api_url

# Кэш и файлы
ISP_CACHE_FILE = "files/isp_cache.json"
CACHE_TTL = 24 * 3600  # 24 часа
DB_FILE = "database.db"

# Активные платёжные системы
ACTIVE_PAYMENT_SYSTEMS = [  
    "telegram_stars",  # Telegram Stars
]

# Планы подписки для каждой платёжной системы
PAYMENT_PLANS = {
    "yookassa": {
        "currency": "RUB",
        "plans": [
            {"months": 1, "price": 80, "label": "1 месяц - 80₽"},
            {"months": 2, "price": 150, "label": "2 месяца - 150₽"},
            {"months": 3, "price": 210, "label": "3 месяца - 210₽"},
        ],
    },
    "telegram_stars": {
        "currency": "STARS",
        "plans": [
            {"months": 1, "price": 100, "label": "1 месяц - 100⭐"},
            {"months": 2, "price": 180, "label": "2 месяца - 180⭐"},
            {"months": 3, "price": 250, "label": "3 месяца - 250⭐"},
        ],
    },
}

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