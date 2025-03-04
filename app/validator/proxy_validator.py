import aiohttp
import asyncio
import logging
from datetime import datetime
from app.core.config import settings
from app.storage.redis_client import redis_conn, redis_storage

logger = logging.getLogger(__name__)

class ProxyValidator:
    def __init__(self):
        # 使用多个测试URL，增加验证的可靠性
        self.test_urls = {
            "http": [
                "http://httpbin.org/ip",
                "http://ip.42.pl/raw",
                "http://ip-api.com/json/"
            ],
            "https": [
                "https://httpbin.org/ip",
                "https://api.ipify.org/",
                "https://ip.seeip.org/jsonip"
            ],
            "socks4": [
                "http://httpbin.org/ip"
            ],
            "socks5": [
                "http://httpbin.org/ip"
            ]
        }
        self.timeout = aiohttp.ClientTimeout(total=settings.PROXY_TIMEOUT)
        self.semaphore = asyncio.Semaphore(50)  # 并发控制
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "close"  # 避免保持连接
        }
        # 优先验证的协议顺序
        self.protocol_priority = ["http", "https", "socks5", "socks4"]

    async def _verify_proxy(self, proxy_url):
        """验证代理有效性"""
        async with self.semaphore:
            # 解析代理URL
            try:
                protocol, address = proxy_url.split("://", 1)
                protocol = protocol.lower()
            except ValueError:
                logger.warning(f"代理格式错误: {proxy_url}")
                return proxy_url, False, 0
            
            # 如果协议不在支持的列表中，尝试使用http协议
            if protocol not in self.protocol_priority:
                logger.warning(f"不支持的代理协议: {protocol}，尝试使用http协议")
                protocol = "http"
                proxy_url = f"http://{address}"
            
            # 获取该协议的测试URL列表
            test_urls = self.test_urls.get(protocol, self.test_urls["http"])
            
            # 测试响应时间和有效性
            best_response_time = float('inf')
            success = False
            
            # 根据协议类型设置代理
            proxy = f"{protocol}://{address}"
            
            # 尝试多个测试URL
            for test_url in test_urls:
                start_time = datetime.now()
                try:
                    async with aiohttp.ClientSession(timeout=self.timeout) as session:
                        async with session.get(
                            test_url,
                            proxy=proxy,
                            headers=self.headers,
                            ssl=False  # 禁用SSL验证以支持自签名证书
                        ) as resp:
                            if resp.status == 200:
                                # 计算响应时间（毫秒）
                                response_time = (datetime.now() - start_time).total_seconds() * 1000
                                logger.debug(f"代理有效: {proxy_url}, URL: {test_url}, 响应时间: {response_time:.2f}ms")
                                
                                # 更新最佳响应时间
                                if response_time < best_response_time:
                                    best_response_time = response_time
                                
                                success = True
                                # 一旦成功，不需要测试其他URL
                                break
                            else:
                                logger.debug(f"代理无效: {proxy_url}, URL: {test_url}, 状态码: {resp.status}")
                except asyncio.TimeoutError:
                    logger.debug(f"代理超时: {proxy_url}, URL: {test_url}")
                except aiohttp.ClientProxyConnectionError:
                    logger.debug(f"代理连接错误: {proxy_url}, URL: {test_url}")
                except aiohttp.ClientConnectorError:
                    logger.debug(f"代理连接器错误: {proxy_url}, URL: {test_url}")
                except Exception as e:
                    logger.debug(f"代理验证异常: {proxy_url}, URL: {test_url}, {str(e)}")
            
            if success:
                return proxy_url, True, best_response_time
            else:
                # 如果是HTTP代理，尝试作为HTTPS代理使用
                if protocol == "http":
                    https_proxy_url = f"https://{address}"
                    logger.debug(f"HTTP代理验证失败，尝试作为HTTPS代理: {https_proxy_url}")
                    return await self._verify_proxy(https_proxy_url)
                
                return proxy_url, False, 0

    async def validate_proxies(self, proxies):
        """验证多个代理并更新到Redis"""
        if not proxies:
            logger.warning("没有代理需要验证")
            return 0
            
        logger.info(f"开始验证 {len(proxies)} 个代理")
        tasks = [self._verify_proxy(proxy) for proxy in proxies]
        results = await asyncio.gather(*tasks)
        
        # 筛选有效代理
        valid_proxies = [(proxy, response_time) for proxy, status, response_time in results if status]
        
        if not valid_proxies:
            logger.warning("没有有效代理")
            return 0
        
        # 计算分数：基础分10分 + 响应时间评分（最快的代理获得最高分）
        # 响应时间评分：将响应时间映射到0-10分，响应时间越短分数越高
        if valid_proxies:
            max_response_time = max(response_time for _, response_time in valid_proxies)
            min_response_time = min(response_time for _, response_time in valid_proxies)
            response_time_range = max(1, max_response_time - min_response_time)  # 避免除以0
        
        # 更新Redis
        now = datetime.now().timestamp()
        async with redis_conn.pipeline() as pipe:
            for proxy, response_time in valid_proxies:
                # 计算响应时间分数（0-10分）
                if max_response_time == min_response_time:
                    response_score = 10  # 如果所有代理响应时间相同，都给10分
                else:
                    # 响应时间越短，分数越高
                    response_score = 10 - 10 * (response_time - min_response_time) / response_time_range
                
                # 总分 = 基础分(10) + 响应时间分数(0-10)
                total_score = 10 + response_score
                
                # 使用时间戳作为分数，便于排序和清理
                pipe.zadd(settings.PROXY_KEY, {proxy: total_score})
                
            # 如果代理数量超过最大限制，移除分数最低的代理
            await pipe.execute()
        
        # 清理旧代理
        await redis_storage.cleanup_old_proxies(settings.MAX_PROXIES)
        
        logger.info(f"验证完成，有效代理: {len(valid_proxies)}/{len(proxies)}")
        return len(valid_proxies)

    async def check_all_proxies(self):
        """定期检查所有代理"""
        try:
            # 获取所有代理
            all_proxies = await redis_conn.zrange(settings.PROXY_KEY, 0, -1)
            if not all_proxies:
                logger.warning("没有代理需要检查")
                return 0
                
            logger.info(f"开始检查 {len(all_proxies)} 个代理")
            valid_count = await self.validate_proxies(all_proxies)
            
            # 检查是否需要触发爬虫任务
            total_count = await redis_storage.count_proxies()
            if total_count < settings.MIN_PROXIES:
                logger.warning(f"代理数量 ({total_count}) 低于最小阈值 ({settings.MIN_PROXIES})，需要触发爬虫任务")
                # 这里可以添加触发爬虫任务的逻辑
            
            return valid_count
        except Exception as e:
            logger.error(f"检查代理异常: {str(e)}")
            return 0
