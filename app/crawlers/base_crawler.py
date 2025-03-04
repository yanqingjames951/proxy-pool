from typing import Optional, List
import httpx
import asyncio
import logging
from app.core.config import settings
from app.storage.redis_client import redis_storage

logger = logging.getLogger(__name__)

class BaseCrawler:
    def __init__(self):
        self.site_name = "base"
        self.urls = []
        self.timeout = settings.CRAWL_TIMEOUT
        self.max_retries = settings.CRAWL_MAX_RETRIES
        
    async def fetch(self, url: str) -> Optional[str]:
        """带重试机制的请求方法"""
        async with httpx.AsyncClient() as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.get(
                        url,
                        timeout=self.timeout,
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                        }
                    )
                    response.raise_for_status()
                    return response.text
                except Exception as e:
                    logger.warning(f"请求失败（尝试 {attempt+1}/{self.max_retries}）: {str(e)}")
                    await asyncio.sleep(2 ** attempt)
        return None

    def parse(self, html: str) -> List[str]:
        """解析方法需要子类实现"""
        raise NotImplementedError("子类必须实现parse方法")

    async def crawl(self) -> int:
        """执行爬取并返回获取的代理数量"""
        proxies = []
        for url in self.urls:
            html = await self.fetch(url)
            if html:
                try:
                    proxies.extend(self.parse(html))
                except Exception as e:
                    logger.error(f"解析失败: {str(e)}")
        
        # 去重并存储代理
        new_count = 0
        for proxy in set(proxies):
            if await redis_storage.add_proxy(proxy, 10):  # 初始分数10
                new_count += 1
        
        logger.info(f"{self.site_name} 爬取完成，新增代理: {new_count}")
        return new_count
