"""
RAG 综合评测单元测试

测试 SemanticJudge 的新增功能：
- rerank_sources 参数传递
- 提示词包含召回文档片段
- 引导性分析要求
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from obd.comparator.semantic_judge import SemanticJudge
from obd.models import LLMEvalConfig


class TestSemanticJudgeRAGEval:
    """测试 RAG 综合评测功能"""

    @pytest.fixture
    def config(self):
        """创建测试配置"""
        return LLMEvalConfig(
            enabled=True,
            api_key="test_key",
            base_url="https://api.test.com/v1",
            model="gpt-4"
        )

    @pytest.fixture
    def mock_llm_comparator(self):
        """Mock LLMComparator"""
        mock_comparator = Mock()
        mock_comparator.evaluate = AsyncMock()
        return mock_comparator

    @pytest.fixture
    def judge(self, config, mock_llm_comparator):
        """创建 SemanticJudge 实例"""
        # 替换内部的 llm_comparator
        judge = SemanticJudge.__new__(SemanticJudge)
        judge.config = config
        judge.llm_comparator = mock_llm_comparator
        return judge

    def test_build_prompt_with_rerank_sources(self, judge):
        """测试包含 rerank_sources 的提示词构建"""
        question = "什么是装饰器？"
        actual_answer = "装饰器是Python中的一个重要概念..."
        rerank_sources = """资料来源 [1]
装饰器是 Python 的一种高级功能...

资料来源 [2]
装饰器可以在不修改原函数的情况下增加功能..."""

        prompt = judge._build_rag_eval_prompt(
            question=question,
            actual_answer=actual_answer,
            rerank_sources=rerank_sources,
            scope=None,
            ref_answer=None,
            history_eval=None
        )

        # 验证提示词包含关键部分
        assert "召回文档片段" in prompt
        assert "资料来源 [1]" in prompt
        assert "资料来源 [2]" in prompt
        assert question in prompt
        assert actual_answer in prompt
        assert "事实基础优先" in prompt
        assert "瞎编 vs 遗漏判断" in prompt

        # 验证引导性分析要求
        assert "是否基于召回文档片段" in prompt
        assert "是否存在瞎编内容" in prompt
        assert "参考了哪些资料编号" in prompt

    def test_build_prompt_with_all_context(self, judge):
        """测试包含所有上下文的提示词构建"""
        question = "如何使用装饰器？"
        actual_answer = "装饰器可以用于..."
        rerank_sources = "资料[1]\n装饰器用法..."
        scope = "仅关注使用方法"
        ref_answer = "装饰器通过@符号使用"
        history_eval = "上一版缺少示例代码"

        prompt = judge._build_rag_eval_prompt(
            question=question,
            actual_answer=actual_answer,
            rerank_sources=rerank_sources,
            scope=scope,
            ref_answer=ref_answer,
            history_eval=history_eval
        )

        # 验证所有部分都包含
        assert "召回文档片段" in prompt
        assert "评测范围" in prompt
        assert "仅关注使用方法" in prompt
        assert "历史信息" in prompt
        assert "上一版回答" in prompt
        assert "历史评测记录" in prompt
        assert "改进对比" in prompt
        assert "相比上一版有什么改进或退化" in prompt

    def test_build_prompt_without_rerank_sources(self, judge):
        """测试没有 rerank_sources 时的提示词"""
        question = "测试问题"
        actual_answer = "测试答案"

        prompt = judge._build_rag_eval_prompt(
            question=question,
            actual_answer=actual_answer,
            rerank_sources=None,  # 未提供
            scope=None,
            ref_answer=None,
            history_eval=None
        )

        # 验证有默认提示
        assert "未提供召回文档片段" in prompt
        assert "召回文档片段" in prompt

    def test_build_prompt_with_ref_answer_only(self, judge):
        """测试只有上一版答案（无历史评测）"""
        prompt = judge._build_rag_eval_prompt(
            question="问题",
            actual_answer="答案",
            rerank_sources="资料[1]",
            scope=None,
            ref_answer="上一版答案",
            history_eval=None
        )

        # 应该有历史信息和改进对比
        assert "历史信息" in prompt
        assert "上一版回答" in prompt
        assert "改进对比" in prompt

    def test_build_prompt_with_history_eval_only(self, judge):
        """测试只有历史评测（无上一版答案）"""
        prompt = judge._build_rag_eval_prompt(
            question="问题",
            actual_answer="答案",
            rerank_sources="资料[1]",
            scope=None,
            ref_answer=None,
            history_eval="上一版评测记录"
        )

        # 应该有历史信息和改进对比
        assert "历史信息" in prompt
        assert "历史评测记录" in prompt
        assert "改进对比" in prompt

    @pytest.mark.asyncio
    async def test_evaluate_with_context_passes_rerank_sources(self, judge, mock_llm_comparator):
        """测试 evaluate_with_context 正确传递 rerank_sources"""
        # 准备测试数据
        question = "什么是装饰器？"
        actual_answer = "装饰器是..."
        rerank_sources = "资料[1]\n内容..."

        # Mock evaluate 方法的返回值
        from obd.comparator.llm_comparator import LLMEvalResult
        mock_result = LLMEvalResult(
            is_correct=True,
            category="fully_correct",
            analysis="测试分析",
            missing_info=None,
            important_info=None
        )
        mock_llm_comparator.evaluate.return_value = mock_result

        # Mock _call_llm_with_prompt 方法
        with patch.object(judge, '_call_llm_with_prompt', new=AsyncMock(return_value=mock_result)) as mock_call:
            await judge.evaluate_with_context(
                question=question,
                actual_answer=actual_answer,
                rerank_sources=rerank_sources,
                scope=None,
                ref_answer=None,
                history_eval=None
            )

            # 验证 _call_llm_with_prompt 被调用
            mock_call.assert_called_once()

            # 获取调用时的 prompt 参数
            call_args = mock_call.call_args
            prompt = call_args[0][0]  # 第一个位置参数是 prompt

            # 验证 prompt 包含 rerank_sources
            assert rerank_sources in prompt

    @pytest.mark.asyncio
    async def test_evaluate_with_context_disabled_config(self, judge):
        """测试配置未启用时的返回值"""
        judge.config.enabled = False

        result = await judge.evaluate_with_context(
            question="问题",
            actual_answer="答案",
            rerank_sources="资料[1]"
        )

        assert result.is_correct is False
        assert result.category == "completely_wrong"
        assert "未启用" in result.analysis

    def test_prompt_structure_completeness(self, judge):
        """测试提示词结构的完整性"""
        prompt = judge._build_rag_eval_prompt(
            question="问题",
            actual_answer="答案",
            rerank_sources="资料[1]",
            scope="范围",
            ref_answer="上一版",
            history_eval="历史评测"
        )

        # 验证所有关键部分存在
        required_sections = [
            "召回文档片段",
            "评测范围",
            "历史信息",
            "评测原则",
            "4级分类标准",
            "输出格式",
            "分析",
            "缺失信息",
            "重要信息识别"
        ]

        for section in required_sections:
            assert section in prompt, f"提示词缺少部分: {section}"

        # 验证引导性问题存在
        guidance_questions = [
            "是否基于召回文档片段",
            "参考了哪些资料编号",
            "是否存在瞎编内容",
            "相比上一版有什么改进或退化"
        ]

        for guidance in guidance_questions:
            assert guidance in prompt, f"提示词缺少引导: {guidance}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
