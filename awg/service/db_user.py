import logging
from datetime import datetime, timedelta
import sqlite3
from typing import List, Literal, Optional, Union
from dateutil.relativedelta import relativedelta

from service.base_model import Payment, UserData, Config

logger = logging.getLogger(__name__)


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
                is_unlimited INTEGER DEFAULT 0,
                has_used_trial INTEGER DEFAULT 0
            )
        """
        )
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS configs (
                config_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                
                -- Интерфейс
                private_key TEXT NOT NULL,
                address TEXT NOT NULL,
                dns TEXT,

                jc INTEGER,
                jmin INTEGER,
                jmax INTEGER,
                s1 INTEGER,
                s2 INTEGER,
                h1 INTEGER,
                h2 INTEGER,
                h3 INTEGER,
                h4 INTEGER,

                -- Параметры peer'а
                public_key TEXT NOT NULL,
                preshared_key TEXT,
                allowed_ips TEXT,
                endpoint TEXT,
                persistent_keepalive INTEGER,

                -- deactivate_presharekey

                deactivate_presharekey TEXT,

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

    def get_user_by_telegram_id(
        self, telegram_id: str
    ) -> Union[UserData, Literal[False]]:
        """Возвращает пользователя по telegram_id или False, если не найден."""
        self.cursor.execute(
            """
            SELECT user_id, telegram_id, name, end_date, is_unlimited, has_used_trial
            FROM users
            WHERE telegram_id = ?
            """,
            (telegram_id,),
        )
        row = self.cursor.fetchone()
        if not row:
            return False
        return UserData(
            user_id=row[0],
            telegram_id=row[1],
            name=row[2],
            end_date=row[3],
            is_unlimited=row[4],
            has_used_trial=row[5],
        )

    def get_user_by_user_id(self, user_id: int) -> Union[UserData, Literal[False]]:
        """Возвращает пользователя по user_id или False, если не найден."""
        self.cursor.execute(
            """
            SELECT user_id, telegram_id, name, end_date, is_unlimited, has_used_trial
            FROM users
            WHERE user_id = ?
            """,
            (user_id,),
        )
        row = self.cursor.fetchone()
        if not row:
            return False
        return UserData(
            user_id=row[0],
            telegram_id=row[1],
            name=row[2],
            end_date=row[3],
            is_unlimited=row[4],
            has_used_trial=row[5],
        )

    def add_user(self, telegram_id: str, name: str) -> None:
        """Добавляет нового пользователя, если он ещё не существует."""
        if not self.get_user_by_telegram_id(telegram_id):
            self.cursor.execute(
                """
                INSERT INTO users (telegram_id, name, end_date, is_unlimited, has_used_trial)
                VALUES (?, ?, NULL, 0, 0)
                """,
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

    def get_users_expired_yesterday(self) -> List[UserData]:
        """Возвращает список пользователей, у которых подписка закончилась вчера,
        is_unlimited != 1 и end_date не NULL.
        """
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        self.cursor.execute(
            """
            SELECT user_id, telegram_id, name, end_date, is_unlimited, has_used_trial
            FROM users
            WHERE is_unlimited != 1
            AND end_date IS NOT NULL
            AND end_date <= ?
            """,
            (yesterday,),
        )
        logger.info(f"yesterday: {yesterday}")
        return [
            UserData(
                user_id=row[0],
                telegram_id=row[1],
                name=row[2],
                end_date=row[3],
                is_unlimited=row[4],
                has_used_trial=row[5],
            )
            for row in self.cursor.fetchall()
        ]

    def get_active_users(self) -> List[UserData]:
        """Возвращает список пользователей с is_unlimited = 1 или у кого end_date сегодня или в будущем."""
        today = datetime.now().strftime("%Y-%m-%d")

        self.cursor.execute(
            """
            SELECT user_id, telegram_id, name, end_date, is_unlimited, has_used_trial
            FROM users
            WHERE is_unlimited = 1
            OR (end_date IS NOT NULL AND end_date >= ?)
            """,
            (today,),
        )

        rows = self.cursor.fetchall()
        return [
            UserData(
                user_id=row[0],
                telegram_id=row[1],
                name=row[2],
                end_date=row[3],
                is_unlimited=row[4],
                has_used_trial=row[5],
            )
            for row in rows
        ]

    def add_config(
        self,
        telegram_id: str,
        private_key: str,
        address: str,
        dns: Optional[str],
        jc: Optional[int],
        jmin: Optional[int],
        jmax: Optional[int],
        s1: Optional[int],
        s2: Optional[int],
        h1: Optional[int],
        h2: Optional[int],
        h3: Optional[int],
        h4: Optional[int],
        public_key: str,
        preshared_key: Optional[str],
        allowed_ips: Optional[str],
        endpoint: Optional[str],
        persistent_keepalive: Optional[int],
        deactivate_presharekey: Optional[str],
    ) -> int:
        """Добавляет VPN-конфигурацию пользователя по telegram_id."""

        user = self.get_user_by_telegram_id(telegram_id)
        if not user:
            raise ValueError(f"Пользователь с telegram_id {telegram_id} не найден.")

        self.cursor.execute(
            """
            INSERT INTO configs (
                user_id, private_key, address, dns,
                jc, jmin, jmax, s1, s2,
                h1, h2, h3, h4,
                public_key, preshared_key,
                allowed_ips, endpoint, persistent_keepalive,
                deactivate_presharekey
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user.user_id,
                private_key,
                address,
                dns,
                jc,
                jmin,
                jmax,
                s1,
                s2,
                h1,
                h2,
                h3,
                h4,
                public_key,
                preshared_key,
                allowed_ips,
                endpoint,
                persistent_keepalive,
                deactivate_presharekey,
            ),
        )
        self.conn.commit()
        return self.cursor.lastrowid  # ID новой конфигурации

    def get_config_by_telegram_id(self, telegram_id: str) -> Optional[Config]:
        """Возвращает полную конфигурацию пользователя по telegram_id."""
        self.cursor.execute(
            """
            SELECT c.config_id, c.user_id,
                c.private_key, c.address, c.dns,
                c.jc, c.jmin, c.jmax,
                c.s1, c.s2,
                c.h1, c.h2, c.h3, c.h4,
                c.public_key, c.preshared_key,
                c.allowed_ips, c.endpoint, c.persistent_keepalive,
                c.deactivate_presharekey
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
                private_key=row[2],
                address=row[3],
                dns=row[4],
                jc=row[5],
                jmin=row[6],
                jmax=row[7],
                s1=row[8],
                s2=row[9],
                h1=row[10],
                h2=row[11],
                h3=row[12],
                h4=row[13],
                public_key=row[14],
                preshared_key=row[15],
                allowed_ips=row[16],
                endpoint=row[17],
                persistent_keepalive=row[18],
                deactivate_presharekey=row[19],
            )
        return None

    def update_user_end_date(
        self, telegram_id: str, months_to_add: int
    ) -> Union[UserData, bool]:
        """Продлевает подписку пользователя на указанное количество месяцев."""

        user = self.get_user_by_telegram_id(telegram_id)
        if not user:
            raise ValueError(f"Пользователь с telegram_id {telegram_id} не найден.")

        # Получаем текущую дату окончания
        self.cursor.execute(
            "SELECT end_date FROM users WHERE user_id = ?", (user.user_id,)
        )
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
                user_id, amount, months, provider_payment_id, raw_payload, unique_payload, status
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

    def update_payment_status(
        self, raw_payload: str, unique_payload: str, new_status: str
    ) -> Optional[Payment]:
        """
        Обновляет unique_payload и статус платежа по raw_payload.
        Возвращает обновлённый объект Payment, если успешно, иначе None.
        """
        self.cursor.execute(
            """
            UPDATE payments
            SET unique_payload = ?, status = ?
            WHERE raw_payload = ?
            """,
            (unique_payload, new_status, raw_payload),
        )
        self.conn.commit()

        if self.cursor.rowcount == 0:
            return None

        # Получаем обновлённый платёж
        self.cursor.execute(
            """
            SELECT payment_id, user_id, amount, months, provider_payment_id,
                payment_time, raw_payload, status, unique_payload
            FROM payments
            WHERE raw_payload = ?
            """,
            (raw_payload,),
        )
        row = self.cursor.fetchone()
        if row:
            return Payment(
                payment_id=row[0],
                user_id=row[1],
                amount=row[2],
                months=row[3],
                provider_payment_id=row[4],
                payment_time=row[5],
                raw_payload=row[6],
                status=row[7],
                unique_payload=row[8],
            )
        return None

    def close(self):
        """Закрывает соединение с базой данных."""
        self.conn.close()
