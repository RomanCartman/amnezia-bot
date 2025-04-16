import json
import os
import re
import aiohttp
import logging
import aiofiles
import ipaddress
from aiogram.types import User
from datetime import datetime, timedelta, timezone

from settings import CACHE_TTL, ISP_CACHE_FILE, WG_CONFIG_FILE

logger = logging.getLogger(__name__)


def parse_relative_time(relative_str: str) -> datetime:
    if not isinstance(relative_str, str) or not relative_str.strip():
        logger.error(f"Некорректный relative_str: {relative_str}")
        return datetime.now(timezone.UTC)  # Значение по умолчанию
    try:
        relative_str = relative_str.lower().replace(" ago", "")
        delta = 0
        for part in relative_str.split(", "):
            num, unit = part.split()
            num = int(num)
            if "minute" in unit:
                delta += num * 60
            elif "hour" in unit:
                delta += num * 3600
            elif "day" in unit:
                delta += num * 86400
            elif "week" in unit:
                delta += num * 604800
            elif "month" in unit:
                delta += num * 2592000
        return datetime.now(timezone.UTC) - timedelta(seconds=delta)
    except Exception as e:
        logger.error(f"Ошибка в parse_relative_time: {str(e)}")
        return datetime.now(timezone.UTC)  # Значение по умолчанию


def parse_transfer(transfer_str):
    if not isinstance(transfer_str, str) or not transfer_str.strip():
        logger.error(f"Некорректный transfer_str: {transfer_str}")
        return 0, 0  # Значения по умолчанию
    try:
        incoming, outgoing = re.split(r"[/,]", transfer_str)[:2]
        size_map = {
            "B": 1,
            "KB": 10**3,
            "KiB": 1024,
            "MB": 10**6,
            "MiB": 1024**2,
            "GB": 10**9,
            "GiB": 1024**3,
        }
        incoming_bytes = outgoing_bytes = 0
        for unit, multiplier in size_map.items():
            if unit in incoming:
                match = re.match(r"([\d.]+)", incoming)
                if match:
                    incoming_bytes = float(match.group(0)) * multiplier
            if unit in outgoing:
                match = re.match(r"([\d.]+)", outgoing)
                if match:
                    outgoing_bytes = float(match.group(0)) * multiplier
        return incoming_bytes, outgoing_bytes
    except Exception as e:
        logger.error(f"Ошибка в parse_transfer: {str(e)}")
        return 0, 0  # Значения по умолчанию


isp_cache = {}


def get_interface_name():
    return os.path.basename(WG_CONFIG_FILE).split(".")[0]


async def load_isp_cache():
    global isp_cache
    if os.path.exists(ISP_CACHE_FILE):
        async with aiofiles.open(ISP_CACHE_FILE, "r") as f:
            isp_cache = json.loads(await f.read())


async def save_isp_cache():
    async with aiofiles.open(ISP_CACHE_FILE, "w") as f:
        await f.write(json.dumps(isp_cache))


async def get_isp_info(ip: str) -> str:
    now = datetime.now(timezone.UTC).timestamp()
    if ip in isp_cache and (now - isp_cache[ip]["timestamp"]) < CACHE_TTL:
        return isp_cache[ip]["isp"]

    try:
        if ipaddress.ip_address(ip).is_private:
            return "Private Range"
    except:
        return "Invalid IP"

    async with aiohttp.ClientSession() as session:
        async with session.get(f"http://ip-api.com/json/{ip}?fields=isp") as resp:
            if resp.status == 200:
                data = await resp.json()
                isp = data.get("isp", "Unknown ISP")
                isp_cache[ip] = {"isp": isp, "timestamp": now}
                await save_isp_cache()
                return isp
    return "Unknown ISP"


def get_short_name(user: User) -> str:
    """Формирует имя пользователя: username или имя + фамилия (обрезается до 30 символов)."""
    if user.username:
        name = f"@{user.username}"
    else:
        name_parts = filter(None, [user.first_name, user.last_name])
        name = " ".join(name_parts)
    return name[:10]