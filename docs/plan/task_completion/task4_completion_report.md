# Task 4 完成报告：LLM 工厂与通用 Prompt

## 任务概述

**任务名称**: LLM 工厂与通用 Prompt  
**完成日期**: 2026-05-02  
**状态**: ✅ 已完成

## 实现内容

### 1. LLM 工厂模块 (`app/graph/common/llm_factory.py`)

#### 核心功能

1. **单例模式的 LLM 实例管理**
   - 使用类级别的字典缓存 LLM 实例
   - 根据 `model_temperature_maxTokens` 生成唯一缓存 key
   - 避免重复创建相同配置的 LLM 实例

2. **统一的 OpenAI 兼容格式**
   - 所有 LLM 统一使用 `ChatOpenAI` 类
   - 通过 `base_url` 参数支持不同的 API 端点
   - 简化代码结构，提高可维护性

3. **广泛的 Provider 支持**
   - **OpenAI**: 官方 OpenAI API
   - **DeepSeek**: 通过自定义 `base_url` 配置
   - **Azure OpenAI**: 通过自定义 `base_url` 配置
   - **本地模型**: 支持 Ollama、vLLM 等本地部署
   - **其他服务**: 任何兼容 OpenAI API 格式的服务

4. **便捷的访问接口**
   - `get_default_llm()`: 获取默认配置的 LLM 实例
   - `get_editor_llm()`: 获取编辑节点专用 LLM（低温度参数）
   - `get_custom_llm()`: 获取自定义参数的 LLM 实例
   - `LLMFactory.clear_cache()`: 清空缓存（用于测试）

#### 代码统计

- **文件**: `app/graph/common/llm_factory.py`
- **行数**: 140 行（相比原版减少 80 行）
- **函数数**: 5 个（相比原版减少 3 个）
- **类数**: 1 个

#### 设计优势

- ✅ **代码简洁**: 移除了 Provider 推断逻辑，减少了 40% 的代码量
- ✅ **统一接口**: 所有 LLM 使用相同的 OpenAI 兼容格式
- ✅ **易于扩展**: 新增 Provider 只需配置 `base_url`，无需修改代码
- ✅ **降低依赖**: 移除了 `langchain-anthropic` 依赖

### 2. 通用 Prompt 模板模块 (`app/graph/common/prompts.py`)

#### 核心内容

1. **通用角色定义**
   - `PROFESSIONAL_WRITER_ROLE`: 专业技术写作专家
   - `PROFESSIONAL_EDITOR_ROLE`: 经验丰富的主编
   - `CONTENT_STRATEGIST_ROLE`: 专业内容策划师

2. **输出格式规范**
   - `MARKDOWN_FORMAT_RULES`: Markdown 格式详细规范
   - `JSON_OUTPUT_RULES`: JSON 输出格式规范

3. **通用约束条件**
   - `ANTI_HALLUCINATION_RULES`: 防止幻觉的约束条件
   - `QUALITY_STANDARDS`: 内容质量标准

4. **通用指令片段**
   - `SEARCH_TOOL_USAGE_INSTRUCTION`: 搜索工具使用指南
   - `CODE_VALIDATION_INSTRUCTION`: 代码验证指南

5. **模板创建函数**
   - `create_base_system_prompt()`: 创建基础系统 Prompt
   - `create_chat_prompt_template()`: 创建 ChatPromptTemplate
   - `get_markdown_output_template()`: 获取 Markdown 输出模板
   - `get_json_output_template()`: 获取 JSON 输出模板

#### 设计原则

- **高内聚低耦合**: 通用模板独立，业务专属模板放在各自模块
- **可组合性**: 通过函数参数灵活组合不同的 Prompt 片段
- **可扩展性**: 新增节点只需在对应模块添加专属 Prompt

#### 代码统计

- **文件**: `app/graph/common/prompts.py`
- **行数**: 350 行
- **常量数**: 10 个
- **函数数**: 4 个

### 3. 模块导出 (`app/graph/common/__init__.py`)

统一导出接口，便于其他模块导入：

```python
from app.graph.common import (
    # LLM Factory
    get_default_llm,
    get_editor_llm,
    get_custom_llm,
    # 角色定义
    PROFESSIONAL_WRITER_ROLE,
    PROFESSIONAL_EDITOR_ROLE,
    # 格式规范
    MARKDOWN_FORMAT_RULES,
    # 模板创建函数
    create_base_system_prompt,
    get_markdown_output_template,
)
```

### 4. 测试脚本 (`scripts/test_llm_factory.py`)

#### 测试覆盖

1. **LLM 实例创建测试**
   - 测试默认 LLM 创建
   - 测试编辑器 LLM 创建
   - 测试自定义参数 LLM 创建

2. **LLM 实例缓存测试**
   - 验证相同参数返回同一实例
   - 验证不同参数返回不同实例

3. **LLM 基本调用测试**
   - 测试实际的 LLM API 调用
   - 验证响应内容

4. **Prompt 模板测试**
   - 测试 Markdown 输出模板
   - 测试 JSON 输出模板
   - 测试自定义系统 Prompt

#### 测试结果

```
✅ 测试 1: LLM 实例创建 - 3/3 通过
✅ 测试 2: LLM 实例缓存 - 2/2 通过
✅ 测试 3: LLM 基本调用 - 1/1 通过
✅ 测试 4: 通用 Prompt 模板 - 3/3 通过

总计: 9/9 测试通过
```

## 技术亮点

### 1. 统一的 OpenAI 兼容格式

```python
@staticmethod
def _create_openai_compatible_llm(
    model: str, temperature: float, max_tokens: int
) -> ChatOpenAI:
    """创建 OpenAI 兼容的 LLM 实例"""
    kwargs = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "api_key": settings.llm_api_key,
    }
    
    # 通过 base_url 支持不同的 Provider
    if settings.llm_api_base:
        kwargs["base_url"] = settings.llm_api_base
    
    return ChatOpenAI(**kwargs)
```

**优势**:
- 代码简洁，易于维护
- 支持所有 OpenAI 兼容的 API
- 无需为每个 Provider 编写特殊逻辑

### 2. 简化的缓存机制

```python
# 生成缓存 key（移除了 provider 维度）
cache_key = f"{model}_{temperature}_{max_tokens}"

if cache_key in cls._instances:
    return cls._instances[cache_key]

# 创建新实例并缓存
llm = cls._create_openai_compatible_llm(model, temperature, max_tokens)
cls._instances[cache_key] = llm
```

**优势**:
- 缓存 key 更简洁
- 减少了不必要的维度
- 提高了缓存命中率

### 3. 可组合的 Prompt 模板

```python
def create_base_system_prompt(
    role: str,
    task_description: str,
    include_markdown_rules: bool = True,
    include_anti_hallucination: bool = True,
    include_quality_standards: bool = True,
    additional_instructions: str = "",
) -> str:
    """灵活组合不同的 Prompt 片段"""
    prompt_parts = [role, "", task_description]
    
    if include_markdown_rules:
        prompt_parts.extend(["", MARKDOWN_FORMAT_RULES])
    # ... 其他片段
    
    return "\n".join(prompt_parts)
```

## 依赖库

```toml
langchain-core = "^0.3.28"
langchain-openai = "^0.2.14"
# 注意：移除了 langchain-anthropic 依赖
```

## 配置示例

### OpenAI 官方 API

```env
LLM_API_KEY="sk-your-openai-api-key"
LLM_API_BASE=""  # 留空使用默认
LLM_MODEL="gpt-4-turbo"
```

### DeepSeek

```env
LLM_API_KEY="your-deepseek-api-key"
LLM_API_BASE="https://api.deepseek.com/v1"
LLM_MODEL="deepseek-chat"
```

### Azure OpenAI

```env
LLM_API_KEY="your-azure-api-key"
LLM_API_BASE="https://your-resource.openai.azure.com/openai/deployments/your-deployment"
LLM_MODEL="gpt-4"
```

### 本地模型（Ollama）

```env
LLM_API_KEY="ollama"  # 任意值
LLM_API_BASE="http://localhost:11434/v1"
LLM_MODEL="llama2"
```

## 使用示例

### 1. 基本使用

```python
from app.graph.common import get_default_llm

# 获取默认 LLM
llm = get_default_llm()

# 调用 LLM
response = await llm.ainvoke([("human", "你好")])
print(response.content)
```

### 2. 使用编辑器 LLM

```python
from app.graph.common import get_editor_llm

# 编辑器 LLM 使用更低的温度参数（0.2）
editor_llm = get_editor_llm()
```

### 3. 自定义参数

```python
from app.graph.common import get_custom_llm

# 创建自定义参数的 LLM
llm = get_custom_llm(
    temperature=0.5,
    model="gpt-4-turbo",
    max_tokens=2000
)
```

### 4. 使用 Prompt 模板

```python
from app.graph.common import (
    create_base_system_prompt,
    PROFESSIONAL_WRITER_ROLE,
    get_markdown_output_template,
)

# 创建自定义系统 Prompt
system_prompt = create_base_system_prompt(
    role=PROFESSIONAL_WRITER_ROLE,
    task_description="撰写技术博客",
    include_markdown_rules=True,
)

# 使用预定义模板
template = get_markdown_output_template()
messages = template.format_messages(input="生成一篇关于 AI 的文章")
```

## 后续优化建议

### 1. 性能优化

- [ ] 实现 LRU 缓存淘汰策略，避免缓存无限增长
- [ ] 添加 LLM 实例的健康检查机制
- [ ] 支持异步初始化，提升启动速度

### 2. 功能增强

- [ ] 支持更多 LLM Provider 配置示例（Google Gemini、Cohere 等）
- [ ] 添加 LLM 调用的重试机制和降级策略
- [ ] 支持流式响应（Streaming）
- [ ] 添加 Token 使用统计和成本追踪
- [ ] 支持多个 LLM 实例的负载均衡

### 3. 可观测性

- [ ] 集成 LangSmith 追踪
- [ ] 添加 LLM 调用的性能监控
- [ ] 记录每次调用的 Token 消耗

### 4. Prompt 管理

- [ ] 支持从外部文件加载 Prompt 模板
- [ ] 实现 Prompt 版本管理
- [ ] 添加 Prompt 效果评估工具

## 文件清单

```
app/graph/common/
├── __init__.py              # 模块导出（60 行）
├── llm_factory.py           # LLM 工厂（140 行，简化版）
└── prompts.py               # 通用 Prompt 模板（350 行）

scripts/
└── test_llm_factory.py      # 测试脚本（160 行，简化版）

docs/plan/task_completion/
└── task4_completion_report.md  # 本文档
```

## 总结

Task 4 成功实现了简化版的 LLM 工厂和通用 Prompt 模板模块，为后续的 Graph 节点开发奠定了坚实的基础。

**核心成果**:
- ✅ 单例模式的 LLM 实例管理
- ✅ 统一的 OpenAI 兼容格式
- ✅ 广泛的 Provider 支持（通过 `base_url` 配置）
- ✅ 通用 Prompt 模板库
- ✅ 完整的测试覆盖

**代码质量**:
- 代码结构清晰，职责明确
- 相比原版减少 40% 代码量
- 完善的类型注解和文档字符串
- 全面的测试覆盖（9/9 通过）
- 遵循 PEP 8 代码规范

**设计优势**:
- 统一接口，降低复杂度
- 易于扩展，无需修改代码
- 减少依赖，降低维护成本

**下一步**: 开始 Task 5 - 工具链封装（TavilySearch、E2B、Validators、Retriever）

---

**报告生成时间**: 2026-05-02  
**报告作者**: CraftFlow 开发团队
