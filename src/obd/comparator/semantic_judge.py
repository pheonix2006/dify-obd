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
        5. 评测决策框架
        6. 输出格式
        """
        # 基础部分
        prompt = f"""你是一个专业的 RAG 系统评测员。请基于【召回文档片段】对【实际回答】进行多维度评测。

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

        # 添加评测决策框架和输出格式
        prompt += """
---
【评测决策框架】

请按照以下逻辑进行评测：

**第一步：召回质量评估**
1. 问题可回答性：召回片段是否包含足够的信息来回答问题？
2. 召回相关性：召回片段与问题的相关程度如何？
3. 如果召回不足或质量差，请在分析中明确标注"【召回问题】"

**第二步：基于性判断**
1. 回答是否基于召回片段？引用了哪些条目？
2. 是否存在非基于召回的内容？
   - 区分通用常识（可接受）和领域专业知识（算作瞎编）
3. 如果存在瞎编，请在分析中明确标注"【瞎编】"

**第三步：准确性判断（如果基于召回）**
1. 引用的条目是否正确对应到回答内容？
2. 是否出现"召回了正确条目但被其他条目误导"的情况？
3. 如果出现误导，请在分析中明确标注"【误导】"

**第四步：完整性判断**
1. 基于召回片段，回答是否完整？
2. 缺失了哪些重要信息？

**第五步：版本对比（如果有上一版回答）**
1. 当前回答相比上一版有哪些改进？
   - 信息完整性提升、准确性提升、表达更清晰等
2. 当前回答相比上一版有哪些退化？
   - 信息遗漏、错误增加、瞎编内容等
3. 如果有改进或退化，请在分析中明确标注"【改进】"或"【退化】"

【4级分类标准】
1. **fully_correct**: 基于召回，回答完整准确，无瞎编
2. **partial_missing**: 基于召回，有少量信息缺失或轻微偏差
3. **large_missing**: 基于召回，有大量信息缺失或显著偏差
4. **completely_wrong**: 未回答、完全瞎编、或完全错误

注意：如果召回本身不足，请在分析中指出这是"召回质量问题"而非"答案生成问题"。

【输出格式】
分类：[4级分类]
召回质量评估：[问题是否可由召回片段回答 | 召回相关性 | 如有不足说明原因]
基于性分析：[是否基于召回片段 | 引用了哪些条目 | 是否存在非基于召回内容（区分常识/瞎编）]
准确性分析：[引用是否正确 | 是否存在误导情况]
完整性分析：[信息缺失情况]
版本对比分析：[如有上一版回答，说明改进或退化情况]
总体判断：[综合以上分析，给出最终分类的理由]
"""

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
