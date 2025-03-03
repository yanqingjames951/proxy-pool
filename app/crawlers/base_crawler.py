import aiohttp
from abc import ABC, abstractmethod
from app.core.config import settings
from app.storage.redis_client import redis_conn
import asyncio

class BaseCrawler(ABC):
    def __init__(self):
        self.timeout = aiohttp.ClientTimeout(total=10)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        
    @abstractmethod
    async def crawl(self):
        pass
        
    async def _fetch(self, url):
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(url, timeout=self.timeout) as response:
                    if response.status == 200:
                        return await response.text()
                    return None
        except Exception as e:
            print(f"Request failed: {str(e)}")
            return None

    async def _save_proxies(self, proxies):
        if proxies:
            await redis_conn.zadd(settings.PROXY_KEY, 
                {proxy: asyncio.get_event_loop().time() for proxy in proxies})
