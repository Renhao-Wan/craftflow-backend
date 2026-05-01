"""全局配置管理模块

使用 Pydantic Settings 从环境变量读取配置，支持 .env 文件加载。
提供单例模式的配置访问接口。
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置类

    所有配置项从环境变量读取，支持 .env 文件。
    使用 Pydantic 进行类型验证和默认值管理。
    """

    model_config = SettingsConfigDict(
        env_file=".env.dev",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # 忽略未定义的环境变量
    )

    # ============================================
    # 应用基础配置
    # ============================================
    app_name: str = Field(default="CraftFlow Backend", description="应用名称")
    app_version: str = Field(default="0.1.0", description="应用版本")
    environment: Literal["development", "production"] = Field(
        default="development", description="运行环境"
    )
    debug: bool = Field(default=True, description="调试模式")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="日志级别"
    )

    # ============================================
    # LLM 配置
    # ============================================
    llm_api_key: str = Field(default="", description="LLM API 密钥")
    llm_api_base: str = Field(default="", description="LLM API 基础 URL（可选）")
    llm_model: str = Field(default="gpt-4-turbo", description="默认 LLM 模型")
    max_tokens: int = Field(default=4096, ge=1, le=128000, description="最大 Token 数")

    # LLM 温度参数
    default_temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="默认温度参数")
    editor_node_temperature: float = Field(
        default=0.2, ge=0.0, le=2.0, description="编辑节点温度参数（更保守）"
    )

    # ============================================
    # 状态持久化配置
    # ============================================
    use_persistent_checkpointer: bool = Field(
        default=False, description="是否使用持久化 Checkpointer"
    )
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/craftflow",
        description="PostgreSQL 数据库连接 URL",
    )
    db_pool_size: int = Field(default=10, ge=1, le=100, description="数据库连接池大小")
    db_max_overflow: int = Field(default=20, ge=0, le=100, description="连接池最大溢出数")

    # ============================================
    # 外部工具 API 配置
    # ============================================
    tavily_api_key: str = Field(default="", description="Tavily Search API 密钥")
    e2b_api_key: str = Field(default="", description="E2B Code Interpreter API 密钥")

    # ============================================
    # LangSmith 追踪配置
    # ============================================
    langchain_tracing_v2: bool = Field(default=False, description="启用 LangSmith 追踪")
    langchain_endpoint: str = Field(
        default="https://api.smith.langchain.com", description="LangSmith API 端点"
    )
    langchain_api_key: str = Field(default="", description="LangSmith API 密钥")
    langchain_project: str = Field(default="craftflow-backend", description="LangSmith 项目名称")

    # ============================================
    # FastAPI 服务配置
    # ============================================
    host: str = Field(default="0.0.0.0", description="服务监听地址")
    port: int = Field(default=8000, ge=1, le=65535, description="服务监听端口")
    reload: bool = Field(default=True, description="热重载（仅开发环境）")
    workers: int = Field(default=1, ge=1, le=32, description="工作进程数")

    # CORS 配置
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:5173",
        description="允许的跨域来源（逗号分隔）",
    )
    cors_allow_credentials: bool = Field(default=True, description="允许携带凭证")

    # ============================================
    # Redis 配置（可选）
    # ============================================
    redis_host: str = Field(default="localhost", description="Redis 主机地址")
    redis_port: int = Field(default=6379, ge=1, le=65535, description="Redis 端口")
    redis_password: str = Field(default="", description="Redis 密码")
    redis_db: int = Field(default=0, ge=0, le=15, description="Redis 数据库索引")
    redis_max_connections: int = Field(default=20, ge=1, le=100, description="Redis 最大连接数")

    # ============================================
    # 业务逻辑配置
    # ============================================
    max_outline_sections: int = Field(default=10, ge=1, le=50, description="大纲最大章节数")
    max_concurrent_writers: int = Field(default=5, ge=1, le=20, description="并发写作节点数量上限")
    max_debate_iterations: int = Field(default=3, ge=1, le=10, description="对抗循环最大迭代次数")
    editor_pass_score: int = Field(default=90, ge=0, le=100, description="主编通过分数阈值")
    task_timeout: int = Field(default=3600, ge=60, le=86400, description="任务超时时间（秒）")
    tool_call_timeout: int = Field(default=30, ge=5, le=300, description="工具调用超时时间（秒）")

    @field_validator("cors_origins")
    @classmethod
    def parse_cors_origins(cls, v: str) -> list[str]:
        """解析 CORS 来源列表"""
        if not v:
            return []
        return [origin.strip() for origin in v.split(",") if origin.strip()]

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str, info) -> str:
        """验证数据库 URL 格式"""
        if info.data.get("use_persistent_checkpointer") and not v:
            raise ValueError("启用持久化 Checkpointer 时必须提供有效的 database_url")
        return v

    @property
    def is_production(self) -> bool:
        """判断是否为生产环境"""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """判断是否为开发环境"""
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """获取全局配置单例

    使用 lru_cache 确保配置对象只创建一次。

    Returns:
        Settings: 全局配置对象
    """
    return Settings()


# 导出便捷访问的配置实例
settings = get_settings()
