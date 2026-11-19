import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Shopify Credentials
    SHOPIFY_STORE_URL: str = os.getenv("SHOPIFY_STORE_URL", "elhoda.net")
    SHOPIFY_ADMIN_ACCESS_TOKEN: str = os.getenv("SHOPIFY_ADMIN_ACCESS_TOKEN", "")
    SHOPIFY_API_VERSION: str = os.getenv("SHOPIFY_API_VERSION", "2024-04")

    # Gemini AI
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_ALLOWED_USER_IDS: str = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")

    # Dashboard Authentication (format: username:password,username2:pass2)
    DASHBOARD_USERS: str = os.getenv("DASHBOARD_USERS", "admin:elhoda@2026")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "elhoda-super-secret-key-2026")

    # Server
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", 8000))

    def clean_store_domain(self) -> str:
        domain = self.SHOPIFY_STORE_URL.strip().lower()
        domain = domain.replace("https://", "").replace("http://", "").rstrip("/")
        return domain

    def get_users_dict(self) -> dict[str, str]:
        users = {}
        raw = self.DASHBOARD_USERS.strip()
        if not raw:
            return {"admin": "elhoda@2026"}
        for item in raw.split(","):
            if ":" in item:
                u, p = item.split(":", 1)
                users[u.strip()] = p.strip()
        return users or {"admin": "elhoda@2026"}

    def allowed_telegram_users(self) -> list[int]:
        if not self.TELEGRAM_ALLOWED_USER_IDS.strip():
            return []
        ids = []
        for x in self.TELEGRAM_ALLOWED_USER_IDS.split(","):
            x = x.strip()
            if x.isdigit():
                ids.append(int(x))
        return ids

settings = Settings()
