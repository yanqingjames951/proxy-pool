from typing import List
from app.crawlers.base_crawler import BaseCrawler
from bs4 import BeautifulSoup
import logging
from app.storage.redis_client import redis_storage

logger = logging.getLogger(__name__)

class XicidailiCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.site_name = "西刺代理"
        self.urls = ["https://www.xicidaili.com/nn/"]
        
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
        
    def parse(self, html: str) -> List[str]:
        """解析西刺代理HTML页面"""
        proxies = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # 解析表格数据
        table = soup.find('table', {'id': 'ip_list'})
        if table:
            for row in table.find_all('tr')[1:]:  # 跳过表头
                cols = row.find_all('td')
                if len(cols) >= 6:
                    ip = cols[1].text.strip()
                    port = cols[2].text.strip()
                    protocol = cols[5].text.strip().lower()
                    if protocol and ip and port:
                        proxies.append(f"{protocol}://{ip}:{port}")
        
        return proxies
