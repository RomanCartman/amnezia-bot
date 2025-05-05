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

# Кэш и файлы
ISP_CACHE_FILE = "files/isp_cache.json"
CACHE_TTL = 24 * 3600  # 24 часа
DB_FILE = "database.db"
