from typing import List
import re
import json
import logging
import httpx
import asyncio
from app.crawlers.base_crawler import BaseCrawler
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class KuaiDaiLiCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.site_name = "快代理"
        self.urls = ["https://www.kuaidaili.com/free/inha/"]
        # 添加更多请求头
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.google.com/"
        }

    async def fetch(self, url: str) -> str:
        """重写fetch方法，添加自定义请求头"""
        async with httpx.AsyncClient() as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.get(
                        url,
                        timeout=self.timeout,
                        headers=self.headers
                    )
                    response.raise_for_status()
                    return response.text
                except Exception as e:
                    logger.warning(f"请求失败（尝试 {attempt+1}/{self.max_retries}）: {str(e)}")
                    await asyncio.sleep(2 ** attempt)
        return None

    def parse(self, html: str) -> List[str]:
        """解析快代理HTML页面，从JavaScript变量中提取代理数据"""
        proxies = []
        
        # 使用正则表达式从JavaScript中提取代理列表
        pattern = r'const\s+fpsList\s*=\s*(\[.*?\]);'
        match = re.search(pattern, html, re.DOTALL)
        
        if not match:
            logger.warning(f"{self.site_name} 未找到代理数据")
            return proxies
            
        try:
            # 修复JSON格式问题（缺少逗号）
            proxy_json_str = match.group(1).replace('} {', '}, {')
            # 解析JSON数据
            proxy_list = json.loads(proxy_json_str)
            
            for proxy_data in proxy_list:
                ip = proxy_data.get('ip')
                port = proxy_data.get('port')
                
                if ip and port:
                    # 默认使用http协议，因为页面中没有明确指定协议
                    protocol = "http"
                    proxy = f"{protocol}://{ip}:{port}"
                    proxies.append(proxy)
                    logger.debug(f"发现代理: {proxy}")
            
            logger.info(f"{self.site_name} 解析完成，找到 {len(proxies)} 个代理")
            
        except json.JSONDecodeError as e:
            logger.error(f"{self.site_name} JSON解析失败: {str(e)}")
        except Exception as e:
            logger.error(f"{self.site_name} 解析出错: {str(e)}")
            
        return proxies
