"""工作流批处理器"""

import json
import os
import time
from typing import Dict, Any, List, Optional

import pandas as pd

from obd.client.dify_client import DifyWorkflowClient
from obd.comparator.answer_comparator import AnswerComparator
from obd.models import QuestionAnswer, WorkflowConfig


class WorkflowBatchProcessor:
    """工作流批处理器"""

    def __init__(self, config: WorkflowConfig, client=None):
        self.config = config
        self.client = client or DifyWorkflowClient(config)
        self.comparator = AnswerComparator()

    def load_excel(self, excel_path: str) -> pd.DataFrame:
        """
        加载Excel文件

        Args:
            excel_path: Excel文件路径

        Returns:
            DataFrame数据
        """
        if not os.path.exists(excel_path):
            raise FileNotFoundError(f"Excel文件不存在: {excel_path}")

        try:
            df = pd.read_excel(excel_path)
        except Exception:
            # 如果不是Excel文件，尝试读取CSV
            df = pd.read_csv(excel_path)

        return df

    def process_question(
        self,
        question: str,
        input_variable_name: str = "query",
        output_variable_name: str = "answer",
        comparison_method: str = "auto",
        user: Optional[str] = None,
        workflow_id: Optional[str] = None
    ) -> QuestionAnswer:
        """
        处理单个问题

        Args:
            question: 问题文本
            input_variable_name: 工作流输入变量名
            output_variable_name: 工作流输出变量名
            comparison_method: 答案对比方法
            user: 用户标识
            workflow_id: 工作流ID（可选）

        Returns:
            QuestionAnswer对象
        """
        qa = QuestionAnswer(question=question, expected_answer="")

        try:
            # 调用工作流
            inputs = {input_variable_name: question}
            result = self.client.execute_workflow(inputs, user, workflow_id)

            # 提取工作流运行ID
            qa.workflow_run_id = result.get("task_id")

            # 根据调试结果，聊天应用返回的answer字段包含回复内容
            # 如果没有answer字段，返回原始响应
            if "answer" in result:
                qa.workflow_result = str(result["answer"])
            else:
                qa.workflow_result = json.dumps(result, ensure_ascii=False)

        except Exception as e:
            qa.error = str(e)

        return qa

    def process_excel(
        self,
        excel_path: str,
        question_column: str = "question",
        answer_column: str = "answer",
        input_variable_name: str = "query",
        output_variable_name: str = "answer",
        comparison_method: str = "auto",
        start_row: int = 0,
        end_row: Optional[int] = None,
        delay: float = 0.5,
        workflow_id: Optional[str] = None
    ) -> List[QuestionAnswer]:
        """
        批量处理Excel中的问题

        Args:
            excel_path: Excel文件路径
            question_column: 问题列名
            answer_column: 答案列名
            input_variable_name: 工作流输入变量名
            output_variable_name: 工作流输出变量名
            comparison_method: 答案对比方法
            start_row: 起始行（0-based）
            end_row: 结束行（不包含）
            delay: 每次请求之间的延迟（秒）
            workflow_id: 工作流ID（可选）

        Returns:
            QuestionAnswer列表
        """
        df = self.load_excel(excel_path)

        # 检查必需的列
        if question_column not in df.columns:
            raise ValueError(f"Excel文件中不存在列: {question_column}")

        if answer_column not in df.columns:
            raise ValueError(f"Excel文件中不存在列: {answer_column}")

        # 确定处理范围
        total_rows = len(df)
        if end_row is None or end_row > total_rows:
            end_row = total_rows

        print(f"共 {total_rows} 行，处理第 {start_row} 行到第 {end_row-1} 行")
        print("-" * 60)

        results = []

        for idx in range(start_row, end_row):
            row = df.iloc[idx]
            question = str(row[question_column])
            expected_answer = str(row[answer_column])

            print(f"[{idx+1}/{total_rows}] 处理问题: {question[:50]}...")

            # 处理问题
            qa = self.process_question(
                question=question,
                input_variable_name=input_variable_name,
                output_variable_name=output_variable_name,
                comparison_method=comparison_method,
                workflow_id=workflow_id
            )
            qa.expected_answer = expected_answer

            # 对比答案
            if qa.workflow_result and not qa.error:
                is_match, match_type = self.comparator.compare(
                    expected_answer,
                    qa.workflow_result,
                    method=comparison_method
                )
                qa.is_correct = is_match
                qa.match_type = match_type

                if is_match:
                    print(f"  ✓ 正确 ({match_type})")
                else:
                    print(f"  ✗ 错误")
                    print(f"    期望: {expected_answer[:100]}")
                    print(f"    实际: {qa.workflow_result[:100]}")
            else:
                print(f"  ✗ 失败: {qa.error}")

            results.append(qa)

            # 延迟以避免请求过快
            if delay > 0 and idx < end_row - 1:
                time.sleep(delay)

        return results

    def calculate_statistics(self, results: List[QuestionAnswer]) -> Dict[str, Any]:
        """
        计算统计信息

        Args:
            results: QuestionAnswer列表

        Returns:
            统计信息字典
        """
        total = len(results)
        if total == 0:
            return {}

        correct = sum(1 for qa in results if qa.is_correct)
        failed = sum(1 for qa in results if qa.error is not None)

        # 按匹配类型统计
        match_type_stats = {}
        for qa in results:
            if qa.match_type:
                match_type_stats[qa.match_type] = match_type_stats.get(qa.match_type, 0) + 1

        statistics = {
            "total": total,
            "correct": correct,
            "incorrect": total - correct - failed,
            "failed": failed,
            "accuracy": correct / total if total > 0 else 0,
            "success_rate": (total - failed) / total if total > 0 else 0,
            "match_type_stats": match_type_stats
        }

        return statistics

    def save_results(
        self,
        results: List[QuestionAnswer],
        statistics: Dict[str, Any],
        output_path: str
    ):
        """
        保存结果到文件

        Args:
            results: QuestionAnswer列表
            statistics: 统计信息
            output_path: 输出文件路径
        """
        # 转换为DataFrame
        data = []
        for idx, qa in enumerate(results):
            data.append({
                "序号": idx + 1,
                "问题": qa.question,
                "期望答案": qa.expected_answer,
                "工作流结果": qa.workflow_result,
                "是否正确": "✓" if qa.is_correct else "✗",
                "匹配类型": qa.match_type or "",
                "错误信息": qa.error or "",
                "工作流运行ID": qa.workflow_run_id or ""
            })

        df = pd.DataFrame(data)

        # 保存Excel
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name="处理结果", index=False)

            # 添加统计信息sheet
            stats_data = []
            stats_data.append(["总数量", statistics.get("total", 0)])
            stats_data.append(["正确数量", statistics.get("correct", 0)])
            stats_data.append(["错误数量", statistics.get("incorrect", 0)])
            stats_data.append(["失败数量", statistics.get("failed", 0)])
            stats_data.append(["准确率", f"{statistics.get('accuracy', 0):.2%}"])
            stats_data.append(["成功率", f"{statistics.get('success_rate', 0):.2%}"])

            stats_df = pd.DataFrame(stats_data, columns=["指标", "数值"])
            stats_df.to_excel(writer, sheet_name="统计信息", index=False)

        print(f"\n结果已保存到: {output_path}")
