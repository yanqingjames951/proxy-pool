from app.crawlers.base_crawler import BaseCrawler
from bs4 import BeautifulSoup

class KuaidailiCrawler(BaseCrawler):
    async def crawl(self):
        url = "https://www.kuaidaili.com/free/inha/"
        html = await self._fetch(url)
        if html:
            soup = BeautifulSoup(html, 'html.parser')
            proxies = []
            
            # 解析表格数据
            table = soup.find('table', class_='table table-bordered table-striped')
            if table:
                for row in table.find_all('tr')[1:]:  # 跳过表头
                    cols = row.find_all('td')
                    if len(cols) >= 4:
                        ip = cols[0].text.strip()
                        port = cols[1].text.strip()
                        protocol = cols[3].text.strip().lower()
                        proxies.append(f"{protocol}://{ip}:{port}")
            
            await self._save_proxies(proxies)
            return len(proxies)
        return 0
