import io
import logging
import os
from datetime import datetime
import zipfile
from aiogram.types import BufferedInputFile
from service.system_stats import find_peak_usage, get_vnstat_hourly
from settings import ADMINS, BOT, DB_FILE

logger = logging.getLogger(__name__)


def create_db_backup(original_path: str, backup_dir: str = "backups") -> bytes:
    """Создает ZIP-резервную копию базы данных и других важных файлов, возвращает путь к ZIP-файлу (который будет удалён после использования)."""
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_zip_path = os.path.join(backup_dir, f"full_backup_{timestamp}.zip")

    with zipfile.ZipFile(backup_zip_path, "w") as zipf:
        # Добавить базу данных
        if os.path.exists(original_path):
            zipf.write(original_path, os.path.relpath(original_path, os.getcwd()))

        # Добавить отдельные скрипты
        for file in ["awg-decode.py", "newclient.sh", "removeclient.sh"]:
            if os.path.exists(file):
                zipf.write(file, os.path.relpath(file, os.getcwd()))

        # Добавить содержимое папки files/
        for root, _, files in os.walk("files"):
            for file in files:
                full_path = os.path.join(root, file)
                zipf.write(full_path, os.path.relpath(full_path, os.getcwd()))

        # Добавить содержимое папки users/
        for root, _, files in os.walk("users"):
            for file in files:
                full_path = os.path.join(root, file)
                zipf.write(full_path, os.path.relpath(full_path, os.getcwd()))

    # Возврат пути для использования, а затем удаление
    try:
        with open(backup_zip_path, "rb") as f:
            zip_bytes = f.read()
    finally:
        os.remove(backup_zip_path)

    return zip_bytes  # Возвращаем содержимое архива как байты


async def send_backup():
    try:
        backup_bytes = create_db_backup(DB_FILE)

        input_file = BufferedInputFile(file=backup_bytes, filename="backup.zip")

        for admin_id in ADMINS:
            await BOT.send_document(
                chat_id=admin_id,
                document=input_file,
                caption="Автоматический бэкап базы данных.",
            )
            logging.info("Бэкап успешно отправлен. {admin_id}")
    except Exception as e:
        logging.error(f"Ошибка при отправке бэкапа: {e}")


async def send_peak_usage():
    """Отчет по нагрузке на сеть"""
    vnstat_data = get_vnstat_hourly()
    peak_hour_total, peak_total, peak_hour_avg, peak_avg_rate = find_peak_usage(
        vnstat_data
    )

    if peak_hour_total and peak_hour_avg:
        response = (
            f"📊 **Самая пиковая нагрузка за день**:\n"
            f"🔹 `total`: {peak_total} ГиБ в {peak_hour_total}\n"
            f"🔹 `avg. rate`: {peak_avg_rate} Мбит/с в {peak_hour_avg}"
        )
    else:
        response = "❌ Не удалось определить пиковую нагрузку!"

    for admin_id in ADMINS:
        await BOT.send_message(chat_id=admin_id, text=response)
