"""数据模型定义"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class WorkflowConfig:
    """工作流配置"""
    api_key: str  # Dify API密钥
    base_url: str = "https://api.dify.ai/v1"  # Dify API基础URL
    response_mode: str = "blocking"  # blocking 或 streaming
    timeout: int = 60  # 请求超时时间（秒）
    user: str = "batch_processor"  # 用户标识
    workflow_mapping: Dict[str, str] = field(default_factory=dict)  # 知识库名称到API Key的映射表


@dataclass
class RoutingConfig:
    """路由配置"""
    knowledge_base_column: str = "KNOWLEDGE_BASE"  # 知识库列名
    answer_state_column: str = "ANSWER_STATE"  # 评测状态列名
    feedback_answer_column: str = "FEEDBACK_ANSWER"  # 反馈答案列名
    problem_value_column: str = "PROBLEM_VALUE"  # 问题值列名
    answer_value_column: str = "ANSWER_VALUE"  # 期望答案列名


@dataclass
class QuestionAnswer:
    """问题-答案对"""
    question: str
    expected_answer: str
    workflow_result: Optional[str] = None
    is_correct: bool = False
    match_type: Optional[str] = None  # exact, fuzzy, keyword, semantic
    workflow_run_id: Optional[str] = None
    error: Optional[str] = None

    # 新增字段（用于动态路由和评测分支）
    knowledge_base: Optional[str] = None  # 知识库名称（路由键）
    model_output: Optional[str] = None  # API返回的原始答案
    final_display: Optional[str] = None  # 最终展示内容（逻辑处理后）
    is_evaluated: bool = True  # 是否参与评测（ANSWER_STATE=False时为False）
    answer_state: Optional[Any] = None  # 原始ANSWER_STATE值
    feedback_answer: Optional[str] = None  # 反馈答案（用于异常模式）
    used_api_key: Optional[str] = None  # 使用的API Key（后四位）
