# CraftFlow 工具调用

流程图中只在 `FactChecker` 里提到了 Google Search 和 Python REPL，但这远远不够。真正能落地的长文 Agent，**工具调用应该贯穿整个生命周期**。

## 场景一：渐进式创作流 (Creation Graph)

在创作阶段，不要让大模型“闭门造车”写大纲和章节。必须为其配备“公网信息”与“私有知识”的双重视野。

| 触发节点            | 工具名称 (建议使用的第三方库/API)                                 | 工具作用描述                                                                               |
| :-------------- | :--------------------------------------------------- | :----------------------------------------------------------------------------------- |
| **PlannerNode** | `TavilySearch` (强推，比 Google 搜索更适合 LLM)               | 在生成大纲前，先检索互联网上关于该 `topic` 的最新行业动态、前沿案例或热门讨论，确保大纲的结构和观点不落伍。                           |
| **PlannerNode** | `LocalKnowledge_Retriever` (自写工具，对接 pgvector/Milvus) | 检索系统本地的私有知识库（如用户提前上传的参考资料、历史沉淀的优秀长文）。提取领域专属知识，让大纲生成带有专业视角的锚点，避免泛泛而谈。                 |
| **WriterNode**  | `WebScraper` (BeautifulSoup / Playwright)            | 仅靠搜索引擎返回的 Snippet (摘要) 写长文深度是不够的。该工具允许 Writer 智能体传入特定 URL，自动抓取并解析完整网页正文，进行深度阅读和素材提炼。 |

## 场景二：多阶润色流 (Polishing Graph)

在审校与润色阶段，工具调用的核心目的是 **“降幻觉”** 与 **“硬性指标控制”**。这里是多智能体博弈与外挂工具的高频调用区。

| 触发节点            | 工具名称 (建议使用的第三方库/API)                    | 工具作用描述                                                                                              |
| :-------------- | :-------------------------------------- | :-------------------------------------------------------------------------------------------------- |
| **FactChecker** | **`E2B_CodeInterpreter` (安全代码沙盒，核心壁垒)** | **极度重要！**遇到技术类长文中的代码块，FactChecker 会自动提取代码，丢进 E2B 独立沙盒执行。捕获运行结果或报错信息，作为“铁证”反馈给 AuthorNode 强制修正。      |
| **FactChecker** | `TavilySearch`                          | 针对文章中出现的专有名词、历史年份、统计数据等客观实体，调用公网数据进行交叉验证（Cross-Check），排查事实性幻觉。                                      |
| **FactChecker** | `LinkValidator` (自写 Python 小工具)         | 大模型在生成长文时极爱“捏造死链”。该工具利用多线程自动扫描文章中生成的所有 Markdown 链接（URL），校验其连通性，对于 404 链接强制要求 LLM 替换。                |
| **EditorNode**  | `Calculate_Readability` (纯 Python 函数)   | **无需调用大模型算力。**纯代码计算文章的字数、词汇丰富度、阅读理解难度（如 Flesch-Kincaid 评分）。该数值作为 EditorNode 评估“通顺度与受众匹配度”的量化打分依据之一。 |

**补充说明 `LocalKnowledge_Retriever`：**
将工具解耦后，这个独立的 **CraftFlow Agent 系统** 具备了极强的通用 SaaS 属性：
* 如果外部调用方是**个人创作者**，他可以上传一批 PDF，`LocalKnowledge_Retriever` 就会基于这些 PDF 帮他写出带引用的专业文章。
* 如果外部调用方是**技术社区/企业内部系统**，只需通过 API 传入对应的业务上下文，Agent 就能直接对接该业务的专属数据库，成为一个即插即用的智能编辑部。

# 在 LangGraph 中如何优雅地注册这些工具？

不要把工具硬编码在 Prompt 里。使用 LangGraph 的 `bind_tools()` 机制：

```python
from langchain_core.tools import tool

# 1. 自定义一个验证死链的工具
@tool
def validate_links(urls: list[str]) -> dict:
    """验证文章中的链接是否有效（非404）。传入URL列表，返回验证结果字典。"""
    results = {}
    for url in urls:
        # requests.get(url) 逻辑
        ...
    return results

# 2. 绑定到特定节点的大模型上
llm_with_tools = llm.bind_tools([validate_links, tavily_search, e2b_code_interpreter])

# 3. 在 FactCheckerNode 中调用
def fact_checker_node(state: GraphState):
    # LLM 会自动决定是否调用工具，如果调用，LangGraph 会将其放入 tool_calls 中
    response = llm_with_tools.invoke(state["draft"])
    ...
```
