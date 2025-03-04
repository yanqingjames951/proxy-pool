from redis.asyncio import Redis
from typing import Optional, List
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class RedisStorage:
    def __init__(self):
        self.conn = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        self.proxy_key = settings.PROXY_KEY

    async def add_proxy(self, proxy: str, score: float) -> bool:
        """添加代理并返回是否为新代理"""
        # 使用NX选项避免重复添加
        added = await self.conn.zadd(
            self.proxy_key,
            {proxy: score},
            nx=True,
            ch=True
        )
        # 如果返回1表示新增，0表示已存在
        is_new = added == 1
        if is_new:
            logger.debug(f"新增代理: {proxy}")
        else:
            logger.debug(f"代理已存在: {proxy}")
        return is_new

    async def get_proxies(self, count: int = 100) -> List[str]:
        """获取分数最高的前N个代理"""
        return await self.conn.zrevrange(
            self.proxy_key, 0, count-1, withscores=False
        )

    async def count_proxies(self) -> int:
        """获取当前代理总数"""
        return await self.conn.zcard(self.proxy_key)

    async def remove_proxy(self, proxy: str) -> None:
        """移除失效代理"""
        await self.conn.zrem(self.proxy_key, proxy)
        logger.info(f"已移除代理: {proxy}")

    async def cleanup_old_proxies(self, max_count: int = settings.MAX_PROXIES) -> int:
        """清理超过最大限制的旧代理"""
        current_count = await self.count_proxies()
        if current_count > max_count:
            remove_count = current_count - max_count
            # 移除分数最低的旧代理
            await self.conn.zpopmin(self.proxy_key, remove_count)
            logger.info(f"清理旧代理: 移除了{remove_count}个")
            return remove_count
        return 0

    async def test_connection(self):
        """测试Redis连接"""
        try:
            return await self.conn.ping()
        except Exception as e:
            logger.error(f"Redis连接测试失败: {str(e)}")
            return False

# 初始化Redis连接
redis_storage = RedisStorage()
redis_conn = redis_storage.conn
