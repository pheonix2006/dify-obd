"""测试数据模型"""

import pytest
from obd.models import WorkflowConfig, QuestionAnswer


class TestWorkflowConfig:
    """测试WorkflowConfig类"""

    def test_workflow_config_defaults(self):
        """测试默认配置"""
        config = WorkflowConfig(api_key="test_key")

        assert config.api_key == "test_key"
        assert config.base_url == "https://api.dify.ai/v1"
        assert config.response_mode == "blocking"
        assert config.timeout == 60
        assert config.user == "batch_processor"

    def test_workflow_config_custom(self):
        """测试自定义配置"""
        config = WorkflowConfig(
            api_key="custom_key",
            base_url="https://custom.dify.ai/v1",
            response_mode="streaming",
            timeout=120,
            user="custom_user"
        )

        assert config.api_key == "custom_key"
        assert config.base_url == "https://custom.dify.ai/v1"
        assert config.response_mode == "streaming"
        assert config.timeout == 120
        assert config.user == "custom_user"


class TestQuestionAnswer:
    """测试QuestionAnswer类"""

    def test_question_answer_basic(self):
        """测试基本QuestionAnswer"""
        qa = QuestionAnswer(
            question="测试问题",
            expected_answer="期望答案"
        )

        assert qa.question == "测试问题"
        assert qa.expected_answer == "期望答案"
        assert qa.workflow_result is None
        assert qa.is_correct is False
        assert qa.match_type is None
        assert qa.workflow_run_id is None
        assert qa.error is None

    def test_question_answer_with_workflow_result(self):
        """测试包含工作流结果的QuestionAnswer"""
        qa = QuestionAnswer(
            question="测试问题",
            expected_answer="期望答案",
            workflow_result="实际答案",
            is_correct=True,
            match_type="exact",
            workflow_run_id="test-run-id"
        )

        assert qa.question == "测试问题"
        assert qa.expected_answer == "期望答案"
        assert qa.workflow_result == "实际答案"
        assert qa.is_correct is True
        assert qa.match_type == "exact"
        assert qa.workflow_run_id == "test-run-id"

    def test_question_answer_with_error(self):
        """测试包含错误的QuestionAnswer"""
        qa = QuestionAnswer(
            question="测试问题",
            expected_answer="期望答案",
            error="API调用失败"
        )

        assert qa.question == "测试问题"
        assert qa.expected_answer == "期望答案"
        assert qa.error == "API调用失败"