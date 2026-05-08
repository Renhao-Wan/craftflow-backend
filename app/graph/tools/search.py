"""互联网搜索工具封装

封装 TavilySearch API，提供结构化的搜索能力。
支持超时控制、错误处理和结果格式化。
"""

from typing import Any

from langchain_tavily import TavilySearch
from langchain_core.tools import tool

from app.core.config import settings
from app.core.exceptions import ToolExecutionError
from app.core.logger import logger


class TavilySearchTool:
    """tavily 搜索工具封装类

    提供单例模式的搜索工具实例，支持配置化管理。
    """

    _instance: TavilySearch | None = None

    @classmethod
    def get_instance(cls, max_results: int = 5) -> TavilySearch:
        """获取 TavilySearch 工具单例

        Args:
            max_results: 最大返回结果数，默认 5 条

        Returns:
            TavilySearch: 搜索工具实例

        Raises:
            ToolExecutionError: 当 API Key 未配置时抛出
        """
        if cls._instance is None:
            if not settings.tavily_api_key:
                raise ToolExecutionError(
                    tool_name="TavilySearch",
                    message="TAVILY_API_KEY 未配置，请在 .env 文件中设置",
                )

            import os
            os.environ["TAVILY_API_KEY"] = settings.tavily_api_key

            cls._instance = TavilySearch(
                max_results=max_results,
                search_depth="advanced",
                include_answer=True,
                include_raw_content=False,
                include_images=False,
            )
            logger.info(f"TavilySearch 工具初始化成功，最大结果数: {max_results}")

        assert cls._instance is not None, "TavilySearch 工具实例未正确初始化"

        return cls._instance


@tool
def search_internet(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """互联网搜索工具

    使用 tavily API 进行高质量的互联网搜索，返回结构化结果。

    Args:
        query: 搜索查询字符串
        max_results: 最大返回结果数，默认 5 条

    Returns:
        list[dict]: 搜索结果列表，每个结果包含：
            - title: 标题
            - url: 链接
            - content: 内容摘要
            - score: 相关性分数（0-1）

    Raises:
        ToolExecutionError: 搜索失败时抛出

    Examples:
        >>> results = search_internet("LangGraph 教程")
        >>> print(results[0]["title"])
        "LangGraph 官方文档"
    """
    try:
        logger.info(f"开始互联网搜索: query='{query}', max_results={max_results}")

        search_tool = TavilySearchTool.get_instance(max_results=max_results)
        raw = search_tool.invoke({"query": query})

        # TavilySearch.invoke() 返回 dict: {"answer": ..., "results": [...]}
        results = raw.get("results", []) if isinstance(raw, dict) else raw

        formatted_results = []
        for idx, result in enumerate(results, 1):
            formatted_results.append(
                {
                    "rank": idx,
                    "title": result.get("title", "无标题"),
                    "url": result.get("url", ""),
                    "content": result.get("content", ""),
                    "score": result.get("score", 0.0),
                }
            )

        logger.info(f"搜索完成，返回 {len(formatted_results)} 条结果")
        return formatted_results

    except Exception as e:
        error_msg = f"互联网搜索失败: {str(e)}"
        logger.error(error_msg)
        raise ToolExecutionError(tool_name="search_internet", message=error_msg) from e


@tool
def search_with_answer(query: str) -> dict[str, Any]:
    """带 AI 答案的互联网搜索

    除了返回搜索结果，还包含 tavily AI 生成的答案摘要。
    适用于需要快速获取答案的场景。

    Args:
        query: 搜索查询字符串

    Returns:
        dict: 包含以下字段：
            - answer: AI 生成的答案摘要
            - results: 搜索结果列表（同 search_internet）

    Raises:
        ToolExecutionError: 搜索失败时抛出

    Examples:
        >>> result = search_with_answer("什么是 LangGraph?")
        >>> print(result["answer"])
        "LangGraph 是一个用于构建有状态、多参与者应用的框架..."
    """
    try:
        logger.info(f"开始带答案的互联网搜索: query='{query}'")

        search_tool = TavilySearchTool.get_instance(max_results=3)
        raw = search_tool.invoke({"query": query})

        # TavilySearch.invoke() 返回 dict: {"answer": ..., "results": [...]}
        answer = ""
        raw_results = []
        if isinstance(raw, dict):
            answer = raw.get("answer", "")
            raw_results = raw.get("results", [])
        elif isinstance(raw, list):
            raw_results = raw

        formatted_results = []
        for idx, result in enumerate(raw_results, 1):
            if isinstance(result, dict):
                formatted_results.append(
                    {
                        "rank": idx,
                        "title": result.get("title", "无标题"),
                        "url": result.get("url", ""),
                        "content": result.get("content", ""),
                        "score": result.get("score", 0.0),
                    }
                )

        response = {"answer": answer, "results": formatted_results}

        logger.info(f"带答案搜索完成，返回 {len(formatted_results)} 条结果")
        return response

    except Exception as e:
        error_msg = f"带答案的互联网搜索失败: {str(e)}"
        logger.error(error_msg)
        raise ToolExecutionError(tool_name="search_with_answer", message=error_msg) from e


# 导出工具列表（供 LangGraph 节点绑定）
SEARCH_TOOLS = [search_internet, search_with_answer]
