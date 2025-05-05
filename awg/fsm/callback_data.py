from aiogram.filters.callback_data import CallbackData

class ClientCallbackFactory(CallbackData, prefix="client"):
    username: str