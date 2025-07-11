import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    API_KEY: str = os.getenv("API_KEY", "demo-key")
    API_SECRET: str = os.getenv("API_SECRET", "demo-secret")
    BASE_URL: str = os.getenv("BASE_URL", "wss://demo.ironbeam.com/socket")
    ENV: str = os.getenv("ENV", "development")

    class Config:
        env_file = ".env"

settings = Settings()
