import importlib
import pkgutil
from pathlib import Path
from typing import List, Type
from .base_crawler import BaseCrawler
import logging

logger = logging.getLogger(__name__)

def discover_crawlers() -> List[Type[BaseCrawler]]:
    """自动发现sources目录下的所有爬虫类"""
    crawlers = []
    sources_path = Path(__file__).parent / "sources"
    
    # 遍历sources目录下的所有模块
    for module_info in pkgutil.iter_modules([str(sources_path)]):
        try:
            module = importlib.import_module(
                f"app.crawlers.sources.{module_info.name}"
            )
            
            # 查找所有BaseCrawler的子类
            for attr in dir(module):
                cls = getattr(module, attr)
                if (
                    isinstance(cls, type)
                    and issubclass(cls, BaseCrawler)
                    and cls != BaseCrawler
                ):
                    crawlers.append(cls)
                    logger.info(f"发现爬虫类: {cls.__name__}")
                    
        except Exception as e:
            logger.error(f"加载模块{module_info.name}失败: {str(e)}")
            continue
            
    return crawlers
