"""外部工具链封装模块

提供以下工具类别：
- search: 互联网搜索工具（TavilySearch）
- sandbox: 代码沙箱工具（E2B Code Interpreter）
- validators: 内容验证工具（链接验证、可读性计算、Markdown 解析）
- retriever: 本地知识库检索工具（PGVector + Chroma 自动降级）
"""

from app.graph.tools.retriever import (
    RETRIEVER_TOOLS,
    create_embeddings,
    initialize_knowledge_base,
)
from app.graph.tools.sandbox import SANDBOX_TOOLS
from app.graph.tools.search import SEARCH_TOOLS
from app.graph.tools.validators import VALIDATOR_TOOLS

# 导出所有工具列表
ALL_TOOLS = SEARCH_TOOLS + SANDBOX_TOOLS + VALIDATOR_TOOLS + RETRIEVER_TOOLS

# 按类别导出
__all__ = [
    # 工具列表
    "SEARCH_TOOLS",
    "SANDBOX_TOOLS",
    "VALIDATOR_TOOLS",
    "RETRIEVER_TOOLS",
    "ALL_TOOLS",
    # 初始化函数
    "create_embeddings",
    "initialize_knowledge_base",
]
