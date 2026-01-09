"""LLM 集成测试 - 简化版"""

import pytest
from obd.processor.batch_processor import WorkflowBatchProcessor
from obd.models import WorkflowConfig, RoutingConfig, LLMEvalConfig, QuestionAnswer, AnswerCategory


class TestLLMIntegration:
    """LLM 集成测试"""

    @pytest.fixture
    def workflow_config(self):
        """工作流配置"""
        return WorkflowConfig(api_key="test-key")

    @pytest.fixture
    def routing_config(self):
        """路由配置"""
        return RoutingConfig()

    def test_llm_evaluation_disabled(self, workflow_config, routing_config):
        """测试禁用 LLM 评测"""
        llm_disabled_config = LLMEvalConfig(enabled=False)

        processor = WorkflowBatchProcessor(
            config=workflow_config,
            routing_config=routing_config,
            llm_eval_config=llm_disabled_config
        )

        # 测试数据
        results = [
            QuestionAnswer(
                question="测试问题",
                expected_answer="正确答案包含A和B",
                model_output="实际回答包含了A和B"
            )
        ]

        # 设置默认值
        for qa in results:
            qa.llm_analysis = "LLM 评测未启用"
            qa.is_correct = False
            qa.match_type = "llm_disabled"

        # 测试统计
        stats = processor.calculate_statistics(results)
        assert stats["evaluated"] == 1
        assert stats["correct"] == 0

    def test_statistics_with_categories(self, workflow_config, routing_config):
        """测试4级分类统计"""
        processor = WorkflowBatchProcessor(
            config=workflow_config,
            routing_config=routing_config
        )

        results = [
            QuestionAnswer(question="Q1", expected_answer="A1", model_output="R1"),
            QuestionAnswer(question="Q2", expected_answer="A2", model_output="R2"),
            QuestionAnswer(question="Q3", expected_answer="A3", model_output="R3"),
        ]

        # 设置不同的4级分类
        results[0].llm_category = "fully_correct"
        results[1].llm_category = "partial_missing"
        results[2].llm_category = "completely_wrong"
        # 设置 is_correct （基于 4级分类）
        results[0].is_correct = True  # fully_correct
        results[1].is_correct = False  # partial_missing
        results[2].is_correct = False  # completely_wrong
        results[0].is_evaluated = True
        results[1].is_evaluated = True
        results[2].is_evaluated = True

        stats = processor.calculate_statistics(results)

        assert stats["total"] == 3
        assert stats["evaluated"] == 3
        assert stats["category_stats"]["fully_correct"] == 1
        assert stats["category_stats"]["partial_missing"] == 1
        assert stats["category_stats"]["completely_wrong"] == 1
        assert stats["category_details"]["fully_correct"]["count"] == 1
        assert stats["category_details"]["partial_missing"]["count"] == 1
        assert stats["category_details"]["completely_wrong"]["count"] == 1
        assert stats["accuracy"] == 1/3  # 只有 fully_correct 是正确的

    def test_judgment_mode_detailed(self, workflow_config, routing_config):
        """测试详细模式配置"""
        config = LLMEvalConfig(
            enabled=True,
            api_key="test-key",
            judgment_mode="detailed"
        )
        processor = WorkflowBatchProcessor(
            config=workflow_config,
            routing_config=routing_config,
            llm_eval_config=config
        )
        assert "完全正确" in processor.llm_comparator.prompt_template

    def test_judgment_mode_autonomous(self, workflow_config, routing_config):
        """测试自主模式配置"""
        config = LLMEvalConfig(
            enabled=True,
            api_key="test-key",
            judgment_mode="autonomous"
        )
        processor = WorkflowBatchProcessor(
            config=workflow_config,
            routing_config=routing_config,
            llm_eval_config=config
        )
        assert "智能识别" in processor.llm_comparator.prompt_template

    def test_temperature_configuration(self, workflow_config, routing_config):
        """测试温度配置"""
        config = LLMEvalConfig(
            enabled=True,
            api_key="test-key",
            temperature=0.8
        )
        processor = WorkflowBatchProcessor(
            config=workflow_config,
            routing_config=routing_config,
            llm_eval_config=config
        )
        assert processor.llm_comparator.config.temperature == 0.8

    def test_parse_llm_response_variations(self, workflow_config, routing_config):
        """测试各种 LLM 响应的解析"""
        llm_enabled_config = LLMEvalConfig(
            enabled=True,
            api_key="test-key"
        )
        processor = WorkflowBatchProcessor(
            config=workflow_config,
            routing_config=routing_config,
            llm_eval_config=llm_enabled_config
        )

        # 测试完全正确
        response1 = """
        分类：完全正确
        分析：回答完整包含了所有重要信息
        缺失信息：无
        重要信息识别：参数A、参数B
        """
        result1 = processor.llm_comparator._parse_llm_response(response1)
        assert result1.is_correct == True
        assert result1.category == "fully_correct"

        # 测试部分缺失
        response2 = """
        分类：部分缺失
        分析：包含了参数A，但缺少参数B
        缺失信息：参数B的值
        重要信息识别：参数A、参数B
        """
        result2 = processor.llm_comparator._parse_llm_response(response2)
        assert result2.is_correct == False
        assert result2.category == "partial_missing"
        assert "参数B" in result2.missing_info

        # 测试大量缺失
        response3 = """
        分类：大量缺失
        分析：信息很少，缺少多个重要参数
        缺失信息：参数B、参数C、完整流程
        重要信息识别：参数A、参数B、参数C、流程
        """
        result3 = processor.llm_comparator._parse_llm_response(response3)
        assert result3.is_correct == False
        assert result3.category == "large_missing"

        # 测试完全错误
        response4 = """
        分类：完全错误
        分析：完全未回答问题
        缺失信息：所有信息
        重要信息识别：无
        """
        result4 = processor.llm_comparator._parse_llm_response(response4)
        assert result4.is_correct == False
        assert result4.category == "completely_wrong"

    def test_answer_category_enum(self):
        """测试 AnswerCategory 枚举"""
        # 测试标签
        assert AnswerCategory.FULLY_CORRECT.label == "完全正确"
        assert AnswerCategory.PARTIAL_MISSING.label == "部分缺失"
        assert AnswerCategory.LARGE_MISSING.label == "大量缺失"
        assert AnswerCategory.COMPLETELY_WRONG.label == "完全错误"

        # 测试2级分类
        assert AnswerCategory.FULLY_CORRECT.is_correct_2level == True
        assert AnswerCategory.PARTIAL_MISSING.is_correct_2level == False
        assert AnswerCategory.LARGE_MISSING.is_correct_2level == False
        assert AnswerCategory.COMPLETELY_WRONG.is_correct_2level == False