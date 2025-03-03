import asyncio
import schedule
from fastapi import FastAPI
from app.api.router import router
from app.validator.proxy_validator import ProxyValidator
from app.crawlers.base_crawler import BaseCrawler
from app.storage.redis_client import redis_conn
import uvicorn
from app.core.config import settings

app = FastAPI()
app.include_router(router, prefix="/api")
validator = ProxyValidator()

async def validate_job():
    proxies = await redis_conn.zrange(settings.PROXY_KEY, 0, -1)
    await validator.validate_proxies(proxies)

async def crawl_job():
    crawlers = BaseCrawler.__subclasses__()
    for crawler_cls in crawlers:
        crawler = crawler_cls()
        await crawler.crawl()

async def scheduler():
    schedule.every(settings.CHECK_INTERVAL).seconds.do(
        lambda: asyncio.create_task(validate_job())
    )
    schedule.every().hour.do(
        lambda: asyncio.create_task(crawl_job())
    )
    
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.create_task(scheduler())
    uvicorn.run(app, host="0.0.0.0", port=8000)
