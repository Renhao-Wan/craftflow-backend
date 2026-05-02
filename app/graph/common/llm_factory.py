"""LLM 工厂模块

提供单例模式的 LLM 实例管理，统一使用 OpenAI 兼容格式。
支持所有兼容 OpenAI API 格式的 LLM Provider（OpenAI、DeepSeek、Azure OpenAI、本地模型等）。
"""

from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.core.config import settings
from app.core.logger import logger


class LLMFactory:
    """LLM 工厂类

    统一使用 OpenAI 兼容格式，支持多种温度参数配置。
    使用单例模式确保全局只有一个 LLM 实例。
    
    支持的 Provider:
    - OpenAI 官方 API
    - DeepSeek
    - Azure OpenAI
    - 本地模型（如 Ollama、vLLM）
    - 其他兼容 OpenAI API 格式的服务
    """

    _instances: dict[str, BaseChatModel] = {}

    @classmethod
    def create_llm(
        cls,
        temperature: float | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
    ) -> BaseChatModel:
        """创建 LLM 实例（OpenAI 兼容格式）

        Args:
            temperature: 温度参数，控制输出随机性（0.0-2.0）。None 时使用配置默认值
            model: 模型名称。None 时使用配置默认值
            max_tokens: 最大 Token 数。None 时使用配置默认值

        Returns:
            BaseChatModel: LLM 实例

        Raises:
            ValueError: 当配置缺失时抛出
        """
        # 使用默认值
        temperature = temperature if temperature is not None else settings.default_temperature
        model = model or settings.llm_model
        max_tokens = max_tokens or settings.max_tokens

        # 生成缓存 key
        cache_key = f"{model}_{temperature}_{max_tokens}"

        # 检查缓存
        if cache_key in cls._instances:
            logger.debug(f"复用已缓存的 LLM 实例: {cache_key}")
            return cls._instances[cache_key]

        # 创建新实例
        logger.info(
            f"创建新的 LLM 实例 - Model: {model}, "
            f"Temperature: {temperature}, MaxTokens: {max_tokens}"
        )

        from typing import cast

        # cast() 在运行时不做任何事，它只是给类型检查器看的。
        llm = cls._create_openai_compatible_llm(
            cast(str, model),
            cast(float, temperature),
            cast(int, max_tokens)
        )

        # 缓存实例
        cls._instances[cache_key] = llm
        return llm

    @staticmethod
    def _create_openai_compatible_llm(
        model: str, temperature: float, max_tokens: int
    ) -> ChatOpenAI:
        """创建 OpenAI 兼容的 LLM 实例

        Args:
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大 Token 数

        Returns:
            ChatOpenAI: LLM 实例

        Raises:
            ValueError: API Key 未配置时抛出
        """
        if not settings.llm_api_key:
            raise ValueError("LLM_API_KEY 未配置，无法创建 LLM 实例")

        kwargs = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "api_key": settings.llm_api_key,
        }

        # 如果配置了自定义 API Base（如 DeepSeek、Azure OpenAI、本地模型）
        if settings.llm_api_base:
            kwargs["base_url"] = settings.llm_api_base
            logger.info(f"使用自定义 API Base: {settings.llm_api_base}")

        return ChatOpenAI(**kwargs)

    @classmethod
    def clear_cache(cls) -> None:
        """清空 LLM 实例缓存

        用于测试或需要重新加载配置的场景。
        """
        logger.info("清空 LLM 实例缓存")
        cls._instances.clear()


@lru_cache
def get_default_llm() -> BaseChatModel:
    """获取默认 LLM 实例（使用配置文件的默认参数）

    使用 lru_cache 确保全局单例。

    Returns:
        BaseChatModel: 默认 LLM 实例
    """
    return LLMFactory.create_llm()


@lru_cache
def get_editor_llm() -> BaseChatModel:
    """获取编辑节点专用 LLM 实例（使用更低的温度参数）

    编辑节点需要更保守的输出，因此使用较低的温度参数。

    Returns:
        BaseChatModel: 编辑节点 LLM 实例
    """
    return LLMFactory.create_llm(temperature=settings.editor_node_temperature)


def get_custom_llm(
    temperature: float | None = None,
    model: str | None = None,
    max_tokens: int | None = None,
) -> BaseChatModel:
    """获取自定义参数的 LLM 实例

    Args:
        temperature: 温度参数
        model: 模型名称
        max_tokens: 最大 Token 数

    Returns:
        BaseChatModel: 自定义 LLM 实例
    """
    return LLMFactory.create_llm(temperature=temperature, model=model, max_tokens=max_tokens)
