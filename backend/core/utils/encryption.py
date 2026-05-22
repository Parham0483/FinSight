from cryptography.fernet import Fernet
from django.conf import settings


def _get_fernet() -> Fernet:
    if not settings.FERNET_KEY:
        raise RuntimeError('FERNET_KEY is not configured')
    return Fernet(settings.FERNET_KEY.encode() if isinstance(settings.FERNET_KEY, str) else settings.FERNET_KEY)


def encrypt(value: str) -> str:
    return _get_fernet().encrypt(value.encode()).decode()


def decrypt(token: str) -> str:
    return _get_fernet().decrypt(token.encode()).decode()
