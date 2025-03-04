from typing import List
import httpx
import asyncio
import logging
import json
import re
from app.crawlers.base_crawler import BaseCrawler
from bs4 import BeautifulSoup
from app.storage.redis_client import redis_storage

logger = logging.getLogger(__name__)

class ZdayeCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.site_name = "站大爷代理"
        # 更新URL列表，添加更多可能的URL和替代站点
        self.urls = [
            "https://www.zdaye.com/api/proxy/free/1",  # 尝试可能的API接口
            "https://www.zdaye.com/dayProxy/ip/1.html",  # 尝试其他可能的URL格式
            "https://www.zdaye.com/free/1",  # 尝试其他可能的URL格式
            "https://www.zdaye.com/dayProxy/1.html",  # 原始URL
            "https://proxy-list.org/english/index.php",  # 替代站点1
            "https://www.proxy-list.download/HTTP",  # 替代站点2
            "https://www.proxynova.com/proxy-server-list/"  # 替代站点3
        ]
        # 添加更多请求头
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.zdaye.com/",
            "Origin": "https://www.zdaye.com",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
    
    async def fetch(self, url: str) -> str:
        """重写fetch方法，尝试不同的请求方法和头信息"""
        methods = ["GET", "POST"]  # 尝试不同的HTTP方法
        
        for method in methods:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                for attempt in range(self.max_retries):
                    try:
                        if method == "GET":
                            response = await client.get(
                                url,
                                timeout=self.timeout,
                                headers=self.headers
                            )
                        else:
                            response = await client.post(
                                url,
                                timeout=self.timeout,
                                headers=self.headers
                            )
                        
                        if response.status_code == 200:
                            return response.text
                        else:
                            logger.warning(f"{method} 请求失败，状态码: {response.status_code}")
                            
                    except Exception as e:
                        logger.warning(f"{method} 请求失败（尝试 {attempt+1}/{self.max_retries}）: {str(e)}")
                        await asyncio.sleep(2 ** attempt)
        
        return None
    
    async def crawl(self) -> int:
        """执行爬取并返回获取的代理数量"""
        proxies = []
        success = False
        
        for url in self.urls:
            logger.info(f"尝试从 {url} 获取代理")
            html = await self.fetch(url)
            if html:
                try:
                    url_proxies = self.parse(html)
                    if url_proxies:
                        proxies.extend(url_proxies)
                        success = True
                        logger.info(f"从 {url} 成功获取 {len(url_proxies)} 个代理")
                        break  # 如果成功获取代理，就不再尝试其他URL
                except Exception as e:
                    logger.error(f"解析失败: {str(e)}")
        
        if not success:
            logger.warning(f"{self.site_name} 所有URL均未获取到代理，可能网站结构已变化或网站不可用")
            return 0
        
        # 去重并存储代理
        new_count = 0
        for proxy in set(proxies):
            if await redis_storage.add_proxy(proxy, 10):  # 初始分数10
                new_count += 1
        
        logger.info(f"{self.site_name} 爬取完成，新增代理: {new_count}")
        return new_count
        
    def parse(self, html: str) -> List[str]:
        """解析站大爷代理HTML页面或API响应"""
        proxies = []
        
        # 尝试解析JSON响应
        try:
            data = json.loads(html)
            # 根据API响应结构提取代理
            if isinstance(data, dict) and "data" in data:
                proxy_list = data.get("data", [])
                for item in proxy_list:
                    ip = item.get("ip")
                    port = item.get("port")
                    protocol = item.get("protocol", "http").lower()
                    
                    if ip and port:
                        proxy = f"{protocol}://{ip}:{port}"
                        proxies.append(proxy)
                        logger.debug(f"从JSON中发现代理: {proxy}")
                        
                        # 如果是HTTP代理，也添加HTTPS版本
                        if protocol == "http":
                            https_proxy = f"https://{ip}:{port}"
                            proxies.append(https_proxy)
                            logger.debug(f"从JSON中发现代理(HTTPS): {https_proxy}")
                
                return proxies
        except json.JSONDecodeError:
            # 不是JSON格式，尝试解析HTML
            pass
        
        # 尝试解析HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # 处理proxy-list.org特殊格式
        if "proxy-list.org" in html:
            script_tags = soup.find_all("script")
            for script in script_tags:
                script_text = script.string
                if script_text and "Proxy(" in script_text:
                    # 提取Base64编码的代理信息
                    import base64
                    matches = re.findall(r"Proxy\('([^']+)'\)", script_text)
                    for match in matches:
                        try:
                            decoded = base64.b64decode(match).decode('utf-8')
                            if ":" in decoded:
                                ip, port = decoded.split(":")
                                if ip and port:
                                    http_proxy = f"http://{ip}:{port}"
                                    https_proxy = f"https://{ip}:{port}"
                                    proxies.append(http_proxy)
                                    proxies.append(https_proxy)
                                    logger.debug(f"从Base64中发现代理: {http_proxy}")
                        except Exception as e:
                            logger.debug(f"Base64解码失败: {str(e)}")
        
        # 尝试查找表格
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) <= 1:  # 只有表头或空表格
                continue
                
            for row in rows[1:]:  # 跳过表头
                cols = row.find_all('td')
                if len(cols) < 2:  # 至少需要IP和端口两列
                    continue
                    
                # 尝试从不同位置提取IP和端口
                ip = None
                port = None
                protocol = "http"  # 默认协议
                
                # 检查每一列，查找IP和端口
                for i, col in enumerate(cols):
                    text = col.text.strip()
                    # 检查是否是IP地址
                    if not ip and "." in text and all(part.isdigit() for part in text.split(".") if part):
                        ip = text
                    # 检查是否是端口号
                    elif not port and text.isdigit() and 1 <= int(text) <= 65535:
                        port = text
                    # 检查是否是协议
                    elif "HTTPS" in text or "https" in text.lower():
                        protocol = "https"
                
                if ip and port:
                    proxy = f"{protocol}://{ip}:{port}"
                    proxies.append(proxy)
                    logger.debug(f"从HTML中发现代理: {proxy}")
                    
                    # 如果是HTTP代理，也添加HTTPS版本
                    if protocol == "http":
                        https_proxy = f"https://{ip}:{port}"
                        proxies.append(https_proxy)
                        logger.debug(f"从HTML中发现代理(HTTPS): {https_proxy}")
        
        # 如果表格解析失败，尝试使用正则表达式直接从HTML中提取IP和端口
        if not proxies:
            ip_port_pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[^\d]*?(\d{1,5})'
            matches = re.findall(ip_port_pattern, html)
            
            for ip, port in matches:
                # 验证IP和端口的有效性
                if all(0 <= int(part) <= 255 for part in ip.split('.')) and 1 <= int(port) <= 65535:
                    # 添加HTTP代理
                    http_proxy = f"http://{ip}:{port}"
                    proxies.append(http_proxy)
                    logger.debug(f"使用正则表达式发现代理(HTTP): {http_proxy}")
                    
                    # 添加HTTPS代理
                    https_proxy = f"https://{ip}:{port}"
                    proxies.append(https_proxy)
                    logger.debug(f"使用正则表达式发现代理(HTTPS): {https_proxy}")
        
        return proxies
