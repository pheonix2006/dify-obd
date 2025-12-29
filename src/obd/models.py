"""数据模型定义"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class WorkflowConfig:
    """工作流配置"""
    api_key: str  # Dify API密钥
    base_url: str = "https://api.dify.ai/v1"  # Dify API基础URL
    response_mode: str = "blocking"  # blocking 或 streaming
    timeout: int = 60  # 请求超时时间（秒）
    user: str = "batch_processor"  # 用户标识


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
