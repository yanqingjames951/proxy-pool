import asyncio
import argparse
import time
import signal
import sys
from fastapi import FastAPI
from app.api.router import router
from app.crawlers import discover_crawlers
from app.validator.proxy_validator import ProxyValidator
from app.storage.redis_client import redis_storage
from app.core.config import settings
import logging
from app.log_config import setup_logging

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="动态代理池",
    description="自动维护的高可用代理池，支持动态爬取/验证/存储/分配代理",
    version="1.0.0"
)
app.include_router(router)

# 全局变量，用于控制后台任务
running = True
validator = ProxyValidator()

async def run_crawlers():
    """运行所有爬虫"""
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

async def validate_task():
    """定期验证代理的后台任务"""
    # 记录上次爬虫执行时间，避免频繁触发
    last_crawl_time = 0
    
    while running:
        try:
            current_time = time.time()
            
            # 检查代理数量
            proxy_count = await redis_storage.count_proxies()
            logger.info(f"当前代理数量: {proxy_count}")
            
            # 如果代理池为空，直接触发爬虫任务
            if proxy_count == 0:
                if current_time - last_crawl_time > settings.CRAWL_MIN_INTERVAL:
                    logger.warning("代理池为空，立即触发爬虫任务")
                    await run_crawlers()
                    last_crawl_time = current_time
                else:
                    logger.info(f"代理池为空，但距离上次爬虫任务不足{settings.CRAWL_MIN_INTERVAL}秒，跳过")
            else:
                # 验证所有代理
                valid_count = await validator.check_all_proxies()
                logger.info(f"验证完成，有效代理数量: {valid_count}")
                
                # 如果代理数量低于阈值，触发爬虫任务
                if valid_count < settings.MIN_PROXIES and current_time - last_crawl_time > settings.CRAWL_MIN_INTERVAL:
                    logger.warning(f"代理数量 ({valid_count}) 低于最小阈值 ({settings.MIN_PROXIES})，触发爬虫任务")
                    await run_crawlers()
                    last_crawl_time = current_time
                # 定期触发爬虫任务，即使代理数量足够，也要保持新鲜度
                elif current_time - last_crawl_time > settings.CRAWL_INTERVAL:
                    logger.info(f"距离上次爬虫任务已超过{settings.CRAWL_INTERVAL}秒，定期触发爬虫任务")
                    await run_crawlers()
                    last_crawl_time = current_time
            
            # 等待下一次验证
            await asyncio.sleep(settings.CHECK_INTERVAL)
        except asyncio.CancelledError:
            logger.info("验证任务被取消")
            break
        except Exception as e:
            logger.error(f"验证任务异常: {str(e)}", exc_info=True)
            await asyncio.sleep(60)  # 出错后等待1分钟再重试

async def startup_event():
    """应用启动时执行的任务"""
    # 测试Redis连接
    if await redis_storage.test_connection():
        logger.info("Redis连接成功")
    else:
        logger.error("Redis连接失败")
        sys.exit(1)
    
    # 检查代理数量
    proxy_count = await redis_storage.count_proxies()
    logger.info(f"当前代理数量: {proxy_count}")
    
    # 如果代理数量为0或低于最小阈值的一半，立即执行一次爬虫任务
    if proxy_count < settings.MIN_PROXIES / 2:
        logger.warning(f"代理数量 ({proxy_count}) 过低，立即执行爬虫任务")
        # 创建一个新的任务来执行爬虫，避免阻塞启动过程
        asyncio.create_task(run_crawlers())
    
    # 启动验证任务
    asyncio.create_task(validate_task())
    logger.info("后台验证任务已启动")

def handle_exit(signum, frame):
    """处理退出信号"""
    global running
    logger.info("接收到退出信号，正在关闭...")
    running = False

async def run_api_server():
    """运行API服务器"""
    import uvicorn
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="代理池管理系统")
    parser.add_argument("--crawl", action="store_true", help="运行爬虫任务")
    parser.add_argument("--validate", action="store_true", help="验证所有代理")
    args = parser.parse_args()
    
    # 注册信号处理
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    
    if args.crawl:
        asyncio.run(run_crawlers())
    elif args.validate:
        asyncio.run(validator.check_all_proxies())
    else:
        # 启动API服务器和后台任务
        app.add_event_handler("startup", startup_event)
        asyncio.run(run_api_server())
