"""双工作流对比评测器"""

import httpx
import json
import logging
import re
from typing import Optional, TYPE_CHECKING
from obd.models import DualWorkflowEvalResult, LLMEvalConfig

if TYPE_CHECKING:
    from obd.recorder import EvalRecorder

logger = logging.getLogger(__name__)


# 双工作流对比评测提示词模板（三方对比：LLM1 vs LLM2 vs History）
COMPARISON_PROMPT_TEMPLATE = """你是一个专业的答案质量评测员。请对比三个答案的质量。

【问题】
{question}

【召回片段】（作为事实依据）
{rerank_sources}

【{label1} 回答】
{llm1_answer}

【{label2} 回答】
{llm2_answer}

【{label_history} 回答】（历史版本，用于对比）
{history_answer}

【评测标准】
1. 召回质量：是否充分利用了召回片段
2. 准确性：是否符合召回片段的事实
3. 完整性：是否回答了问题的所有方面
4. 版本改进：相比历史版本是否有改进

【输出格式】
推荐答案：[llm1 / llm2 / history / tie]
置信度：[high / medium / low]
总体分析：[综合三个答案的质量对比]
{label1}评价：[简述优缺点]
{label2}评价：[简述优缺点]
{label_history}评价：[简述优缺点]
推荐理由：[具体理由]

注意:
- llm1 代表 {label1}
- llm2 代表 {label2}
- history 代表 {label_history}
- tie 表示三个答案质量相当
"""


class DualWorkflowComparator:
    """双工作流对比评测器"""

    def __init__(
        self,
        config: LLMEvalConfig,
        recorder: Optional["EvalRecorder"] = None
    ):
        """
        初始化对比评测器

        Args:
            config: LLM 评测配置
            recorder: 可选的评测记录器
        """
        self.config = config
        self.recorder = recorder
        self.prompt_template = COMPARISON_PROMPT_TEMPLATE
        
        # 日志记录评测记录器状态
        if recorder:
            session_dir = getattr(recorder, 'get_session_dir', lambda: 'N/A')()
            logger.info(f"[双工作流评测器] 评测记录器已启用，会话目录: {session_dir}")
        else:
            logger.debug(f"[双工作流评测器] 评测记录器未启用")

    async def compare_answers(
        self,
        question: str,
        llm1_answer: str,
        llm2_answer: str,
        history_answer: Optional[str] = None,
        rerank_sources: Optional[str] = None,
        label_1: str = "LLM1",
        label_2: str = "LLM2",
        label_history: str = "历史回答",
        question_index: Optional[int] = None
    ) -> DualWorkflowEvalResult:
        """对比三个答案的质量（LLM1 vs LLM2 vs History）

        Args:
            question: 原始问题
            llm1_answer: LLM1 的回答
            llm2_answer: LLM2 的回答
            history_answer: 历史回答（可选）
            rerank_sources: 召回片段（可选）
            label_1: LLM1 的标签
            label_2: LLM2 的标签
            label_history: 历史回答的标签
            question_index: 问题索引（用于记录）

        Returns:
            DualWorkflowEvalResult: 对比评测结果
        """
        try:
            # 构建提示词
            prompt = self._build_comparison_prompt(
                question, llm1_answer, llm2_answer, history_answer,
                rerank_sources, label_1, label_2, label_history
            )

            # 调用 LLM API
            content = await self._call_llm_api(prompt)

            if not content:
                error_msg = "API 返回内容为空"
                logger.error(error_msg)
                return DualWorkflowEvalResult(
                    winner="tie",
                    confidence="low",
                    overall_analysis=error_msg,
                    llm1_comment="",
                    llm2_comment="",
                    history_comment="",
                    recommendation="",
                    raw_response=""
                )

            # 解析响应（传递动态标签以正确解析）
            result = self._parse_comparison_response(
                content,
                label_1,
                label_2,
                label_history,
                prompt if self.config.save_prompt else None
            )

            # 记录评测（使用 save_record 方法）
            if self.recorder and question_index is not None:
                logger.info(f"[评测记录] 开始保存双工作流对比评测记录，问题索引: {question_index}")
                parsed_result = {
                    "winner": result.winner,
                    "confidence": result.confidence,
                    "overall_analysis": result.overall_analysis,
                    "llm1_comment": result.llm1_comment,
                    "llm2_comment": result.llm2_comment,
                    "history_comment": result.history_comment,
                    "recommendation": result.recommendation,
                    "label_1": label_1,
                    "label_2": label_2,
                    "label_history": label_history,
                    # 拆分答案字段，便于日志查看
                    "llm1_answer": llm1_answer,
                    "llm2_answer": llm2_answer,
                    "history_answer": history_answer or "",
                }

                record_path = await self.recorder.save_record(
                    question=question,
                    context=rerank_sources or "",  # 使用召回片段作为 context
                    actual_answer="",  # 答案已拆分到 parsed_result 中
                    prompt=prompt if self.config.save_prompt else "",
                    raw_response=content,
                    parsed_result=parsed_result,
                    question_index=question_index,
                    model=self.config.model,
                    category=None,  # 双工作流对比没有4级分类
                    is_correct=None  # 双工作流对比没有2级分类
                )
                if record_path:
                    logger.info(f"[评测记录] 评测记录已保存到: {record_path}")
                else:
                    logger.warning(f"[评测记录] 评测记录保存失败，recorder.enabled={self.recorder.enabled}")
            elif self.recorder is None:
                logger.debug(f"[评测记录] recorder 为 None，未保存评测记录")
            elif question_index is None:
                logger.debug(f"[评测记录] question_index 为 None，未保存评测记录")

            return result

        except Exception as e:
            error_msg = f"双工作流对比评测请求失败: {str(e)}"
            logger.error(error_msg)
            return DualWorkflowEvalResult(
                winner="tie",
                confidence="low",
                overall_analysis=error_msg,
                llm1_comment="",
                llm2_comment="",
                history_comment="",
                recommendation="",
                raw_response=str(e)
            )

    async def _call_llm_api(self, prompt: str) -> str:
        """
        调用 LLM API 进行评测
        
        支持 standard 和 custom_azure 两种 API 格式
        
        Args:
            prompt: 完整的提示词
            
        Returns:
            LLM 返回的文本内容
        """
        if not self.config.enabled or not self.config.api_key:
            logger.warning("LLM 评测未启用或未配置 API Key")
            return ""
        
        url = self.config.base_url.rstrip('/')
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }
        
        # 根据配置的 api_type 构建请求数据
        if self.config.api_type == "custom_azure":
            # Azure 特殊格式：使用 input 而不是 messages
            data = {
                "model": self.config.model,
                "input": [{"role": "user", "content": prompt}],
                "temperature": self.config.temperature
            }
        else:
            # 标准 OpenAI 格式
            data = {
                "model": self.config.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.config.temperature
            }
        
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
            
            # 根据配置的 api_type 提取内容
            content = None
            
            if self.config.api_type == "custom_azure":
                # Azure 格式：从 output 中提取
                if "output" in result and len(result["output"]) > 0:
                    output_content = result["output"][0].get("content", [])
                    if output_content and isinstance(output_content, list):
                        content = output_content[0].get("text", "").strip()
            else:
                # 标准 OpenAI 格式：从 choices 中提取
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"].strip()
            
            # 容错降级：如果指定格式未解析到，尝试另一种格式
            if not content:
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"].strip()
                elif "output" in result and len(result["output"]) > 0:
                    output_content = result["output"][0].get("content", [])
                    if output_content and isinstance(output_content, list):
                        content = output_content[0].get("text", "").strip()
            
            if not content:
                logger.error(f"API 返回格式异常: {json.dumps(result, ensure_ascii=False)}")
                return ""
            
            logger.debug(f"LLM API 响应: {content[:200]}...")
            return content
            
        except Exception as e:
            logger.error(f"LLM API 请求失败: {str(e)}")
            return ""

    def _build_comparison_prompt(
        self,
        question: str,
        llm1_answer: str,
        llm2_answer: str,
        history_answer: Optional[str],
        rerank_sources: Optional[str],
        label_1: str,
        label_2: str,
        label_history: str
    ) -> str:
        """
        构建对比评测提示词（三方对比）

        Args:
            question: 问题
            llm1_answer: LLM1 的回答
            llm2_answer: LLM2 的回答
            history_answer: 历史回答（可选）
            rerank_sources: 召回片段（可选）
            label_1: LLM1 的标签
            label_2: LLM2 的标签
            label_history: 历史回答的标签

        Returns:
            完整的提示词
        """
        return self.prompt_template.format(
            question=question,
            rerank_sources=rerank_sources or "（无召回片段）",
            llm1_answer=llm1_answer,
            llm2_answer=llm2_answer,
            history_answer=history_answer or "（无历史回答）",
            label1=label_1,
            label2=label_2,
            label_history=label_history
        )

    def _parse_comparison_response(
        self,
        content: str,
        label_1: str,
        label_2: str,
        label_history: str,
        prompt: Optional[str] = None
    ) -> DualWorkflowEvalResult:
        """
        解析 LLM 返回的三方对比评测响应

        支持动态标签（如 LLM1, LLM2, 历史回答 或其他自定义标签）

        新格式：
        - 推荐答案：[llm1 / llm2 / history / tie]
        - 置信度：[high / medium / low]
        - 总体分析：[综合分析]
        - {label1}评价：[优缺点合一]
        - {label2}评价：[优缺点合一]
        - {label_history}评价：[优缺点合一]
        - 推荐理由：[具体理由]

        Args:
            content: LLM 返回的完整文本
            label_1: LLM1 的标签（用于构建解析模式）
            label_2: LLM2 的标签（用于构建解析模式）
            label_history: 历史回答的标签
            prompt: 可选的原始提示词（用于调试）

        Returns:
            DualWorkflowEvalResult 对象
        """
        logger.debug(f"对比评测原始响应: {content[:500]}...")
        logger.debug(f"解析标签: label_1={label_1}, label_2={label_2}, label_history={label_history}")

        # 转义标签中的特殊字符（用于正则）
        label_1_escaped = re.escape(label_1)
        label_2_escaped = re.escape(label_2)
        label_history_escaped = re.escape(label_history)

        # 提取函数
        def extract_with_pattern(pattern: str, text: str, group: int = 1) -> Optional[str]:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                result = match.group(group).strip()
                # 清理末尾的空白和多余换行
                result = re.sub(r'\n+$', '', result).strip()
                return result
            return None

        # 1. 提取推荐答案 (llm1 / llm2 / history / tie)
        winner = "tie"
        winner_patterns = [
            r"\*{0,2}推荐答案\*{0,2}[：:]\s*(llm1|llm2|history|tie)",
            # 降级：支持中文
            r"\*{0,2}推荐答案\*{0,2}[：:]\s*(LLM1|LLM2|历史回答|平局)",
        ]
        for pattern in winner_patterns:
            winner_match = re.search(pattern, content, re.IGNORECASE)
            if winner_match:
                winner_raw = winner_match.group(1).lower()
                # 映射中文到英文
                winner_map = {"llm1": "llm1", "llm2": "llm2", "history": "history", "tie": "tie"}
                winner = winner_map.get(winner_raw, "tie")
                break

        # 2. 提取置信度
        confidence = "medium"
        confidence_match = re.search(r"\*{0,2}置信度\*{0,2}[：:]\s*(high|medium|low)", content, re.IGNORECASE)
        if confidence_match:
            confidence = confidence_match.group(1).lower()

        # 3. 提取总体分析
        overall_analysis = extract_with_pattern(
            rf"\*{{0,2}}总体分析\*{{0,2}}[：:]\s*([\s\S]+?)(?=\s*\*{{0,2}}(?:{label_1_escaped}|{label_2_escaped}|{label_history_escaped})评价\*{{0,2}}[：:]|$)",
            content
        ) or ""

        # 4. 提取各评价（动态标签支持）
        llm1_comment = extract_with_pattern(
            rf"\*{{0,2}}{label_1_escaped}评价\*{{0,2}}[：:]\s*([\s\S]+?)(?=\s*\*{{0,2}}(?:{label_2_escaped}|{label_history_escaped}|推荐理由)评价\*{{0,2}}[：:]|$)",
            content
        ) or ""

        llm2_comment = extract_with_pattern(
            rf"\*{{0,2}}{label_2_escaped}评价\*{{0,2}}[：:]\s*([\s\S]+?)(?=\s*\*{{0,2}}(?:{label_history_escaped}|推荐理由)评价\*{{0,2}}[：:]|$)",
            content
        ) or ""

        history_comment = extract_with_pattern(
            rf"\*{{0,2}}{label_history_escaped}评价\*{{0,2}}[：:]\s*([\s\S]+?)(?=\s*\*{{0,2}}推荐理由\*{{0,2}}[：:]|$)",
            content
        ) or ""

        # 5. 提取推荐理由
        recommendation = extract_with_pattern(
            rf"\*{{0,2}}推荐理由\*{{0,2}}[：:]\s*([\s\S]+?)(?=$)",
            content
        ) or ""

        # 日志记录解析结果
        logger.debug(f"解析结果: winner={winner}, confidence={confidence}, "
                    f"llm1_comment={'有' if llm1_comment else '无'}, "
                    f"llm2_comment={'有' if llm2_comment else '无'}, "
                    f"history_comment={'有' if history_comment else '无'}")

        return DualWorkflowEvalResult(
            winner=winner,
            confidence=confidence,
            overall_analysis=overall_analysis,
            llm1_comment=llm1_comment,
            llm2_comment=llm2_comment,
            history_comment=history_comment,
            recommendation=recommendation,
            prompt=prompt,
            raw_response=content
        )
