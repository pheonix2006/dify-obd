"""评测逻辑分支组件"""

from typing import Any, Optional

from obd.comparator.answer_comparator import AnswerComparator
from obd.models import QuestionAnswer


class EvaluationBranch:
    """评测逻辑分支处理器"""

    def __init__(self, comparison_method: str = "auto"):
        self.comparator = AnswerComparator()
        self.comparison_method = comparison_method

    def parse_answer_state(self, answer_state: Any) -> bool:
        """
        解析ANSWER_STATE值

        Args:
            answer_state: 原始ANSWER_STATE值

        Returns:
            是否为False值（False表示异常模式）
        """
        if answer_state is None:
            return True  # 默认为正常评测

        # 处理字符串"false", "FALSE"等
        if isinstance(answer_state, str):
            return answer_state.strip().lower() not in ("false", "0", "")

        # 处理布尔值
        if isinstance(answer_state, bool):
            return answer_state

        # 处理数字
        if isinstance(answer_state, (int, float)):
            return bool(answer_state)

        # 默认返回True（正常评测）
        return True

    def evaluate_normal(
        self, qa: QuestionAnswer, expected_answer: str, actual_answer: str
    ) -> QuestionAnswer:
        """
        正常评测模式
        - 对比API结果与期望答案
        - 计入统计

        Args:
            qa: QuestionAnswer对象
            expected_answer: 期望答案
            actual_answer: 实际答案

        Returns:
            更新后的QuestionAnswer对象
        """
        qa.model_output = str(actual_answer) if actual_answer is not None else None
        qa.final_display = str(actual_answer) if actual_answer is not None else None
        qa.is_evaluated = True

        if actual_answer and not qa.error:
            is_match, match_type = self.comparator.compare(
                expected_answer, actual_answer, method=self.comparison_method
            )
            qa.is_correct = is_match
            qa.match_type = match_type

        return qa

    def evaluate_feedback(
        self, qa: QuestionAnswer, actual_answer: str, feedback_answer: str
    ) -> QuestionAnswer:
        """
        异常/反馈模式
        - 忽略API结果（仅记录）
        - 强制使用FEEDBACK_ANSWER
        - 不计入统计

        Args:
            qa: QuestionAnswer对象
            actual_answer: 实际答案（仅记录）
            feedback_answer: 反馈答案

        Returns:
            更新后的QuestionAnswer对象
        """
        qa.model_output = str(actual_answer) if actual_answer is not None else None
        qa.final_display = str(feedback_answer) if feedback_answer is not None else None
        qa.is_evaluated = False  # 不计入统计
        qa.is_correct = False  # N/A（异常模式不计入统计，使用 False 作为默认值）
        qa.match_type = None
        qa.feedback_answer = feedback_answer

        return qa

    def evaluate(
        self,
        qa: QuestionAnswer,
        answer_state: Any,
        expected_answer: str,
        actual_answer: str,
        feedback_answer: Optional[str] = None,
    ) -> QuestionAnswer:
        """
        根据ANSWER_STATE进行分支处理

        Args:
            qa: QuestionAnswer对象
            answer_state: ANSWER_STATE值
            expected_answer: 期望答案
            actual_answer: 实际答案
            feedback_answer: 反馈答案（异常模式需要）

        Returns:
            更新后的QuestionAnswer对象
        """
        qa.answer_state = answer_state

        # 判断是否为正常评测模式
        is_normal = self.parse_answer_state(answer_state)

        if is_normal:
            return self.evaluate_normal(qa, expected_answer, actual_answer)
        else:
            if not feedback_answer:
                feedback_answer = "N/A"
            return self.evaluate_feedback(qa, actual_answer, feedback_answer)
