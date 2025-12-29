"""
Dify工作流批处理程序
功能：从Excel读取问题，调用Dify工作流API，对比答案并计算准确率
"""

import os
import json
import time
import requests
import pandas as pd
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import re
from pathlib import Path


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
    match_type: Optional[str] = None  # exact, fuzzy, semantic
    workflow_run_id: Optional[str] = None
    error: Optional[str] = None


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
        user: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行工作流

        Args:
            inputs: 工作流输入参数
            user: 用户标识（可选）

        Returns:
            工作流执行结果
        """
        url = f"{self.config.base_url}/workflows/run"

        payload = {
            "inputs": inputs,
            "response_mode": self.config.response_mode,
            "user": user or self.config.user
        }

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


class AnswerComparator:
    """答案对比器"""

    @staticmethod
    def exact_match(answer1: str, answer2: str) -> bool:
        """精确匹配"""
        return str(answer1).strip().lower() == str(answer2).strip().lower()

    @staticmethod
    def fuzzy_match(answer1: str, answer2: str, threshold: float = 0.8) -> bool:
        """
        模糊匹配（基于相似度）

        Args:
            answer1: 答案1
            answer2: 答案2
            threshold: 相似度阈值

        Returns:
            是否匹配
        """
        from difflib import SequenceMatcher

        answer1 = str(answer1).strip()
        answer2 = str(answer2).strip()

        if len(answer1) == 0 or len(answer2) == 0:
            return False

        similarity = SequenceMatcher(None, answer1, answer2).ratio()
        return similarity >= threshold

    @staticmethod
    def keyword_match(answer1: str, answer2: str) -> bool:
        """
        关键词匹配（检查是否包含关键信息）

        Args:
            answer1: 答案1（通常用于查找关键词）
            answer2: 答案2（通常用于检查是否包含）

        Returns:
            是否匹配
        """
        answer1 = str(answer1).strip().lower()
        answer2 = str(answer2).strip().lower()

        # 提取answer1中的关键词
        keywords = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+|[0-9]+', answer1)

        # 检查这些关键词是否在answer2中出现
        for keyword in keywords:
            if len(keyword) > 1 and keyword in answer2:
                return True

        return False

    @staticmethod
    def compare(
        expected: str,
        actual: str,
        method: str = "auto"
    ) -> tuple[bool, str]:
        """
        对比答案

        Args:
            expected: 期望答案
            actual: 实际答案
            method: 匹配方法 (exact, fuzzy, keyword, auto)

        Returns:
            (是否匹配, 匹配类型)
        """
        if not expected or not actual:
            return False, "empty"

        # 空白匹配
        if not expected.strip() and not actual.strip():
            return True, "empty_match"

        if method == "exact":
            is_match = AnswerComparator.exact_match(expected, actual)
            return is_match, "exact"

        elif method == "fuzzy":
            is_match = AnswerComparator.fuzzy_match(expected, actual)
            return is_match, "fuzzy"

        elif method == "keyword":
            is_match = AnswerComparator.keyword_match(expected, actual)
            return is_match, "keyword"

        elif method == "auto":
            # 自动选择匹配方法
            # 1. 先尝试精确匹配
            if AnswerComparator.exact_match(expected, actual):
                return True, "exact"

            # 2. 尝试模糊匹配
            if AnswerComparator.fuzzy_match(expected, actual):
                return True, "fuzzy"

            # 3. 尝试关键词匹配
            if AnswerComparator.keyword_match(expected, actual):
                return True, "keyword"

            return False, "no_match"

        return False, "unknown"


class WorkflowBatchProcessor:
    """工作流批处理器"""

    def __init__(self, config: WorkflowConfig):
        self.config = config
        self.client = DifyWorkflowClient(config)
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

        df = pd.read_excel(excel_path)
        return df

    def process_question(
        self,
        question: str,
        input_variable_name: str = "query",
        output_variable_name: str = "answer",
        comparison_method: str = "auto",
        user: Optional[str] = None
    ) -> QuestionAnswer:
        """
        处理单个问题

        Args:
            question: 问题文本
            input_variable_name: 工作流输入变量名
            output_variable_name: 工作流输出变量名
            comparison_method: 答案对比方法
            user: 用户标识

        Returns:
            QuestionAnswer对象
        """
        qa = QuestionAnswer(question=question, expected_answer="")

        try:
            # 调用工作流
            inputs = {input_variable_name: question}
            result = self.client.execute_workflow(inputs, user)

            # 提取工作流运行ID
            qa.workflow_run_id = result.get("workflow_run_id") or result.get("task_id")

            # 提取输出结果
            data = result.get("data", {})
            outputs = data.get("outputs", {})

            if output_variable_name in outputs:
                qa.workflow_result = str(outputs[output_variable_name])
            elif len(outputs) > 0:
                # 如果指定的输出变量不存在，取第一个输出
                qa.workflow_result = str(list(outputs.values())[0])
            else:
                qa.workflow_result = json.dumps(data, ensure_ascii=False)

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
        delay: float = 0.5
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
                comparison_method=comparison_method
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


def main():
    """主函数示例"""
    import configparser

    # 从配置文件加载配置
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')

    # 创建工作流配置
    workflow_config = WorkflowConfig(
        api_key=config.get('Dify', 'api_key'),
        base_url=config.get('Dify', 'base_url', fallback='https://api.dify.ai/v1'),
        response_mode=config.get('Dify', 'response_mode', fallback='blocking'),
        timeout=config.getint('Dify', 'timeout', fallback=60)
    )

    # 创建批处理器
    processor = WorkflowBatchProcessor(workflow_config)

    # 处理Excel
    excel_path = config.get('Excel', 'file_path')
    question_column = config.get('Excel', 'question_column', fallback='question')
    answer_column = config.get('Excel', 'answer_column', fallback='answer')
    input_variable_name = config.get('Workflow', 'input_variable_name', fallback='query')
    output_variable_name = config.get('Workflow', 'output_variable_name', fallback='answer')
    comparison_method = config.get('Workflow', 'comparison_method', fallback='auto')
    delay = config.getfloat('Workflow', 'delay', fallback=0.5)

    print("开始批处理...")
    print("=" * 60)

    results = processor.process_excel(
        excel_path=excel_path,
        question_column=question_column,
        answer_column=answer_column,
        input_variable_name=input_variable_name,
        output_variable_name=output_variable_name,
        comparison_method=comparison_method,
        delay=delay
    )

    # 计算统计
    statistics = processor.calculate_statistics(results)

    print("\n" + "=" * 60)
    print("统计信息:")
    print(f"总数量: {statistics['total']}")
    print(f"正确: {statistics['correct']}")
    print(f"错误: {statistics['incorrect']}")
    print(f"失败: {statistics['failed']}")
    print(f"准确率: {statistics['accuracy']:.2%}")
    print(f"成功率: {statistics['success_rate']:.2%}")

    if statistics['match_type_stats']:
        print("\n匹配类型统计:")
        for match_type, count in statistics['match_type_stats'].items():
            print(f"  {match_type}: {count}")

    # 保存结果
    output_path = config.get('Output', 'file_path', fallback='results.xlsx')
    processor.save_results(results, statistics, output_path)

    print("\n处理完成！")


if __name__ == "__main__":
    main()
