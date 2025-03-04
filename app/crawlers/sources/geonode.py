from typing import List
from app.crawlers.base_crawler import BaseCrawler
import logging
import json

logger = logging.getLogger(__name__)

class GeoNodeCrawler(BaseCrawler):
    def __init__(self):
        super().__init__()
        self.site_name = "GeoNode"
        # 使用GeoNode API获取代理列表
        self.urls = [
            "https://proxylist.geonode.com/api/proxy-list?limit=100&page=1&sort_by=lastChecked&sort_type=desc"
        ]
        
    def parse(self, html: str) -> List[str]:
        """解析GeoNode API返回的JSON代理列表"""
        proxies = []
        
        try:
            data = json.loads(html)
            proxy_list = data.get('data', [])
            
            for proxy_data in proxy_list:
                ip = proxy_data.get('ip')
                port = proxy_data.get('port')
                protocols = proxy_data.get('protocols', [])
                
                if not ip or not port or not protocols:
                    continue
                
                # 为每个支持的协议创建代理
                for protocol in protocols:
                    protocol = protocol.lower()
                    if protocol in ['http', 'https', 'socks4', 'socks5']:
                        proxy = f"{protocol}://{ip}:{port}"
                        proxies.append(proxy)
                        logger.debug(f"发现代理: {proxy}")
            
            logger.info(f"{self.site_name} 解析完成，找到 {len(proxies)} 个代理")
            
        except json.JSONDecodeError:
            logger.error(f"{self.site_name} JSON解析失败")
        except Exception as e:
            logger.error(f"{self.site_name} 解析出错: {str(e)}")
            
        return proxies
