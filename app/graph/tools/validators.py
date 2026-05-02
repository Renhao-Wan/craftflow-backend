"""内容验证工具集

提供纯 Python 实现的验证工具，包括：
- 链接有效性验证
- 文本可读性计算
- Markdown 格式解析与验证
"""

import re
from typing import Any
from urllib.parse import urlparse

from langchain_core.tools import tool
from app.core.exceptions import ToolExecutionError
from app.core.logger import logger

# 延迟导入以避免未安装时报错
try:
    import requests
except ImportError:
    requests = None
    logger.warning("requests 未安装，链接验证功能将不可用")

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None
    logger.warning("beautifulsoup4 未安装，HTML 解析功能将不可用")


# ============================================
# 链接验证工具
# ============================================


@tool
def validate_url(url: str, timeout: int = 10) -> dict[str, Any]:
    """验证 URL 的有效性

    检查 URL 是否可访问，返回状态码和基本信息。

    Args:
        url: 要验证的 URL
        timeout: 请求超时时间（秒），默认 10 秒

    Returns:
        dict: 验证结果，包含：
            - valid: URL 是否有效
            - status_code: HTTP 状态码（如果可访问）
            - accessible: 是否可访问（2xx 或 3xx）
            - error: 错误信息（如果有）
            - final_url: 最终 URL（处理重定向后）

    Examples:
        >>> result = validate_url("https://www.python.org")
        >>> print(result["accessible"])
        True
    """
    if requests is None:
        raise ToolExecutionError(
            tool_name="validate_url",
            message="requests 未安装，请运行: pip install requests",
        )

    try:
        logger.info(f"开始验证 URL: {url}")

        # 基本格式验证
        parsed = urlparse(url)
        if not all([parsed.scheme, parsed.netloc]):
            return {
                "valid": False,
                "status_code": None,
                "accessible": False,
                "error": "URL 格式无效（缺少 scheme 或 netloc）",
                "final_url": url,
            }

        # 发送 HEAD 请求（更轻量）
        response = requests.head(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": "CraftFlow-Validator/1.0"},
        )

        # 如果 HEAD 失败，尝试 GET
        if response.status_code >= 400:
            response = requests.get(
                url,
                timeout=timeout,
                allow_redirects=True,
                headers={"User-Agent": "CraftFlow-Validator/1.0"},
            )

        result = {
            "valid": True,
            "status_code": response.status_code,
            "accessible": 200 <= response.status_code < 400,
            "error": None,
            "final_url": response.url,
        }

        if result["accessible"]:
            logger.info(f"URL 可访问: {url} (状态码: {response.status_code})")
        else:
            logger.warning(f"URL 不可访问: {url} (状态码: {response.status_code})")

        return result

    except requests.exceptions.Timeout:
        logger.warning(f"URL 验证超时: {url}")
        return {
            "valid": False,
            "status_code": None,
            "accessible": False,
            "error": f"请求超时（{timeout}s）",
            "final_url": url,
        }

    except requests.exceptions.RequestException as e:
        logger.warning(f"URL 验证失败: {url} - {str(e)}")
        return {
            "valid": False,
            "status_code": None,
            "accessible": False,
            "error": str(e),
            "final_url": url,
        }

    except Exception as e:
        error_msg = f"URL 验证异常: {str(e)}"
        logger.error(error_msg)
        raise ToolExecutionError(tool_name="validate_url", message=error_msg) from e


@tool
def batch_validate_urls(urls: list[str], timeout: int = 10) -> dict[str, Any]:
    """批量验证多个 URL

    Args:
        urls: URL 列表
        timeout: 每个请求的超时时间（秒），默认 10 秒

    Returns:
        dict: 批量验证结果，包含：
            - total: 总 URL 数
            - accessible: 可访问的 URL 数
            - inaccessible: 不可访问的 URL 数
            - results: 每个 URL 的详细结果列表

    Examples:
        >>> result = batch_validate_urls([
        ...     "https://www.python.org",
        ...     "https://invalid-url-12345.com"
        ... ])
        >>> print(result["accessible"])
        1
    """
    logger.info(f"开始批量验证 {len(urls)} 个 URL")

    results = []
    accessible_count = 0

    for url in urls:
        result = validate_url.invoke({"url": url, "timeout": timeout})
        results.append({"url": url, **result})

        if result["accessible"]:
            accessible_count += 1

    summary = {
        "total": len(urls),
        "accessible": accessible_count,
        "inaccessible": len(urls) - accessible_count,
        "results": results,
    }

    logger.info(
        f"批量验证完成: {accessible_count}/{len(urls)} 个 URL 可访问"
    )

    return summary


# ============================================
# 可读性计算工具
# ============================================


@tool
def calculate_readability(text: str) -> dict[str, Any]:
    """计算文本的可读性指标

    使用多种算法评估文本的阅读难度，包括：
    - Flesch Reading Ease（越高越易读，0-100）
    - 平均句子长度
    - 平均单词长度
    - 复杂词汇比例

    Args:
        text: 要分析的文本

    Returns:
        dict: 可读性指标，包含：
            - flesch_reading_ease: Flesch 阅读容易度（0-100）
            - avg_sentence_length: 平均句子长度（单词数）
            - avg_word_length: 平均单词长度（字符数）
            - complex_word_ratio: 复杂词汇比例（0-1）
            - readability_level: 可读性等级（"易读" / "中等" / "困难"）

    Examples:
        >>> result = calculate_readability("这是一个简单的句子。")
        >>> print(result["readability_level"])
        "易读"
    """
    try:
        logger.info("开始计算文本可读性")

        # 基本文本清理
        text = text.strip()
        if not text:
            raise ValueError("文本不能为空")

        # 分句（简单实现，支持中英文）
        sentences = re.split(r'[。！？.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        sentence_count = len(sentences)

        # 分词（简单实现）
        # 中文：按字符计数
        # 英文：按空格分词
        if re.search(r'[\u4e00-\u9fff]', text):  # 包含中文
            # 中文文本：去除标点后计数
            clean_text = re.sub(r'[^\u4e00-\u9fff\w\s]', '', text)
            word_count = len(clean_text.replace(' ', ''))
            words = list(clean_text.replace(' ', ''))
        else:  # 英文文本
            words = re.findall(r'\b\w+\b', text.lower())
            word_count = len(words)

        if sentence_count == 0 or word_count == 0:
            raise ValueError("无法解析文本结构")

        # 计算平均句子长度
        avg_sentence_length = word_count / sentence_count

        # 计算平均单词/字符长度
        avg_word_length = sum(len(w) for w in words) / len(words)

        # 计算复杂词汇比例（英文：>3 音节，中文：>4 字）
        if re.search(r'[\u4e00-\u9fff]', text):
            # 中文：长度 > 4 的词组视为复杂
            complex_words = [w for w in words if len(w) > 4]
        else:
            # 英文：长度 > 7 的单词视为复杂（粗略估计音节）
            complex_words = [w for w in words if len(w) > 7]

        complex_word_ratio = len(complex_words) / len(words) if words else 0

        # 计算 Flesch Reading Ease（简化版，适配中英文）
        # 公式：206.835 - 1.015 * (总词数/总句数) - 84.6 * (总音节数/总词数)
        # 简化：用平均单词长度近似音节数
        syllables_per_word = avg_word_length / 2  # 粗略估计
        flesch_score = 206.835 - 1.015 * avg_sentence_length - 84.6 * syllables_per_word

        # 限制分数范围
        flesch_score = max(0, min(100, flesch_score))

        # 确定可读性等级
        if flesch_score >= 60:
            readability_level = "易读"
        elif flesch_score >= 30:
            readability_level = "中等"
        else:
            readability_level = "困难"

        result = {
            "flesch_reading_ease": round(flesch_score, 2),
            "avg_sentence_length": round(avg_sentence_length, 2),
            "avg_word_length": round(avg_word_length, 2),
            "complex_word_ratio": round(complex_word_ratio, 2),
            "readability_level": readability_level,
            "sentence_count": sentence_count,
            "word_count": word_count,
        }

        logger.info(f"可读性计算完成: {readability_level} (Flesch: {flesch_score:.2f})")
        return result

    except Exception as e:
        error_msg = f"可读性计算失败: {str(e)}"
        logger.error(error_msg)
        raise ToolExecutionError(tool_name="calculate_readability", message=error_msg) from e


# ============================================
# Markdown 验证工具
# ============================================


@tool
def validate_markdown(content: str) -> dict[str, Any]:
    """验证 Markdown 格式的正确性

    检查 Markdown 文档的结构和格式问题，包括：
    - 标题层级是否合理
    - 代码块是否闭合
    - 链接格式是否正确
    - 列表格式是否规范

    Args:
        content: Markdown 内容

    Returns:
        dict: 验证结果，包含：
            - valid: 是否通过验证
            - issues: 问题列表（如果有）
            - structure: 文档结构信息
                - heading_count: 标题数量
                - code_block_count: 代码块数量
                - link_count: 链接数量
                - list_count: 列表数量

    Examples:
        >>> result = validate_markdown("# 标题\\n\\n正文内容")
        >>> print(result["valid"])
        True
    """
    try:
        logger.info("开始验证 Markdown 格式")

        issues = []
        structure = {
            "heading_count": 0,
            "code_block_count": 0,
            "link_count": 0,
            "list_count": 0,
        }

        lines = content.split('\n')

        # 检查标题层级
        headings = []
        for line in lines:
            if line.strip().startswith('#'):
                match = re.match(r'^(#{1,6})\s+(.+)$', line.strip())
                if match:
                    level = len(match.group(1))
                    headings.append(level)
                    structure["heading_count"] += 1
                else:
                    issues.append(f"标题格式错误: {line[:50]}")

        # 检查标题层级跳跃
        for i in range(1, len(headings)):
            if headings[i] - headings[i - 1] > 1:
                issues.append(
                    f"标题层级跳跃: 从 H{headings[i-1]} 直接跳到 H{headings[i]}"
                )

        # 检查代码块闭合
        code_block_open = False
        for i, line in enumerate(lines, 1):
            if line.strip().startswith('```'):
                code_block_open = not code_block_open
                if not code_block_open:
                    structure["code_block_count"] += 1

        if code_block_open:
            issues.append("代码块未闭合（缺少结束的 ```）")

        # 检查链接格式
        link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        links = re.findall(link_pattern, content)
        structure["link_count"] = len(links)

        for text, url in links:
            if not url.strip():
                issues.append(f"链接 URL 为空: [{text}]()")

        # 检查列表格式
        list_pattern = r'^\s*[-*+]\s+.+$'
        for line in lines:
            if re.match(list_pattern, line):
                structure["list_count"] += 1

        # 判断是否通过验证
        valid = len(issues) == 0

        result = {
            "valid": valid,
            "issues": issues,
            "structure": structure,
        }

        if valid:
            logger.info("Markdown 格式验证通过")
        else:
            logger.warning(f"Markdown 格式存在 {len(issues)} 个问题")

        return result

    except Exception as e:
        error_msg = f"Markdown 验证失败: {str(e)}"
        logger.error(error_msg)
        raise ToolExecutionError(tool_name="validate_markdown", message=error_msg) from e


@tool
def extract_markdown_structure(content: str) -> dict[str, Any]:
    """提取 Markdown 文档的结构信息

    解析 Markdown 文档，提取标题、代码块、链接等结构化信息。

    Args:
        content: Markdown 内容

    Returns:
        dict: 文档结构，包含：
            - headings: 标题列表（包含层级和文本）
            - code_blocks: 代码块列表（包含语言和内容）
            - links: 链接列表（包含文本和 URL）
            - images: 图片列表（包含 alt 文本和 URL）

    Examples:
        >>> result = extract_markdown_structure("# 标题\\n\\n```python\\nprint('hello')\\n```")
        >>> print(len(result["headings"]))
        1
    """
    try:
        logger.info("开始提取 Markdown 结构")

        structure = {
            "headings": [],
            "code_blocks": [],
            "links": [],
            "images": [],
        }

        lines = content.split('\n')

        # 提取标题
        for line in lines:
            match = re.match(r'^(#{1,6})\s+(.+)$', line.strip())
            if match:
                structure["headings"].append(
                    {"level": len(match.group(1)), "text": match.group(2).strip()}
                )

        # 提取代码块
        in_code_block = False
        current_code_block = {"language": "", "content": []}

        for line in lines:
            if line.strip().startswith('```'):
                if not in_code_block:
                    # 开始代码块
                    in_code_block = True
                    lang = line.strip()[3:].strip()
                    current_code_block = {"language": lang, "content": []}
                else:
                    # 结束代码块
                    in_code_block = False
                    current_code_block["content"] = '\n'.join(current_code_block["content"])
                    structure["code_blocks"].append(current_code_block)
            elif in_code_block:
                current_code_block["content"].append(line)

        # 提取链接
        link_pattern = r'\[([^\]]+)\]\(([^)]+)\)'
        for match in re.finditer(link_pattern, content):
            structure["links"].append({"text": match.group(1), "url": match.group(2)})

        # 提取图片
        image_pattern = r'!\[([^\]]*)\]\(([^)]+)\)'
        for match in re.finditer(image_pattern, content):
            structure["images"].append({"alt": match.group(1), "url": match.group(2)})

        logger.info(
            f"结构提取完成: {len(structure['headings'])} 个标题, "
            f"{len(structure['code_blocks'])} 个代码块, "
            f"{len(structure['links'])} 个链接"
        )

        return structure

    except Exception as e:
        error_msg = f"Markdown 结构提取失败: {str(e)}"
        logger.error(error_msg)
        raise ToolExecutionError(
            tool_name="extract_markdown_structure", message=error_msg
        ) from e


# 导出工具列表（供 LangGraph 节点绑定）
VALIDATOR_TOOLS = [
    validate_url,
    batch_validate_urls,
    calculate_readability,
    validate_markdown,
    extract_markdown_structure,
]
