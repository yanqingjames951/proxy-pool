from typing import List
from app.crawlers.base_crawler import BaseCrawler
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

class FreeProxyListCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.site_name = "Free Proxy List"
        self.urls = ["https://free-proxy-list.net/"]
        
    def parse(self, html: str) -> List[str]:
        """解析Free Proxy List HTML页面"""
        proxies = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # 解析表格数据
        table = soup.find('table', {'id': 'proxylisttable'})
        if not table:
            logger.warning(f"{self.site_name} 未找到代理表格")
            return proxies
            
        tbody = table.find('tbody')
        if not tbody:
            logger.warning(f"{self.site_name} 未找到表格内容")
            return proxies
            
        for row in tbody.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 7:
                ip = cols[0].text.strip()
                port = cols[1].text.strip()
                https = cols[6].text.strip().lower() == 'yes'
                protocol = "https" if https else "http"
                
                if ip and port:
                    proxy = f"{protocol}://{ip}:{port}"
                    proxies.append(proxy)
                    logger.debug(f"发现代理: {proxy}")
        
        logger.info(f"{self.site_name} 解析完成，找到 {len(proxies)} 个代理")
        return proxies
