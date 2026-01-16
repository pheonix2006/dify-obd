"""工作流批处理器"""

import asyncio
import json
import logging
import os
from typing import Dict, Any, List, Optional

import httpx
import pandas as pd

from obd.client.dify_client import DifyWorkflowClient
from obd.comparator.answer_comparator import AnswerComparator
from obd.comparator.llm_comparator import LLMComparator
from obd.models import QuestionAnswer, WorkflowConfig, RoutingConfig, LLMEvalConfig
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
        client=None,
        llm_eval_config: Optional[LLMEvalConfig] = None
    ):
        self.config = config
        self.routing_config = routing_config or RoutingConfig()
        self.llm_eval_config = llm_eval_config or LLMEvalConfig()
        self.client = client or DifyWorkflowClient(config)
        self.comparator = AnswerComparator()
        self.llm_comparator = LLMComparator(self.llm_eval_config)

        # 初始化路由和评测组件
        self.routing = WorkflowRouting(config)
        self.evaluator = EvaluationBranch(comparison_method="auto")
        
        # 共享异步客户端
        self._async_client = httpx.AsyncClient(timeout=config.timeout)
        self._file_lock = asyncio.Lock()

    async def close(self):
        """关闭资源"""
        await self._async_client.aclose()
        if hasattr(self.client, 'close'):
            await self.client.close()

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

    def _load_results_from_excel(self, output_path: str) -> List[QuestionAnswer]:
        """从现有的Excel文件中加载已处理的结果"""
        if not os.path.exists(output_path):
            return []
        
        try:
            import pandas as pd
            df = pd.read_excel(output_path, sheet_name="处理结果")
            results = []
            for _, row in df.iterrows():
                # 尝试解析 IS_CORRECT
                is_correct = None
                if row.get("IS_CORRECT") == "✓":
                    is_correct = True
                elif row.get("IS_CORRECT") == "✗":
                    is_correct = False
                
                # 尝试还原 4级分类
                llm_category = None
                category_label = row.get("4级分类")
                from obd.models import AnswerCategory
                for cat in AnswerCategory:
                    if cat.label == category_label:
                        llm_category = cat.value
                        break
                
                qa = QuestionAnswer(
                    question=str(row.get("问题", "")),
                    expected_answer=str(row.get("期望答案", "")),
                    original_index=int(row.get("序号", 0)) - 1 if pd.notna(row.get("序号")) else None,
                    workflow_result=row.get("MODEL_OUTPUT", ""),
                    is_correct=is_correct,
                    match_type=row.get("匹配类型", ""),
                    workflow_run_id=row.get("工作流运行ID", ""),
                    error=row.get("错误信息") if pd.notna(row.get("错误信息")) and row.get("错误信息") != "" else None,
                    knowledge_base=row.get("知识库", ""),
                    model_output=row.get("MODEL_OUTPUT", ""),
                    final_display=row.get("FINAL_DISPLAY", ""),
                    is_evaluated=True if row.get("是否评测") == "是" else False,
                    used_api_key=row.get("USED_API_KEY", ""),
                )
                qa.llm_category = llm_category
                qa.llm_analysis = row.get("LLM 评测分析", "N/A" if row.get("LLM 评测分析") == "N/A" else row.get("LLM 评测分析"))
                qa.missing_info = row.get("缺失信息", "")
                
                results.append(qa)
            return results
        except Exception as e:
            logger.warning(f"读取现有结果文件失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def _save_incremental_all(self, results: List[QuestionAnswer], output_path: str):
        """增量保存所有当前结果"""
        async with self._file_lock:
            # 排序以保持顺序
            sorted_results = sorted(results, key=lambda x: x.original_index if x.original_index is not None else 0)
            stats = self.calculate_statistics(sorted_results)
            self.save_results(sorted_results, stats, output_path)

    async def process_row_with_routing(
        self,
        row: pd.Series,
        idx: int,
        total_rows: int,
        semaphore: Optional[asyncio.Semaphore] = None
    ) -> Optional[QuestionAnswer]:
        """
        处理单行数据（支持路由和分支）

        Args:
            row: DataFrame行
            idx: 行索引
            total_rows: 总行数
            semaphore: 并发控制信号量

        Returns:
            QuestionAnswer对象（如果跳过则返回None）
        """
        if semaphore:
            async with semaphore:
                return await self._process_row_logic(row, idx, total_rows)
        else:
            return await self._process_row_logic(row, idx, total_rows)

    async def _process_row_logic(
        self,
        row: pd.Series,
        idx: int,
        total_rows: int
    ) -> Optional[QuestionAnswer]:
        """单行处理的具体逻辑"""
        # 提取列值
        problem_val = row.get(self.routing_config.problem_value_column, "")
        if pd.isna(problem_val) or (isinstance(problem_val, str) and not problem_val.strip()):
            return None

        question = str(problem_val)
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
        qa.original_index = idx

        # 2. API调用（使用动态API Key）
        try:
            # 创建临时配置
            temp_config = WorkflowConfig(
                api_key=api_key,
                base_url=self.config.base_url,
                response_mode=self.config.response_mode,
                timeout=self.config.timeout,
                user=self.config.user,
                input_variable_name=self.config.input_variable_name,
                output_variable_name=self.config.output_variable_name
            )

            # 使用共享异步客户端
            temp_client = DifyWorkflowClient(temp_config, client=self._async_client)

            # 调用工作流
            inputs = {self.config.input_variable_name: question}
            result = await temp_client.execute_workflow(
                inputs,
                self.config.user,
                None
            )

            qa.workflow_run_id = result.get("task_id")
            actual_answer = result.get(self.config.output_variable_name, json.dumps(result, ensure_ascii=False))

        except Exception as e:
            qa.error = str(e)
            actual_answer = None

        # 3. 评测分支（完全依赖 LLM 评测）
        if actual_answer and not qa.error:
            qa.model_output = str(actual_answer)
            qa.final_display = str(actual_answer)

            # 判断是否评测模式
            is_eval_mode = True
            if answer_state is not None:
                if isinstance(answer_state, str):
                    is_eval_mode = answer_state.strip().lower() not in ("false", "0", "")
                elif isinstance(answer_state, bool):
                    is_eval_mode = answer_state
                elif isinstance(answer_state, (int, float)):
                    is_eval_mode = bool(answer_state)

            if not is_eval_mode:
                # 异常模式：使用反馈答案
                qa.is_evaluated = False
                if pd.notna(feedback_answer) and feedback_answer != "":
                    qa.final_display = str(feedback_answer)
            else:
                # 正常模式：使用 LLM 评测
                qa.is_evaluated = True
                if self.llm_eval_config.enabled:
                    llm_result = await self.llm_comparator.evaluate(
                        question=qa.question,
                        expected=str(expected_answer),
                        actual=actual_answer
                    )
                    qa.llm_analysis = llm_result.analysis
                    qa.llm_category = llm_result.category
                    qa.missing_info = llm_result.missing_info
                    qa.is_correct = llm_result.is_correct
                    qa.match_type = llm_result.category  # 使用4级分类作为匹配类型
                else:
                    # LLM 评测未启用，标记为未评测
                    qa.llm_analysis = "LLM 评测未启用"
                    qa.is_correct = False
                    qa.match_type = "llm_disabled"
        else:
            # API调用失败
            qa.model_output = str(actual_answer) if actual_answer is not None else None
            qa.final_display = str(actual_answer) if actual_answer is not None else None
            qa.is_evaluated = True

        # 实时打印结果
        self._print_result(qa, idx, total_rows)

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
            if qa.llm_category:
                from obd.models import AnswerCategory
                category = AnswerCategory(qa.llm_category).label
                status = "✓" if qa.is_correct else "✗"
                print(f"{prefix}")
                print(f"  {status} {category} (4级分类)")
                if qa.missing_info:
                    print(f"  缺失: {qa.missing_info}")
            else:
                print(f"{prefix}")
                print(f"  ↔ 未启用 LLM 评测")
        else:
            # 确保 final_display 是字符串且不为 None
            display_text = str(qa.final_display) if qa.final_display is not None else ""
            print(f"{prefix}")
            print(f"  ↔ 异常模式 - 使用反馈答案: {display_text[:50]}...")

    async def process_question(
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
            result = await self.client.execute_workflow(inputs, user, workflow_id)

            # 提取工作流运行ID
            qa.workflow_run_id = result.get("task_id")

            # 根据调试结果，聊天应用返回的answer字段包含回复内容
            # 如果没有该字段，返回原始响应
            if output_variable_name in result:
                qa.workflow_result = str(result[output_variable_name])
            else:
                qa.workflow_result = json.dumps(result, ensure_ascii=False)

        except Exception as e:
            qa.error = str(e)

        return qa

    async def process_excel(
        self,
        excel_path: str,
        output_path: Optional[str] = None,
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
            output_path: 输出文件路径（用于增量保存和恢复）
            question_column: 问题列名（兼容旧版）
            answer_column: 答案列名（兼容旧版）
            input_variable_name: 工作流输入变量名
            output_variable_name: 工作流输出变量名
            comparison_method: 答案对比方法
            start_row: 起始行（0-based）
            end_row: 结束行（不包含）
            delay: 每批次请求之间的最小延迟（秒）
            workflow_id: 工作流ID（可选）

        Returns:
            QuestionAnswer列表
        """
        df = self.load_excel(excel_path)

        # 检查必需的列（兼容新旧两种模式）
        is_new_mode = self._check_new_columns(df)

        if is_new_mode:
            print(f"使用新模式：路由分发 + 评测分支 (并发数: {self.config.max_workers})")
            return await self._process_excel_new_mode(df, start_row, end_row, delay, output_path)
        else:
            print(f"使用旧模式：单API Key + 全量评测 (并发数: {self.config.max_workers})")
            return await self._process_excel_legacy_mode(
                df,
                question_column,
                answer_column,
                input_variable_name,
                output_variable_name,
                comparison_method,
                start_row,
                end_row,
                delay,
                workflow_id,
                output_path
            )

    async def _process_excel_new_mode(
        self,
        df: pd.DataFrame,
        start_row: int,
        end_row: Optional[int],
        delay: float,
        output_path: Optional[str] = None
    ) -> List[QuestionAnswer]:
        """处理Excel（新模式）"""
        total_rows = len(df)
        if end_row is None or end_row > total_rows:
            end_row = total_rows

        print(f"共 {total_rows} 行，处理第 {start_row} 行到第 {end_row-1} 行")
        print("-" * 60)

        results = []
        processed_indices = set()
        
        # 加载现有结果实现支持断点续传
        if output_path and os.path.exists(output_path):
            existing_results = self._load_results_from_excel(output_path)
            if existing_results:
                results.extend(existing_results)
                # 记录已处理的问题索引
                processed_indices = {r.original_index for r in existing_results if r.original_index is not None}
                print(f"检测到断点：已从现有结果中加载了 {len(existing_results)} 条已处理记录。")
        
        # 确定真正需要处理的行
        remaining_indices = [i for i in range(start_row, end_row) if i not in processed_indices]
        
        if not remaining_indices:
            print("所有指定范围内的记录已在之前处理完成。")
            return results

        print(f"还需处理 {len(remaining_indices)} 条新记录")

        # 创建信号量
        semaphore = asyncio.Semaphore(self.config.max_workers)
        
        async def run_task(idx):
            row = df.iloc[idx]
            res = await self.process_row_with_routing(row, idx, total_rows, semaphore)
            if res:
                results.append(res)
                if output_path:
                    # 每完成一个就增量保存
                    await self._save_incremental_all(results, output_path)
            return res

        # 并发执行
        tasks = [run_task(idx) for idx in remaining_indices]
        await asyncio.gather(*tasks)
        
        # 排序并返回最终结果
        return sorted(results, key=lambda x: x.original_index if x.original_index is not None else 0)

    async def _process_excel_legacy_mode(
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
        workflow_id: Optional[str],
        output_path: Optional[str] = None
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
        processed_indices = set()
        
        # 加载现有结果实现支持断点续传
        if output_path and os.path.exists(output_path):
            existing_results = self._load_results_from_excel(output_path)
            if existing_results:
                results.extend(existing_results)
                processed_indices = {r.original_index for r in existing_results if r.original_index is not None}
                print(f"检测到断点：已从现有结果中加载了 {len(existing_results)} 条已处理记录。")
        
        remaining_indices = [i for i in range(start_row, end_row) if i not in processed_indices]
        
        if not remaining_indices:
            print("所有指定范围内的记录已在之前处理完成。")
            return results

        semaphore = asyncio.Semaphore(self.config.max_workers)

        async def process_task(idx):
            row = df.iloc[idx]
            question = str(row[question_column])
            expected_answer = str(row[answer_column])

            print(f"[{idx+1}/{total_rows}] 处理问题: {question[:50]}...")

            async with semaphore:
                # 处理问题
                qa = await self.process_question(
                    question=question,
                    input_variable_name=input_variable_name,
                    output_variable_name=output_variable_name,
                    comparison_method=comparison_method,
                    workflow_id=workflow_id
                )
                qa.expected_answer = expected_answer
                qa.original_index = idx

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
            if output_path:
                await self._save_incremental_all(results, output_path)
            return qa

        tasks = [process_task(i) for i in remaining_indices]
        await asyncio.gather(*tasks)

        return sorted(results, key=lambda x: x.original_index if x.original_index is not None else 0)

    def calculate_statistics(self, results: List[QuestionAnswer]) -> Dict[str, Any]:
        """
        计算统计信息（排除异常模式）

        Args:
            results: QuestionAnswer列表

        Returns:
            统计信息字典
        """
        from obd.models import AnswerCategory

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

        # 4级分类统计
        category_stats = {}
        for qa in evaluated_results:
            if qa.llm_category:
                category_stats[qa.llm_category] = category_stats.get(qa.llm_category, 0) + 1

        # 计算4级分类的占比
        category_percentages = {}
        if evaluated_count > 0:
            for category, count in category_stats.items():
                category_percentages[category] = count / evaluated_count

        # 4级分类详情
        category_details = {}
        for category in AnswerCategory:
            category_details[category.value] = {
                "count": category_stats.get(category.value, 0),
                "percentage": category_percentages.get(category.value, 0.0),
                "label": category.label
            }

        # 按匹配类型统计（兼容旧版本）
        match_type_stats = {}
        for qa in evaluated_results:
            if qa.match_type:
                match_type_stats[qa.match_type] = match_type_stats.get(qa.match_type, 0) + 1

        statistics = {
            "total": total,
            "evaluated": evaluated_count,  # 参与评测的数量
            "feedback_mode": feedback_mode_count,  # 异常模式数量
            # 2级分类
            "correct": correct,
            "incorrect": evaluated_count - correct - failed,
            "failed": failed,
            "accuracy": correct / evaluated_count if evaluated_count > 0 else 0,
            "success_rate": (total - failed) / total if total > 0 else 0,
            # 4级分类
            "category_stats": category_stats,
            "category_percentages": category_percentages,
            "category_details": category_details,
            # 兼容旧版本
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
        from obd.models import AnswerCategory

        # 转换为DataFrame（新增列）
        data = []
        for qa in results:
            # 4级分类标签
            category_label = "N/A"
            if qa.llm_category:
                try:
                    category_label = AnswerCategory(qa.llm_category).label
                except (ValueError, AttributeError):
                    category_label = str(qa.llm_category)

            display_idx = (qa.original_index + 1) if qa.original_index is not None else len(data) + 1

            data.append({
                "序号": display_idx,
                "问题": qa.question,
                "知识库": qa.knowledge_base or "",
                "期望答案": qa.expected_answer,
                "MODEL_OUTPUT": qa.model_output or "",
                "FINAL_DISPLAY": qa.final_display or "",
                "IS_CORRECT": "N/A" if qa.is_correct is None else ("✓" if qa.is_correct else "✗"),
                "4级分类": category_label,
                "缺失信息": qa.missing_info or "",
                "匹配类型": qa.match_type or "N/A",
                "错误信息": qa.error or "",
                "工作流运行ID": qa.workflow_run_id or "",
                "USED_API_KEY": qa.used_api_key or "",
                "是否评测": "是" if qa.is_evaluated else "否",
                "LLM 评测分析": qa.llm_analysis or "N/A"
            })

        # 确保按序号排序
        df = pd.DataFrame(data)
        if "序号" in df.columns:
            df = df.sort_values("序号")

        # 保存Excel
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name="处理结果", index=False)

            # 添加统计信息sheet
            stats_data = []
            stats_data.append(["总数量", statistics.get("total", 0)])
            stats_data.append(["评测数量", statistics.get("evaluated", 0)])
            stats_data.append(["异常模式数量", statistics.get("feedback_mode", 0)])
            stats_data.append(["", ""])  # 分隔行
            stats_data.append(["--- 2级分类 ---", ""])
            stats_data.append(["正确数量", statistics.get("correct", 0)])
            stats_data.append(["错误数量", statistics.get("incorrect", 0)])
            stats_data.append(["失败数量", statistics.get("failed", 0)])
            stats_data.append(["准确率", f"{statistics.get('accuracy', 0):.2%}"])
            stats_data.append(["成功率", f"{statistics.get('success_rate', 0):.2%}"])
            stats_data.append(["", ""])  # 分隔行
            stats_data.append(["--- 4级分类 ---", ""])
            # 4级分类详情
            for category in AnswerCategory:
                details = statistics.get("category_details", {}).get(category.value, {})
                stats_data.append([
                    details.get("label", category.label),
                    f"{details.get('count', 0)} ({details.get('percentage', 0):.2%})"
                ])

            stats_df = pd.DataFrame(stats_data, columns=["指标", "数值"])
            stats_df.to_excel(writer, sheet_name="统计信息", index=False)

        print(f"\n结果已保存到: {output_path}")
