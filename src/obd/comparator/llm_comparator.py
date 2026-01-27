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
    missing_info: Optional[str] = None  # 缺失信息（兼容旧版）
    important_info: Optional[str] = None  # 重要信息识别（兼容旧版）
    prompt: Optional[str] = None  # LLM 评测提示词（调试用）
    raw_response: Optional[str] = None  # LLM 原始响应（JSON 格式，用于调试分析）

    # 新增：各维度独立分析字段
    retrieval_quality: Optional[str] = None  # 召回质量评估
    basis_analysis: Optional[str] = None  # 基于性分析
    accuracy_analysis: Optional[str] = None  # 准确性分析
    completeness_analysis: Optional[str] = None  # 完整性分析
    version_analysis: Optional[str] = None  # 版本对比分析
    overall_judgment: Optional[str] = None  # 总体判断


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

        # 2. 尝试宽松匹配（支持英文格式和更宽松的分隔符，兼容 Markdown 粗体）
        if not category_match:
            category_match = re.search(
                r'category[：:]\s*\*{0,2}(fully_correct|partial_missing|large_missing|completely_wrong)\*{0,2}',
                content, re.IGNORECASE
            )

        if category_match:
            # 清理可能的 Markdown 格式符（**）和首尾空格
            category_str = category_match.group(1).strip('*').strip()
            category = category_map.get(category_str, "completely_wrong")
        else:
            # 3. 降级推断逻辑：基于关键词内容推断分类
            content_lower = content.lower()
            if "完全正确" in content or "fully correct" in content_lower:
                category = "fully_correct"
            elif "部分缺失" in content or ("partial" in content_lower and "missing" in content_lower):
                category = "partial_missing"
            elif "大量缺失" in content or ("large" in content_lower and "missing" in content_lower):
                category = "large_missing"
            else:
                category = "completely_wrong"
                logger.warning(
                    f"无法解析分类，使用默认值 completely_wrong。"
                    f"响应预览: {content[:200]}..."
                )

        # 定义提取节的辅助函数
        def extract_section(name_pattern, next_patterns=None):
            if next_patterns is None:
                next_patterns = [
                    "基于性", "准确性", "完整性", 
                    "版本对比", "总体分析", "总体判断", "###", "---"
                ]
            
            # 过滤掉当前的 pattern (包含可能的部分匹配)
            current_next = [p for p in next_patterns if p not in name_pattern and name_pattern not in p]
            lookahead = "|".join(current_next)
            
            # 匹配当前节的内容
            # 支持 ### 标题, ## 标题, 标题：, 标题
            # 增加 (?:\s*分析)? 支持 "版本对比" 或 "版本对比分析"
            pattern = rf"(?:###?\s*)?{name_pattern}(?:\s*分析)?[：:]?\s*(.+?)(?=\n\s*(?:###?\s*)?(?:{lookahead})|$)"
            match = re.search(pattern, content, re.DOTALL)
            return match.group(1).strip() if match else None

        # 提取各维度分析
        retrieval_quality = extract_section("召回质量评估")
        basis_analysis = extract_section("基于性")
        accuracy_analysis = extract_section("准确性")
        completeness_analysis = extract_section("完整性")
        version_analysis = extract_section("版本对比")
        overall_judgment = extract_section("总体(?:判断|分析)", next_patterns=["###", "---"])

        # 组合完整分析（用于 Excel "LLM 评测分析" 列）
        analysis_parts = []
        if retrieval_quality:
            analysis_parts.append(f"召回质量评估：{retrieval_quality}")
        if basis_analysis:
            analysis_parts.append(f"基于性分析：{basis_analysis}")
        if accuracy_analysis:
            analysis_parts.append(f"准确性分析：{accuracy_analysis}")
        if completeness_analysis:
            analysis_parts.append(f"完整性分析：{completeness_analysis}")
        if version_analysis:
            analysis_parts.append(f"版本对比分析：{version_analysis}")
        if overall_judgment:
            analysis_parts.append(f"总体判断：{overall_judgment}")

        # 如果解析到了新格式，使用结构化分析；否则使用原始内容
        if analysis_parts:
            analysis = "\n\n".join(analysis_parts)
        else:
            analysis = content.strip()

        # 兼容旧字段：从新格式推断，保持向后兼容
        # 优先尝试从旧格式中提取
        missing_match = re.search(
            r'缺失信息[：:]\s*(.+?)(?=重要信息识别|$)', content, re.DOTALL
        )
        important_match = re.search(
            r'重要信息识别[：:]\s*(.+)', content, re.DOTALL
        )

        # 如果旧格式不存在，从新格式推断
        if missing_match:
            missing_info = missing_match.group(1).strip()
        else:
            # 从完整性分析推断缺失信息
            missing_info = completeness_analysis

        if important_match:
            important_info = important_match.group(1).strip()
        else:
            # 从召回质量评估推断重要信息识别
            important_info = retrieval_quality

        # 判断2级分类
        is_correct = category == "fully_correct"

        return LLMEvalResult(
            is_correct=is_correct,
            category=category,
            analysis=analysis,
            missing_info=missing_info,
            important_info=important_info,
            # 新增字段
            retrieval_quality=retrieval_quality,
            basis_analysis=basis_analysis,
            accuracy_analysis=accuracy_analysis,
            completeness_analysis=completeness_analysis,
            version_analysis=version_analysis,
            overall_judgment=overall_judgment
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
