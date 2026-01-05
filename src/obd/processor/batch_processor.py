"""工作流批处理器"""

import json
import logging
import os
import time
from typing import Dict, Any, List, Optional

import pandas as pd

from obd.client.dify_client import DifyWorkflowClient
from obd.comparator.answer_comparator import AnswerComparator
from obd.models import QuestionAnswer, WorkflowConfig, RoutingConfig
from obd.processor.routing import WorkflowRouting
from obd.processor.evaluation import EvaluationBranch

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WorkflowBatchProcessor:
    """工作流批处理器"""

    def __init__(
        self,
        config: WorkflowConfig,
        routing_config: Optional[RoutingConfig] = None,
        client=None
    ):
        self.config = config
        self.routing_config = routing_config or RoutingConfig()
        self.client = client or DifyWorkflowClient(config)
        self.comparator = AnswerComparator()

        # 初始化路由和评测组件
        self.routing = WorkflowRouting(config)
        self.evaluator = EvaluationBranch(comparison_method="auto")

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

    def process_row_with_routing(
        self,
        row: pd.Series,
        idx: int,
        total_rows: int
    ) -> Optional[QuestionAnswer]:
        """
        处理单行数据（支持路由和分支）

        Args:
            row: DataFrame行
            idx: 行索引
            total_rows: 总行数

        Returns:
            QuestionAnswer对象（如果跳过则返回None）
        """
        # 提取列值
        question = str(row.get(self.routing_config.problem_value_column, ""))
        knowledge_base = row.get(self.routing_config.knowledge_base_column, "")
        answer_state = row.get(self.routing_config.answer_state_column, None)
        expected_answer = row.get(self.routing_config.answer_value_column, "")
        feedback_answer = row.get(self.routing_config.feedback_answer_column, None)

        # 1. 路由验证
        is_valid, error_msg = self.routing.validate_mapping(knowledge_base)
        if not is_valid:
            logger.warning(f"[{idx+1}/{total_rows}] {error_msg}")
            return None

        # 获取API Key
        api_key = self.routing.get_api_key(knowledge_base)

        # 创建QuestionAnswer对象
        qa = QuestionAnswer(question=question, expected_answer=str(expected_answer))
        qa.knowledge_base = knowledge_base
        qa.used_api_key = api_key[-4:] if api_key else None

        # 2. API调用（使用动态API Key）
        try:
            # 创建临时配置
            temp_config = WorkflowConfig(
                api_key=api_key,
                base_url=self.config.base_url,
                response_mode=self.config.response_mode,
                timeout=self.config.timeout,
                user=self.config.user
            )

            # 创建临时客户端
            temp_client = DifyWorkflowClient(temp_config)

            # 调用工作流
            inputs = {"query": question}
            result = temp_client.execute_workflow(
                inputs,
                self.config.user,
                None
            )

            qa.workflow_run_id = result.get("task_id")
            actual_answer = result.get("answer", json.dumps(result, ensure_ascii=False))

        except Exception as e:
            qa.error = str(e)
            actual_answer = None

        # 3. 评测分支
        if actual_answer and not qa.error:
            qa = self.evaluator.evaluate(
                qa,
                answer_state=answer_state,
                expected_answer=str(expected_answer),
                actual_answer=actual_answer,
                feedback_answer=str(feedback_answer) if feedback_answer else None
            )
        else:
            # API调用失败，默认为正常模式但标记错误
            qa.model_output = actual_answer
            qa.final_display = actual_answer
            qa.is_evaluated = True

        return qa

    def _check_new_columns(self, df: pd.DataFrame) -> bool:
        """检查是否为新模式所需的列"""
        required_columns = [
            self.routing_config.knowledge_base_column,
            self.routing_config.answer_state_column,
            self.routing_config.problem_value_column,
            self.routing_config.answer_value_column
        ]
        return all(col in df.columns for col in required_columns)

    def _print_result(self, qa: QuestionAnswer, idx: int, total_rows: int):
        """打印处理结果"""
        prefix = f"[{idx+1}/{total_rows}] {qa.question[:50]}..."
        prefix += f" (KB: {qa.knowledge_base})"

        if qa.error:
            print(f"{prefix}")
            print(f"  ✗ 失败: {qa.error}")
        elif qa.is_evaluated:
            status = "✓" if qa.is_correct else "✗"
            print(f"{prefix}")
            print(f"  {status} 正确 ({qa.match_type})")
        else:
            print(f"{prefix}")
            print(f"  ↔ 异常模式 - 使用反馈答案: {qa.final_display[:50]}...")

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
        批量处理Excel中的问题（支持路由和评测分支）

        Args:
            excel_path: Excel文件路径
            question_column: 问题列名（兼容旧版）
            answer_column: 答案列名（兼容旧版）
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

        # 检查必需的列（兼容新旧两种模式）
        is_new_mode = self._check_new_columns(df)

        if is_new_mode:
            print("使用新模式：路由分发 + 评测分支")
            return self._process_excel_new_mode(df, start_row, end_row, delay)
        else:
            print("使用旧模式：单API Key + 全量评测")
            return self._process_excel_legacy_mode(
                df,
                question_column,
                answer_column,
                input_variable_name,
                output_variable_name,
                comparison_method,
                start_row,
                end_row,
                delay,
                workflow_id
            )

    def _process_excel_new_mode(
        self,
        df: pd.DataFrame,
        start_row: int,
        end_row: Optional[int],
        delay: float
    ) -> List[QuestionAnswer]:
        """处理Excel（新模式）"""
        total_rows = len(df)
        if end_row is None or end_row > total_rows:
            end_row = total_rows

        print(f"共 {total_rows} 行，处理第 {start_row} 行到第 {end_row-1} 行")
        print("-" * 60)

        results = []

        for idx in range(start_row, end_row):
            row = df.iloc[idx]

            # 处理单行
            qa = self.process_row_with_routing(row, idx, total_rows)

            if qa is None:
                continue  # 跳过无效行

            # 打印结果
            self._print_result(qa, idx, total_rows)
            results.append(qa)

            # 延迟
            if delay > 0 and idx < end_row - 1:
                time.sleep(delay)

        return results

    def _process_excel_legacy_mode(
        self,
        df: pd.DataFrame,
        question_column: str,
        answer_column: str,
        input_variable_name: str,
        output_variable_name: str,
        comparison_method: str,
        start_row: int,
        end_row: Optional[int],
        delay: float,
        workflow_id: Optional[str]
    ) -> List[QuestionAnswer]:
        """处理Excel（旧模式）"""
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
        计算统计信息（排除异常模式）

        Args:
            results: QuestionAnswer列表

        Returns:
            统计信息字典
        """
        total = len(results)
        if total == 0:
            return {}

        # 只统计参与评测的样本
        evaluated_results = [r for r in results if r.is_evaluated]
        evaluated_count = len(evaluated_results)

        correct = sum(1 for qa in evaluated_results if qa.is_correct)
        failed = sum(1 for qa in results if qa.error is not None)

        # 异常模式数量
        feedback_mode_count = sum(1 for qa in results if not qa.is_evaluated and qa.error is None)

        # 按匹配类型统计
        match_type_stats = {}
        for qa in evaluated_results:
            if qa.match_type:
                match_type_stats[qa.match_type] = match_type_stats.get(qa.match_type, 0) + 1

        statistics = {
            "total": total,
            "evaluated": evaluated_count,  # 参与评测的数量
            "feedback_mode": feedback_mode_count,  # 异常模式数量
            "correct": correct,
            "incorrect": evaluated_count - correct - failed,
            "failed": failed,
            "accuracy": correct / evaluated_count if evaluated_count > 0 else 0,
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
        保存结果到文件（保留原始列）

        Args:
            results: QuestionAnswer列表
            statistics: 统计信息
            output_path: 输出文件路径
        """
        # 转换为DataFrame（新增列）
        data = []
        for idx, qa in enumerate(results):
            data.append({
                "序号": idx + 1,
                "问题": qa.question,
                "知识库": qa.knowledge_base or "",
                "期望答案": qa.expected_answer,
                "MODEL_OUTPUT": qa.model_output or "",
                "FINAL_DISPLAY": qa.final_display or "",
                "IS_CORRECT": "N/A" if qa.is_correct is None else ("✓" if qa.is_correct else "✗"),
                "匹配类型": qa.match_type or "N/A",
                "错误信息": qa.error or "",
                "工作流运行ID": qa.workflow_run_id or "",
                "USED_API_KEY": qa.used_api_key or "",
                "是否评测": "是" if qa.is_evaluated else "否"
            })

        df = pd.DataFrame(data)

        # 保存Excel
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name="处理结果", index=False)

            # 添加统计信息sheet
            stats_data = []
            stats_data.append(["总数量", statistics.get("total", 0)])
            stats_data.append(["评测数量", statistics.get("evaluated", 0)])  # 新增
            stats_data.append(["异常模式数量", statistics.get("feedback_mode", 0)])  # 新增
            stats_data.append(["正确数量", statistics.get("correct", 0)])
            stats_data.append(["错误数量", statistics.get("incorrect", 0)])
            stats_data.append(["失败数量", statistics.get("failed", 0)])
            stats_data.append(["准确率", f"{statistics.get('accuracy', 0):.2%}"])
            stats_data.append(["成功率", f"{statistics.get('success_rate', 0):.2%}"])

            stats_df = pd.DataFrame(stats_data, columns=["指标", "数值"])
            stats_df.to_excel(writer, sheet_name="统计信息", index=False)

        print(f"\n结果已保存到: {output_path}")
