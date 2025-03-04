import logging
import sys
from pathlib import Path
from .core.config import settings

def setup_logging():
    """初始化日志配置"""
    logger = logging.getLogger()
    logger.setLevel(settings.LOG_LEVEL.value)

    formatter = logging.Formatter(settings.LOG_FORMAT)

    # 控制台输出
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件输出（日志目录为项目根目录下的logs）
    logs_dir = Path(__file__).parent.parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    
    file_handler = logging.FileHandler(
        logs_dir / "proxy_pool.log",
        encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # 禁用第三方库的INFO级别日志
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
