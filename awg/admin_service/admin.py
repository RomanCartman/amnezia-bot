from settings import ADMINS, MODERATORS

def is_privileged(user_id: int) -> bool:
    return user_id in ADMINS or user_id in MODERATORS