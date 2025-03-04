from fastapi import APIRouter, HTTPException, Query, Path, BackgroundTasks
from app.core.config import settings
from app.storage.redis_client import redis_conn, redis_storage
from app.validator.proxy_validator import ProxyValidator
from app.crawlers import discover_crawlers
from typing import List, Optional
import random
import logging
import asyncio

logger = logging.getLogger(__name__)
router = APIRouter()
validator = ProxyValidator()

@router.get("/proxy", summary="获取随机代理")
async def get_proxy(
    protocol: Optional[str] = Query(None, description="指定代理协议(http/https/socks5)"),
    count: int = Query(1, description="返回代理数量", ge=1, le=20)
):
    """
    获取随机代理
    
    - **protocol**: 可选，指定代理协议(http/https/socks5)
    - **count**: 可选，返回代理数量，默认为1，最大20
    """
    # 获取最新验证通过的代理（按分数倒序）
    proxies = await redis_conn.zrevrangebyscore(
        settings.PROXY_KEY,
        "+inf",
        "-inf",
        withscores=True
    )
    
    if not proxies:
        raise HTTPException(status_code=404, detail="代理池为空")
    
    # 如果指定了协议，过滤代理
    if protocol:
        protocol = protocol.lower()
        filtered_proxies = [(p, s) for p, s in proxies if p.startswith(f"{protocol}://")]
        if not filtered_proxies:
            raise HTTPException(status_code=404, detail=f"没有找到{protocol}协议的代理")
        proxies = filtered_proxies
    
    # 如果请求数量大于可用数量，返回所有可用代理
    if count > len(proxies):
        count = len(proxies)
    
    # 随机选择指定数量的代理
    selected_proxies = random.sample(proxies, count)
    
    if count == 1:
        proxy, score = selected_proxies[0]
        return {
            "proxy": proxy,
            "score": score,
            "protocol": proxy.split("://")[0] if "://" in proxy else "unknown"
        }
    else:
        return {
            "count": len(selected_proxies),
            "proxies": [
                {
                    "proxy": p,
                    "score": s,
                    "protocol": p.split("://")[0] if "://" in p else "unknown"
                }
                for p, s in selected_proxies
            ]
        }

@router.get("/proxies", summary="获取所有代理")
async def get_all_proxies(
    limit: int = Query(100, description="返回代理数量限制", ge=1),
    offset: int = Query(0, description="分页偏移量", ge=0),
    protocol: Optional[str] = Query(None, description="指定代理协议(http/https/socks5)")
):
    """
    获取所有代理列表
    
    - **limit**: 可选，返回代理数量限制，默认100
    - **offset**: 可选，分页偏移量，默认0
    - **protocol**: 可选，指定代理协议(http/https/socks5)
    """
    # 获取代理总数
    total = await redis_conn.zcard(settings.PROXY_KEY)
    
    # 获取代理列表（按分数倒序）
    proxies = await redis_conn.zrevrangebyscore(
        settings.PROXY_KEY,
        "+inf",
        "-inf",
        withscores=True,
        start=offset,
        num=limit
    )
    
    # 如果指定了协议，过滤代理
    if protocol:
        protocol = protocol.lower()
        proxies = [(p, s) for p, s in proxies if p.startswith(f"{protocol}://")]
    
    return {
        "count": len(proxies),
        "total": total,
        "proxies": [
            {
                "proxy": p,
                "score": s,
                "protocol": p.split("://")[0] if "://" in p else "unknown"
            }
            for p, s in proxies
        ]
    }

@router.get("/stats", summary="获取系统统计信息")
async def get_stats():
    """获取代理池系统统计信息"""
    # 获取代理总数
    total = await redis_conn.zcard(settings.PROXY_KEY)
    
    # 获取各协议代理数量
    all_proxies = await redis_conn.zrange(settings.PROXY_KEY, 0, -1)
    protocol_counts = {}
    for proxy in all_proxies:
        protocol = proxy.split("://")[0] if "://" in proxy else "unknown"
        protocol_counts[protocol] = protocol_counts.get(protocol, 0) + 1
    
    return {
        "total_proxies": total,
        "protocol_distribution": protocol_counts,
        "system_settings": {
            "check_interval": settings.CHECK_INTERVAL,
            "min_proxies_threshold": settings.MIN_PROXIES,
            "max_proxies_limit": settings.MAX_PROXIES,
            "proxy_timeout": settings.PROXY_TIMEOUT
        }
    }

# 辅助函数：执行爬虫任务
async def run_crawlers_task():
    """运行所有爬虫的辅助函数"""
    crawler_classes = discover_crawlers()
    if not crawler_classes:
        logger.warning("未发现爬虫类")
        return 0
        
    logger.info(f"开始运行 {len(crawler_classes)} 个爬虫")
    tasks = []
    
    for crawler_cls in crawler_classes:
        crawler = crawler_cls()
        tasks.append(crawler.crawl())
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 处理结果，记录错误
    total_proxies = 0
    success_count = 0
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"爬虫 {crawler_classes[i].__name__} 执行出错: {str(result)}")
        elif isinstance(result, int):
            total_proxies += result
            if result > 0:
                success_count += 1
    
    logger.info(f"爬虫任务完成，{success_count}/{len(crawler_classes)} 个爬虫成功，共获取 {total_proxies} 个代理")
    return total_proxies

@router.post("/crawl", summary="触发爬虫任务")
async def trigger_crawl(background_tasks: BackgroundTasks):
    """手动触发爬虫任务（异步执行）"""
    # 在后台任务中执行爬虫，避免阻塞API响应
    background_tasks.add_task(run_crawlers_task)
    return {"message": "爬虫任务已触发，正在后台执行"}

@router.post("/validate", summary="触发代理验证")
async def trigger_validate(background_tasks: BackgroundTasks):
    """手动触发代理验证任务（异步执行）"""
    # 在后台任务中执行验证，避免阻塞API响应
    background_tasks.add_task(validator.check_all_proxies)
    return {"message": "代理验证任务已触发，正在后台执行"}

@router.delete("/proxy/{proxy}", summary="删除指定代理")
async def delete_proxy(proxy: str = Path(..., description="要删除的代理URL")):
    """删除指定的代理"""
    # 检查代理是否存在
    exists = await redis_conn.zscore(settings.PROXY_KEY, proxy)
    if exists is None:
        raise HTTPException(status_code=404, detail="代理不存在")
    
    # 删除代理
    await redis_conn.zrem(settings.PROXY_KEY, proxy)
    logger.info(f"已删除代理: {proxy}")
    
    return {"message": f"代理 {proxy} 已成功删除"}

@router.post("/proxy", summary="添加新代理")
async def add_proxy(proxy: str = Query(..., description="要添加的代理URL")):
    """手动添加新代理"""
    # 验证代理格式
    if "://" not in proxy:
        raise HTTPException(status_code=400, detail="代理格式无效，应为 protocol://ip:port")
    
    # 添加代理
    added = await redis_storage.add_proxy(proxy, 10)
    
    if added:
        # 在后台验证代理
        background_tasks = BackgroundTasks()
        background_tasks.add_task(validator.validate_proxies, [proxy])
        
        return {"message": f"代理 {proxy} 已添加并将在后台验证"}
    else:
        return {"message": f"代理 {proxy} 已存在"}
