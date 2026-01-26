"""
RAG 语义评测器

专门用于 RAG 系统的评测，支持：
- 评测范围（Scope）限制
- 历史回答对比
- 改进情况分析
"""

import asyncio
import httpx
import json
import logging
from dataclasses import asdict
from typing import Optional, TYPE_CHECKING
from .llm_comparator import LLMComparator, LLMEvalResult
from ..models import LLMEvalConfig

if TYPE_CHECKING:
    from ..utils.eval_recorder import EvalRecorder

logger = logging.getLogger(__name__)


class SemanticJudge:
    """
    RAG 语义评测器

    封装 LLMComparator，提供专门针对 RAG 场景的评测接口。
    支持评测范围限制和历史回答对比。
    """

    def __init__(self, config: LLMEvalConfig, recorder: Optional["EvalRecorder"] = None):
        """
        初始化评测器

        Args:
            config: LLM 评测配置
            recorder: 评测记录器（可选），用于记录 prompt 和响应
        """
        self.llm_comparator = LLMComparator(config)
        self.config = config
        self.recorder = recorder

    async def evaluate_with_context(
        self,
        question: str,
        actual_answer: str,
        rerank_sources: Optional[str] = None,
        scope: Optional[str] = None,
        ref_answer: Optional[str] = None,
        history_eval: Optional[str] = None,
        question_index: Optional[int] = None
    ) -> LLMEvalResult:
        """
        带上下文的 RAG 综合评测

        Args:
            question: 问题文本
            actual_answer: 实际回答（API 返回的答案）
            rerank_sources: 召回的文档片段（可选）- rerank 后的资料
            scope: 评测范围（可选）- 如"仅关注参数完整性"
            ref_answer: 上一版回答（可选）- 用于对比改进
            history_eval: 历史评测记录（可选）- 用于对比改进
            question_index: 问题索引（可选）- 用于记录文件命名

        Returns:
            LLMEvalResult 对象，包含：
            - is_correct: 2级分类（是否正确）
            - category: 4级分类
            - analysis: 完整分析（包含参考资料、瞎编判断、改进分析）
            - missing_info: 缺失信息
            - important_info: 重要信息识别
        """
        if not self.config.enabled or not self.config.api_key:
            return LLMEvalResult(
                is_correct=False,
                category="completely_wrong",
                analysis="LLM 评测未启用或未配置 API Key",
                missing_info=None,
                important_info=None
            )

        # 构建增强版评测提示词（传递 rerank_sources）
        prompt = self._build_rag_eval_prompt(
            question=question,
            actual_answer=actual_answer,
            rerank_sources=rerank_sources,
            scope=scope,
            ref_answer=ref_answer,
            history_eval=history_eval
        )

        # 调用底层 LLM 评测（使用私有方法或扩展接口）
        return await self._call_llm_with_prompt(
            prompt,
            ref_answer,
            history_eval,
            question=question,
            context=rerank_sources,
            actual_answer=actual_answer,
            question_index=question_index
        )

    def _build_rag_eval_prompt(
        self,
        question: str,
        actual_answer: str,
        rerank_sources: Optional[str] = None,
        scope: Optional[str] = None,
        ref_answer: Optional[str] = None,
        history_eval: Optional[str] = None
    ) -> str:
        """
        构建 RAG 综合评测提示词

        提示词结构：
        1. 基础评测指令
        2. 召回文档片段（如果提供）
        3. 评测范围（如果提供）
        4. 历史回答和评测（如果提供）
        5. 评测标准
        6. 输出格式
        """
        # 基础部分
        prompt = f"""你是一个专业的 RAG 系统评测员。请基于【召回文档片段】评测【实际回答】的质量。

【问题】
{question}

【召回文档片段】（rerank 后的资料）
{rerank_sources or "（未提供召回文档片段）"}

【实际回答】
{actual_answer}
"""

        # 添加评测范围
        if scope:
            prompt += f"""
【评测范围】
{scope}

请在上述范围内进行评测，超出范围的内容可以忽略。
"""

        # 添加历史信息
        if ref_answer or history_eval:
            prompt += "\n【历史信息】\n"
            if ref_answer:
                prompt += f"上一版回答：\n{ref_answer}\n\n"
            if history_eval:
                prompt += f"历史评测记录：\n{history_eval}\n\n"
            prompt += "请对比当前回答与历史信息，评估改进情况。\n"

        # 添加评测标准和输出格式
        prompt += """
【评测原则】
1. **事实基础优先**：召回文档片段是唯一的事实依据，回答必须基于这些资料
2. **瞎编 vs 遗漏判断**：
   - 瞎编：回答中包含了召回资料中完全没有的信息（非通用知识）
   - 遗漏：召回资料中有相关信息，但回答未提及

【4级分类标准】
1. **完全正确** (fully_correct): 核心重要信息完整覆盖，可忽略非重要信息缺失
2. **部分缺失** (partial_missing): 缺少1-2个重要信息点
3. **大量缺失** (large_missing): 缺少多个重要信息点
4. **完全错误** (completely_wrong): 未回答、无关或完全错误

【输出格式】
分类：[fully_correct/partial_missing/large_missing/completely_wrong]
分析：[请包含以下方面的分析]
  - 是否基于召回文档片段？如果是，参考了哪些资料编号？
  - 是否存在瞎编内容？（基于召回片段判断，说明具体内容）
  - 如果有上一版答案，相比上一版有什么改进或退化？
  - 其他你认为重要的分析
{history_analysis}
缺失信息：[如果有遗漏，列出召回资料中缺失的具体重要内容]
重要信息识别：[说明哪些信息是重要的（由LLM智能判断）]
"""

        # 添加历史分析要求
        if ref_answer or history_eval:
            prompt = prompt.replace(
                "{history_analysis}",
                "\n改进对比：[说明与历史信息相比的改进情况，如有]"
            )
        else:
            prompt = prompt.replace("{history_analysis}", "")

        return prompt

    async def _call_llm_with_prompt(
        self,
        prompt: str,
        ref_answer: Optional[str],
        history_eval: Optional[str],
        # 新增参数（用于记录）
        question: Optional[str] = None,
        context: Optional[str] = None,
        actual_answer: Optional[str] = None,
        question_index: Optional[int] = None
    ) -> LLMEvalResult:
        """
        直接调用 LLM API 执行评测，绕过 LLMComparator.evaluate() 的 format 逻辑

        由于 RAG 评测的 prompt 已包含完整信息（问题、召回文档、实际回答），
        直接调用 API 可以避免 prompt 被 format() 方法替换为空字符串。

        Args:
            prompt: 完整的评测提示词
            ref_answer: 上一版回答（可选）
            history_eval: 历史评测记录（可选）
            question: 问题内容（用于记录）
            context: 召回文档片段（用于记录）
            actual_answer: 实际回答（用于记录）
            question_index: 问题索引（用于记录文件命名）

        Returns:
            LLMEvalResult 对象
        """
        if not self.config.api_key:
            return LLMEvalResult(
                is_correct=False,
                category="completely_wrong",
                analysis="LLM 评测未配置 API Key",
                missing_info=None,
                important_info=None
            )

        # 直接使用配置的完整 URL，不自动拼接
        url = self.config.base_url.rstrip('/')
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }
        data = {
            "model": self.config.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.config.temperature
        }

        # 记录原始响应（初始化为空）
        raw_response_json = ""

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=data,
                    timeout=self.config.timeout
                )
                response.raise_for_status()
                result = response.json()
                # 记录原始 JSON 响应
                raw_response_json = json.dumps(result, ensure_ascii=False)

            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"].strip()
                # 使用 LLMComparator 的静态方法解析响应
                parsed_result = LLMComparator._parse_llm_response(content)

                # 根据配置保存 prompt（调试用）
                if self.config.save_prompt:
                    parsed_result.prompt = prompt

                # 保存原始响应
                parsed_result.raw_response = raw_response_json

                # 记录到文件（如果启用且提供了问题索引）
                if self.recorder and question_index is not None:
                    await self.recorder.save_record(
                        question=question or "",
                        context=context,
                        actual_answer=actual_answer or "",
                        prompt=prompt,
                        raw_response=raw_response_json,
                        parsed_result=asdict(parsed_result),
                        question_index=question_index,
                        model=self.config.model,
                        category=parsed_result.category,
                        is_correct=parsed_result.is_correct
                    )

                # 添加改进分析标记（如果有历史信息）
                if ref_answer or history_eval:
                    if parsed_result.analysis and "改进对比" not in parsed_result.analysis:
                        parsed_result.analysis += "\n（改进对比：请参考历史信息手动评估）"

                return parsed_result
            else:
                # 异常响应也记录
                if self.recorder and question_index is not None:
                    await self.recorder.save_record(
                        question=question or "",
                        context=context,
                        actual_answer=actual_answer or "",
                        prompt=prompt,
                        raw_response=raw_response_json,
                        parsed_result={"error": "API 返回格式异常"},
                        question_index=question_index,
                        model=self.config.model,
                        category="completely_wrong",
                        is_correct=False
                    )

                return LLMEvalResult(
                    is_correct=False,
                    category="completely_wrong",
                    analysis=f"API 返回格式异常: {raw_response_json}",
                    missing_info=None,
                    important_info=None,
                    raw_response=raw_response_json
                )
        except Exception as e:
            logger.error(f"LLM 评测请求失败: {e}")

            # 异常情况也尝试记录
            if self.recorder and question_index is not None:
                await self.recorder.save_record(
                    question=question or "",
                    context=context,
                    actual_answer=actual_answer or "",
                    prompt=prompt,
                    raw_response=raw_response_json,
                    parsed_result={"error": str(e)},
                    question_index=question_index,
                    model=self.config.model,
                    category="completely_wrong",
                    is_correct=False
                )

            return LLMEvalResult(
                is_correct=False,
                category="completely_wrong",
                analysis=f"LLM 评测请求失败: {e}",
                missing_info=None,
                important_info=None,
                raw_response=raw_response_json
            )
