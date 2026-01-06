"""Dify工作流API客户端"""

import httpx
from typing import Dict, Any, Optional
from obd.models import WorkflowConfig


class DifyWorkflowClient:
    """Dify工作流API客户端"""

    def __init__(self, config: WorkflowConfig, client: Optional[httpx.AsyncClient] = None):
        self.config = config
        self.headers = {
            'Authorization': f'Bearer {config.api_key}',
            'Content-Type': 'application/json'
        }
        self.client = client or httpx.AsyncClient(headers=self.headers, timeout=config.timeout)
        self._is_external_client = client is not None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if not self._is_external_client:
            await self.client.aclose()

    async def close(self):
        """关闭客户端"""
        if not self._is_external_client:
            await self.client.aclose()

    async def execute_workflow(
        self,
        inputs: Dict[str, Any],
        user: Optional[str] = None,
        workflow_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行工作流

        根据Dify API文档，工作流应用使用 /chat-messages 端点

        Args:
            inputs: 工作流输入参数（通过inputs字段传递）
            user: 用户标识（可选）
            workflow_id: 工作流ID（可选，用于指定特定版本）

        Returns:
            工作流执行结果
        """
        url = f"{self.config.base_url}/chat-messages"

        payload = {
            "query": list(inputs.values())[0] if inputs else "",
            "inputs": inputs,
            "response_mode": self.config.response_mode,
            "user": user or self.config.user
        }

        # 如果提供了workflow_id，添加到payload中
        if workflow_id:
            payload["workflow_id"] = workflow_id

        try:
            # 同样支持传入特定 api_key 对应的 headers
            headers = self.headers.copy()
            if self._is_external_client:
                # 如果是复用的外部客户端，可能需要覆盖 headers
                # 显式合并字典，确保 Authorization 使用最新的 api_key
                ext_headers = dict(self.client.headers)
                headers = {**ext_headers, **self.headers}

            response = await self.client.post(
                url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise Exception(f"API调用失败: {str(e)}")

    async def get_workflow_run_detail(self, workflow_run_id: str) -> Dict[str, Any]:
        """
        获取工作流执行详情

        Args:
            workflow_run_id: 工作流执行ID

        Returns:
            工作流执行详情
        """
        url = f"{self.config.base_url}/workflows/run/{workflow_run_id}"

        try:
            response = await self.client.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            raise Exception(f"获取工作流详情失败: {str(e)}")
