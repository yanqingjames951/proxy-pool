from app.crawlers.base_crawler import BaseCrawler
from bs4 import BeautifulSoup
import re

class XicidailiCrawler(BaseCrawler):
    async def crawl(self):
        url = "https://www.xicidaili.com/nn/"
        html = await self._fetch(url)
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            proxies = []
            
            # 解析表格数据
            table = soup.find('table', {'id': 'ip_list'})
            if table:
                for row in table.find_all('tr')[1:]:  # 跳过表头
                    cols = row.find_all('td')
                    if len(cols) >= 5:
                        ip = cols[1].text.strip()
                        port = cols[2].text.strip()
                        protocol = cols[5].text.strip().lower()
                        proxies.append(f"{protocol}://{ip}:{port}")
            
            await self._save_proxies(proxies)
            return len(proxies)
        return 0
