"""LLM 答案对比器"""

import httpx
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional
from obd.models import LLMEvalConfig, AnswerCategory

logger = logging.getLogger(__name__)


@dataclass
class LLMEvalResult:
    """LLM评测结果"""
    is_correct: bool  # 2级分类结果
    category: str  # 4级分类
    analysis: str  # 完整分析
    missing_info: Optional[str]  # 缺失信息
    important_info: Optional[str]  # 重要信息识别
    prompt: Optional[str] = None  # LLM 评测提示词（调试用）
    raw_response: Optional[str] = None  # LLM 原始响应（JSON 格式，用于调试分析）


# 详细标准模式提示词
DETAILED_PROMPT_TEMPLATE = """你是一个专业的RAG系统评测员。请对比【问题】、【期望答案】和【实际回答】，判断实际回答的质量。

【问题】
{question}

【期望答案】
{expected}

【实际回答】
{actual}

请按照以下标准进行4级分类判断：

**1. 完全正确**
- 实际回答包含期望答案的所有重要信息（关键事实、参数、数值等）
- 可以忽略非重要信息的缺失或微小差异
- 表述方式可以与期望答案不同，但语义一致

**2. 部分缺失**
- 包含期望答案的部分重要信息
- 缺少1-2个重要信息点（如某个参数、某个关键步骤）
- 整体回答合理但不完整

**3. 大量缺失**
- 包含期望答案的少量信息或不完整信息
- 缺少多个重要信息点（如多个参数、完整流程等）
- 或者只回答了部分内容

**4. 完全错误**
- 完全未回答问题
- 回答内容与问题无关
- 提供了错误的信息
- 只说"不知道"、"无法回答"等

请按以下格式输出：

分类：[完全正确/部分缺失/大量缺失/完全错误]
分析：[简要说明判断理由，包括回答的优点和缺点]
缺失信息：[如果是错误类型，列出缺失的具体重要内容]
重要信息识别：[说明哪些信息是重要的（由LLM智能判断）]
"""


# 自主判断模式提示词
AUTONOMOUS_PROMPT_TEMPLATE = """你是一个专业的RAG系统评测员。请对比【问题】、【期望答案】和【实际回答】，判断实际回答的质量。

【问题】
{question}

【期望答案】
{expected}

【实际回答】
{actual}

判断原则：
1. 重点评估实际回答是否包含了期望答案的核心重要信息
2. 智能识别哪些信息是关键的，哪些是可以忽略的
3. 根据重要信息的覆盖程度进行4级分类

分类标准：
- 完全正确：核心重要信息完整覆盖
- 部分缺失：有少量核心信息缺失
- 大量缺失：大量核心信息缺失
- 完全错误：未回答或回答错误

请按以下格式输出：

分类：[完全正确/部分缺失/大量缺失/完全错误]
分析：[简要说明判断理由，包括识别出的重要信息和评估依据]
缺失信息：[如果是错误类型，列出缺失的具体重要内容]
重要信息识别：[说明哪些信息被判断为重要的]
"""

class LLMComparator:
    """基于 LLM 的答案对比分析器"""

    def __init__(self, config: LLMEvalConfig):
        self.config = config
        # 根据模式选择提示词模板
        if config.prompt_template:
            self.prompt_template = config.prompt_template
        elif config.judgment_mode == "detailed":
            self.prompt_template = DETAILED_PROMPT_TEMPLATE
        else:  # autonomous
            self.prompt_template = AUTONOMOUS_PROMPT_TEMPLATE

    @staticmethod
    def _parse_llm_response(content: str) -> LLMEvalResult:
        """
        解析 LLM 返回的结构化响应

        Args:
            content: LLM 返回的完整文本

        Returns:
            LLMEvalResult 对象
        """
        # 添加调试日志（限制日志长度）
        logger.debug(f"LLM 原始响应: {content[:500]}...")

        # 扩展分类映射，支持中英文
        category_map = {
            "完全正确": "fully_correct",
            "部分缺失": "partial_missing",
            "大量缺失": "large_missing",
            "完全错误": "completely_wrong",
            "fully_correct": "fully_correct",
            "partial_missing": "partial_missing",
            "large_missing": "large_missing",
            "completely_wrong": "completely_wrong"
        }

        # 1. 尝试标准格式匹配（中文）
        category_match = re.search(r'分类[：:]\s*(\S+)', content)

        # 2. 尝试宽松匹配（支持英文格式和更宽松的分隔符）
        if not category_match:
            category_match = re.search(
                r'category[：:]\s*(fully_correct|partial_missing|large_missing|completely_wrong)',
                content, re.IGNORECASE
            )

        if category_match:
            category_str = category_match.group(1)
            category = category_map.get(category_str, "completely_wrong")
        else:
            # 3. 降级推断逻辑：基于关键词内容推断分类
            content_lower = content.lower()
            if "完全正确" in content or "fully correct" in content_lower:
                category = "fully_correct"
            elif "部分缺失" in content or "partial" in content_lower and "missing" in content_lower:
                category = "partial_missing"
            elif "大量缺失" in content or ("large" in content_lower and "missing" in content_lower):
                category = "large_missing"
            else:
                category = "completely_wrong"
                logger.warning(
                    f"无法解析分类，使用默认值 completely_wrong。"
                    f"响应预览: {content[:200]}..."
                )

        # 提取分析部分
        analysis_match = re.search(
            r'分析[：:]\s*(.+?)(?=缺失信息|重要信息识别|$)', content, re.DOTALL
        )
        analysis = analysis_match.group(1).strip() if analysis_match else content

        # 提取缺失信息
        missing_match = re.search(
            r'缺失信息[：:]\s*(.+?)(?=重要信息识别|$)', content, re.DOTALL
        )
        missing_info = missing_match.group(1).strip() if missing_match else None

        # 提取重要信息识别
        important_match = re.search(
            r'重要信息识别[：:]\s*(.+)', content, re.DOTALL
        )
        important_info = important_match.group(1).strip() if important_match else None

        # 判断2级分类
        is_correct = category == "fully_correct"

        return LLMEvalResult(
            is_correct=is_correct,
            category=category,
            analysis=analysis,
            missing_info=missing_info,
            important_info=important_info
        )

    async def evaluate(self, question: str, expected: str, actual: str) -> LLMEvalResult:
        """
        调用 LLM 进行评测分析

        Returns:
            LLMEvalResult 对象（包含2级分类和4级分类）
        """
        if not self.config.enabled or not self.config.api_key:
            return LLMEvalResult(
                is_correct=False,
                category="completely_wrong",
                analysis="LLM 评测未启用或未配置 API Key",
                missing_info=None,
                important_info=None
            )

        url = f"{self.config.base_url.rstrip('/')}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }

        prompt = self.prompt_template.format(
            question=question,
            expected=expected,
            actual=actual
        )

        data = {
            "model": self.config.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": self.config.temperature  # 使用配置的温度参数
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=data, timeout=self.config.timeout)
                response.raise_for_status()
                result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"].strip()
                # 使用结构化解析
                return self._parse_llm_response(content)
            else:
                return LLMEvalResult(
                    is_correct=False,
                    category="completely_wrong",
                    analysis=f"API 返回格式异常: {json.dumps(result, ensure_ascii=False)}",
                    missing_info=None,
                    important_info=None
                )

        except Exception as e:
            error_msg = f"LLM 评测请求失败: {str(e)}"
            logger.error(error_msg)
            return LLMEvalResult(
                is_correct=False,
                category="completely_wrong",
                analysis=error_msg,
                missing_info=None,
                important_info=None
            )
