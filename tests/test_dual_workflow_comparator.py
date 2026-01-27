"""Dual Workflow Comparator 单元测试（三方对比：LLM1 vs LLM2 vs History）"""

import pytest
from obd.comparator.dual_workflow_comparator import DualWorkflowComparator
from obd.models import LLMEvalConfig, DualWorkflowEvalResult


@pytest.fixture
def llm_eval_config():
    """LLM 评测配置"""
    return LLMEvalConfig(
        enabled=True,
        api_key="test-key",
        model="gpt-4o",
        judgment_mode="detailed",
        temperature=0.0
    )


class TestDualWorkflowComparator:
    """Dual Workflow Comparator 单元测试"""

    @pytest.fixture
    def comparator(self, llm_eval_config):
        """创建评测器实例"""
        return DualWorkflowComparator(llm_eval_config)

    def test_parse_comparison_response_llm1_wins(self, comparator):
        """测试解析 LLM1 获胜的响应"""
        content = """
推荐答案：llm1
置信度：high
总体分析：LLM1的回答更准确和完整，充分利用了召回片段
LLM1评价：信息准确、结构清晰，涵盖了所有关键点
LLM2评价：简洁但缺少关键参数X
历史回答评价：结构完整但部分内容过时
推荐理由：建议使用LLM1的回答，既准确又完整
        """

        result = comparator._parse_comparison_response(
            content, "LLM1", "LLM2", "历史回答"
        )
        assert result.winner == "llm1"
        assert result.confidence == "high"
        assert "更准确和完整" in result.overall_analysis
        assert "信息准确" in result.llm1_comment
        assert "缺少关键参数" in result.llm2_comment
        assert "部分内容过时" in result.history_comment

    def test_parse_comparison_response_llm2_wins(self, comparator):
        """测试解析 LLM2 获胜的响应"""
        content = """
推荐答案：llm2
置信度：medium
总体分析：LLM2的回答更实用，更符合召回片段的事实
LLM1评价：结构清晰但缺少实际操作步骤
LLM2评价：提供了完整的操作步骤，可操作性强
历史回答评价：描述过于笼统
推荐理由：建议使用LLM2的回答，更具可操作性
        """

        result = comparator._parse_comparison_response(
            content, "模型A", "模型B", "历史版本"
        )
        assert result.winner == "llm2"
        assert result.confidence == "medium"
        assert "更实用" in result.overall_analysis

    def test_parse_comparison_response_history_wins(self, comparator):
        """测试解析历史回答获胜的响应"""
        content = """
推荐答案：history
置信度：high
总体分析：历史回答质量最高，既准确又完整
LLM1评价：略显简略
LLM2评价：存在事实错误
历史回答评价：准确完整，完全符合召回片段
推荐理由：建议保持历史回答不变
        """

        result = comparator._parse_comparison_response(
            content, "LLM1", "LLM2", "历史版本"
        )
        assert result.winner == "history"
        assert result.confidence == "high"

    def test_parse_comparison_response_tie(self, comparator):
        """测试解析平局的响应"""
        content = """
推荐答案：tie
置信度：low
总体分析：三个回答质量相当
LLM1评价：信息准确
LLM2评价：信息详尽
历史回答评价：结构清晰
推荐理由：三个答案都可接受，根据具体需求选择
        """

        result = comparator._parse_comparison_response(
            content, "LLM1", "LLM2", "历史回答"
        )
        assert result.winner == "tie"
        assert result.confidence == "low"

    def test_parse_comparison_response_with_custom_labels(self, comparator):
        """测试解析使用自定义标签的响应"""
        content = """
推荐答案：llm1
置信度：high
总体分析：模型A表现最佳
模型A评价：准确完整
模型B评价：略显简略
旧版回答评价：部分过时
推荐理由：使用模型A的回答
        """

        result = comparator._parse_comparison_response(
            content, "模型A", "模型B", "旧版回答"
        )
        assert result.winner == "llm1"
        assert "准确完整" in result.llm1_comment
        assert "略显简略" in result.llm2_comment
        assert "部分过时" in result.history_comment

    def test_parse_comparison_response_fallback(self, comparator):
        """测试解析响应失败时的降级处理"""
        # 无法解析的响应
        content = "无法解析的响应内容"

        result = comparator._parse_comparison_response(
            content, "LLM1", "LLM2", "历史回答"
        )
        # 降级到默认值
        assert result.winner == "tie"  # 默认值
        assert result.confidence == "medium"  # 默认值

    def test_parse_comparison_response_missing_sections(self, comparator):
        """测试解析缺少某些节的响应"""
        content = """
推荐答案：llm1
置信度：high
总体分析：总体分析内容
        """

        result = comparator._parse_comparison_response(
            content, "LLM1", "LLM2", "历史回答"
        )
        assert result.winner == "llm1"
        assert result.confidence == "high"
        assert result.overall_analysis == "总体分析内容"
        # 缺失的节应该为空字符串
        assert result.llm1_comment == ""
        assert result.llm2_comment == ""
        assert result.history_comment == ""

    def test_build_comparison_prompt_without_history(self, comparator):
        """测试构建对比评测提示词（无历史回答）"""
        question = "什么是Python？"
        llm1_answer = "Python是一种编程语言"
        llm2_answer = "Python是Guido van Rossum创建的编程语言"
        rerank_sources = "Python是高级编程语言"
        label_1 = "模型A"
        label_2 = "模型B"
        label_history = "历史回答"

        prompt = comparator._build_comparison_prompt(
            question, llm1_answer, llm2_answer, None,
            rerank_sources, label_1, label_2, label_history
        )

        assert question in prompt
        assert llm1_answer in prompt
        assert llm2_answer in prompt
        assert rerank_sources in prompt
        assert label_1 in prompt
        assert label_2 in prompt
        assert "无历史回答" in prompt
        assert "推荐答案" in prompt
        assert "置信度" in prompt
        assert "总体分析" in prompt

    def test_build_comparison_prompt_with_history(self, comparator):
        """测试构建对比评测提示词（含历史回答）"""
        question = "什么是Python？"
        llm1_answer = "Python是一种编程语言"
        llm2_answer = "Python是Guido van Rossum创建的编程语言"
        history_answer = "Python是脚本语言"
        rerank_sources = "Python由Guido van Rossum于1991年创建"

        prompt = comparator._build_comparison_prompt(
            question, llm1_answer, llm2_answer, history_answer,
            rerank_sources, "LLM1", "LLM2", "历史版本"
        )

        assert history_answer in prompt
        assert "召回片段" in prompt
        assert "版本改进" in prompt

    def test_dual_workflow_eval_result_creation(self):
        """测试 DualWorkflowEvalResult 创建（新格式）"""
        result = DualWorkflowEvalResult(
            winner="llm1",
            confidence="high",
            overall_analysis="总体对比",
            llm1_comment="LLM1优缺点",
            llm2_comment="LLM2优缺点",
            history_comment="历史版本评价",
            recommendation="推荐LLM1"
        )

        assert result.winner == "llm1"
        assert result.confidence == "high"
        assert result.overall_analysis == "总体对比"
        assert result.llm1_comment == "LLM1优缺点"
        assert result.llm2_comment == "LLM2优缺点"
        assert result.history_comment == "历史版本评价"
        assert result.recommendation == "推荐LLM1"

    def test_dual_workflow_comparator_initialization(self, llm_eval_config):
        """测试评测器初始化"""
        comparator = DualWorkflowComparator(llm_eval_config)
        assert comparator.config == llm_eval_config
        assert comparator.recorder is None
        assert comparator.prompt_template is not None

    def test_dual_workflow_comparator_with_recorder(self, llm_eval_config):
        """测试带记录器的评测器初始化"""
        # 使用 mock recorder
        class MockRecorder:
            pass

        recorder = MockRecorder()
        comparator = DualWorkflowComparator(llm_eval_config, recorder=recorder)

        assert comparator.recorder is recorder


class TestDualWorkflowIntegration:
    """双工作流对比评测集成测试"""

    def test_comparison_prompt_template_completeness(self):
        """测试提示词模板的完整性"""
        from obd.comparator.dual_workflow_comparator import COMPARISON_PROMPT_TEMPLATE

        # 检查模板包含必要的占位符
        assert "{question}" in COMPARISON_PROMPT_TEMPLATE
        assert "{llm1_answer}" in COMPARISON_PROMPT_TEMPLATE
        assert "{llm2_answer}" in COMPARISON_PROMPT_TEMPLATE
        assert "{history_answer}" in COMPARISON_PROMPT_TEMPLATE
        assert "{rerank_sources}" in COMPARISON_PROMPT_TEMPLATE
        assert "{label1}" in COMPARISON_PROMPT_TEMPLATE
        assert "{label2}" in COMPARISON_PROMPT_TEMPLATE
        assert "{label_history}" in COMPARISON_PROMPT_TEMPLATE

        # 检查模板包含必要的输出格式说明
        assert "推荐答案" in COMPARISON_PROMPT_TEMPLATE
        assert "置信度" in COMPARISON_PROMPT_TEMPLATE
        assert "总体分析" in COMPARISON_PROMPT_TEMPLATE
        assert "评价" in COMPARISON_PROMPT_TEMPLATE
        assert "推荐理由" in COMPARISON_PROMPT_TEMPLATE

        # 检查评测标准
        assert "召回质量" in COMPARISON_PROMPT_TEMPLATE
        assert "准确性" in COMPARISON_PROMPT_TEMPLATE
        assert "完整性" in COMPARISON_PROMPT_TEMPLATE
        assert "版本改进" in COMPARISON_PROMPT_TEMPLATE

    def test_parse_response_with_markdown_format(self, llm_eval_config):
        """测试解析 Markdown 格式的响应"""
        content = """
**推荐答案**：llm1
**置信度**：high

**总体分析**：LLM1更优

**LLM1评价**：准确、完整

**LLM2评价**：简洁

**历史回答评价**：部分过时

**推荐理由**：使用LLM1
        """

        comparator = DualWorkflowComparator(llm_eval_config)
        result = comparator._parse_comparison_response(
            content, "LLM1", "LLM2", "历史回答"
        )
        # 应该能够解析（正则兼容 Markdown）
        assert result.winner == "llm1"

    def test_parse_response_with_chinese_winner(self, comparator):
        """测试解析中文 winner 值"""
        content = """
推荐答案：LLM1
置信度：high
总体分析：LLM1表现最佳
LLM1评价：优秀
LLM2评价：一般
历史回答评价：可接受
推荐理由：选择LLM1
        """

        result = comparator._parse_comparison_response(
            content, "LLM1", "LLM2", "历史回答"
        )
        # 应该映射中文到英文
        assert result.winner == "llm1"
