import aiohttp
import asyncio
from datetime import datetime
from app.core.config import settings
from app.storage.redis_client import redis_conn

class ProxyValidator:
    def __init__(self):
        self.test_url = "http://httpbin.org/ip"
        self.timeout = aiohttp.ClientTimeout(total=settings.PROXY_TIMEOUT)
        self.semaphore = asyncio.Semaphore(50)  # 并发控制

    async def _verify_proxy(self, proxy):
        async with self.semaphore:
            try:
                async with aiohttp.ClientSession(timeout=self.timeout) as session:
                    async with session.get(
                        self.test_url,
                        proxy=f"http://{proxy}",
                        headers={"User-Agent": "ProxyPool Validator"}
                    ) as resp:
                        if resp.status == 200:
                            return proxy, True
            except Exception as e:
                pass
            return proxy, False

    async def validate_proxies(self, proxies):
        tasks = [self._verify_proxy(proxy) for proxy in proxies]
        results = await asyncio.gather(*tasks)
        
        valid_proxies = [proxy for proxy, status in results if status]
        now = datetime.now().timestamp()
        
        async with redis_conn.pipeline() as pipe:
            for proxy in valid_proxies:
                pipe.zadd(settings.PROXY_KEY, {proxy: now})
            pipe.zremrangebyrank(settings.PROXY_KEY, 0, -settings.MAX_PROXIES)
            await pipe.execute()
            
        return len(valid_proxies)
