"""
Configuration Management for Social Media CRM Backend
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Settings(BaseSettings):
    """Application Settings"""

    # Application
    APP_NAME: str = "Social Media CRM API"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./social_media_crm.db",
    )

    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ]

    # Allowed Hosts (for TrustedHostMiddleware in production)
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1", "*.example.com"]

    # Social Media Platform Settings
    FACEBOOK_API_VERSION: str = "v27.0"
    FACEBOOK_API_BASE_URL: str = "https://graph.facebook.com"
    FACEBOOK_APP_SECRET: str = ""

    INSTAGRAM_API_VERSION: str = "v18.0"
    INSTAGRAM_API_BASE_URL: str = "https://graph.instagram.com"

    # Pagination Defaults
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Webhook Settings
    WEBHOOK_VERIFY_TOKEN: str = os.getenv(
        "WEBHOOK_VERIFY_TOKEN", "your-webhook-verify-token"
    )

    # Email Settings (for future use)
    SMTP_SERVER: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SENDER_EMAIL: str = os.getenv("SENDER_EMAIL", "noreply@example.com")
    SENDER_PASSWORD: str = os.getenv("SENDER_PASSWORD", "")

    # Redis (for caching - optional)
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    USE_REDIS: bool = os.getenv("USE_REDIS", "False").lower() == "true"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)


# Initialize settings
settings = Settings()
