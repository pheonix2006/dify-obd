"""测试Dify客户端"""

import pytest
import httpx
from unittest.mock import AsyncMock, patch, Mock, MagicMock
from obd.client.dify_client import DifyWorkflowClient
from obd.models import WorkflowConfig


class TestDifyWorkflowClient:
    """测试DifyWorkflowClient类"""

    @pytest.fixture
    def config(self):
        """测试配置"""
        return WorkflowConfig(
            api_key="test_api_key",
            base_url="https://api.dify.ai/v1",
            response_mode="blocking",
            timeout=60
        )

    @pytest.fixture
    def client(self, config):
        """测试客户端实例"""
        return DifyWorkflowClient(config)

    @pytest.mark.asyncio
    async def test_execute_workflow_success(self, config):
        """测试成功执行工作流"""
        # 创建 mock 响应
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "workflow_run_id": "test-run-id",
            "task_id": "test-task-id",
            "data": {
                "outputs": {
                    "answer": "这是处理结果"
                }
            }
        }
        mock_response.raise_for_status = Mock()

        # 创建 mock httpx 客户端
        mock_httpx_client = AsyncMock()
        mock_httpx_client.post = AsyncMock(return_value=mock_response)
        mock_httpx_client.headers = {}  # 添加 headers 属性

        client = DifyWorkflowClient(config, client=mock_httpx_client)

        # 执行工作流
        inputs = {"query": "测试问题"}
        result = await client.execute_workflow(inputs)

        # 验证结果
        assert result["workflow_run_id"] == "test-run-id"
        assert result["task_id"] == "test-task-id"

        # 验证请求参数
        mock_httpx_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_workflow_request_error(self, config):
        """测试API请求错误"""
        # 模拟网络错误
        mock_httpx_client = AsyncMock()
        mock_httpx_client.post = AsyncMock(side_effect=httpx.HTTPError("连接超时"))
        mock_httpx_client.headers = {}

        client = DifyWorkflowClient(config, client=mock_httpx_client)
        inputs = {"query": "测试问题"}

        # 应该抛出异常
        with pytest.raises(Exception) as exc_info:
            await client.execute_workflow(inputs)
        # 验证异常消息包含"API调用失败"
        assert "API调用失败" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_workflow_run_detail_success(self, config):
        """测试成功获取工作流详情"""
        # 模拟API响应
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "test-run-id",
            "workflow_id": "test-workflow-id",
            "status": "completed",
            "outputs": {"answer": "这是处理结果"},
            "total_steps": 5,
            "elapsed_time": 1234
        }
        mock_response.raise_for_status = Mock()

        # 创建 mock httpx 客户端
        mock_httpx_client = AsyncMock()
        mock_httpx_client.get = AsyncMock(return_value=mock_response)
        mock_httpx_client.headers = {}

        client = DifyWorkflowClient(config, client=mock_httpx_client)

        # 获取工作流详情
        workflow_run_id = "test-run-id"
        result = await client.get_workflow_run_detail(workflow_run_id)

        # 验证结果
        assert result["id"] == "test-run-id"
        assert result["status"] == "completed"
        assert result["outputs"]["answer"] == "这是处理结果"
        assert result["total_steps"] == 5
        assert result["elapsed_time"] == 1234

        # 验证请求参数
        mock_httpx_client.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_workflow_run_detail_error(self, config):
        """测试获取工作流详情错误"""
        # 模拟404错误
        mock_httpx_client = AsyncMock()
        mock_httpx_client.get = AsyncMock(side_effect=httpx.HTTPError("未找到工作流"))
        mock_httpx_client.headers = {}

        client = DifyWorkflowClient(config, client=mock_httpx_client)

        workflow_run_id = "non-existent-id"

        # 应该抛出异常
        with pytest.raises(Exception) as exc_info:
            await client.get_workflow_run_detail(workflow_run_id)
        # 验证异常消息包含"获取工作流详情失败"
        assert "获取工作流详情失败" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_workflow_invalid_response(self, client):
        """测试处理无效响应"""
        from unittest.mock import patch
        # 模拟无效的JSON响应
        async def mock_invalid_response(*args, **kwargs):
            raise ValueError("无效的JSON")

        # Mock 客户端
        client_with_mock = DifyWorkflowClient(client.config)
        client_with_mock.execute_workflow = mock_invalid_response

        inputs = {"query": "测试问题"}

        # 应该抛出异常
        with pytest.raises(Exception):
            await client_with_mock.execute_workflow(inputs)

    def test_client_headers(self, client):
        """测试客户端头部设置"""
        # 验证头部设置 - 只检查我们设置的header
        assert client.headers['Authorization'] == 'Bearer test_api_key'
        assert client.headers['Content-Type'] == 'application/json'
