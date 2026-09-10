from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@db:5432/fieldkit"
    REDIS_URL: str = "redis://redis:6379/0"
    WEBHOOK_SECRET: str = "fieldkit_production_hmac_secret_2026"
    ERP_API_URL: str = "http://mock-erp:8080/api/v1/sync"
    ERP_API_TOKEN: str = "mock_erp_token_secret"
    PII_ENCRYPTION_KEY: str = "k8v1A9zL3qP5rT7wY2xM4bN6cF8jH0sD"
    AI_PROVIDER: str = "mock"
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""

settings = Settings()