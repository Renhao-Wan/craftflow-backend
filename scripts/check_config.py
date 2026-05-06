"""配置验证脚本

用于测试配置模块是否能正确读取环境变量。
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core import settings, setup_logger, logger


def main():
    """测试配置读取"""
    # 初始化日志
    setup_logger()
    
    logger.info("=" * 60)
    logger.info("CraftFlow 配置验证")
    logger.info("=" * 60)
    
    # 应用配置
    logger.info(f"应用名称: {settings.app_name}")
    logger.info(f"应用版本: {settings.app_version}")
    logger.info(f"运行环境: {settings.environment}")
    logger.info(f"调试模式: {settings.debug}")
    logger.info(f"日志级别: {settings.log_level}")
    
    # LLM 配置
    logger.info(f"\nLLM 模型: {settings.llm_model}")
    logger.info(f"LLM API Key: {'已配置' if settings.llm_api_key else '未配置'}")
    logger.info(f"最大 Token 数: {settings.max_tokens}")
    logger.info(f"默认温度: {settings.default_temperature}")
    
    # 持久化配置
    logger.info(f"\nCheckpointer 后端: {settings.checkpointer_backend}")
    if settings.checkpointer_backend == "postgres":
        logger.info(f"数据库 URL: {settings.database_url}")
    
    # 外部工具配置
    logger.info(f"\nTavily API Key: {'已配置' if settings.tavily_api_key else '未配置'}")
    logger.info(f"E2B API Key: {'已配置' if settings.e2b_api_key else '未配置'}")
    
    # 服务配置
    logger.info(f"\n服务地址: {settings.host}:{settings.port}")
    logger.info(f"CORS 来源: {settings.cors_origins}")
    
    # 业务配置
    logger.info(f"\n最大大纲章节数: {settings.max_outline_sections}")
    logger.info(f"最大并发写作节点: {settings.max_concurrent_writers}")
    logger.info(f"对抗循环最大迭代: {settings.max_debate_iterations}")
    logger.info(f"主编通过分数: {settings.editor_pass_score}")
    
    logger.info("=" * 60)
    logger.success("✓ 配置验证完成")
    logger.info("=" * 60)
    
    # 测试日志级别
    logger.debug("这是 DEBUG 级别日志")
    logger.info("这是 INFO 级别日志")
    logger.warning("这是 WARNING 级别日志")
    logger.error("这是 ERROR 级别日志")


if __name__ == "__main__":
    main()
