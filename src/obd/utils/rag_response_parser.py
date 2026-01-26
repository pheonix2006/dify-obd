"""RAG响应解析工具"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RAGResponseParts:
    """RAG响应解析结果"""
    question: str  # 提取的问题
    rerank_sources: str  # rerank片段（合并）
    llm_answer: str  # LLM生成的答案
    is_valid_format: bool  # 是否成功解析


class RAGResponseParser:
    """RAG响应解析器"""

    # 分隔符模式
    QUESTION_MARKER = "rerank后的片段是："
    LLM_MARKER = "经过llm的结果："

    @classmethod
    def parse(cls, answer: str) -> RAGResponseParts:
        """
        解析RAG响应格式

        输入示例：
        ```
        装饰符
        rerank后的片段是：
        资料来源 [1]
        装饰器（decorator）是...
        ...
        经过llm的结果：
        装饰符（decorator）是 Python 中...
        ```

        返回：
        - question: "装饰符"
        - rerank_sources: "资料来源 [1]\\n装饰器（decorator）是..."
        - llm_answer: "装饰符（decorator）是 Python 中..."
        """
        if not answer:
            return cls._fallback(answer)

        # 尝试解析
        try:
            return cls._do_parse(answer)
        except Exception:
            # 解析失败，返回fallback
            return cls._fallback(answer)

    @classmethod
    def _do_parse(cls, answer: str) -> RAGResponseParts:
        """执行解析逻辑"""
        # 查找分隔符位置
        question_idx = answer.find(cls.QUESTION_MARKER)
        llm_idx = answer.find(cls.LLM_MARKER)

        # 情况1：完整格式（两个分隔符都存在）
        if question_idx >= 0 and llm_idx > question_idx:
            question = answer[:question_idx].strip()
            rerank_start = question_idx + len(cls.QUESTION_MARKER)
            rerank = answer[rerank_start:llm_idx].strip()
            llm = answer[llm_idx + len(cls.LLM_MARKER):].strip()

            return RAGResponseParts(
                question=question,
                rerank_sources=rerank,
                llm_answer=llm,
                is_valid_format=True
            )

        # 情况2：只有问题分隔符
        if question_idx >= 0:
            question = answer[:question_idx].strip()
            rerank = answer[question_idx + len(cls.QUESTION_MARKER):].strip()

            return RAGResponseParts(
                question=question,
                rerank_sources=rerank,
                llm_answer="",  # 没有LLM答案
                is_valid_format=True
            )

        # 情况3：只有LLM分隔符
        if llm_idx >= 0:
            question = ""  # 没有明确的问题
            rerank = answer[:llm_idx].strip()
            llm = answer[llm_idx + len(cls.LLM_MARKER):].strip()

            return RAGResponseParts(
                question=question,
                rerank_sources=rerank,
                llm_answer=llm,
                is_valid_format=True
            )

        # 情况4：都没有，当作纯LLM答案
        return RAGResponseParts(
            question="",
            rerank_sources="",
            llm_answer=answer.strip(),
            is_valid_format=False
        )

    @classmethod
    def _fallback(cls, answer: str) -> RAGResponseParts:
        """解析失败时的fallback"""
        return RAGResponseParts(
            question="",
            rerank_sources="",
            llm_answer=answer if answer else "",
            is_valid_format=False
        )
