from typing import List
import httpx
import asyncio
import logging
import re
from app.crawlers.base_crawler import BaseCrawler
from bs4 import BeautifulSoup
from app.storage.redis_client import redis_storage

logger = logging.getLogger(__name__)

class ProxyListPlusCrawler(BaseCrawler):
    """
    ProxyListPlus爬虫 - 专门从国际代理站点获取HTTP/HTTPS代理
    """
    def __init__(self):
        super().__init__()
        self.site_name = "ProxyListPlus"
        self.urls = [
            "https://list.proxylistplus.com/Fresh-HTTP-Proxy-List-1",
            "https://list.proxylistplus.com/Fresh-HTTP-Proxy-List-2",
            "https://list.proxylistplus.com/SSL-List-1",
            "https://www.sslproxies.org/",
            "https://www.us-proxy.org/",
            "https://hidemy.name/en/proxy-list/",
            "https://www.freeproxylists.net/"
        ]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
    
    async def fetch(self, url: str) -> str:
        """获取页面内容"""
        async with httpx.AsyncClient(follow_redirects=True) as client:
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
    
    async def crawl(self) -> int:
        """执行爬取并返回获取的代理数量"""
        proxies = []
        
        for url in self.urls:
            logger.info(f"尝试从 {url} 获取代理")
            html = await self.fetch(url)
            if html:
                try:
                    url_proxies = self.parse(html, url)
                    if url_proxies:
                        proxies.extend(url_proxies)
                        logger.info(f"从 {url} 成功获取 {len(url_proxies)} 个代理")
                except Exception as e:
                    logger.error(f"解析失败: {str(e)}")
        
        if not proxies:
            logger.warning(f"{self.site_name} 所有URL均未获取到代理")
            return 0
        
        # 去重并存储代理
        new_count = 0
        for proxy in set(proxies):
            if await redis_storage.add_proxy(proxy, 10):  # 初始分数10
                new_count += 1
        
        logger.info(f"{self.site_name} 爬取完成，新增代理: {new_count}")
        return new_count
    
    def parse(self, html: str, url: str) -> List[str]:
        """解析HTML页面，提取代理"""
        proxies = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # 根据不同网站使用不同的解析逻辑
        if "proxylistplus.com" in url:
            # ProxyListPlus网站解析
            tables = soup.find_all('table', {'class': 'bg'})
            for table in tables:
                rows = table.find_all('tr')
                for row in rows[2:]:  # 跳过表头和分隔行
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        ip = cols[1].text.strip()
                        port = cols[2].text.strip()
                        if ip and port:
                            # 添加HTTP和HTTPS代理
                            http_proxy = f"http://{ip}:{port}"
                            https_proxy = f"https://{ip}:{port}"
                            proxies.append(http_proxy)
                            proxies.append(https_proxy)
                            logger.debug(f"发现代理: {http_proxy}")
        
        elif "sslproxies.org" in url or "us-proxy.org" in url:
            # sslproxies.org和us-proxy.org网站解析
            table = soup.find('table', {'id': 'proxylisttable'})
            if table:
                rows = table.find_all('tr')
                for row in rows[1:]:  # 跳过表头
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        ip = cols[0].text.strip()
                        port = cols[1].text.strip()
                        https = cols[6].text.strip() if len(cols) > 6 else ""
                        
                        if ip and port:
                            # 根据HTTPS列决定协议
                            if https.lower() == "yes":
                                proxy = f"https://{ip}:{port}"
                            else:
                                proxy = f"http://{ip}:{port}"
                            
                            proxies.append(proxy)
                            logger.debug(f"发现代理: {proxy}")
        
        elif "hidemy.name" in url:
            # hidemy.name网站解析
            table = soup.find('table', {'class': 'proxy__t'})
            if table:
                rows = table.find_all('tr')
                for row in rows[1:]:  # 跳过表头
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        ip = cols[0].text.strip()
                        port = cols[1].text.strip()
                        
                        if ip and port:
                            # 添加HTTP和HTTPS代理
                            http_proxy = f"http://{ip}:{port}"
                            https_proxy = f"https://{ip}:{port}"
                            proxies.append(http_proxy)
                            proxies.append(https_proxy)
                            logger.debug(f"发现代理: {http_proxy}")
        
        elif "freeproxylists.net" in url:
            # freeproxylists.net网站解析
            # 这个网站的代理信息可能在JavaScript中
            script_tags = soup.find_all("script")
            for script in script_tags:
                script_text = str(script)
                if "IPDecode" in script_text:
                    # 尝试提取编码的IP
                    ip_matches = re.findall(r"IPDecode\('([^']+)'\)", script_text)
                    port_matches = re.findall(r"<td>(\d+)</td>", script_text)
                    
                    for i in range(min(len(ip_matches), len(port_matches))):
                        try:
                            # 解码IP (通常是Base64或其他编码)
                            import base64
                            ip = base64.b64decode(ip_matches[i]).decode('utf-8')
                            port = port_matches[i]
                            
                            if ip and port:
                                # 添加HTTP和HTTPS代理
                                http_proxy = f"http://{ip}:{port}"
                                https_proxy = f"https://{ip}:{port}"
                                proxies.append(http_proxy)
                                proxies.append(https_proxy)
                                logger.debug(f"发现代理: {http_proxy}")
                        except Exception as e:
                            logger.debug(f"解码失败: {str(e)}")
        
        # 如果以上解析方法都失败，尝试通用的表格解析
        if not proxies:
            tables = soup.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows[1:]:  # 跳过表头
                    cols = row.find_all('td')
                    if len(cols) >= 2:
                        for i in range(len(cols) - 1):
                            col_text = cols[i].text.strip()
                            next_col_text = cols[i+1].text.strip()
                            
                            # 检查是否是IP地址
                            if "." in col_text and all(part.isdigit() for part in col_text.split(".") if part):
                                # 检查下一列是否是端口号
                                if next_col_text.isdigit() and 1 <= int(next_col_text) <= 65535:
                                    ip = col_text
                                    port = next_col_text
                                    
                                    # 添加HTTP和HTTPS代理
                                    http_proxy = f"http://{ip}:{port}"
                                    https_proxy = f"https://{ip}:{port}"
                                    proxies.append(http_proxy)
                                    proxies.append(https_proxy)
                                    logger.debug(f"发现代理: {http_proxy}")
        
        # 如果表格解析失败，尝试使用正则表达式直接从HTML中提取IP和端口
        if not proxies:
            ip_port_pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[^\d]*?(\d{1,5})'
            matches = re.findall(ip_port_pattern, html)
            
            for ip, port in matches:
                # 验证IP和端口的有效性
                if all(0 <= int(part) <= 255 for part in ip.split('.')) and 1 <= int(port) <= 65535:
                    # 添加HTTP和HTTPS代理
                    http_proxy = f"http://{ip}:{port}"
                    https_proxy = f"https://{ip}:{port}"
                    proxies.append(http_proxy)
                    proxies.append(https_proxy)
                    logger.debug(f"使用正则表达式发现代理: {http_proxy}")
        
        return proxies
