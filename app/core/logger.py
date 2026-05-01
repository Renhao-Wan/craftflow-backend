"""结构化日志配置模块

使用 loguru 提供结构化日志功能，支持：
- 自动日志轮转
- 彩色终端输出
- JSON 格式日志文件
- 异步日志写入
"""

import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings


def setup_logger() -> None:
    """配置全局日志系统

    根据环境变量配置日志级别、输出格式和文件轮转策略。
    开发环境：彩色终端输出 + 详细格式
    生产环境：JSON 格式文件 + 精简格式
    """
    # 移除默认的 handler
    logger.remove()

    # 日志目录
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # ============================================
    # 终端输出配置
    # ============================================
    if settings.is_development:
        # 开发环境：彩色输出 + 详细格式
        logger.add(
            sys.stdout,
            level=settings.log_level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                "<level>{message}</level>"
            ),
            colorize=True,
            backtrace=True,  # 显示完整堆栈
            diagnose=True,  # 显示变量值
        )
    else:
        # 生产环境：精简格式
        logger.add(
            sys.stdout,
            level=settings.log_level,
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
                "{level: <8} | "
                "{name}:{function}:{line} | "
                "{message}"
            ),
            colorize=False,
            backtrace=False,
            diagnose=False,
        )

    # ============================================
    # 文件输出配置
    # ============================================
    # 通用日志文件（所有级别）
    logger.add(
        log_dir / "app_{time:YYYY-MM-DD}.log",
        level="DEBUG",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}"
        ),
        rotation="00:00",  # 每天午夜轮转
        retention="30 days",  # 保留 30 天
        compression="zip",  # 压缩旧日志
        encoding="utf-8",
        enqueue=True,  # 异步写入
    )

    # 错误日志文件（仅 ERROR 及以上）
    logger.add(
        log_dir / "error_{time:YYYY-MM-DD}.log",
        level="ERROR",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}\n{exception}"
        ),
        rotation="00:00",
        retention="90 days",  # 错误日志保留更久
        compression="zip",
        encoding="utf-8",
        enqueue=True,
        backtrace=True,
        diagnose=True,
    )

    # ============================================
    # JSON 格式日志（生产环境）
    # ============================================
    if settings.is_production:
        logger.add(
            log_dir / "app_{time:YYYY-MM-DD}.json",
            level="INFO",
            format="{message}",
            rotation="00:00",
            retention="30 days",
            compression="zip",
            encoding="utf-8",
            enqueue=True,
            serialize=True,  # 输出 JSON 格式
        )

    # 记录启动信息
    logger.info(f"日志系统初始化完成 | 环境: {settings.environment} | 级别: {settings.log_level}")


def get_logger(name: str):
    """获取指定名称的 logger

    Args:
        name: logger 名称（通常使用 __name__）

    Returns:
        logger 实例

    Example:
        >>> from app.core.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("这是一条日志")
    """
    return logger.bind(name=name)


# 导出便捷访问的 logger 实例
__all__ = ["logger", "setup_logger", "get_logger"]
