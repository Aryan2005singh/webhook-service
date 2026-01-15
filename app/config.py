"""
Configuration management via environment variables.
"""
import os
from functools import lru_cache


class Config:
    """Application configuration loaded from environment variables."""
    
    def __init__(self):
        self.webhook_secret = os.getenv("WEBHOOK_SECRET", "")
        self.database_url = os.getenv("DATABASE_URL", "messages.db")
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
    
    def is_ready(self) -> bool:
        """Check if required configuration is present."""
        return bool(self.webhook_secret)


@lru_cache()
def get_config() -> Config:
    """Get cached configuration instance."""
    return Config()
