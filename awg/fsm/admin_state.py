from aiogram.fsm.state import State, StatesGroup

class AdminState(StatesGroup):
    """Состояния для действий администратора, требующих ввода от пользователя"""
    waiting_for_user_name = State()
    waiting_for_admin_id = State()