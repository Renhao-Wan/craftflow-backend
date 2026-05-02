"""共享抽象层模块

提供跨模块可复用的组件：
- LLM 工厂：统一的 LLM 实例管理
- 通用 Prompt 模板：跨模块可复用的提示词
"""

from app.graph.common.llm_factory import (
    LLMFactory,
    get_custom_llm,
    get_default_llm,
    get_editor_llm,
)
from app.graph.common.prompts import (
    ANTI_HALLUCINATION_RULES,
    CODE_VALIDATION_INSTRUCTION,
    CONTENT_STRATEGIST_ROLE,
    JSON_OUTPUT_RULES,
    MARKDOWN_FORMAT_RULES,
    PROFESSIONAL_EDITOR_ROLE,
    PROFESSIONAL_WRITER_ROLE,
    QUALITY_STANDARDS,
    SEARCH_TOOL_USAGE_INSTRUCTION,
    create_base_system_prompt,
    create_chat_prompt_template,
    get_json_output_template,
    get_markdown_output_template,
)

__all__ = [
    # LLM Factory
    "LLMFactory",
    "get_default_llm",
    "get_editor_llm",
    "get_custom_llm",
    # 角色定义
    "PROFESSIONAL_WRITER_ROLE",
    "PROFESSIONAL_EDITOR_ROLE",
    "CONTENT_STRATEGIST_ROLE",
    # 格式规范
    "MARKDOWN_FORMAT_RULES",
    "JSON_OUTPUT_RULES",
    # 约束条件
    "ANTI_HALLUCINATION_RULES",
    "QUALITY_STANDARDS",
    # 指令片段
    "SEARCH_TOOL_USAGE_INSTRUCTION",
    "CODE_VALIDATION_INSTRUCTION",
    # 模板创建函数
    "create_base_system_prompt",
    "create_chat_prompt_template",
    "get_markdown_output_template",
    "get_json_output_template",
]
