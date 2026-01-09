"""路由分发组件"""

from typing import Optional, Tuple, Any

from obd.models import WorkflowConfig


class WorkflowRouting:
    """工作流路由分发器"""

    def __init__(self, config: WorkflowConfig):
        self.config = config
        self.workflow_mapping = config.workflow_mapping

    def standardize_kb_name(self, kb_name: Any) -> str:
        """
        标准化知识库名称
        - 处理 NaN, None, 空字符串
        - 去除首尾空格
        - 转换为小写
        - 将空值标识为 'null' 以匹配配置

        Args:
            kb_name: 原始知识库名称

        Returns:
            标准化后的名称
        """
        # 处理 None
        if kb_name is None:
            return "null"
        
        # 处理 NaN (float)
        if isinstance(kb_name, float) and kb_name != kb_name:
            return "null"
            
        # 转换为字符串并处理
        kb_str = str(kb_name).strip().lower()
        
        # 处理空字符串或字符串形式的 'nan'
        if not kb_str or kb_str == 'nan' or kb_str == 'none':
            return "null"
            
        return kb_str

    def get_api_key(self, knowledge_base: Any) -> Optional[str]:
        """
        根据知识库名称获取对应的API Key

        Args:
            knowledge_base: 知识库名称

        Returns:
            API Key或None（如果未找到）
        """
        standardized_kb = self.standardize_kb_name(knowledge_base)
        return self.workflow_mapping.get(standardized_kb)

    def validate_mapping(self, kb_name: Any) -> Tuple[bool, Optional[str]]:
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
