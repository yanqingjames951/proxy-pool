import os

class Settings:
    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB = int(os.getenv("REDIS_DB", 0))
    PROXY_KEY = "proxies:valid"  # Redis有序集合键名
    CHECK_INTERVAL = 600  # 代理验证间隔(秒)
    PROXY_TIMEOUT = 10  # 代理验证超时时间
    MIN_PROXIES = 50  # 最小代理数阈值
    MAX_PROXIES = 1000  # 最大代理数限制

settings = Settings()
