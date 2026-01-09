"""LLM Comparator 单元测试"""

import pytest
from obd.comparator.llm_comparator import LLMComparator, LLMEvalResult
from obd.models import LLMEvalConfig, AnswerCategory


class TestLLMComparator:
    """LLM Comparator 单元测试"""

    @pytest.fixture
    def detailed_config(self):
        """详细模式配置"""
        return LLMEvalConfig(
            enabled=True,
            api_key="test-key",
            model="gpt-4o",
            judgment_mode="detailed",
            temperature=0.0
        )

    @pytest.fixture
    def autonomous_config(self):
        """自主模式配置"""
        return LLMEvalConfig(
            enabled=True,
            api_key="test-key",
            model="gpt-4o",
            judgment_mode="autonomous",
            temperature=0.0
        )

    def test_parse_llm_response_fully_correct(self):
        """测试解析完全正确的响应"""
        content = """
        分类：完全正确
        分析：回答包含了所有重要信息
        缺失信息：无
        重要信息识别：参数A、参数B、步骤C
        """

        result = LLMComparator._parse_llm_response(content)
        assert result.is_correct == True
        assert result.category == "fully_correct"
        assert "回答包含了所有重要信息" in result.analysis
        assert result.missing_info == "无"

    def test_parse_llm_response_partial_missing(self):
        """测试解析部分缺失的响应"""
        content = """
        分类：部分缺失
        分析：包含了参数A，但缺少参数B
        缺失信息：参数B的值
        重要信息识别：参数A、参数B
        """

        result = LLMComparator._parse_llm_response(content)
        assert result.is_correct == False
        assert result.category == "partial_missing"
        assert "参数B" in result.missing_info

    def test_parse_llm_response_largely_missing(self):
        """测试解析大量缺失的响应"""
        content = """
        分类：大量缺失
        分析：只包含了少量信息，缺少多个重要参数
        缺失信息：参数B、参数C、完整流程说明
        重要信息识别：参数A、参数B、参数C、流程
        """

        result = LLMComparator._parse_llm_response(content)
        assert result.is_correct == False
        assert result.category == "large_missing"
        assert "参数C" in result.missing_info

    def test_parse_llm_response_completely_wrong(self):
        """测试解析完全错误的响应"""
        content = """
        分类：完全错误
        分析：完全未回答问题
        缺失信息：所有信息
        重要信息识别：无
        """

        result = LLMComparator._parse_llm_response(content)
        assert result.is_correct == False
        assert result.category == "completely_wrong"

    def test_parse_llm_response_invalid_category(self):
        """测试解析无效分类的响应"""
        content = """
        分类：无效分类
        分析：无效的分类
        缺失信息：无
        """

        result = LLMComparator._parse_llm_response(content)
        assert result.category == "completely_wrong"  # 默认值

    def test_parse_llm_response_missing_fields(self):
        """测试解析缺少字段的响应"""
        content = "分析：只有分析内容"

        result = LLMComparator._parse_llm_response(content)
        assert result.category == "completely_wrong"  # 默认值
        assert result.analysis == "只有分析内容"
        assert result.missing_info is None

    def test_judgment_mode_selection(self, detailed_config, autonomous_config):
        """测试判断模式选择"""
        detailed_comp = LLMComparator(detailed_config)
        autonomous_comp = LLMComparator(autonomous_config)

        assert "完全正确" in detailed_comp.prompt_template
        assert "智能识别" in autonomous_comp.prompt_template

    def test_temperature_config(self):
        """测试温度配置"""
        config = LLMEvalConfig(
            enabled=True,
            api_key="test-key",
            model="gpt-4o",
            temperature=0.5
        )
        comparator = LLMComparator(config)
        assert comparator.config.temperature == 0.5

    def test_custom_prompt_template(self):
        """测试自定义提示词模板"""
        custom_prompt = "自定义提示词：{question}"
        config = LLMEvalConfig(
            enabled=True,
            api_key="test-key",
            model="gpt-4o",
            prompt_template=custom_prompt
        )
        comparator = LLMComparator(config)
        assert comparator.prompt_template == custom_prompt

    def test_answer_category_properties(self):
        """测试 AnswerCategory 属性"""
        assert AnswerCategory.FULLY_CORRECT.label == "完全正确"
        assert AnswerCategory.PARTIAL_MISSING.label == "部分缺失"
        assert AnswerCategory.LARGE_MISSING.label == "大量缺失"
        assert AnswerCategory.COMPLETELY_WRONG.label == "完全错误"

        assert AnswerCategory.FULLY_CORRECT.is_correct_2level == True
        assert AnswerCategory.PARTIAL_MISSING.is_correct_2level == False
        assert AnswerCategory.LARGE_MISSING.is_correct_2level == False
        assert AnswerCategory.COMPLETELY_WRONG.is_correct_2level == False

    def test_llm_eval_result_creation(self):
        """测试 LLMEvalResult 创建"""
        result = LLMEvalResult(
            is_correct=True,
            category="fully_correct",
            analysis="测试分析",
            missing_info="无缺失",
            important_info="重要信息"
        )
        assert result.is_correct == True
        assert result.category == "fully_correct"
        assert result.analysis == "测试分析"
        assert result.missing_info == "无缺失"
        assert result.important_info == "重要信息"

    def test_llm_eval_validation_config(self):
        """测试 LLM 配置验证"""
        # 测试无效的 judgment_mode
        with pytest.raises(ValueError):
            LLMEvalConfig(judgment_mode="invalid_mode")

        # 测试无效的 temperature
        with pytest.raises(ValueError):
            LLMEvalConfig(temperature=1.5)

        with pytest.raises(ValueError):
            LLMEvalConfig(temperature=-0.1)

        # 测试有效的配置
        config = LLMEvalConfig(judgment_mode="detailed", temperature=0.0)
        assert config.judgment_mode == "detailed"
        assert config.temperature == 0.0