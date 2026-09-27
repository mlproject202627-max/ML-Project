from pydantic_settings import BaseSettings
from typing import List
import json


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://sentinel:sentinel_secret@localhost:5432/sentinel_db"
    
    # JWT
    JWT_SECRET: str = "your-super-secret-jwt-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # CORS
    CORS_ORIGINS: str = '["http://localhost:3000","http://localhost:5173","https://airy-stillness-production-cac9.up.railway.app"]'
    
    # Endpoint agent authentication (X-Agent-Key header)
    AGENT_API_KEY: str = ""  # optional shared bootstrap key; per-user keys preferred

    # Environment
    ENVIRONMENT: str = "development"

    # ML model artefact. Read by `ml.anomaly`; the default lives beside the
    # code so a fresh checkout trains and loads from the same place.
    MODEL_PATH: str = ""

    # Redis (optional)
    REDIS_URL: str = "redis://localhost:6379"

    @property
    def cors_origins_list(self) -> List[str]:
        try:
            return json.loads(self.CORS_ORIGINS)
        except (json.JSONDecodeError, TypeError):
            return ["http://localhost:3000", "http://localhost:5173", "https://airy-stillness-production-cac9.up.railway.app"]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
