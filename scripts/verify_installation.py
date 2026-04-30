"""
验证 CraftFlow Backend 安装脚本
运行此脚本以确认所有依赖已正确安装
"""

import sys
from importlib import import_module


def check_module(module_name: str, display_name: str = None) -> bool:
    """检查模块是否可导入"""
    display_name = display_name or module_name
    try:
        mod = import_module(module_name)
        version = getattr(mod, "__version__", "未知版本")
        print(f"✅ {display_name}: {version}")
        return True
    except ImportError as e:
        print(f"❌ {display_name}: 导入失败 - {e}")
        return False


def main():
    """主验证函数"""
    print("=" * 60)
    print("CraftFlow Backend 依赖验证")
    print("=" * 60)
    print()

    # 核心框架
    print("【核心框架】")
    core_modules = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("pydantic", "Pydantic"),
        ("pydantic_settings", "Pydantic Settings"),
    ]

    # LangGraph & LangChain
    print("\n【LangGraph & LangChain】")
    langgraph_modules = [
        ("langgraph", "LangGraph"),
        ("langgraph.checkpoint", "LangGraph Checkpoint"),
        ("langchain", "LangChain"),
        ("langchain_core", "LangChain Core"),
        ("langchain_openai", "LangChain OpenAI"),
        ("langchain_anthropic", "LangChain Anthropic"),
        ("langchain_community", "LangChain Community"),
    ]

    # 可选依赖（生产环境需要）
    print("\n【可选依赖 - 生产环境】")
    optional_modules = [
        ("langgraph.checkpoint.postgres", "LangGraph Checkpoint Postgres (需要 PostgreSQL libpq)"),
    ]

    # 外部工具
    print("\n【外部工具】")
    tool_modules = [
        ("tavily", "Tavily Python"),
        ("e2b_code_interpreter", "E2B Code Interpreter"),
        ("requests", "Requests"),
        ("bs4", "BeautifulSoup4"),
    ]

    # 工具库
    print("\n【工具库】")
    util_modules = [
        ("loguru", "Loguru"),
        ("dotenv", "Python Dotenv"),
        ("asyncpg", "AsyncPG"),
    ]

    # 开发工具
    print("\n【开发工具】")
    dev_modules = [
        ("pytest", "Pytest"),
        ("pytest_asyncio", "Pytest Asyncio"),
        ("httpx", "HTTPX"),
        ("black", "Black"),
        ("ruff", "Ruff"),
    ]

    all_modules = (
        core_modules
        + langgraph_modules
        + tool_modules
        + util_modules
        + dev_modules
    )

    results = []
    for module_name, display_name in all_modules:
        results.append(check_module(module_name, display_name))

    # 检查可选依赖（不计入成功率）
    print()
    optional_results = []
    for module_name, display_name in optional_modules:
        optional_results.append(check_module(module_name, display_name))

    # 统计结果
    print()
    print("=" * 60)
    success_count = sum(results)
    total_count = len(results)
    optional_success = sum(optional_results)
    optional_total = len(optional_results)
    
    print(f"核心依赖: {success_count}/{total_count} 个模块成功导入")
    print(f"可选依赖: {optional_success}/{optional_total} 个模块成功导入")

    if success_count == total_count:
        print("🎉 所有核心依赖安装成功！")
        if optional_success < optional_total:
            print("ℹ️  部分可选依赖未安装（开发环境可忽略）")
        print()
        print("下一步:")
        print("1. 复制 .env.example 为 .env.dev 并填写 API Key")
        print("2. 运行 'uv run uvicorn app.main:app --reload' 启动开发服务器")
        return 0
    else:
        print("⚠️  部分核心依赖安装失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(main())
