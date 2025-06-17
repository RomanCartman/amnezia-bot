from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_menu_markup(user_id, admins):
    buttons = [
        [
            InlineKeyboardButton(
                text="➕ Добавить пользователя", callback_data="add_user"
            ),
            InlineKeyboardButton(text="📋 Список клиентов", callback_data="list_users"),
        ],
        [
            InlineKeyboardButton(text="🔑 Получить конфиг", callback_data="get_config"),
            InlineKeyboardButton(text="ℹ️ Инструкция", callback_data="instructions"),
        ],
    ]

    if user_id in admins:
        buttons.append(
            [
                InlineKeyboardButton(
                    text="👥 Список админов", callback_data="list_admins"
                ),
                InlineKeyboardButton(
                    text="👤 Добавить админа", callback_data="add_admin"
                ),
            ]
        )
        buttons.append(
            [
                InlineKeyboardButton(
                    text="💾 Создать бекап", callback_data="create_backup"
                ),
            ]
        )

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_home_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура с кнопкой 'Домой'."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🏠 Домой", callback_data="home")]]
    )


def get_client_profile_keyboard(username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="ℹ️ IP info", callback_data=f"ip_info_{username}"
                ),
                InlineKeyboardButton(
                    text="🔗 Подключения", callback_data=f"connections_{username}"
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑️ Удалить", callback_data=f"delete_user_{username}"
                )
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="list_users"),
                InlineKeyboardButton(text="🏠 Домой", callback_data="home"),
            ],
        ]
    )


def get_user_main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Купить VPN", callback_data="buy_vpn")],
            [InlineKeyboardButton(text="💳 Профиль", callback_data="user_account")],
            [
                InlineKeyboardButton(
                    text="📲 Как установить", callback_data="instructions"
                )
            ],
        ]
    )


def get_user_profile_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📥 Получить конфиг", callback_data="get_config"
                ),
                InlineKeyboardButton(text="🔄 Продлить", callback_data="buy_vpn"),
            ],
            [
                InlineKeyboardButton(text="ℹ️ Инструкция", callback_data="instructions"),
            ],
            [
                InlineKeyboardButton(text="🏠 Домой", callback_data="home"),
            ],
        ]
    )


def get_user_profile_menu_expired() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Продлить", callback_data="renew_vpn"),
            ],
            [
                InlineKeyboardButton(text="🏠 Домой", callback_data="home"),
            ],
        ]
    )


def get_instruction_type() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📱 iPhone", callback_data="instruction_iphone"
                ),
                InlineKeyboardButton(
                    text="🤖 Android", callback_data="instruction_android"
                ),
            ],
            [
                InlineKeyboardButton(text="🏠 Домой", callback_data="home"),
            ],
        ]
    )
