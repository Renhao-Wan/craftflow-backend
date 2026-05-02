"""本地知识库检索工具

提供基于向量数据库的知识检索能力。
支持 PostgreSQL (pgvector) 和 Chroma 两种后端，自动降级。

优先级：
1. PGVector (PostgreSQL + pgvector) - 生产环境推荐
2. Chroma - 开发环境备选方案
"""

from typing import Any, Literal

from langchain_core.tools import tool

from app.core.config import settings
from app.core.exceptions import ToolExecutionError
from app.core.logger import logger

# 延迟导入以避免未安装时报错
try:
    from langchain_core.documents import Document
    from langchain_core.embeddings import Embeddings
    from langchain_core.vectorstores import VectorStore
except ImportError:
    Document = None
    Embeddings = None
    VectorStore = None
    logger.warning("langchain-core 相关模块未完全导入，知识库检索功能将不可用")

# PGVector 导入
try:
    from langchain_postgres import PGVector
except ImportError:
    PGVector = None
    logger.info("langchain-postgres 未安装，PGVector 功能将不可用")

# Chroma 导入
try:
    from langchain_chroma import Chroma
except ImportError:
    Chroma = None
    logger.info("langchain-chroma 未安装，Chroma 功能将不可用")


class KnowledgeRetriever:
    """知识库检索器

    提供向量检索和语义搜索能力。
    支持 PGVector 和 Chroma 两种向量数据库后端，自动降级。
    """

    _instance: VectorStore
    _embeddings: Embeddings
    _backend: Literal["pgvector", "chroma", "none"] = "none"

    @classmethod
    def get_instance(cls) -> VectorStore:
        """获取知识库检索器单例

        Returns:
            VectorStore: 向量存储实例

        Raises:
            ToolExecutionError: 当知识库未初始化时抛出
        """
        if cls._instance is None:
            raise ToolExecutionError(
                tool_name="KnowledgeRetriever",
                message="知识库检索器未初始化，请先调用 initialize_knowledge_base()",
            )
        return cls._instance

    @classmethod
    def initialize(cls, embeddings: Embeddings, vector_store: VectorStore, backend: Literal["pgvector", "chroma", "none"]) -> None:
        """初始化知识库检索器

        Args:
            embeddings: 嵌入模型实例
            vector_store: 向量存储实例
            backend: 后端类型 ("pgvector" 或 "chroma")
        """
        cls._embeddings = embeddings
        cls._instance = vector_store
        cls._backend = backend
        logger.info(f"知识库检索器初始化成功，使用后端: {backend}")

    @classmethod
    def is_initialized(cls) -> bool:
        """检查知识库是否已初始化

        Returns:
            bool: 是否已初始化
        """
        return cls._instance is not None

    @classmethod
    def get_backend(cls) -> str:
        """获取当前使用的后端类型

        Returns:
            str: 后端类型 ("pgvector", "chroma", 或 "none")
        """
        return cls._backend


@tool
def search_knowledge_base(query: str, top_k: int = 5) -> list[dict[str, Any]]:
    """在本地知识库中搜索相关内容

    使用语义搜索在向量数据库中查找与查询最相关的文档片段。

    Args:
        query: 搜索查询字符串
        top_k: 返回的最大结果数，默认 5 条

    Returns:
        list[dict]: 搜索结果列表，每个结果包含：
            - content: 文档内容
            - metadata: 元数据（来源、标题等）
            - score: 相似度分数（0-1）

    Raises:
        ToolExecutionError: 搜索失败时抛出

    Examples:
        >>> results = search_knowledge_base("LangGraph 状态管理")
        >>> print(results[0]["content"])
        "LangGraph 使用 TypedDict 定义状态..."

    Note:
        此功能需要先调用 initialize_knowledge_base() 初始化知识库。
        如果 ENABLE_RAG=false，将直接返回空结果。
    """
    try:
        # 检查 RAG 是否启用
        if not settings.enable_rag:
            logger.info("RAG 功能未启用，返回空结果")
            return []
        
        logger.info(f"开始知识库搜索: query='{query}', top_k={top_k}")

        # 检查知识库是否已初始化
        if not KnowledgeRetriever.is_initialized():
            logger.warning("知识库未初始化，返回空结果")
            return []

        # 获取检索器实例
        vector_store = KnowledgeRetriever.get_instance()

        # 执行相似度搜索
        docs_with_scores = vector_store.similarity_search_with_score(query, k=top_k)

        # 格式化结果
        results = []
        for doc, score in docs_with_scores:
            results.append(
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": float(score),
                }
            )

        logger.info(f"知识库搜索完成，返回 {len(results)} 条结果")
        return results

    except Exception as e:
        error_msg = f"知识库搜索失败: {str(e)}"
        logger.error(error_msg)
        raise ToolExecutionError(tool_name="search_knowledge_base", message=error_msg) from e


@tool
def search_knowledge_with_filter(
    query: str, filters: dict[str, Any], top_k: int = 5
) -> list[dict[str, Any]]:
    """在知识库中执行带过滤条件的搜索

    支持基于元数据的过滤，例如按文档类型、标签、日期等筛选。

    Args:
        query: 搜索查询字符串
        filters: 过滤条件字典，例如 {"type": "tutorial", "language": "zh"}
        top_k: 返回的最大结果数，默认 5 条

    Returns:
        list[dict]: 搜索结果列表（格式同 search_knowledge_base）

    Raises:
        ToolExecutionError: 搜索失败时抛出

    Examples:
        >>> results = search_knowledge_with_filter(
        ...     query="状态管理",
        ...     filters={"type": "documentation", "language": "zh"}
        ... )
        >>> print(len(results))
        3

    Note:
        此功能需要先调用 initialize_knowledge_base() 初始化知识库。
        如果 ENABLE_RAG=false，将直接返回空结果。
    """
    try:
        # 检查 RAG 是否启用
        if not settings.enable_rag:
            logger.info("RAG 功能未启用，返回空结果")
            return []
        
        logger.info(
            f"开始带过滤的知识库搜索: query='{query}', filters={filters}, top_k={top_k}"
        )

        # 检查知识库是否已初始化
        if not KnowledgeRetriever.is_initialized():
            logger.warning("知识库未初始化，返回空结果")
            return []

        # 获取检索器实例
        vector_store = KnowledgeRetriever.get_instance()

        # 执行带过滤的相似度搜索
        # 注意：不同的向量数据库对过滤的支持方式不同
        # 这里使用通用接口，具体实现取决于后端
        docs_with_scores = vector_store.similarity_search_with_score(
            query, k=top_k, filter=filters
        )

        # 格式化结果
        results = []
        for doc, score in docs_with_scores:
            results.append(
                {
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "score": float(score),
                }
            )

        logger.info(f"带过滤的知识库搜索完成，返回 {len(results)} 条结果")
        return results

    except Exception as e:
        error_msg = f"带过滤的知识库搜索失败: {str(e)}"
        logger.error(error_msg)
        raise ToolExecutionError(
            tool_name="search_knowledge_with_filter", message=error_msg
        ) from e


@tool
def add_documents_to_knowledge_base(
    documents: list[dict[str, Any]]
) -> dict[str, Any]:
    """向知识库添加文档

    将新文档向量化并存储到知识库中。

    Args:
        documents: 文档列表，每个文档包含：
            - content: 文档内容（必需）
            - metadata: 元数据字典（可选）

    Returns:
        dict: 添加结果，包含：
            - success: 是否成功
            - added_count: 成功添加的文档数
            - failed_count: 失败的文档数
            - errors: 错误信息列表（如果有）

    Raises:
        ToolExecutionError: 添加失败时抛出

    Examples:
        >>> result = add_documents_to_knowledge_base([
        ...     {"content": "LangGraph 教程", "metadata": {"type": "tutorial"}},
        ...     {"content": "FastAPI 指南", "metadata": {"type": "guide"}}
        ... ])
        >>> print(result["added_count"])
        2

    Note:
        此功能需要先调用 initialize_knowledge_base() 初始化知识库。
        如果 ENABLE_RAG=false，将返回失败结果。
    """
    try:
        # 检查 RAG 是否启用
        if not settings.enable_rag:
            logger.warning("RAG 功能未启用，无法添加文档")
            return {
                "success": False,
                "added_count": 0,
                "failed_count": len(documents),
                "errors": ["RAG 功能未启用（ENABLE_RAG=false）"],
            }
        
        logger.info(f"开始向知识库添加 {len(documents)} 个文档")

        # 检查知识库是否已初始化
        if not KnowledgeRetriever.is_initialized():
            raise ToolExecutionError(
                tool_name="add_documents_to_knowledge_base",
                message="知识库未初始化，无法添加文档",
            )

        # 获取检索器实例
        vector_store = KnowledgeRetriever.get_instance()

        # 转换为 Document 对象
        if Document is None:
            raise ToolExecutionError(
                tool_name="add_documents_to_knowledge_base",
                message="langchain-core 未安装，无法创建 Document 对象",
            )

        docs = []
        for doc_dict in documents:
            if "content" not in doc_dict:
                logger.warning(f"文档缺少 content 字段，跳过: {doc_dict}")
                continue

            docs.append(
                Document(
                    page_content=doc_dict["content"],
                    metadata=doc_dict.get("metadata", {}),
                )
            )

        # 添加文档到向量存储
        vector_store.add_documents(docs)

        result = {
            "success": True,
            "added_count": len(docs),
            "failed_count": len(documents) - len(docs),
            "errors": [],
        }

        logger.info(f"成功向知识库添加 {len(docs)} 个文档")
        return result

    except Exception as e:
        error_msg = f"向知识库添加文档失败: {str(e)}"
        logger.error(error_msg)
        raise ToolExecutionError(
            tool_name="add_documents_to_knowledge_base", message=error_msg
        ) from e


# 导出工具列表（供 LangGraph 节点绑定）
RETRIEVER_TOOLS = [
    search_knowledge_base,
    search_knowledge_with_filter,
    add_documents_to_knowledge_base,
]


# ============================================
# 初始化辅助函数（供应用启动时调用）
# ============================================


def create_embeddings() -> Embeddings | None:
    """创建 Embeddings 模型实例

    根据配置自动选择并创建 Embeddings 模型。
    优先使用专门的 Embedding 配置，否则使用 LLM 配置。

    Returns:
        Embeddings | None: Embeddings 实例，失败时返回 None

    Examples:
        >>> embeddings = create_embeddings()
        >>> if embeddings:
        ...     print("Embeddings 创建成功")
    """
    try:
        from langchain_openai import OpenAIEmbeddings

        # 确定使用的 API Key
        api_key = settings.embedding_api_key
        if not api_key:
            logger.warning("未配置 Embedding API Key，无法创建 Embeddings")
            return None

        # 确定使用的 API Base
        api_base = settings.embedding_api_base

        logger.info(f"创建 Embeddings 模型: {settings.embedding_model}")
        if api_base:
            logger.info(f"  API Base: {api_base}")

        embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=api_key,
            base_url=api_base if api_base else None,
            dimensions=settings.embedding_dimensions if settings.embedding_dimensions else None,
        )

        logger.info("✅ Embeddings 模型创建成功")
        return embeddings

    except ImportError:
        logger.error("langchain-openai 未安装，无法创建 Embeddings")
        return None
    except Exception as e:
        logger.error(f"Embeddings 创建失败: {e}")
        return None


def create_pgvector_store(embeddings: Embeddings, collection_name: str = "craftflow_docs") -> VectorStore | None:
    """创建 PGVector 向量存储实例

    Args:
        embeddings: 嵌入模型实例
        collection_name: 集合名称，默认 "craftflow_docs"

    Returns:
        VectorStore | None: PGVector 实例，失败时返回 None
    """
    if PGVector is None:
        logger.warning("PGVector 未安装，无法创建 PGVector 存储")
        return None

    if not settings.use_persistent_checkpointer or not settings.database_url:
        logger.info("未配置 PostgreSQL，跳过 PGVector 初始化")
        return None

    try:
        # 从 database_url 提取连接字符串（移除 +asyncpg 后缀）
        connection_string = settings.database_url.replace("+asyncpg", "")

        logger.info(f"尝试连接 PGVector: {collection_name}")

        vector_store = PGVector(
            embeddings=embeddings,
            collection_name=collection_name,
            connection=connection_string,
            use_jsonb=True,  # 使用 JSONB 存储元数据
        )

        logger.info("PGVector 向量存储创建成功")
        return vector_store

    except Exception as e:
        logger.warning(f"PGVector 初始化失败: {e}")
        return None


def create_chroma_store(embeddings: Embeddings, persist_directory: str = "./chroma_db") -> VectorStore | None:
    """创建 Chroma 向量存储实例

    Args:
        embeddings: 嵌入模型实例
        persist_directory: 持久化目录，默认 "./chroma_db"

    Returns:
        VectorStore | None: Chroma 实例，失败时返回 None
    """
    if Chroma is None:
        logger.warning("Chroma 未安装，无法创建 Chroma 存储")
        return None

    try:
        logger.info(f"创建 Chroma 向量存储: {persist_directory}")

        vector_store = Chroma(
            embedding_function=embeddings,
            persist_directory=persist_directory,
            collection_name="craftflow_docs",
        )

        logger.info("Chroma 向量存储创建成功")
        return vector_store

    except Exception as e:
        logger.warning(f"Chroma 初始化失败: {e}")
        return None


def initialize_knowledge_base(
    embeddings: Embeddings | None = None,
    prefer_backend: Literal["pgvector", "chroma"] = "pgvector",
    collection_name: str = "craftflow_docs",
    chroma_persist_dir: str = "./chroma_db",
) -> bool:
    """初始化知识库检索器（自动降级）

    优先使用 PGVector，如果不可用则降级到 Chroma。
    如果未提供 embeddings，将自动根据配置创建。

    Args:
        embeddings: 嵌入模型实例（可选，不提供则自动创建）
        prefer_backend: 首选后端，默认 "pgvector"
        collection_name: 集合名称，默认 "craftflow_docs"
        chroma_persist_dir: Chroma 持久化目录，默认 "./chroma_db"

    Returns:
        bool: 是否成功初始化

    Examples:
        >>> # 自动创建 Embeddings
        >>> success = initialize_knowledge_base()
        >>> if success:
        ...     print("知识库初始化成功")
        
        >>> # 手动提供 Embeddings
        >>> from langchain_openai import OpenAIEmbeddings
        >>> embeddings = OpenAIEmbeddings()
        >>> success = initialize_knowledge_base(embeddings)

    Note:
        初始化顺序：
        1. 如果未提供 embeddings，自动根据配置创建
        2. 如果 prefer_backend="pgvector"，先尝试 PGVector，失败则尝试 Chroma
        3. 如果 prefer_backend="chroma"，先尝试 Chroma，失败则尝试 PGVector
        4. 如果两者都失败，返回 False
    """
    try:
        logger.info(f"开始初始化知识库，首选后端: {prefer_backend}")
        
        # 检查 RAG 是否启用
        if not settings.enable_rag:
            logger.info("RAG 功能未启用（ENABLE_RAG=false），跳过知识库初始化")
            return False

        # 如果未提供 embeddings，自动创建
        if embeddings is None:
            logger.info("未提供 Embeddings，尝试自动创建...")
            embeddings = create_embeddings()
            if embeddings is None:
                logger.error("Embeddings 创建失败，无法初始化知识库")
                return False

        vector_store = None
        backend = "none"

        # 根据首选后端决定尝试顺序
        if prefer_backend == "pgvector":
            # 先尝试 PGVector
            vector_store = create_pgvector_store(embeddings, collection_name)
            if vector_store:
                backend = "pgvector"
            else:
                # 降级到 Chroma
                logger.info("PGVector 不可用，尝试降级到 Chroma")
                vector_store = create_chroma_store(embeddings, chroma_persist_dir)
                if vector_store:
                    backend = "chroma"

        else:  # prefer_backend == "chroma"
            # 先尝试 Chroma
            vector_store = create_chroma_store(embeddings, chroma_persist_dir)
            if vector_store:
                backend = "chroma"
            else:
                # 降级到 PGVector
                logger.info("Chroma 不可用，尝试降级到 PGVector")
                vector_store = create_pgvector_store(embeddings, collection_name)
                if vector_store:
                    backend = "pgvector"

        # 检查是否成功创建向量存储
        if vector_store is None:
            logger.error("所有向量数据库后端均不可用，知识库检索功能将被禁用")
            return False

        # 初始化检索器
        KnowledgeRetriever.initialize(embeddings, vector_store, backend)
        logger.info(f"✅ 知识库检索器初始化成功，使用后端: {backend}")
        return True

    except Exception as e:
        logger.error(f"知识库初始化失败: {e}")
        return False
