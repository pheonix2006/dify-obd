"""数据模型定义"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, TYPE_CHECKING
from enum import Enum

# 类型注解导入（避免运行时循环引用）
if TYPE_CHECKING:
    from obd.comparator.llm_comparator import LLMEvalResult


# 类型注解导出
__all__ = [
    "AnswerCategory",
    "WorkflowConfig",
    "RoutingConfig",
    "ExecutionModeConfig",
    "StandardSchemaConfig",
    "RAGEvalSchemaConfig",
    "DualWorkflowSchemaConfig",
    "DualModelResponseParts",
    "DualWorkflowConfig",
    "DualWorkflowEvalResult",
    "LLMEvalConfig",
    "QuestionAnswer",
]


class AnswerCategory(Enum):
    """4级答案分类"""

    FULLY_CORRECT = "fully_correct"  # 完全正确
    PARTIAL_MISSING = "partial_missing"  # 部分缺失
    LARGE_MISSING = "large_missing"  # 大量缺失
    COMPLETELY_WRONG = "completely_wrong"  # 完全错误

    @property
    def label(self) -> str:
        """中文标签"""
        labels = {
            "fully_correct": "完全正确",
            "partial_missing": "部分缺失",
            "large_missing": "大量缺失",
            "completely_wrong": "完全错误",
        }
        return labels[self.value]

    @property
    def is_correct_2level(self) -> bool:
        """2级分类：是否正确"""
        return self == AnswerCategory.FULLY_CORRECT


@dataclass
class WorkflowConfig:
    """工作流配置"""

    api_key: str  # Dify API密钥
    base_url: str = "https://api.dify.ai/v1"  # Dify API基础URL
    response_mode: str = "blocking"  # blocking 或 streaming
    timeout: int = 60  # 请求超时时间（秒）
    max_workers: int = 5  # 最大并发数
    user: str = "batch_processor"  # 用户标识
    input_variable_name: str = "query"  # 工作流输入变量名
    output_variable_name: str = "answer"  # 工作流输出变量名
    workflow_mapping: Dict[str, str] = field(
        default_factory=dict
    )  # 知识库名称到API Key的映射表


@dataclass
class RoutingConfig:
    """路由配置"""

    knowledge_base_column: str = "KNOWLEDGE_BASE"  # 知识库列名
    answer_state_column: str = "ANSWER_STATE"  # 评测状态列名
    feedback_answer_column: str = "FEEDBACK_ANSWER"  # 反馈答案列名
    problem_value_column: str = "PROBLEM_VALUE"  # 问题值列名
    answer_value_column: str = "ANSWER_VALUE"  # 期望答案列名


@dataclass
class ExecutionModeConfig:
    """执行模式配置"""

    mode: str = "standard"  # standard, rag_eval, dual_workflow_compare

    def __post_init__(self):
        """验证模式配置"""
        valid_modes = ["standard", "rag_eval", "dual_workflow_compare"]
        if self.mode not in valid_modes:
            raise ValueError(
                f"无效的执行模式: {self.mode}\n" f"支持的模式: {', '.join(valid_modes)}"
            )


@dataclass
class StandardSchemaConfig:
    """标准模式列配置"""

    col_question: str = "Question"
    col_ground_truth: str = "Ground Truth"
    col_knowledge_base: Optional[str] = "KNOWLEDGE_BASE"
    col_answer_state: Optional[str] = "ANSWER_STATE"
    col_feedback_answer: Optional[str] = "FEEDBACK_ANSWER"


@dataclass
class RAGEvalSchemaConfig:
    """RAG 评测模式列配置"""

    col_question: str = "Question"
    col_scope: str = "Scope"
    col_ref_answer: str = "Ref_Answer"
    col_history_eval: str = "Evaluation_Notes"


@dataclass
class DualWorkflowSchemaConfig:
    """双工作流对比评测模式列配置"""

    col_question: str = "Question"
    col_history: Optional[str] = None  # 历史回答列（用于三方对比）


@dataclass
class DualModelResponseParts:
    """双模型响应解析结果（由 DualModelResponseParser 生成）"""

    question: str  # 原始问题
    rerank_sources: str  # 召回片段
    llm1_output: str  # LLM1 输出
    llm2_output: str  # LLM2 输出
    is_valid_format: bool = True  # 是否成功解析


@dataclass
class DualWorkflowConfig:
    """双工作流配置（单工作流+双模型输出）"""

    # 单工作流配置
    api_key: str  # 单一 API Key
    workflow_id: Optional[str] = None

    # 标签配置（用于结果展示）
    label_1: str = "LLM1"
    label_2: str = "LLM2"
    label_history: str = "历史回答"  # 历史回答标签

    # 共享配置
    base_url: str = "https://api.dify.ai/v1"
    response_mode: str = "blocking"
    timeout: int = 60


@dataclass
class DualWorkflowEvalResult:
    """三方对比评测结果（LLM1 vs LLM2 vs History）"""

    winner: str  # "llm1", "llm2", "history", "tie"
    confidence: str  # "high", "medium", "low"

    # 综合分析
    overall_analysis: str  # 总体分析

    # 各答案简要评价（优缺点合一）
    llm1_comment: str
    llm2_comment: str
    history_comment: str

    # 推荐理由
    recommendation: str

    prompt: Optional[str] = None
    raw_response: Optional[str] = None


@dataclass
class LLMEvalConfig:
    """LLM评测配置"""

    enabled: bool = False
    api_key: Optional[str] = None
    base_url: str = "https://api.openai.com/v1/chat/completions"  # 完整 URL，不自动拼接
    model: str = "gpt-4o"
    api_type: str = (
        "standard"  # standard 采用 messages/choices, custom_azure 采用 input/output
    )
    prompt_template: Optional[str] = None
    timeout: int = 30
    judgment_mode: str = "detailed"  # detailed/autonomous
    temperature: float = 0.0  # 控制输出的确定性
    save_prompt: bool = False  # 是否在 Excel 中保存 LLM 提示词（调试用）
    # 评测记录配置
    eval_record_enabled: bool = False  # 是否启用评测记录（保存为 JSON 文件）
    eval_record_path: str = "logs/eval_records"  # 评测记录保存路径

    def __post_init__(self):
        """验证配置项"""
        if self.judgment_mode not in ("detailed", "autonomous"):
            raise ValueError(
                f"Invalid judgment_mode: {self.judgment_mode}. "
                f"Must be 'detailed' or 'autonomous'"
            )
        if not 0.0 <= self.temperature <= 1.0:
            raise ValueError(
                f"Invalid temperature: {self.temperature}. "
                f"Must be between 0.0 and 1.0"
            )


@dataclass
class QuestionAnswer:
    """问题-答案对"""

    question: str
    expected_answer: str
    original_index: Optional[int] = None  # 原始行索引
    workflow_result: Optional[str] = None
    is_correct: bool = False
    match_type: Optional[str] = None  # exact, fuzzy, keyword, semantic, llm
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
    llm_analysis: Optional[str] = None  # LLM 评测分析结果
    llm_category: Optional[str] = None  # LLM 4级分类结果
    missing_info: Optional[str] = None  # 缺失的具体内容
    important_info: Optional[str] = None  # 重要信息识别

    # RAG 评测模式字段（可选）
    scope: Optional[str] = None  # 评测范围
    ref_answer: Optional[str] = None  # 上一版回答
    history_eval: Optional[str] = None  # 历史评价
    improvement_analysis: Optional[str] = None  # 改进分析（新）

    # RAG响应解析字段（新增）
    extracted_question: Optional[str] = None  # 从answer中提取的问题
    rerank_sources: Optional[str] = None  # rerank片段（合并）
    llm_answer: Optional[str] = None  # LLM生成的答案（纯净版）
    is_rag_format: bool = False  # 是否成功解析RAG格式

    # LLM评测完整结果（包含prompt等调试信息）
    llm_eval: Optional["LLMEvalResult"] = None

    # 双工作流对比评测模式字段
    workflow_1_result: Optional[str] = None  # 兼容保留（映射到 llm1）
    workflow_2_result: Optional[str] = None  # 兼容保留（映射到 llm2）
    history_answer: Optional[str] = None  # 历史回答（用于三方对比）
    winner: Optional[str] = None  # 获胜者: "llm1", "llm2", "history", "tie"
    comparison_analysis: Optional[str] = None  # 对比分析结果（映射到 overall_analysis）
    dual_workflow_eval: Optional["DualWorkflowEvalResult"] = None  # 完整评测结果

    @property
    def answer_category(self) -> Optional[AnswerCategory]:
        """获取4级分类枚举"""
        if self.llm_category:
            return AnswerCategory(self.llm_category)
        return None
