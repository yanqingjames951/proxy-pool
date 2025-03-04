from typing import List
import httpx
import asyncio
import logging
import json
import re
from app.crawlers.base_crawler import BaseCrawler
from app.storage.redis_client import redis_storage

logger = logging.getLogger(__name__)

class FreeProxyApiCrawler(BaseCrawler):
    """
    FreeProxyApi爬虫 - 专门从各种免费代理API获取HTTP/HTTPS代理
    """
    def __init__(self):
        super().__init__()
        self.site_name = "FreeProxyApi"
        # 各种免费代理API
        self.urls = [
            # ProxyScan API
            "https://www.proxyscan.io/api/proxy?format=json&type=http,https&limit=100",
            "https://www.proxyscan.io/api/proxy?format=json&type=http,https&limit=100&uptime=50",
            "https://www.proxyscan.io/api/proxy?format=json&type=http,https&limit=100&uptime=80",
            
            # GetProxyList API
            "https://api.getproxylist.com/proxy?protocol=http",
            "https://api.getproxylist.com/proxy?protocol=https",
            
            # ProxyNova API
            "https://www.proxynova.com/api/proxy?format=json&limit=100",
            
            # ProxyList.to API
            "https://api.proxylist.to/http?format=json&limit=100",
            "https://api.proxylist.to/https?format=json&limit=100",
            
            # FreeProxy API
            "https://api.freeproxy.world/v1/free-proxies?limit=100&type=http",
            "https://api.freeproxy.world/v1/free-proxies?limit=100&type=https",
            
            # ProxyDB API
            "https://proxydb.net/api/proxies?protocol=http&format=json&limit=100",
            "https://proxydb.net/api/proxies?protocol=https&format=json&limit=100",
            
            # GimmeProxy API
            "https://gimmeproxy.com/api/getProxy?protocol=http&maxCheckPeriod=3600",
            "https://gimmeproxy.com/api/getProxy?protocol=https&maxCheckPeriod=3600",
            
            # ProxyList.icu API
            "https://www.proxylist.icu/api/v1/proxy?protocol=http&limit=100",
            "https://www.proxylist.icu/api/v1/proxy?protocol=https&limit=100",
            
            # ProxyList.cc API
            "https://www.proxylist.cc/api/v1/proxy?protocol=http&limit=100",
            "https://www.proxylist.cc/api/v1/proxy?protocol=https&limit=100",
            
            # FreeProxyList API
            "https://www.freeproxylists.net/api/v1/proxy?protocol=http&limit=100",
            "https://www.freeproxylists.net/api/v1/proxy?protocol=https&limit=100"
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
                    if "proxyscan.io" in url:
                        url_proxies = self.parse_proxyscan(response_text)
                    elif "getproxylist.com" in url:
                        url_proxies = self.parse_getproxylist(response_text)
                    elif "proxynova.com" in url:
                        url_proxies = self.parse_proxynova(response_text)
                    elif "proxylist.to" in url:
                        url_proxies = self.parse_proxylist_to(response_text)
                    elif "freeproxy.world" in url:
                        url_proxies = self.parse_freeproxy_world(response_text)
                    elif "proxydb.net" in url:
                        url_proxies = self.parse_proxydb(response_text)
                    elif "gimmeproxy.com" in url:
                        url_proxies = self.parse_gimmeproxy(response_text)
                    elif "proxylist.icu" in url or "proxylist.cc" in url or "freeproxylists.net" in url:
                        url_proxies = self.parse_generic_json(response_text, "https" in url)
                    else:
                        # 通用解析方法
                        url_proxies = self.parse_generic_json(response_text, "https" in url)
                    
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
    
    def parse_proxyscan(self, response_text: str) -> List[str]:
        """解析ProxyScan API响应"""
        proxies = []
        try:
            data = json.loads(response_text)
            if isinstance(data, list):
                for item in data:
                    ip = item.get("Ip")
                    port = str(item.get("Port"))
                    protocols = [p.lower() for p in item.get("Type", [])]
                    
                    if ip and port:
                        # 添加所有支持的协议
                        for protocol in protocols:
                            if protocol in ["http", "https"]:
                                proxy = f"{protocol}://{ip}:{port}"
                                proxies.append(proxy)
                                logger.debug(f"从ProxyScan发现代理: {proxy}")
                        
                        # 如果没有指定协议，默认添加HTTP和HTTPS
                        if not protocols:
                            http_proxy = f"http://{ip}:{port}"
                            https_proxy = f"https://{ip}:{port}"
                            proxies.append(http_proxy)
                            proxies.append(https_proxy)
                            logger.debug(f"从ProxyScan发现代理(默认): {http_proxy}")
        except json.JSONDecodeError:
            logger.warning("ProxyScan响应不是有效的JSON")
        
        return proxies
    
    def parse_getproxylist(self, response_text: str) -> List[str]:
        """解析GetProxyList API响应"""
        proxies = []
        try:
            data = json.loads(response_text)
            if isinstance(data, dict):
                ip = data.get("ip")
                port = str(data.get("port"))
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
    
    def parse_proxynova(self, response_text: str) -> List[str]:
        """解析ProxyNova API响应"""
        proxies = []
        try:
            data = json.loads(response_text)
            if isinstance(data, dict) and "items" in data:
                items = data["items"]
                for item in items:
                    ip = item.get("ip")
                    port = str(item.get("port"))
                    
                    if ip and port:
                        # 添加HTTP和HTTPS代理
                        http_proxy = f"http://{ip}:{port}"
                        https_proxy = f"https://{ip}:{port}"
                        proxies.append(http_proxy)
                        proxies.append(https_proxy)
                        logger.debug(f"从ProxyNova发现代理: {http_proxy}")
        except json.JSONDecodeError:
            logger.warning("ProxyNova响应不是有效的JSON")
        
        return proxies
    
    def parse_proxylist_to(self, response_text: str) -> List[str]:
        """解析ProxyList.to API响应"""
        proxies = []
        try:
            data = json.loads(response_text)
            if isinstance(data, dict) and "proxies" in data:
                items = data["proxies"]
                for item in items:
                    ip = item.get("ip")
                    port = str(item.get("port"))
                    protocol = item.get("protocol", "http").lower()
                    
                    if ip and port:
                        proxy = f"{protocol}://{ip}:{port}"
                        proxies.append(proxy)
                        logger.debug(f"从ProxyList.to发现代理: {proxy}")
                        
                        # 如果是HTTP代理，也添加HTTPS版本
                        if protocol == "http":
                            https_proxy = f"https://{ip}:{port}"
                            proxies.append(https_proxy)
                            logger.debug(f"从ProxyList.to发现代理(HTTPS): {https_proxy}")
        except json.JSONDecodeError:
            logger.warning("ProxyList.to响应不是有效的JSON")
        
        return proxies
    
    def parse_freeproxy_world(self, response_text: str) -> List[str]:
        """解析FreeProxy.world API响应"""
        proxies = []
        try:
            data = json.loads(response_text)
            if isinstance(data, dict) and "data" in data:
                items = data["data"]
                for item in items:
                    ip = item.get("ip")
                    port = str(item.get("port"))
                    protocol = item.get("type", "http").lower()
                    
                    if ip and port:
                        proxy = f"{protocol}://{ip}:{port}"
                        proxies.append(proxy)
                        logger.debug(f"从FreeProxy.world发现代理: {proxy}")
                        
                        # 如果是HTTP代理，也添加HTTPS版本
                        if protocol == "http":
                            https_proxy = f"https://{ip}:{port}"
                            proxies.append(https_proxy)
                            logger.debug(f"从FreeProxy.world发现代理(HTTPS): {https_proxy}")
        except json.JSONDecodeError:
            logger.warning("FreeProxy.world响应不是有效的JSON")
        
        return proxies
    
    def parse_proxydb(self, response_text: str) -> List[str]:
        """解析ProxyDB API响应"""
        proxies = []
        try:
            data = json.loads(response_text)
            if isinstance(data, dict) and "proxies" in data:
                items = data["proxies"]
                for item in items:
                    ip = item.get("ip")
                    port = str(item.get("port"))
                    protocol = item.get("protocol", "http").lower()
                    
                    if ip and port:
                        proxy = f"{protocol}://{ip}:{port}"
                        proxies.append(proxy)
                        logger.debug(f"从ProxyDB发现代理: {proxy}")
                        
                        # 如果是HTTP代理，也添加HTTPS版本
                        if protocol == "http":
                            https_proxy = f"https://{ip}:{port}"
                            proxies.append(https_proxy)
                            logger.debug(f"从ProxyDB发现代理(HTTPS): {https_proxy}")
        except json.JSONDecodeError:
            logger.warning("ProxyDB响应不是有效的JSON")
        
        return proxies
    
    def parse_gimmeproxy(self, response_text: str) -> List[str]:
        """解析GimmeProxy API响应"""
        proxies = []
        try:
            data = json.loads(response_text)
            if isinstance(data, dict):
                ip = data.get("ip")
                port = str(data.get("port"))
                protocol = data.get("protocol", "http").lower()
                
                if ip and port:
                    proxy = f"{protocol}://{ip}:{port}"
                    proxies.append(proxy)
                    logger.debug(f"从GimmeProxy发现代理: {proxy}")
                    
                    # 如果是HTTP代理，也添加HTTPS版本
                    if protocol == "http":
                        https_proxy = f"https://{ip}:{port}"
                        proxies.append(https_proxy)
                        logger.debug(f"从GimmeProxy发现代理(HTTPS): {https_proxy}")
        except json.JSONDecodeError:
            logger.warning("GimmeProxy响应不是有效的JSON")
        
        return proxies
    
    def parse_generic_json(self, response_text: str, is_https: bool = False) -> List[str]:
        """通用JSON解析方法"""
        proxies = []
        try:
            # 尝试解析JSON
            data = json.loads(response_text)
            
            # 尝试不同的JSON结构
            if isinstance(data, list):
                # 列表结构
                for item in data:
                    if isinstance(item, dict):
                        # 尝试不同的字段名
                        ip = item.get("ip") or item.get("Ip") or item.get("IP") or item.get("ipAddress") or item.get("host")
                        port_raw = item.get("port") or item.get("Port") or item.get("PORT")
                        port = str(port_raw) if port_raw is not None else None
                        protocol_raw = item.get("protocol") or item.get("type") or item.get("Protocol") or item.get("scheme")
                        protocol = protocol_raw.lower() if protocol_raw else ("https" if is_https else "http")
                        
                        if ip and port:
                            proxy = f"{protocol}://{ip}:{port}"
                            proxies.append(proxy)
                            logger.debug(f"从通用JSON发现代理: {proxy}")
                            
                            # 如果是HTTP代理，也添加HTTPS版本
                            if protocol == "http":
                                https_proxy = f"https://{ip}:{port}"
                                proxies.append(https_proxy)
                                logger.debug(f"从通用JSON发现代理(HTTPS): {https_proxy}")
            elif isinstance(data, dict):
                # 字典结构
                # 尝试查找包含代理列表的字段
                for key in ["data", "proxies", "items", "list", "result", "results"]:
                    if key in data and isinstance(data[key], list):
                        return self.parse_generic_json(json.dumps(data[key]), is_https)
                
                # 单个代理
                ip = data.get("ip") or data.get("Ip") or data.get("IP") or data.get("ipAddress") or data.get("host")
                port_raw = data.get("port") or data.get("Port") or data.get("PORT")
                port = str(port_raw) if port_raw is not None else None
                protocol_raw = data.get("protocol") or data.get("type") or data.get("Protocol") or data.get("scheme")
                protocol = protocol_raw.lower() if protocol_raw else ("https" if is_https else "http")
                
                if ip and port:
                    proxy = f"{protocol}://{ip}:{port}"
                    proxies.append(proxy)
                    logger.debug(f"从通用JSON发现代理: {proxy}")
                    
                    # 如果是HTTP代理，也添加HTTPS版本
                    if protocol == "http":
                        https_proxy = f"https://{ip}:{port}"
                        proxies.append(https_proxy)
                        logger.debug(f"从通用JSON发现代理(HTTPS): {https_proxy}")
        except json.JSONDecodeError:
            # 如果不是JSON，尝试解析纯文本
            lines = response_text.strip().split('\n')
            for line in lines:
                line = line.strip()
                if ":" in line:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        ip = parts[0]
                        port = parts[1].split(" ")[0] if " " in parts[1] else parts[1]
                        
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
                            
                            logger.debug(f"从纯文本发现代理: {proxy}")
        
        return proxies
