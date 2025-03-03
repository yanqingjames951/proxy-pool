from app.crawlers.base_crawler import BaseCrawler
from lxml import etree
import re

class ZdayeCrawler(BaseCrawler):
    async def crawl(self):
        proxies = []
        urls = [
            "https://www.zdaye.com/dayProxy/1.html",
            "https://www.zdaye.com/dayProxy/2.html"
        ]
        
        for url in urls:
            html = await self._fetch(url)
            if html:
                tree = etree.HTML(html)
                items = tree.xpath('//table/tr[position()>1]')
                for item in items:
                    ip = item.xpath('./td[1]/text()')[0]
                    port = item.xpath('./td[2]/text()')[0]
                    protocol = "https" if "HTTPS" in item.xpath('./td[4]/text()')[0] else "http"
                    proxies.append(f"{protocol}://{ip}:{port}")
                    
        return proxies
