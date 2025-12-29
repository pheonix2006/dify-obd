"""Dify工作流API客户端"""

import time
import requests
from typing import Dict, Any, Optional
from obd.models import WorkflowConfig


class DifyWorkflowClient:
    """Dify工作流API客户端"""

    def __init__(self, config: WorkflowConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {config.api_key}',
            'Content-Type': 'application/json'
        })

    def execute_workflow(
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
            "user": user or self.config.user,
            "conversation_id": "",  # 不需要会话ID
        }

        # 如果提供了workflow_id，添加到payload中
        if workflow_id:
            payload["workflow_id"] = workflow_id

        try:
            response = self.session.post(
                url,
                json=payload,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"API调用失败: {str(e)}")

    def get_workflow_run_detail(self, workflow_run_id: str) -> Dict[str, Any]:
        """
        获取工作流执行详情

        Args:
            workflow_run_id: 工作流执行ID

        Returns:
            工作流执行详情
        """
        url = f"{self.config.base_url}/workflows/run/{workflow_run_id}"

        try:
            response = self.session.get(url, timeout=self.config.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"获取工作流详情失败: {str(e)}")
