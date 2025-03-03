from fastapi import APIRouter, HTTPException
from app.core.config import settings
from app.storage.redis_client import redis_conn
import random

router = APIRouter()

@router.get("/proxy")
async def get_proxy():
    # 获取最新验证通过的代理（按分数倒序）
    proxies = await redis_conn.zrevrangebyscore(
        settings.PROXY_KEY,
        "+inf",
        "-inf",
        withscores=True,
        start=0,
        num=100
    )
    
    if not proxies:
        raise HTTPException(status_code=404, detail="No proxies available")
        
    # 随机选择前100个中的一个
    proxy, _ = random.choice(proxies)
    return {"proxy": proxy}

@router.get("/stats")
async def get_stats():
    total = await redis_conn.zcard(settings.PROXY_KEY)
    return {
        "total_proxies": total,
        "check_interval": settings.CHECK_INTERVAL,
        "min_threshold": settings.MIN_PROXIES
    }
