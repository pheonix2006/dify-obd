"""双模型响应解析工具"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DualModelResponseParser:
    """双模型输出解析器

    解析 Dify 工作流返回的结构化输出，格式为：
    ```
    问题：{{#sys.query#}}
    rerank后的片段：{{#...formatted_result#}}
    经过llm1的结果：{{#...text#}}
    经过llm2的结果：{{#...text#}}
    ```
    """

    # 标准分隔符（需与 Dify 工作流输出格式一致）
    QUESTION_MARKER = "问题："
    RERANK_MARKER = "rerank后的片段："
    LLM1_MARKER = "经过llm1的结果："
    LLM2_MARKER = "经过llm2的结果："

    # 分隔符变体（容错处理）
    QUESTION_MARKERS = ["问题：", "问题:", "Question:"]
    RERANK_MARKERS = ["rerank后的片段：", "rerank后的片段:", "召回片段：", "召回片段:"]
    LLM1_MARKERS = ["经过llm1的结果：", "经过llm1的结果:", "LLM1结果：", "LLM1回答：", "llm1的结果："]
    LLM2_MARKERS = ["经过llm2的结果：", "经过llm2的结果:", "LLM2结果：", "LLM2回答：", "llm2的结果："]

    @classmethod
    def parse(cls, response: str) -> "DualModelResponseParts":
        """
        解析工作流响应

        Args:
            response: Dify 工作流返回的原始响应

        Returns:
            DualModelResponseParts: 解析后的各部分内容
        """
        from obd.models import DualModelResponseParts

        if not response:
            return cls._fallback(response)

        try:
            return cls._do_parse(response)
        except Exception:
            return cls._fallback(response)

    @classmethod
    def _do_parse(cls, response: str) -> "DualModelResponseParts":
        """执行解析：按分隔符位置分段"""
        from obd.models import DualModelResponseParts

        # 调试日志：记录原始响应
        logger.debug(f"[双工作流解析器] 原始响应长度: {len(response)}")

        # 尝试标准分隔符
        question_idx = response.find(cls.QUESTION_MARKER)
        rerank_idx = response.find(cls.RERANK_MARKER)
        llm1_idx = response.find(cls.LLM1_MARKER)
        llm2_idx = response.find(cls.LLM2_MARKER)

        # 调试日志：记录分隔符位置
        logger.debug(
            f"[双工作流解析器] 标准分隔符位置: "
            f"question={question_idx}, rerank={rerank_idx}, llm1={llm1_idx}, llm2={llm2_idx}"
        )

        # 如果标准分隔符不完整，尝试变体
        if not all(idx >= 0 for idx in [question_idx, rerank_idx, llm1_idx, llm2_idx]):
            logger.debug("[双工作流解析器] 标准分隔符不完整，尝试变体...")
            question_idx, rerank_idx, llm1_idx, llm2_idx = cls._try_variant_markers(response)
            logger.debug(
                f"[双工作流解析器] 变体分隔符位置: "
                f"question={question_idx}, rerank={rerank_idx}, llm1={llm1_idx}, llm2={llm2_idx}"
            )

        # 完整格式：四个分隔符都存在，且顺序正确
        if all(idx >= 0 for idx in [question_idx, rerank_idx, llm1_idx, llm2_idx]):
            # 验证顺序：问题 → rerank → llm1 → llm2
            if question_idx < rerank_idx < llm1_idx < llm2_idx:
                # 提取各部分内容（在标记之后，下一个标记之前）
                question_start = question_idx + len(cls.QUESTION_MARKER)
                question = response[question_start:rerank_idx].strip()

                rerank_start = rerank_idx + len(cls.RERANK_MARKER)
                rerank = response[rerank_start:llm1_idx].strip()

                llm1_start = llm1_idx + len(cls.LLM1_MARKER)
                llm1 = response[llm1_start:llm2_idx].strip()

                llm2_start = llm2_idx + len(cls.LLM2_MARKER)
                llm2 = response[llm2_start:].strip()

                # 调试日志：记录解析结果摘要
                logger.debug(
                    f"[双工作流解析器] 解析成功 - "
                    f"问题长度={len(question)}, 召回长度={len(rerank)}, "
                    f"LLM1长度={len(llm1)}, LLM2长度={len(llm2)}"
                )

                return DualModelResponseParts(
                    question=question,
                    rerank_sources=rerank,
                    llm1_output=llm1,
                    llm2_output=llm2,
                    is_valid_format=True
                )

        # 尝试部分格式解析（只有 llm1 和 llm2）
        llm1_search = response.find(cls.LLM1_MARKER)
        llm2_search = response.find(cls.LLM2_MARKER)
        if llm1_search >= 0 and llm2_search >= 0 and llm1_search < llm2_search:
            logger.debug("[双工作流解析器] 部分格式解析：只有 LLM1 和 LLM2")
            llm1_start = llm1_search + len(cls.LLM1_MARKER)
            llm1 = response[llm1_start:llm2_search].strip()
            llm2_start = llm2_search + len(cls.LLM2_MARKER)
            llm2 = response[llm2_start:].strip()

            return DualModelResponseParts(
                question="",
                rerank_sources="",
                llm1_output=llm1,
                llm2_output=llm2,
                is_valid_format=False  # 部分格式
            )

        # Fallback
        logger.warning("[双工作流解析器] 解析失败，使用 fallback")
        return cls._fallback(response)

    @classmethod
    def _try_variant_markers(cls, response: str) -> tuple:
        """尝试使用变体分隔符找到各个部分

        Args:
            response: 原始响应文本

        Returns:
            (question_idx, rerank_idx, llm1_idx, llm2_idx) 各部分分隔符位置
        """
        question_idx = -1
        rerank_idx = -1
        llm1_idx = -1
        llm2_idx = -1

        # 找到第一个问题标记
        for marker in cls.QUESTION_MARKERS:
            idx = response.find(marker)
            if idx >= 0 and (question_idx == -1 or idx < question_idx):
                question_idx = idx

        # 找到第一个召回标记（在问题之后）
        for marker in cls.RERANK_MARKERS:
            idx = response.find(marker)
            if idx >= 0 and idx > question_idx and (rerank_idx == -1 or idx < rerank_idx):
                rerank_idx = idx

        # 找到第一个 LLM1 标记（在召回之后）
        for marker in cls.LLM1_MARKERS:
            idx = response.find(marker)
            if idx >= 0 and idx > rerank_idx and (llm1_idx == -1 or idx < llm1_idx):
                llm1_idx = idx

        # 找到第一个 LLM2 标记（在 LLM1 之后）
        for marker in cls.LLM2_MARKERS:
            idx = response.find(marker)
            if idx >= 0 and idx > llm1_idx and (llm2_idx == -1 or idx < llm2_idx):
                llm2_idx = idx

        return question_idx, rerank_idx, llm1_idx, llm2_idx

    @classmethod
    def _fallback(cls, response: str) -> "DualModelResponseParts":
        """解析失败时的 fallback

        将整个响应作为 llm1_output 返回
        """
        from obd.models import DualModelResponseParts

        return DualModelResponseParts(
            question="",
            rerank_sources="",
            llm1_output=response if response else "",
            llm2_output="",
            is_valid_format=False
        )
