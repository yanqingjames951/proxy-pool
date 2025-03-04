from typing import List
from app.crawlers.base_crawler import BaseCrawler
import logging
import re

logger = logging.getLogger(__name__)

class ProxyScrapeCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.site_name = "ProxyScrape"
        # 直接使用API获取代理列表，格式为纯文本
        self.urls = [
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=https&timeout=10000&country=all&ssl=all&anonymity=all"
        ]
        
    def parse(self, html: str) -> List[str]:
        """解析ProxyScrape API返回的纯文本代理列表"""
        proxies = []
        
        # 确定协议类型
        protocol = "http"
        if "protocol=https" in self.urls[0]:
            protocol = "https"
            
        # 按行分割文本
        lines = html.strip().split('\n')
        
        # 解析每一行
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 检查是否符合IP:PORT格式
            if re.match(r'^\d+\.\d+\.\d+\.\d+:\d+$', line):
                proxy = f"{protocol}://{line}"
                proxies.append(proxy)
                logger.debug(f"发现代理: {proxy}")
        
        logger.info(f"{self.site_name} ({protocol}) 解析完成，找到 {len(proxies)} 个代理")
        return proxies
