"""工具链功能测试脚本

测试各个工具的基本功能，验证 Task 5 的实现。
"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import settings
from app.core.logger import logger


def test_search_tools():
    """测试搜索工具"""
    print("\n" + "=" * 60)
    print("测试搜索工具")
    print("=" * 60)

    try:
        from app.graph.tools.search import search_internet, search_with_answer

        # 测试基本搜索
        print("\n1. 测试 search_internet...")
        if settings.tavily_api_key:
            result = search_internet.invoke({"query": "LangGraph tutorial", "max_results": 3})
            print(f"✓ 搜索成功，返回 {len(result)} 条结果")
            if result:
                print(f"  第一条结果: {result[0]['title'][:50]}...")
        else:
            print("⚠ TAVILY_API_KEY 未配置，跳过测试")

        # 测试带答案的搜索
        print("\n2. 测试 search_with_answer...")
        if settings.tavily_api_key:
            result = search_with_answer.invoke({"query": "What is LangGraph?"})
            print(f"✓ 搜索成功")
            if result.get("answer"):
                print(f"  AI 答案: {result['answer'][:100]}...")
        else:
            print("⚠ TAVILY_API_KEY 未配置，跳过测试")

    except Exception as e:
        print(f"✗ 搜索工具测试失败: {e}")


def test_sandbox_tools():
    """测试沙箱工具"""
    print("\n" + "=" * 60)
    print("测试沙箱工具")
    print("=" * 60)

    try:
        from app.graph.tools.sandbox import execute_python_code, validate_code_snippet

        # 测试代码执行
        print("\n1. 测试 execute_python_code...")
        if settings.e2b_api_key:
            result = execute_python_code.invoke({"code": "print('Hello from E2B!')"})
            if result["success"]:
                print(f"✓ 代码执行成功")
                print(f"  输出: {result['output']}")
            else:
                print(f"✗ 代码执行失败: {result['error']}")
        else:
            print("✗ E2B_API_KEY 未配置，请在 .env 文件中设置")

        # 测试代码验证
        print("\n2. 测试 validate_code_snippet...")
        if settings.e2b_api_key:
            result = validate_code_snippet.invoke(
                {"code": "print(2 + 2)", "expected_output": "4"}
            )
            if result["valid"]:
                print(f"✓ 代码验证成功")
                print(f"  匹配期望输出: {result['matches_expected']}")
            else:
                print(f"✗ 代码验证失败: {result['error']}")
        else:
            print("✗ E2B_API_KEY 未配置，请在 .env 文件中设置")

    except Exception as e:
        print(f"✗ 沙箱工具测试失败: {e}")


def test_validator_tools():
    """测试验证工具"""
    print("\n" + "=" * 60)
    print("测试验证工具")
    print("=" * 60)

    try:
        from app.graph.tools.validators import (
            validate_url,
            calculate_readability,
            validate_markdown,
            extract_markdown_structure,
        )

        # 测试 URL 验证
        print("\n1. 测试 validate_url...")
        result = validate_url.invoke({"url": "https://www.python.org"})
        if result["accessible"]:
            print(f"✓ URL 验证成功")
            print(f"  状态码: {result['status_code']}")
        else:
            print(f"✗ URL 不可访问: {result['error']}")

        # 测试可读性计算
        print("\n2. 测试 calculate_readability...")
        test_text = """
        这是一个测试文本。它包含多个句子。
        我们用它来测试可读性计算功能。
        """
        result = calculate_readability.invoke({"text": test_text})
        print(f"✓ 可读性计算成功")
        print(f"  可读性等级: {result['readability_level']}")
        print(f"  Flesch 分数: {result['flesch_reading_ease']}")

        # 测试 Markdown 验证
        print("\n3. 测试 validate_markdown...")
        test_markdown = """
# 标题

这是正文内容。

```python
print("Hello, World!")
```

[链接](https://example.com)
"""
        result = validate_markdown.invoke({"content": test_markdown})
        if result["valid"]:
            print(f"✓ Markdown 验证通过")
            print(f"  结构: {result['structure']}")
        else:
            print(f"✗ Markdown 验证失败: {result['issues']}")

        # 测试 Markdown 结构提取
        print("\n4. 测试 extract_markdown_structure...")
        result = extract_markdown_structure.invoke({"content": test_markdown})
        print(f"✓ 结构提取成功")
        print(f"  标题数: {len(result['headings'])}")
        print(f"  代码块数: {len(result['code_blocks'])}")
        print(f"  链接数: {len(result['links'])}")

    except Exception as e:
        print(f"✗ 验证工具测试失败: {e}")


def test_retriever_tools():
    """测试检索工具"""
    print("\n" + "=" * 60)
    print("测试检索工具")
    print("=" * 60)

    try:
        from app.graph.tools.retriever import search_knowledge_base, add_documents_to_knowledge_base

        # 测试 RAG 开关
        print(f"\n1. RAG 功能状态: {'启用' if settings.enable_rag else '禁用'}")
        print(f"   配置项: ENABLE_RAG={settings.enable_rag}")

        # 测试知识库搜索
        print("\n2. 测试 search_knowledge_base...")
        result = search_knowledge_base.invoke({"query": "test query"})
        
        if not settings.enable_rag:
            if result == []:
                print("✓ RAG 未启用时正确返回空结果")
            else:
                print(f"✗ RAG 未启用时应返回空结果，实际返回: {result}")
        else:
            if result == []:
                print("⚠ RAG 已启用但知识库未初始化，返回空结果")
            else:
                print(f"✓ 搜索成功，返回 {len(result)} 条结果")

        # 测试添加文档
        print("\n3. 测试 add_documents_to_knowledge_base...")
        test_docs = [
            {"content": "测试文档", "metadata": {"type": "test"}},
        ]
        result = add_documents_to_knowledge_base.invoke({"documents": test_docs})
        
        if not settings.enable_rag:
            if not result["success"]:
                print("✓ RAG 未启用时正确返回失败")
                print(f"  错误信息: {result['errors'][0]}")
            else:
                print("✗ RAG 未启用时应返回失败")
        else:
            if result["success"]:
                print(f"✓ 文档添加成功: {result['added_count']} 个")
            else:
                print(f"⚠ 文档添加失败（可能是知识库未初始化）")

        print("\n注意:")
        print("  - RAG 功能通过 ENABLE_RAG 配置项控制")
        print("  - 关闭时不会初始化向量数据库，节省资源")
        print("  - 检索工具调用时返回空结果，不影响其他功能")

    except Exception as e:
        print(f"✗ 检索工具测试失败: {e}")


def main():
    """主测试函数"""
    print("\n" + "=" * 60)
    print("CraftFlow 工具链测试")
    print("=" * 60)
    print(f"环境: {settings.environment}")
    print(f"日志级别: {settings.log_level}")
    print(f"Tavily API Key 已配置: {bool(settings.tavily_api_key)}")
    print(f"E2B API Key 已配置: {bool(settings.e2b_api_key)}")
    print(f"RAG 功能: {'启用' if settings.enable_rag else '禁用'}")

    # 运行各个测试
    test_search_tools()
    test_sandbox_tools()
    test_validator_tools()
    test_retriever_tools()

    print("\n" + "=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
