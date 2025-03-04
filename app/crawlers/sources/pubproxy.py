from typing import List
import httpx
import asyncio
import logging
import json
from app.crawlers.base_crawler import BaseCrawler
from app.storage.redis_client import redis_storage

logger = logging.getLogger(__name__)

class PubProxyCrawler(BaseCrawler):
    """
    PubProxy爬虫 - 专门从API获取HTTP/HTTPS代理
    """
    def __init__(self):
        super().__init__()
        self.site_name = "PubProxy"
        # 使用多个API端点获取代理
        self.urls = [
            "http://pubproxy.com/api/proxy?limit=20&format=json&type=http",
            "http://pubproxy.com/api/proxy?limit=20&format=json&type=https",
            "https://api.getproxylist.com/proxy?protocol[]=http&protocol[]=https",
            "https://proxylist.geonode.com/api/proxy-list?limit=50&page=1&sort_by=lastChecked&sort_type=desc",
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all",
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=https&timeout=10000&country=all&ssl=all&anonymity=all"
        ]
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache"
        }
    
    async def fetch(self, url: str) -> str:
        """获取API响应"""
        async with httpx.AsyncClient(follow_redirects=True) as client:
            for attempt in range(self.max_retries):
                try:
                    response = await client.get(
                        url,
                        timeout=self.timeout,
                        headers=self.headers
                    )
                    if response.status_code == 200:
                        return response.text
                    else:
                        logger.warning(f"请求失败，状态码: {response.status_code}")
                except Exception as e:
                    logger.warning(f"请求失败（尝试 {attempt+1}/{self.max_retries}）: {str(e)}")
                    await asyncio.sleep(2 ** attempt)
        return None
    
    async def crawl(self) -> int:
        """执行爬取并返回获取的代理数量"""
        proxies = []
        
        for url in self.urls:
            logger.info(f"尝试从 {url} 获取代理")
            response_text = await self.fetch(url)
            if response_text:
                try:
                    # 根据URL选择不同的解析方法
                    if "pubproxy.com" in url:
                        url_proxies = self.parse_pubproxy(response_text)
                    elif "getproxylist.com" in url:
                        url_proxies = self.parse_getproxylist(response_text)
                    elif "geonode.com" in url:
                        url_proxies = self.parse_geonode(response_text)
                    elif "proxyscrape.com" in url:
                        url_proxies = self.parse_proxyscrape(response_text)
                    else:
                        url_proxies = []
                    
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
    
    def parse_pubproxy(self, response_text: str) -> List[str]:
        """解析PubProxy API响应"""
        proxies = []
        try:
            data = json.loads(response_text)
            if "data" in data and isinstance(data["data"], list):
                for item in data["data"]:
                    ip = item.get("ip")
                    port = item.get("port")
                    proxy_type = item.get("type", "http").lower()
                    
                    if ip and port:
                        proxy = f"{proxy_type}://{ip}:{port}"
                        proxies.append(proxy)
                        logger.debug(f"从PubProxy发现代理: {proxy}")
        except json.JSONDecodeError:
            logger.warning("PubProxy响应不是有效的JSON")
        
        return proxies
    
    def parse_getproxylist(self, response_text: str) -> List[str]:
        """解析GetProxyList API响应"""
        proxies = []
        try:
            data = json.loads(response_text)
            if isinstance(data, dict):
                ip = data.get("ip")
                port = data.get("port")
                protocol = data.get("protocol", "http").lower()
                
                if ip and port:
                    proxy = f"{protocol}://{ip}:{port}"
                    proxies.append(proxy)
                    logger.debug(f"从GetProxyList发现代理: {proxy}")
                    
                    # 如果是HTTP代理，也添加HTTPS版本
                    if protocol == "http":
                        https_proxy = f"https://{ip}:{port}"
                        proxies.append(https_proxy)
                        logger.debug(f"从GetProxyList发现代理(HTTPS): {https_proxy}")
        except json.JSONDecodeError:
            logger.warning("GetProxyList响应不是有效的JSON")
        
        return proxies
    
    def parse_geonode(self, response_text: str) -> List[str]:
        """解析GeoNode API响应"""
        proxies = []
        try:
            data = json.loads(response_text)
            if "data" in data and isinstance(data["data"], list):
                for item in data["data"]:
                    ip = item.get("ip")
                    port = item.get("port")
                    protocols = item.get("protocols", [])
                    
                    if ip and port:
                        # 添加所有支持的协议
                        for protocol in protocols:
                            protocol = protocol.lower()
                            if protocol in ["http", "https"]:
                                proxy = f"{protocol}://{ip}:{port}"
                                proxies.append(proxy)
                                logger.debug(f"从GeoNode发现代理: {proxy}")
                        
                        # 如果没有指定协议，默认添加HTTP和HTTPS
                        if not protocols:
                            http_proxy = f"http://{ip}:{port}"
                            https_proxy = f"https://{ip}:{port}"
                            proxies.append(http_proxy)
                            proxies.append(https_proxy)
                            logger.debug(f"从GeoNode发现代理(默认): {http_proxy}")
        except json.JSONDecodeError:
            logger.warning("GeoNode响应不是有效的JSON")
        
        return proxies
    
    def parse_proxyscrape(self, response_text: str) -> List[str]:
        """解析ProxyScrape API响应"""
        proxies = []
        
        # ProxyScrape返回的是纯文本格式的代理列表，每行一个代理
        lines = response_text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if line and ':' in line:
                # 确定协议
                protocol = "http"
                if "https" in line.lower() or "proxyscrape.com" in self.urls and "protocol=https" in self.urls:
                    protocol = "https"
                
                # 提取IP和端口
                ip_port = line.split(' ')[0] if ' ' in line else line
                
                if ':' in ip_port:
                    ip, port = ip_port.split(':')
                    
                    # 验证IP和端口
                    if all(0 <= int(part) <= 255 for part in ip.split('.') if part.isdigit()) and port.isdigit() and 1 <= int(port) <= 65535:
                        proxy = f"{protocol}://{ip}:{port}"
                        proxies.append(proxy)
                        logger.debug(f"从ProxyScrape发现代理: {proxy}")
                        
                        # 如果是HTTP代理，也添加HTTPS版本
                        if protocol == "http":
                            https_proxy = f"https://{ip}:{port}"
                            proxies.append(https_proxy)
                            logger.debug(f"从ProxyScrape发现代理(HTTPS): {https_proxy}")
        
        return proxies
