import asyncio
import argparse
from fastapi import FastAPI
from app.api.router import router
from app.crawlers import discover_crawlers
import logging
from app.log_config import setup_logging

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI()
app.include_router(router)

async def run_crawlers():
    """运行所有爬虫"""
    crawler_classes = discover_crawlers()
    tasks = []
    
    for crawler_cls in crawler_classes:
        crawler = crawler_cls()
        tasks.append(crawler.crawl())
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 处理结果，记录错误
    total_proxies = 0
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.error(f"爬虫 {crawler_classes[i].__name__} 执行出错: {str(result)}")
        elif isinstance(result, int):
            total_proxies += result
    
    logger.info(f"爬虫任务完成，共获取 {total_proxies} 个代理")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="代理池管理系统")
    parser.add_argument("--crawl", action="store_true", help="运行爬虫任务")
    args = parser.parse_args()
    
    if args.crawl:
        asyncio.run(run_crawlers())
    else:
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
