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
from obd.models import (
    QuestionAnswer, WorkflowConfig, RoutingConfig, LLMEvalConfig,
    ExecutionModeConfig, StandardSchemaConfig, RAGEvalSchemaConfig
)
from obd.processor.routing import WorkflowRouting
from obd.processor.evaluation import EvaluationBranch
from obd.utils.rag_response_parser import RAGResponseParser
from obd.utils.eval_recorder import EvalRecorder

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
        llm_eval_config: Optional[LLMEvalConfig] = None,
        execution_mode_config: Optional['ExecutionModeConfig'] = None,  # 新增
        standard_schema_config: Optional['StandardSchemaConfig'] = None,  # 新增
        rag_eval_schema_config: Optional['RAGEvalSchemaConfig'] = None  # 新增
    ):
        self.config = config
        self.routing_config = routing_config or RoutingConfig()
        self.llm_eval_config = llm_eval_config or LLMEvalConfig()
        self.client = client or DifyWorkflowClient(config)
        self.comparator = AnswerComparator()
        self.llm_comparator = LLMComparator(self.llm_eval_config)

        # 新增：保存模式配置
        self.execution_mode_config = execution_mode_config
        self.standard_schema_config = standard_schema_config
        self.rag_eval_schema_config = rag_eval_schema_config

        # 新增：创建评测记录器（如果启用）
        self.eval_recorder: Optional[EvalRecorder] = None
        if self.llm_eval_config.eval_record_enabled:
            self.eval_recorder = EvalRecorder(
                base_dir=self.llm_eval_config.eval_record_path,
                enabled=True
            )
            logger.info(f"评测记录器已启用，记录目录: {self.eval_recorder.get_session_dir()}")

        # 新增：创建 SemanticJudge（用于 rag_eval 模式），传递记录器
        if llm_eval_config:
            from ..comparator.semantic_judge import SemanticJudge
            self.semantic_judge = SemanticJudge(
                llm_eval_config,
                recorder=self.eval_recorder  # 传递记录器
            )
        else:
            self.semantic_judge = None

        # 初始化路由和评测组件
        self.routing = WorkflowRouting(config)
        self.evaluator = EvaluationBranch(comparison_method="auto")

        # 共享异步客户端
        self._async_client = httpx.AsyncClient(timeout=config.timeout)
        self._file_lock = asyncio.Lock()
        self._save_lock = asyncio.Lock()

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

            # 自动检测 sheet 名称，支持两种模式
            xl_file = pd.ExcelFile(output_path)
            sheet_name = None
            detected_mode = None

            # 按优先级检测 sheet 名称
            if "RAG 评测结果" in xl_file.sheet_names:
                sheet_name = "RAG 评测结果"
                detected_mode = "RAG"
            elif "处理结果" in xl_file.sheet_names:
                sheet_name = "处理结果"
                detected_mode = "STANDARD"
            else:
                logger.warning(
                    f"输出文件中未找到预期的结果 sheet，"
                    f"可用的 sheets: {xl_file.sheet_names}"
                )
                return []

            logger.info(f"检测到 {detected_mode} 模式的结果文件，正在加载...")
            df = pd.read_excel(output_path, sheet_name=sheet_name)

            # 根据检测到的模式调用对应的加载方法
            if detected_mode == "RAG":
                return self._load_rag_results_from_df(df)
            else:
                return self._load_standard_results_from_df(df)

        except Exception as e:
            logger.warning(f"读取现有结果文件失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _load_rag_results_from_df(self, df: 'pd.DataFrame') -> List[QuestionAnswer]:
        """从 DataFrame 加载 RAG 评测结果"""
        from obd.models import AnswerCategory

        results = []
        for _, row in df.iterrows():
            # 解析是否正确
            is_correct = None
            correct_val = row.get("是否正确")
            if pd.notna(correct_val):
                if correct_val == "✓":
                    is_correct = True
                elif correct_val == "✗":
                    is_correct = False

            # 解析 4级分类
            llm_category = None
            category_label = row.get("4级分类")
            if pd.notna(category_label) and category_label != "N/A":
                for cat in AnswerCategory:
                    if cat.label == category_label:
                        llm_category = cat.value
                        break

            # 解析 IS_RAG_FORMAT
            is_rag_format = False
            rag_format_val = row.get("IS_RAG_FORMAT")
            if pd.notna(rag_format_val) and rag_format_val == "是":
                is_rag_format = True

            qa = QuestionAnswer(
                question=str(row.get("问题", "")),
                expected_answer="",  # RAG 模式不需要
                original_index=int(row.get("序号", 0)) - 1 if pd.notna(row.get("序号")) else None,
                workflow_result=row.get("实际回答", ""),
                is_correct=is_correct,
                match_type="",
                error=row.get("错误信息") if pd.notna(row.get("错误信息")) and row.get("错误信息") != "" else None,
            )

            # RAG 特有字段恢复
            extracted_val = row.get("EXTRACTED_QUESTION", "")
            qa.extracted_question = extracted_val if pd.notna(extracted_val) else None
            rerank_val = row.get("RERANK_SOURCES", "")
            qa.rerank_sources = rerank_val if pd.notna(rerank_val) else None
            llm_ans_val = row.get("LLM_ANSWER", "")
            qa.llm_answer = llm_ans_val if pd.notna(llm_ans_val) else None
            qa.is_rag_format = is_rag_format
            scope_val = row.get("评测范围", "")
            qa.scope = scope_val if pd.notna(scope_val) else None
            ref_val = row.get("上一版回答", "")
            qa.ref_answer = ref_val if pd.notna(ref_val) else None
            history_val = row.get("历史评价", "")
            qa.history_eval = history_val if pd.notna(history_val) else None
            improvement_val = row.get("改进分析", "N/A")
            qa.improvement_analysis = improvement_val if pd.notna(improvement_val) else None
            important_val = row.get("重要信息识别", "")
            qa.important_info = important_val if pd.notna(important_val) else None

            # 通用字段
            qa.llm_category = llm_category
            qa.llm_analysis = row.get("LLM 评测分析", "N/A")
            qa.missing_info = row.get("缺失信息", "")

            results.append(qa)

        return results

    def _load_standard_results_from_df(self, df: 'pd.DataFrame') -> List[QuestionAnswer]:
        """从 DataFrame 加载标准评测结果"""
        from obd.models import AnswerCategory

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
            if pd.notna(category_label):
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
            llm_analysis_val = row.get("LLM 评测分析", "N/A")
            qa.llm_analysis = "N/A" if llm_analysis_val == "N/A" else llm_analysis_val
            qa.missing_info = row.get("缺失信息", "")

            results.append(qa)

        return results

    async def _save_incremental_all(self, results: List[QuestionAnswer], output_path: str):
        """增量保存所有当前结果"""
        async with self._file_lock:
            # 排序以保持顺序
            sorted_results = sorted(results, key=lambda x: x.original_index if x.original_index is not None else 0)
            stats = self.calculate_statistics(sorted_results)
            self.save_results(sorted_results, stats, output_path)

    async def _results_saver(
        self,
        result_queue: 'asyncio.Queue',
        all_results: List[QuestionAnswer],
        output_path: str,
        stop_event: 'asyncio.Event'
    ) -> None:
        """
        后台保存任务，从队列中取出结果并累积保存
        
        使用异步队列和锁保护并发场景下的结果累积，避免竞争条件。
        
        Args:
            result_queue: 存放已完成结果的队列
            all_results: 累积所有结果的列表（共享可变状态）
            output_path: 输出文件路径
            stop_event: 停止事件
        """
        while not stop_event.is_set():
            try:
                # 等待新结果，超时 0.5 秒检查一次停止事件
                new_result = await asyncio.wait_for(result_queue.get(), timeout=0.5)

                if new_result is not None:
                    async with self._save_lock:
                        all_results.append(new_result)
                        # 立即保存所有累积的结果
                        await self._save_incremental_all(all_results, output_path)
                
                # 标记任务完成，允许 join() 继续
                result_queue.task_done()

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"保存结果时出错: {e}")
                # 即使出错也要标记任务完成
                try:
                    result_queue.task_done()
                except:
                    pass

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

        # 3. RAG响应解析（新增）
        answer_for_eval = ""
        if actual_answer and not qa.error:
            # 解析RAG格式
            parsed = RAGResponseParser.parse(str(actual_answer))

            qa.extracted_question = parsed.question if parsed.question else None
            qa.rerank_sources = parsed.rerank_sources if parsed.rerank_sources else None
            qa.llm_answer = parsed.llm_answer if parsed.llm_answer else None
            qa.is_rag_format = parsed.is_valid_format

            # 如果成功解析，使用llm_answer进行评测
            if parsed.is_valid_format and parsed.llm_answer:
                answer_for_eval = parsed.llm_answer
            else:
                answer_for_eval = str(actual_answer)

        # 4. 评测分支（完全依赖 LLM 评测）
        if actual_answer and not qa.error:
            qa.model_output = str(actual_answer)  # 原始完整响应
            qa.final_display = answer_for_eval  # 用于展示和评测的答案

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
                        actual=answer_for_eval  # 使用解析后的答案
                    )
                    qa.llm_analysis = llm_result.analysis
                    qa.llm_category = llm_result.category
                    qa.missing_info = llm_result.missing_info
                    qa.important_info = llm_result.important_info
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

        根据配置的模式选择处理逻辑：
        - standard: 标准问答模式
        - rag_eval: RAG 语义评测模式

        Args:
            excel_path: Excel文件路径
            output_path: 输出文件路径（用于增量保存和恢复）
            question_column: 问题列名（兼容旧版，standard模式使用）
            answer_column: 答案列名（兼容旧版，standard模式使用）
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

        # 根据配置的模式选择处理逻辑
        if self.execution_mode_config and self.execution_mode_config.mode == "rag_eval":
            print(f"使用 RAG 语义评测模式 (并发数: {self.config.max_workers})")
            return await self._process_excel_rag_eval_mode(
                df, start_row, end_row, delay, output_path
            )
        else:
            # 默认使用 standard 模式（兼容旧逻辑）
            mode = "standard"
            if self.execution_mode_config:
                mode = self.execution_mode_config.mode
            print(f"使用 {mode} 模式 (并发数: {self.config.max_workers})")
            return await self._process_excel_standard_mode(
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

        # 创建结果队列和停止事件
        result_queue: 'asyncio.Queue[Optional[QuestionAnswer]]' = asyncio.Queue()
        stop_saver_event = asyncio.Event()

        # 启动后台保存任务
        saver_task = None
        if output_path:
            saver_task = asyncio.create_task(
                self._results_saver(result_queue, results, output_path, stop_saver_event)
            )

        # 创建信号量
        semaphore = asyncio.Semaphore(self.config.max_workers)
        
        async def run_task(idx):
            row = df.iloc[idx]
            res = await self.process_row_with_routing(row, idx, total_rows, semaphore)
            if res:
                # 将结果放入队列（由后台保存任务处理）
                await result_queue.put(res)
            return res

        # 并发执行
        tasks = [run_task(idx) for idx in remaining_indices]
        await asyncio.gather(*tasks)

        # 等待所有结果都被保存
        if output_path and saver_task:
            # 等待队列清空
            await result_queue.join()

            # 停止后台保存任务
            stop_saver_event.set()

            # 等待保存任务完成
            try:
                await asyncio.wait_for(saver_task, timeout=5.0)
            except asyncio.TimeoutError:
                saver_task.cancel()
                try:
                    await saver_task
                except asyncio.CancelledError:
                    pass
        
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

        # 创建结果队列和停止事件
        result_queue: 'asyncio.Queue[Optional[QuestionAnswer]]' = asyncio.Queue()
        stop_saver_event = asyncio.Event()

        # 启动后台保存任务
        saver_task = None
        if output_path:
            saver_task = asyncio.create_task(
                self._results_saver(result_queue, results, output_path, stop_saver_event)
            )

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
            
            # 将结果放入队列（由后台保存任务处理）
            await result_queue.put(qa)
            return qa

        tasks = [process_task(i) for i in remaining_indices]
        await asyncio.gather(*tasks)

        # 等待所有结果都被保存
        if output_path and saver_task:
            # 等待队列清空
            await result_queue.join()

            # 停止后台保存任务
            stop_saver_event.set()

            # 等待保存任务完成
            try:
                await asyncio.wait_for(saver_task, timeout=5.0)
            except asyncio.TimeoutError:
                saver_task.cancel()
                try:
                    await saver_task
                except asyncio.CancelledError:
                    pass

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
        保存结果到文件（根据模式选择输出格式）

        Args:
            results: QuestionAnswer列表
            statistics: 统计信息
            output_path: 输出文件路径
        """
        from obd.models import AnswerCategory

        # 判断当前模式
        is_rag_eval_mode = (
            self.execution_mode_config and
            self.execution_mode_config.mode == "rag_eval"
        )

        if is_rag_eval_mode:
            self._save_results_rag_eval(results, statistics, output_path)
        else:
            self._save_results_standard(results, statistics, output_path)

    def _save_results_standard(
        self,
        results: List[QuestionAnswer],
        statistics: Dict[str, Any],
        output_path: str
    ):
        """保存标准模式结果"""
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
                # 新增列：RAG响应解析结果
                "EXTRACTED_QUESTION": qa.extracted_question or "",
                "RERANK_SOURCES": qa.rerank_sources or "",
                "LLM_ANSWER": qa.llm_answer or "",
                "IS_RAG_FORMAT": "是" if qa.is_rag_format else "否",
                # 原有列
                "MODEL_OUTPUT": qa.model_output or "",
                "FINAL_DISPLAY": qa.final_display or "",
                "IS_CORRECT": "N/A" if qa.is_correct is None else ("✓" if qa.is_correct else "✗"),
                "4级分类": category_label,
                "缺失信息": qa.missing_info or "",
                "重要信息识别": qa.important_info or "",
                "匹配类型": qa.match_type or "N/A",
                "错误信息": qa.error or "",
                "工作流运行ID": qa.workflow_run_id or "",
                "USED_API_KEY": qa.used_api_key or "",
                "是否评测": "是" if qa.is_evaluated else "否",
                "LLM 评测分析": qa.llm_analysis or "N/A",
                "LLM 评测提示词": qa.llm_eval.prompt if (qa.llm_eval and qa.llm_eval.prompt) else ""
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

    def _save_results_rag_eval(
        self,
        results: List[QuestionAnswer],
        statistics: Dict[str, Any],
        output_path: str
    ):
        """保存 RAG 评测模式结果"""
        from obd.models import AnswerCategory

        # 转换为DataFrame（RAG 模式特定格式）
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
                # 新增列：RAG响应解析结果
                "EXTRACTED_QUESTION": qa.extracted_question or "",
                "RERANK_SOURCES": qa.rerank_sources or "",
                "LLM_ANSWER": qa.llm_answer or "",
                "IS_RAG_FORMAT": "是" if qa.is_rag_format else "否",
                # 原有列
                "评测范围": qa.scope or "",
                "上一版回答": qa.ref_answer or "",
                "实际回答": qa.workflow_result or "",
                "历史评价": qa.history_eval or "",
                "4级分类": category_label,
                "改进分析": qa.improvement_analysis or "N/A",
                "是否正确": "N/A" if qa.is_correct is None else ("✓" if qa.is_correct else "✗"),
                "缺失信息": qa.missing_info or "",
                "重要信息识别": qa.important_info or "",
                "LLM 评测分析": qa.llm_analysis or "N/A",
                "LLM 评测提示词": qa.llm_eval.prompt if (qa.llm_eval and qa.llm_eval.prompt) else "",
                "错误信息": qa.error or ""
            })

        # 确保按序号排序
        df = pd.DataFrame(data)
        if "序号" in df.columns:
            df = df.sort_values("序号")

        # 保存Excel
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name="RAG 评测结果", index=False)

            # 添加统计信息sheet
            stats_data = []
            stats_data.append(["总数量", statistics.get("total", 0)])
            stats_data.append(["评测数量", statistics.get("evaluated", 0)])
            stats_data.append(["", ""])  # 分隔行
            stats_data.append(["--- 2级分类 ---", ""])
            stats_data.append(["正确数量", statistics.get("correct", 0)])
            stats_data.append(["错误数量", statistics.get("incorrect", 0)])
            stats_data.append(["失败数量", statistics.get("failed", 0)])
            stats_data.append(["准确率", f"{statistics.get('accuracy', 0):.2%}"])
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

        print(f"\nRAG 评测结果已保存到: {output_path}")


    async def _process_excel_standard_mode(
        self,
        df: pd.DataFrame,
        question_column: str = "question",
        answer_column: str = "answer",
        input_variable_name: str = "query",
        output_variable_name: str = "answer",
        comparison_method: str = "auto",
        start_row: int = 0,
        end_row: Optional[int] = None,
        delay: float = 0.5,
        workflow_id: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> List[QuestionAnswer]:
        """
        标准问答模式处理逻辑

        使用现有的处理逻辑，保持向后兼容。
        """
        # 检查是否使用新的路由模式
        is_new_mode = self._check_new_columns(df)

        if is_new_mode:
            print(f"检测到路由配置列，使用路由分发 + 评测分支模式")
            return await self._process_excel_new_mode(df, start_row, end_row, delay, output_path)
        else:
            print(f"使用传统模式：单API Key + 全量评测")
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

    async def _process_excel_rag_eval_mode(
        self,
        df: pd.DataFrame,
        start_row: int = 0,
        end_row: Optional[int] = None,
        delay: float = 0.5,
        output_path: Optional[str] = None
    ) -> List[QuestionAnswer]:
        """
        RAG 语义评测模式处理逻辑

        这是新的处理逻辑，专门处理 RAG 评测场景。
        """
        schema = self.rag_eval_schema_config

        # 验证必需列
        required_columns = [
            schema.col_question,
            schema.col_scope,
            schema.col_ref_answer,
            schema.col_history_eval
        ]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(
                f"RAG 评测模式缺少必需列: {', '.join(missing_columns)}\n"
                f"请检查 Excel 文件或配置文件中的 [SCHEMA_RAG_EVAL] 设置。"
            )

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

        # 如果有输出路径，使用队列+后台保存模式
        if output_path:
            # 创建结果队列和停止事件
            result_queue: 'asyncio.Queue[Optional[QuestionAnswer]]' = asyncio.Queue()
            stop_saver_event = asyncio.Event()

            # 启动后台保存任务
            saver_task = asyncio.create_task(
                self._results_saver(result_queue, results, output_path, stop_saver_event)
            )

            async def run_task(idx):
                row = df.iloc[idx]
                try:
                    # 提取列值
                    question = str(row[schema.col_question])
                    scope = row.get(schema.col_scope, "")
                    ref_answer = row.get(schema.col_ref_answer, "")
                    history_eval = row.get(schema.col_history_eval, "")

                    print(f"[{idx+1}/{total_rows}] 处理问题: {question[:50]}...")

                    # 异步操作 - 使用信号量保护
                    async with semaphore:
                        # 调用 Dify API 获取实际回答
                        workflow_result = await self._call_dify_api_for_rag(question)

                        # RAG响应解析（新增）
                        answer_for_eval = workflow_result
                        extracted_question = None
                        rerank_sources = None
                        llm_answer = None
                        is_rag_format = False

                        if workflow_result:
                            parsed = RAGResponseParser.parse(str(workflow_result))

                            extracted_question = parsed.question if parsed.question else None
                            rerank_sources = parsed.rerank_sources if parsed.rerank_sources else None
                            llm_answer = parsed.llm_answer if parsed.llm_answer else None
                            is_rag_format = parsed.is_valid_format

                            # 如果成功解析，使用llm_answer进行评测
                            if parsed.is_valid_format and parsed.llm_answer:
                                answer_for_eval = parsed.llm_answer

                        # 使用 SemanticJudge 进行评测
                        if self.semantic_judge:
                            eval_result = await self.semantic_judge.evaluate_with_context(
                                question=question,
                                actual_answer=answer_for_eval,  # 使用解析后的纯净答案
                                rerank_sources=rerank_sources,  # 传递 rerank 片段
                                scope=scope,
                                ref_answer=ref_answer,
                                history_eval=history_eval,
                                question_index=idx  # 传递问题索引用于记录
                            )

                    # 结果处理（不需要并发控制）
                    # 创建 QuestionAnswer 对象
                    if self.semantic_judge:
                        qa = QuestionAnswer(
                            question=question,
                            expected_answer=ref_answer,  # 使用上一版回答作为期望
                            original_index=idx,
                            workflow_result=workflow_result,
                            is_correct=eval_result.is_correct,
                            llm_analysis=eval_result.analysis,
                            llm_category=eval_result.category,
                            missing_info=eval_result.missing_info,
                            important_info=eval_result.important_info,
                            scope=scope,
                            ref_answer=ref_answer,
                            history_eval=history_eval,
                            improvement_analysis=eval_result.version_analysis,  # 版本对比分析
                            # 新增字段：RAG响应解析结果
                            extracted_question=extracted_question,
                            rerank_sources=rerank_sources,
                            llm_answer=llm_answer,
                            is_rag_format=is_rag_format
                        )
                    else:
                        # 未配置评测器，仅记录回答
                        qa = QuestionAnswer(
                            question=question,
                            expected_answer=ref_answer,
                            original_index=idx,
                            workflow_result=workflow_result,
                            is_evaluated=False,
                            # 新增字段：RAG响应解析结果
                            extracted_question=extracted_question,
                            rerank_sources=rerank_sources,
                            llm_answer=llm_answer,
                            is_rag_format=is_rag_format
                        )

                    # 将结果放入队列（由后台保存任务处理）
                    await result_queue.put(qa)
                    return qa

                except Exception as e:
                    logger.error(f"处理第 {idx} 行时出错: {str(e)}")
                    # 创建错误记录
                    qa = QuestionAnswer(
                        question=row.get(schema.col_question, ""),
                        expected_answer="",
                        original_index=idx,
                        error=str(e)
                    )
                    # 错误结果也放入队列
                    await result_queue.put(qa)
                    return qa

            # 并发执行
            tasks = [run_task(idx) for idx in remaining_indices]
            await asyncio.gather(*tasks)

            # 等待所有结果都被保存
            # 等待队列清空
            await result_queue.join()

            # 停止后台保存任务
            stop_saver_event.set()

            # 等待保存任务完成
            try:
                await asyncio.wait_for(saver_task, timeout=5.0)
            except asyncio.TimeoutError:
                saver_task.cancel()
                try:
                    await saver_task
                except asyncio.CancelledError:
                    pass
        else:
            # 无输出路径时，直接使用锁保护 results 列表
            async def run_task_no_save(idx):
                row = df.iloc[idx]
                try:
                    # 提取列值
                    question = str(row[schema.col_question])
                    scope = row.get(schema.col_scope, "")
                    ref_answer = row.get(schema.col_ref_answer, "")
                    history_eval = row.get(schema.col_history_eval, "")

                    print(f"[{idx+1}/{total_rows}] 处理问题: {question[:50]}...")

                    # 异步操作 - 使用信号量保护
                    async with semaphore:
                        # 调用 Dify API 获取实际回答
                        workflow_result = await self._call_dify_api_for_rag(question)

                        # RAG响应解析（新增）
                        answer_for_eval = workflow_result
                        extracted_question = None
                        rerank_sources = None
                        llm_answer = None
                        is_rag_format = False

                        if workflow_result:
                            parsed = RAGResponseParser.parse(str(workflow_result))

                            extracted_question = parsed.question if parsed.question else None
                            rerank_sources = parsed.rerank_sources if parsed.rerank_sources else None
                            llm_answer = parsed.llm_answer if parsed.llm_answer else None
                            is_rag_format = parsed.is_valid_format

                            # 如果成功解析，使用llm_answer进行评测
                            if parsed.is_valid_format and parsed.llm_answer:
                                answer_for_eval = parsed.llm_answer

                        # 使用 SemanticJudge 进行评测
                        if self.semantic_judge:
                            eval_result = await self.semantic_judge.evaluate_with_context(
                                question=question,
                                actual_answer=answer_for_eval,  # 使用解析后的纯净答案
                                rerank_sources=rerank_sources,  # 传递 rerank 片段
                                scope=scope,
                                ref_answer=ref_answer,
                                history_eval=history_eval,
                                question_index=idx  # 传递问题索引用于记录
                            )

                    # 结果处理（不需要并发控制）
                    # 创建 QuestionAnswer 对象
                    if self.semantic_judge:
                        qa = QuestionAnswer(
                            question=question,
                            expected_answer=ref_answer,  # 使用上一版回答作为期望
                            original_index=idx,
                            workflow_result=workflow_result,
                            is_correct=eval_result.is_correct,
                            llm_analysis=eval_result.analysis,
                            llm_category=eval_result.category,
                            missing_info=eval_result.missing_info,
                            important_info=eval_result.important_info,
                            scope=scope,
                            ref_answer=ref_answer,
                            history_eval=history_eval,
                            improvement_analysis=eval_result.version_analysis,  # 版本对比分析
                            # 新增字段：RAG响应解析结果
                            extracted_question=extracted_question,
                            rerank_sources=rerank_sources,
                            llm_answer=llm_answer,
                            is_rag_format=is_rag_format
                        )
                    else:
                        # 未配置评测器，仅记录回答
                        qa = QuestionAnswer(
                            question=question,
                            expected_answer=ref_answer,
                            original_index=idx,
                            workflow_result=workflow_result,
                            is_evaluated=False,
                            # 新增字段：RAG响应解析结果
                            extracted_question=extracted_question,
                            rerank_sources=rerank_sources,
                            llm_answer=llm_answer,
                            is_rag_format=is_rag_format
                        )

                    # 使用锁保护 results 列表
                    async with self._save_lock:
                        results.append(qa)
                    return qa

                except Exception as e:
                    logger.error(f"处理第 {idx} 行时出错: {str(e)}")
                    # 创建错误记录
                    qa = QuestionAnswer(
                        question=row.get(schema.col_question, ""),
                        expected_answer="",
                        original_index=idx,
                        error=str(e)
                    )
                    # 错误结果也需要保存
                    async with self._save_lock:
                        results.append(qa)
                    return qa

            # 并发执行
            tasks = [run_task_no_save(idx) for idx in remaining_indices]
            await asyncio.gather(*tasks)

        # 排序并返回最终结果
        return sorted(results, key=lambda x: x.original_index if x.original_index is not None else 0)

    async def _call_dify_api_for_rag(self, question: str) -> str:
        """
        调用 Dify API 获取回答（用于 RAG 模式）

        注意：RAG 模式使用默认 API Key（config.api_key），不需要动态路由。
        这与 Standard 模式不同，Standard 模式根据 knowledge_base 列动态选择 API Key。

        Args:
            question: 问题文本

        Returns:
            API 返回的答案文本
        """
        try:
            # 准备输入参数
            inputs = {self.config.input_variable_name: question}

            # 调用 Dify API（使用默认客户端）
            # 注意：直接使用 self.client，不需要创建临时配置（与 Standard 模式的区别）
            result = await self.client.execute_workflow(
                inputs=inputs,                    # 工作流输入参数
                user=self.config.user,            # 用户标识
                workflow_id=None                  # 不指定工作流版本
            )

            # 提取答案
            if isinstance(result, dict):
                return result.get(self.config.output_variable_name, "")
            return str(result)

        except Exception as e:
            error_msg = f"调用 Dify API 失败: {str(e)}"
            logger.error(error_msg)
            return error_msg
