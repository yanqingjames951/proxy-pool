from typing import List
import httpx
import asyncio
import logging
import re
from app.crawlers.base_crawler import BaseCrawler
from bs4 import BeautifulSoup
from app.storage.redis_client import redis_storage

logger = logging.getLogger(__name__)

class SpysOneCrawler(BaseCrawler):
    """
    SpysOne爬虫 - 专门从多个免费代理站点获取HTTP/HTTPS代理
    """
    def __init__(self):
        super().__init__()
        self.site_name = "SpysOne"
        # 多个免费代理站点
        self.urls = [
            "https://spys.one/en/free-proxy-list/",
            "https://www.proxy-list.download/api/v1/get?type=http",
            "https://www.proxy-list.download/api/v1/get?type=https",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/https.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/https.txt",
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
            "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/https.txt",
            "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
            "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
            "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt",
            "https://api.proxyscrape.com/?request=getproxies&proxytype=http",
            "https://api.proxyscrape.com/?request=getproxies&proxytype=https",
            "https://openproxy.space/list/http",
            "https://openproxy.space/list/https",
            "http://www.httptunnel.ge/ProxyListForFree.aspx",
            "https://proxyservers.pro/proxy/list/download/txt/http/all/",
            "https://proxyservers.pro/proxy/list/download/txt/https/all/"
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
                    # 根据URL选择不同的解析方法
                    if "spys.one" in url:
                        url_proxies = self.parse_spysone(html)
                    elif "proxy-list.download/api" in url:
                        url_proxies = self.parse_plain_text(html, "https" in url)
                    elif "githubusercontent.com" in url:
                        url_proxies = self.parse_plain_text(html, "https.txt" in url)
                    elif "openproxy.space" in url:
                        url_proxies = self.parse_openproxy(html)
                    elif "httptunnel.ge" in url:
                        url_proxies = self.parse_httptunnel(html)
                    elif "proxyservers.pro" in url:
                        url_proxies = self.parse_plain_text(html, "https" in url)
                    else:
                        # 通用解析方法
                        url_proxies = self.parse_plain_text(html, "https" in url)
                    
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
    
    def parse_spysone(self, html: str) -> List[str]:
        """解析SpysOne网站"""
        proxies = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # SpysOne网站的代理通常在表格中
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 2:
                    # 尝试提取IP和端口
                    ip_col = cols[0].text.strip() if cols[0].text else ""
                    if "." in ip_col and all(part.isdigit() for part in ip_col.split(".") if part.isdigit()):
                        ip = ip_col.split(":")[0] if ":" in ip_col else ip_col
                        
                        # 尝试从不同位置提取端口
                        port = None
                        for col in cols[1:]:
                            col_text = col.text.strip()
                            if col_text.isdigit() and 1 <= int(col_text) <= 65535:
                                port = col_text
                                break
                        
                        # 如果在文本中找不到端口，尝试从IP列中提取
                        if not port and ":" in ip_col:
                            port_part = ip_col.split(":")[1]
                            if port_part.isdigit() and 1 <= int(port_part) <= 65535:
                                port = port_part
                        
                        if ip and port:
                            # 添加HTTP和HTTPS代理
                            http_proxy = f"http://{ip}:{port}"
                            https_proxy = f"https://{ip}:{port}"
                            proxies.append(http_proxy)
                            proxies.append(https_proxy)
                            logger.debug(f"从SpysOne发现代理: {http_proxy}")
        
        # 如果表格解析失败，尝试使用正则表达式
        if not proxies:
            ip_port_pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[^\d]*?(\d{1,5})'
            matches = re.findall(ip_port_pattern, html)
            
            for ip, port in matches:
                # 验证IP和端口的有效性
                if all(0 <= int(part) <= 255 for part in ip.split('.') if part.isdigit()) and port.isdigit() and 1 <= int(port) <= 65535:
                    # 添加HTTP和HTTPS代理
                    http_proxy = f"http://{ip}:{port}"
                    https_proxy = f"https://{ip}:{port}"
                    proxies.append(http_proxy)
                    proxies.append(https_proxy)
                    logger.debug(f"使用正则表达式从SpysOne发现代理: {http_proxy}")
        
        return proxies
    
    def parse_plain_text(self, text: str, is_https: bool = False) -> List[str]:
        """解析纯文本格式的代理列表"""
        proxies = []
        lines = text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or ":" not in line:
                continue
            
            # 提取IP和端口
            parts = line.split(":")
            if len(parts) >= 2:
                ip = parts[0]
                port = parts[1].split(" ")[0] if " " in parts[1] else parts[1]  # 处理可能的额外信息
                
                # 验证IP和端口的有效性
                if all(0 <= int(part) <= 255 for part in ip.split('.') if part.isdigit()) and port.isdigit() and 1 <= int(port) <= 65535:
                    # 根据来源确定协议
                    protocol = "https" if is_https else "http"
                    proxy = f"{protocol}://{ip}:{port}"
                    proxies.append(proxy)
                    
                    # 如果是HTTP代理，也添加HTTPS版本
                    if protocol == "http":
                        https_proxy = f"https://{ip}:{port}"
                        proxies.append(https_proxy)
                        logger.debug(f"从纯文本发现代理(HTTPS): {https_proxy}")
                    
                    logger.debug(f"从纯文本发现代理: {proxy}")
        
        return proxies
    
    def parse_openproxy(self, html: str) -> List[str]:
        """解析OpenProxy网站"""
        proxies = []
        
        # OpenProxy通常以JSON格式返回数据
        try:
            import json
            data = json.loads(html)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "ip" in item and "port" in item:
                        ip = item["ip"]
                        port = str(item["port"])
                        protocol = item.get("type", "http").lower()
                        
                        if ip and port:
                            proxy = f"{protocol}://{ip}:{port}"
                            proxies.append(proxy)
                            logger.debug(f"从OpenProxy发现代理: {proxy}")
                            
                            # 如果是HTTP代理，也添加HTTPS版本
                            if protocol == "http":
                                https_proxy = f"https://{ip}:{port}"
                                proxies.append(https_proxy)
                                logger.debug(f"从OpenProxy发现代理(HTTPS): {https_proxy}")
            return proxies
        except json.JSONDecodeError:
            pass
        
        # 如果不是JSON，尝试解析HTML
        soup = BeautifulSoup(html, 'html.parser')
        pre_tags = soup.find_all('pre')
        
        for pre in pre_tags:
            text = pre.text.strip()
            if text:
                # 解析预格式化文本中的代理
                is_https = "https" in soup.text.lower()
                text_proxies = self.parse_plain_text(text, is_https)
                proxies.extend(text_proxies)
        
        return proxies
    
    def parse_httptunnel(self, html: str) -> List[str]:
        """解析HTTPTunnel网站"""
        proxies = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # 查找包含代理的表格
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 2:
                    # 尝试提取IP和端口
                    for i in range(len(cols) - 1):
                        col_text = cols[i].text.strip()
                        next_col_text = cols[i+1].text.strip()
                        
                        # 检查是否是IP地址
                        if "." in col_text and all(part.isdigit() for part in col_text.split(".") if part.isdigit()):
                            # 检查下一列是否是端口号
                            if next_col_text.isdigit() and 1 <= int(next_col_text) <= 65535:
                                ip = col_text
                                port = next_col_text
                                
                                # 添加HTTP和HTTPS代理
                                http_proxy = f"http://{ip}:{port}"
                                https_proxy = f"https://{ip}:{port}"
                                proxies.append(http_proxy)
                                proxies.append(https_proxy)
                                logger.debug(f"从HTTPTunnel发现代理: {http_proxy}")
        
        # 如果表格解析失败，尝试使用正则表达式
        if not proxies:
            ip_port_pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[^\d]*?(\d{1,5})'
            matches = re.findall(ip_port_pattern, html)
            
            for ip, port in matches:
                # 验证IP和端口的有效性
                if all(0 <= int(part) <= 255 for part in ip.split('.') if part.isdigit()) and port.isdigit() and 1 <= int(port) <= 65535:
                    # 添加HTTP和HTTPS代理
                    http_proxy = f"http://{ip}:{port}"
                    https_proxy = f"https://{ip}:{port}"
                    proxies.append(http_proxy)
                    proxies.append(https_proxy)
                    logger.debug(f"使用正则表达式从HTTPTunnel发现代理: {http_proxy}")
        
        return proxies
