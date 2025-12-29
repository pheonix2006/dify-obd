"""测试Dify客户端"""

import pytest
import requests
from unittest.mock import Mock, patch
from obd.client.dify_client import DifyWorkflowClient
from obd.models import WorkflowConfig


class TestDifyWorkflowClient:
    """测试DifyWorkflowClient类"""

    def setup_method(self):
        """测试前设置"""
        self.config = WorkflowConfig(
            api_key="test_api_key",
            base_url="https://api.dify.ai/v1",
            response_mode="blocking",
            timeout=60
        )
        self.client = DifyWorkflowClient(self.config)

    @patch('requests.Session.post')
    def test_execute_workflow_success(self, mock_post):
        """测试成功执行工作流"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "workflow_run_id": "test-run-id",
            "task_id": "test-task-id",
            "data": {
                "outputs": {
                    "answer": "这是处理结果"
                }
            }
        }
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # 执行工作流
        inputs = {"query": "测试问题"}
        result = self.client.execute_workflow(inputs)

        # 验证结果
        assert result["workflow_run_id"] == "test-run-id"
        assert result["task_id"] == "test-task-id"
        assert result["data"]["outputs"]["answer"] == "这是处理结果"

        # 验证请求参数
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]['json']['inputs'] == inputs
        assert call_args[1]['json']['response_mode'] == "blocking"
        assert call_args[1]['json']['user'] == "batch_processor"

    @patch('requests.Session.post')
    def test_execute_workflow_with_custom_user(self, mock_post):
        """测试使用自定义用户ID执行工作流"""
        mock_response = Mock()
        mock_response.json.return_value = {"workflow_run_id": "test-run-id"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        inputs = {"query": "测试问题"}
        user = "test_user"
        result = self.client.execute_workflow(inputs, user)

        # 验证使用了自定义用户ID
        call_args = mock_post.call_args
        assert call_args[1]['json']['user'] == user
        assert result["workflow_run_id"] == "test-run-id"

    @patch('requests.Session.post')
    def test_execute_workflow_request_error(self, mock_post):
        """测试API请求错误"""
        # 模拟网络错误
        mock_post.side_effect = requests.exceptions.RequestException("连接超时")

        inputs = {"query": "测试问题"}

        # 应该抛出异常
        with pytest.raises(Exception) as exc_info:
            self.client.execute_workflow(inputs)
        # 验证异常消息包含"API调用失败"
        assert "API调用失败" in str(exc_info.value)

    @patch('requests.Session.get')
    def test_get_workflow_run_detail_success(self, mock_get):
        """测试成功获取工作流详情"""
        # 模拟API响应
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "test-run-id",
            "workflow_id": "test-workflow-id",
            "status": "completed",
            "outputs": {"answer": "这是处理结果"},
            "total_steps": 5,
            "elapsed_time": 1234
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # 获取工作流详情
        workflow_run_id = "test-run-id"
        result = self.client.get_workflow_run_detail(workflow_run_id)

        # 验证结果
        assert result["id"] == "test-run-id"
        assert result["status"] == "completed"
        assert result["outputs"]["answer"] == "这是处理结果"
        assert result["total_steps"] == 5
        assert result["elapsed_time"] == 1234

        # 验证请求参数
        mock_get.assert_called_once_with(
            f"{self.config.base_url}/workflows/run/{workflow_run_id}",
            timeout=60
        )

    @patch('requests.Session.get')
    def test_get_workflow_run_detail_error(self, mock_get):
        """测试获取工作流详情错误"""
        # 模拟404错误
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("未找到工作流")
        mock_get.return_value = mock_response

        workflow_run_id = "non-existent-id"

        # 应该抛出异常
        with pytest.raises(Exception) as exc_info:
            self.client.get_workflow_run_detail(workflow_run_id)
        # 验证异常消息包含"获取工作流详情失败"
        assert "获取工作流详情失败" in str(exc_info.value)

    @patch('requests.Session.post')
    def test_execute_workflow_invalid_response(self, mock_post):
        """测试处理无效响应"""
        # 模拟无效的JSON响应
        mock_response = Mock()
        mock_response.json.side_effect = ValueError("无效的JSON")
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        inputs = {"query": "测试问题"}

        # 应该抛出异常
        with pytest.raises(Exception):
            self.client.execute_workflow(inputs)

    def test_client_headers(self):
        """测试客户端头部设置"""
        # 验证头部设置 - 只检查我们设置的header
        assert self.client.session.headers['Authorization'] == 'Bearer test_api_key'
        assert self.client.session.headers['Content-Type'] == 'application/json'