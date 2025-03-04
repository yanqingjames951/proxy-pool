from typing import List
import httpx
import asyncio
import logging
from app.crawlers.base_crawler import BaseCrawler
from bs4 import BeautifulSoup
from app.storage.redis_client import redis_storage

logger = logging.getLogger(__name__)

class XicidailiCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.site_name = "西刺代理"
        # 更新为新的URL
        self.urls = [
            "https://www.xicidaili.com/nn/",
            "http://www.xicidaili.com/",
            "https://www.xicidaili.com/",
            "http://xicidaili.com/",
            "https://free-proxy-list.com/"  # 替代网站，类似西刺
        ]
        # 添加更多请求头
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.google.com/",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
        
    async def fetch(self, url: str) -> str:
        """重写fetch方法，添加自定义请求头和重定向处理"""
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
        
        # 去重并存储代理
        new_count = 0
        for proxy in set(proxies):
            if await redis_storage.add_proxy(proxy, 10):  # 初始分数10
                new_count += 1
        
        logger.info(f"{self.site_name} 爬取完成，新增代理: {new_count}")
        return new_count
        
    def parse(self, html: str) -> List[str]:
        """解析西刺代理HTML页面"""
        proxies = []
        soup = BeautifulSoup(html, 'html.parser')
        
        # 尝试查找表格
        tables = soup.find_all('table')
        for table in tables:
            # 尝试查找包含IP和端口的表格
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
                    elif text.lower() in ["http", "https"]:
                        protocol = text.lower()
                
                if ip and port:
                    proxy = f"{protocol}://{ip}:{port}"
                    proxies.append(proxy)
                    logger.debug(f"发现代理: {proxy}")
        
        # 如果表格解析失败，尝试使用正则表达式直接从HTML中提取IP和端口
        if not proxies:
            import re
            # 匹配IP:端口格式
            ip_port_pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})[^\d]*?(\d{1,5})'
            matches = re.findall(ip_port_pattern, html)
            
            for ip, port in matches:
                # 验证IP和端口的有效性
                if all(0 <= int(part) <= 255 for part in ip.split('.')) and 1 <= int(port) <= 65535:
                    # 默认使用HTTP协议，也可以添加HTTPS
                    proxy = f"http://{ip}:{port}"
                    proxies.append(proxy)
                    logger.debug(f"使用正则表达式发现代理: {proxy}")
                    
                    # 同时添加HTTPS版本，增加代理多样性
                    https_proxy = f"https://{ip}:{port}"
                    proxies.append(https_proxy)
                    logger.debug(f"使用正则表达式发现代理(HTTPS): {https_proxy}")
        
        return proxies
