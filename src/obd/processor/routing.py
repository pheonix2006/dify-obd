"""路由分发组件"""

from typing import Optional, Tuple

from obd.models import WorkflowConfig


class WorkflowRouting:
    """工作流路由分发器"""

    def __init__(self, config: WorkflowConfig):
        self.config = config
        self.workflow_mapping = config.workflow_mapping

    def standardize_kb_name(self, kb_name: str) -> str:
        """
        标准化知识库名称
        - 去除首尾空格
        - 转换为小写

        Args:
            kb_name: 原始知识库名称

        Returns:
            标准化后的名称
        """
        if not kb_name or not isinstance(kb_name, str):
            return ""
        return kb_name.strip().lower()

    def get_api_key(self, knowledge_base: str) -> Optional[str]:
        """
        根据知识库名称获取对应的API Key

        Args:
            knowledge_base: 知识库名称

        Returns:
            API Key或None（如果未找到）
        """
        standardized_kb = self.standardize_kb_name(knowledge_base)
        return self.workflow_mapping.get(standardized_kb)

    def validate_mapping(self, kb_name: str) -> Tuple[bool, Optional[str]]:
        """
        验证知识库映射是否存在

        Args:
            kb_name: 知识库名称

        Returns:
            (是否存在, 错误信息)
        """
        api_key = self.get_api_key(kb_name)
        if not api_key:
            return False, f"Config Missing for KB: [{kb_name}]"
        return True, None
