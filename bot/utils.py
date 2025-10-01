import re
from cryptography.fernet import Fernet
from config import FERNET_KEY

fernet = Fernet(FERNET_KEY.encode()) if FERNET_KEY else None

URL_PHONE_RE = re.compile(r"(https?://|www\.|\+?\d{6,}|\w+@\w+\.)")

def sanitize_text(text: str) -> str:
    clean = URL_PHONE_RE.sub('[redacted]', text)
    return clean.strip()

def encrypt_userid(uid: int) -> str:
    if not fernet:
        raise RuntimeError("FERNET_KEY not set")
    return fernet.encrypt(str(uid).encode()).decode()

def decrypt_userid(token: str) -> int:
    if not fernet:
        raise RuntimeError("FERNET_KEY not set")
    return int(fernet.decrypt(token.encode()).decode())
