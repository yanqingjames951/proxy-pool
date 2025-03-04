import os
from enum import Enum

class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"

class Settings:
    # Redis配置
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    PROXY_KEY: str = os.getenv("PROXY_KEY", "proxies:valid")
    
    # 代理验证配置
    CHECK_INTERVAL: int = int(os.getenv("CHECK_INTERVAL", 600))
    PROXY_TIMEOUT: int = int(os.getenv("PROXY_TIMEOUT", 10))
    MIN_PROXIES: int = int(os.getenv("MIN_PROXIES", 50))
    MAX_PROXIES: int = int(os.getenv("MAX_PROXIES", 1000))
    
    # 日志配置
    LOG_LEVEL: LogLevel = LogLevel[os.getenv("LOG_LEVEL", "INFO")]
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", 
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # 爬虫配置
    CRAWL_TIMEOUT: int = int(os.getenv("CRAWL_TIMEOUT", 30))
    CRAWL_MAX_RETRIES: int = int(os.getenv("CRAWL_MAX_RETRIES", 3))

settings = Settings()
