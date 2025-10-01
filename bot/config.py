import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")  # e.g. @myconfessions
DATABASE_URL = os.getenv("DATABASE_URL")
FERNET_KEY = os.getenv("FERNET_KEY")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Notify author when reactions increase by this number
NOTIFY_DELTA = int(os.getenv("NOTIFY_DELTA", "3"))
