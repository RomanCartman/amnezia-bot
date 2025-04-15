from datetime import datetime, timedelta
import re
import pytz
import logging

logger = logging.getLogger(__name__)


def parse_relative_time(relative_str: str) -> datetime:
    if not isinstance(relative_str, str) or not relative_str.strip():
        logger.error(f"Некорректный relative_str: {relative_str}")
        return datetime.now(pytz.UTC)  # Значение по умолчанию
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
        return datetime.now(pytz.UTC) - timedelta(seconds=delta)
    except Exception as e:
        logger.error(f"Ошибка в parse_relative_time: {str(e)}")
        return datetime.now(pytz.UTC)  # Значение по умолчанию


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
