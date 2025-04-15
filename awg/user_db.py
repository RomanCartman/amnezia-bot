from datetime import datetime, timedelta
import sqlite3
from typing import Literal, Optional, Union
from dateutil.relativedelta import relativedelta


from service.base_model import Config, User


# =====================================================================
# Интегрированный класс Database для управления пользователями и конфигурациями VPN
# =====================================================================

DB_FILE = "database.db"


class Database:
    def __init__(self, db_path=DB_FILE):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        """Создает таблицы для пользователей и конфигураций VPN, если они отсутствуют."""
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                telegram_id TEXT UNIQUE,
                name TEXT,
                end_date TEXT,
                is_unlimited INTEGER DEFAULT 0
            )
        """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS configs (
                config_id INTEGER PRIMARY KEY,
                user_id INTEGER,
                public_key TEXT NOT NULL,
                preshared_key TEXT,
                tunnel_ip TEXT NOT NULL,
                vpn_url TEXT,
                wireguard_config TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                months INTEGER,
                provider_payment_id TEXT,
                payment_time TEXT DEFAULT CURRENT_TIMESTAMP,
                raw_payload TEXT,
                status TEXT DEFAULT 'pending',
                unique_payload TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
"""
        )
        self.conn.commit()

    def get_user_by_telegram_id(self, telegram_id: str) -> Union[User, Literal[False]]:
        """Возвращает пользователя по telegram_id или False, если не найден."""
        self.cursor.execute(
            "SELECT user_id, telegram_id, name, end_date, is_unlimited FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = self.cursor.fetchone()
        if not row:
            return False
        return User(
            user_id=row[0],
            telegram_id=row[1],
            name=row[2],
            end_date=row[3],
            is_unlimited=row[4],
        )

    def add_user(self, telegram_id, name):
        """Добавляет нового пользователя по telegram_id, если его нет."""
        if not self.user_exists(telegram_id):
            self.cursor.execute(
                "INSERT INTO users (telegram_id, name) VALUES (?, ?)",
                (telegram_id, name),
            )
            self.conn.commit()

    def has_active_subscription(self, telegram_id):
        """Проверяем подписку пользователя
        end_date = NULL и is_unlimited = 0 → нет подписки
        end_date = [дата] и is_unlimited = 0 → обычная подписка
        is_unlimited = 1 → подписка безлимитная (дата не имеет значения)"""
        self.cursor.execute(
            "SELECT end_date, is_unlimited FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        row = self.cursor.fetchone()
        if not row:
            return False
        end_date, is_unlimited = row
        if is_unlimited:
            return True
        if end_date:
            return datetime.strptime(end_date, "%Y-%m-%d") > datetime.now()
        return False

    def get_users_expired_yesterday(self):
        """Возвращает список пользователей, у которых подписка закончилась вчера,
        is_unlimited != 1 и end_date не NULL.
        """
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        self.cursor.execute(
            """
            SELECT user_id, telegram_id, name, end_date
            FROM users
            WHERE is_unlimited != 1
            AND end_date IS NOT NULL
            AND end_date = ?
            """,
            (yesterday,),
        )
        return self.cursor.fetchall()

    def add_config(
        self,
        telegram_id: str,
        public_key: str,
        preshared_key: Optional[str],
        tunnel_ip: str,
        vpn_url: Optional[str],
        wireguard_config: Optional[str],
    ) -> int:
        """Добавляет VPN-конфигурацию пользователя по telegram_id."""

        user = self.get_user_by_telegram_id(telegram_id)
        if not user:
            raise ValueError(f"Пользователь с telegram_id {telegram_id} не найден.")

        self.cursor.execute(
            """
            INSERT INTO configs (
                user_id, public_key, preshared_key, tunnel_ip, vpn_url, wireguard_config
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user.user_id,
                public_key,
                preshared_key,
                tunnel_ip,
                vpn_url,
                wireguard_config,
            ),
        )
        self.conn.commit()
        return self.cursor.lastrowid  # ID новой конфигурации

    def get_config_by_telegram_id(self, telegram_id) -> Optional[Config]:
        """Возвращает конфигурацию пользователя по telegram_id."""
        self.cursor.execute(
            """
            SELECT c.config_id, c.user_id, c.public_key, c.preshared_key,
                c.tunnel_ip, c.vpn_url, c.wireguard_config
            FROM configs c
            JOIN users u ON c.user_id = u.user_id
            WHERE u.telegram_id = ?
            """,
            (telegram_id,),
        )
        row = self.cursor.fetchone()
        if row:
            return Config(
                config_id=row[0],
                user_id=row[1],
                public_key=row[2],
                preshared_key=row[3],
                tunnel_ip=row[4],
                vpn_url=row[5],
                wireguard_config=row[6],
            )
        return None

    def update_user_end_date(self, telegram_id, months_to_add) -> Union[User, bool]:
        """Продлевает подписку пользователя на указанное количество месяцев."""

        user = self.get_user_by_telegram_id(telegram_id)
        if not user:
            raise ValueError(f"Пользователь с telegram_id {telegram_id} не найден.")
        
        # Получаем текущую дату окончания
        self.cursor.execute("SELECT end_date FROM users WHERE user_id = ?", (user.user_id,))
        result = self.cursor.fetchone()

        if result and result[0]:
            current_end_date = datetime.strptime(result[0], "%Y-%m-%d")
            # Если дата окончания в прошлом — берем сегодняшнюю дату
            if current_end_date < datetime.now():
                current_end_date = datetime.now()
        else:
            # Если даты нет, начинаем с сегодняшнего дня
            current_end_date = datetime.now()

        # Прибавляем месяцы
        new_end_date = current_end_date + relativedelta(months=months_to_add)
        new_end_date_str = new_end_date.strftime("%Y-%m-%d")

        # Обновляем дату окончания
        self.cursor.execute(
            "UPDATE users SET end_date = ? WHERE user_id = ?",
            (new_end_date_str, user.user_id),
        )
        self.conn.commit()
        return user

    def delete_configs_by_user_id(self, user_id):
        """Удаляет все VPN-конфигурации, связанные с пользователем по его ID."""
        self.cursor.execute("DELETE FROM configs WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def add_payment(
        self,
        user_id,
        amount,
        months,
        provider_payment_id,
        raw_payload,
        unique_payload,
        status="pending",
    ):
        """Создаёт запись о платеже."""
        self.cursor.execute(
            """
            INSERT INTO payments (
                user_id, amount, months, provider_payment_id, raw_payload, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                amount,
                months,
                provider_payment_id,
                raw_payload,
                unique_payload,
                status,
            ),
        )
        self.conn.commit()
        return self.cursor.lastrowid

    def update_payment_status(self, unique_payload, new_status):
        """Обновляет статус платежа по unique_payload."""
        self.cursor.execute(
            "UPDATE payments SET status = ? WHERE unique_payload = ?",
            (new_status, unique_payload),
        )
        self.conn.commit()

    def close(self):
        """Закрывает соединение с базой данных."""
        self.conn.close()
