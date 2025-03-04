from typing import List
from app.crawlers.base_crawler import BaseCrawler
from bs4 import BeautifulSoup

class KuaiDaiLiCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.site_name = "快代理"
        self.urls = ["https://www.kuaidaili.com/free/inha/"]

    def parse(self, html: str) -> List[str]:
        """解析快代理HTML页面"""
        proxies = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # 解析表格数据
        table = soup.find('table')
        if table:
            for row in table.find_all('tr')[1:]:  # 跳过表头
                cols = row.find_all('td')
                if len(cols) >= 5:
                    ip = cols[0].text.strip()
                    port = cols[1].text.strip()
                    protocol = cols[4].text.strip().replace(" ", "").lower()
                    if protocol and ip and port:
                        proxies.append(f"{protocol}://{ip}:{port}")
        
        return proxies
