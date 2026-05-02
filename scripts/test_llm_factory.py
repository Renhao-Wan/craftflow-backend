"""测试 LLM 工厂模块

验证 LLM 工厂的基本功能：
1. 创建不同温度参数的 LLM 实例
2. 实例缓存机制
3. 基本的 LLM 调用
"""

import asyncio
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import settings
from app.core.logger import logger
from app.graph.common import get_custom_llm, get_default_llm, get_editor_llm, LLMFactory


async def test_llm_creation():
    """测试 LLM 实例创建"""
    logger.info("=" * 60)
    logger.info("测试 1: LLM 实例创建")
    logger.info("=" * 60)

    try:
        # 测试默认 LLM
        logger.info("创建默认 LLM 实例...")
        default_llm = get_default_llm()
        logger.info(f"✅ 默认 LLM: {type(default_llm).__name__}")

        # 测试编辑器 LLM
        logger.info("创建编辑器 LLM 实例...")
        editor_llm = get_editor_llm()
        logger.info(f"✅ 编辑器 LLM: {type(editor_llm).__name__}")

        # 测试自定义参数 LLM
        logger.info("创建自定义参数 LLM 实例...")
        custom_llm = get_custom_llm(temperature=0.5, max_tokens=2000)
        logger.info(f"✅ 自定义 LLM: {type(custom_llm).__name__}")

    except Exception as e:
        logger.error(f"❌ LLM 创建失败: {e}")
        return False

    return True


async def test_llm_caching():
    """测试 LLM 实例缓存"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 2: LLM 实例缓存")
    logger.info("=" * 60)

    # 清空缓存
    LLMFactory.clear_cache()
    logger.info("已清空缓存")

    # 创建两个相同参数的实例
    llm1 = LLMFactory.create_llm(temperature=0.7)
    llm2 = LLMFactory.create_llm(temperature=0.7)

    if llm1 is llm2:
        logger.info("✅ 缓存机制正常：相同参数返回同一实例")
    else:
        logger.warning("⚠️ 缓存机制异常：相同参数返回不同实例")

    # 创建不同参数的实例
    llm3 = LLMFactory.create_llm(temperature=0.3)

    if llm1 is not llm3:
        logger.info("✅ 缓存机制正常：不同参数返回不同实例")
    else:
        logger.warning("⚠️ 缓存机制异常：不同参数返回同一实例")


async def test_llm_invocation():
    """测试 LLM 基本调用"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 3: LLM 基本调用")
    logger.info("=" * 60)

    if not settings.llm_api_key:
        logger.warning("⚠️ 未配置 LLM_API_KEY，跳过调用测试")
        return

    try:
        llm = get_default_llm()
        logger.info(f"使用模型: {settings.llm_model}")

        # 简单的测试调用
        messages = [("human", "请用一句话介绍 Python 编程语言。")]
        logger.info("发送测试消息...")

        response = await llm.ainvoke(messages)
        logger.info(f"✅ LLM 调用成功")
        logger.info(f"响应内容: {response.content[:100]}...")

    except Exception as e:
        logger.error(f"❌ LLM 调用失败: {e}")
        logger.info("提示：请检查 .env.dev 中的 LLM_API_KEY 和 LLM_MODEL 配置")


async def test_prompt_templates():
    """测试通用 Prompt 模板"""
    logger.info("\n" + "=" * 60)
    logger.info("测试 4: 通用 Prompt 模板")
    logger.info("=" * 60)

    from app.graph.common import (
        get_markdown_output_template,
        get_json_output_template,
        create_base_system_prompt,
        PROFESSIONAL_WRITER_ROLE,
    )

    # 测试 Markdown 模板
    logger.info("测试 Markdown 输出模板...")
    markdown_template = get_markdown_output_template()
    markdown_prompt = markdown_template.format_messages(input="生成一篇关于 AI 的文章")
    logger.info(f"✅ Markdown 模板消息数: {len(markdown_prompt)}")

    # 测试 JSON 模板
    logger.info("测试 JSON 输出模板...")
    json_template = get_json_output_template()
    json_prompt = json_template.format_messages(input="生成用户信息 JSON")
    logger.info(f"✅ JSON 模板消息数: {len(json_prompt)}")

    # 测试自定义系统 Prompt
    logger.info("测试自定义系统 Prompt...")
    custom_prompt = create_base_system_prompt(
        role=PROFESSIONAL_WRITER_ROLE,
        task_description="撰写技术博客",
        include_markdown_rules=True,
    )
    logger.info(f"✅ 自定义 Prompt 长度: {len(custom_prompt)} 字符")


async def main():
    """主测试函数"""
    logger.info("开始测试 LLM 工厂模块")
    logger.info(f"当前配置:")
    logger.info(f"  - LLM Model: {settings.llm_model}")
    logger.info(f"  - Default Temperature: {settings.default_temperature}")
    logger.info(f"  - Editor Temperature: {settings.editor_node_temperature}")
    logger.info(f"  - Max Tokens: {settings.max_tokens}")
    logger.info(f"  - API Key 已配置: {'是' if settings.llm_api_key else '否'}")

    # 运行所有测试
    await test_llm_creation()
    await test_llm_caching()
    await test_llm_invocation()
    await test_prompt_templates()

    logger.info("\n" + "=" * 60)
    logger.info("所有测试完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
