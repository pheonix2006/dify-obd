"""测试批处理器"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch, MagicMock
from obd.processor.batch_processor import WorkflowBatchProcessor
from obd.models import QuestionAnswer


@pytest.fixture
def mock_process_question():
    """Mock process_question方法"""
    return Mock()


class TestWorkflowBatchProcessor:
    """测试WorkflowBatchProcessor类"""

    @pytest.fixture
    def processor(self, sample_config):
        """测试用的批处理器"""
        return WorkflowBatchProcessor(sample_config)

    def test_load_excel_success(self, processor, sample_excel_file):
        """测试成功加载Excel文件"""
        df = processor.load_excel(sample_excel_file)

        assert len(df) == 3
        assert 'question' in df.columns
        assert 'answer' in df.columns
        assert df.iloc[0]['question'] == '问题1：1+1=?'
        assert df.iloc[0]['answer'] == '2'

    def test_load_excel_file_not_found(self, processor):
        """测试加载不存在的Excel文件"""
        with pytest.raises(FileNotFoundError):
            processor.load_excel("nonexistent_file.xlsx")

    def test_load_excel_invalid_column(self, processor, sample_excel_file):
        """测试Excel文件中缺少必需列"""
        # 重命名question列
        df = processor.load_excel(sample_excel_file)
        df = df.rename(columns={'question': 'invalid_question'})
        df.to_excel(sample_excel_file, index=False)

        with pytest.raises(ValueError, match="Excel文件中不存在列: question"):
            processor.process_excel(sample_excel_file)

    @patch('obd.client.dify_client.DifyWorkflowClient')
    def test_process_question_success(self, mock_client_class, processor):
        """测试成功处理单个问题"""
        # 设置mock
        mock_client = Mock()
        mock_client.execute_workflow.return_value = {
            "task_id": "test-task-id",
            "answer": "这是处理结果"
        }
        mock_client_class.return_value = mock_client

        # 创建使用mock客户端的处理器
        processor_with_mock = WorkflowBatchProcessor(processor.config, client=mock_client)

        # 处理问题
        question = "测试问题"
        result = processor_with_mock.process_question(question, input_variable_name="query", output_variable_name="answer")

        # 验证结果
        assert result.question == question
        assert result.workflow_run_id == "test-task-id"
        assert result.workflow_result == "这是处理结果"
        assert result.error is None

        # 验证调用参数
        mock_client.execute_workflow.assert_called_once_with(
            {"query": question},
            None,
            None
        )

    @patch('obd.client.dify_client.DifyWorkflowClient')
    def test_process_question_without_output_var(self, mock_client_class, processor):
        """测试工作流输出没有指定变量名的情况"""
        # 设置mock - 输出中没有指定的变量名
        mock_client = Mock()
        mock_client.execute_workflow.return_value = {
            "task_id": "test-task-id",
            "data": {
                "outputs": {
                    "result": "这是处理结果"
                }
            }
        }
        mock_client_class.return_value = mock_client

        # 创建使用mock客户端的处理器
        processor_with_mock = WorkflowBatchProcessor(processor.config, client=mock_client)

        # 处理问题
        question = "测试问题"
        result = processor_with_mock.process_question(question)

        # 验证结果 - 使用JSON字符串而非特定字段
        assert '"task_id"' in result.workflow_result
        assert '"result": "这是处理结果"' in result.workflow_result

    @patch('obd.client.dify_client.DifyWorkflowClient')
    def test_process_question_api_error(self, mock_client_class, processor):
        """测试API调用错误"""
        # 设置mock - API调用失败
        mock_client = Mock()
        mock_client.execute_workflow.side_effect = Exception("API调用失败")
        mock_client_class.return_value = mock_client

        # 创建使用mock客户端的处理器
        processor_with_mock = WorkflowBatchProcessor(processor.config, client=mock_client)

        # 处理问题
        question = "测试问题"
        result = processor_with_mock.process_question(question)

        # 验证结果
        assert result.question == question
        assert result.error == "API调用失败"
        assert result.workflow_result is None

    @patch('obd.processor.batch_processor.WorkflowBatchProcessor.load_excel')
    def test_process_excel_basic(self, mock_load_excel, sample_config):
        """测试基本Excel处理"""
        # 使用新创建的processor实例，这样我们可以直接修改它的comparator
        processor = WorkflowBatchProcessor(sample_config)

        # 设置mock DataFrame
        mock_df = Mock()
        mock_df.__len__ = Mock(return_value=2)
        mock_df.columns = ['question', 'answer']

        # 创建Series对象用于模拟iloc返回
        test_series = pd.Series({
            'question': '测试问题1',
            'answer': '期望答案1'
        })
        mock_df.iloc.__getitem__ = Mock(return_value=test_series)
        mock_load_excel.return_value = mock_df

        # 设置mock process_question
        with patch('obd.processor.batch_processor.WorkflowBatchProcessor.process_question') as mock_process_question:
            # 设置mock comparator
            mock_comparator = Mock()
            mock_comparator.compare.return_value = (True, "exact")
            processor.comparator = mock_comparator

            qa = QuestionAnswer(
                question="测试问题1",
                expected_answer="期望答案1",
                workflow_result="实际答案1",
                is_correct=True,
                match_type="exact",
                workflow_run_id=None,
                error=None
            )
            mock_process_question.return_value = qa

            # 处理Excel
            results = processor.process_excel(
                "dummy_path.xlsx",
                question_column="question",
                answer_column="answer",
                start_row=0,
                end_row=1
            )

        # 验证结果
        assert len(results) == 1
        assert results[0].question == "测试问题1"
        assert results[0].expected_answer == "期望答案1"
        assert results[0].is_correct is True

        # 验证调用参数
        mock_process_question.assert_called_once_with(
            question="测试问题1",
            input_variable_name="query",
            output_variable_name="answer",
            comparison_method="auto",
            workflow_id=None
        )

    def test_calculate_statistics_empty(self, processor):
        """测试空列表的统计信息"""
        stats = processor.calculate_statistics([])
        assert stats == {}

    def test_calculate_statistics_basic(self, processor, sample_results):
        """测试基本统计信息"""
        stats = processor.calculate_statistics(sample_results)

        assert stats["total"] == 4
        assert stats["correct"] == 2
        assert stats["incorrect"] == 1
        assert stats["failed"] == 1
        assert stats["accuracy"] == 0.5  # 2/4
        assert stats["success_rate"] == 0.75  # 3/4
        assert stats["match_type_stats"] == {
            "exact": 1,
            "fuzzy": 1,
            "keyword": 1
        }

    @patch('obd.processor.batch_processor.pd.ExcelWriter')
    @patch('obd.processor.batch_processor.pd.DataFrame')
    def test_save_results(self, mock_df_class, mock_excel_writer, processor, sample_results):
        """测试保存结果 - 简化版本"""
        # 准备统计信息
        stats = {
            "total": 4,
            "correct": 2,
            "accuracy": 0.5,
            "success_rate": 0.75
        }

        # 调用save_results - 这是集成测试，验证方法能正常运行
        # 由于涉及文件操作，这个测试主要验证不会抛出异常
        processor.save_results(sample_results, stats, "test_output.xlsx")

        # 验证调用了ExcelWriter和DataFrame
        mock_excel_writer.assert_called_once()
        assert mock_df_class.call_count >= 1

    @patch('obd.processor.batch_processor.WorkflowBatchProcessor.process_question')
    @patch('obd.processor.batch_processor.WorkflowBatchProcessor.load_excel')
    def test_process_excel_with_range(self, mock_load_excel, mock_process_question, processor):
        """测试处理指定范围的Excel"""
        # 设置mock DataFrame
        mock_df = Mock()
        mock_df.__len__ = Mock(return_value=5)
        mock_df.columns = ['question', 'answer']

        # 创建Series对象用于模拟iloc返回
        test_series = pd.Series({
            'question': '问题1',
            'answer': '答案1'
        })
        mock_df.__getitem__ = Mock(return_value=test_series)

        # 模拟iloc返回5个不同的Series
        series_list = [
            pd.Series({'question': f'问题{i+1}', 'answer': f'答案{i+1}'})
            for i in range(5)
        ]

        def mock_iloc_getitem(self, idx):
            return series_list[idx]

        mock_df.iloc = Mock()
        mock_df.iloc.__getitem__ = mock_iloc_getitem
        mock_load_excel.return_value = mock_df

        # 设置mock process_question
        qa = QuestionAnswer(
            question="问题1",
            expected_answer="答案1",
            workflow_result="结果1",
            is_correct=True
        )
        mock_process_question.return_value = qa

        # 处理前2行
        results = processor.process_excel(
            "dummy_path.xlsx",
            start_row=0,
            end_row=2
        )

        # 验证只处理了2行
        assert len(results) == 2

        # 验证process_question被调用2次
        assert mock_process_question.call_count == 2

    @patch('obd.processor.batch_processor.WorkflowBatchProcessor.process_question')
    @patch('obd.processor.batch_processor.WorkflowBatchProcessor.load_excel')
    def test_process_excel_all_columns_not_found(self, mock_load_excel, mock_process_question, processor):
        """测试Excel中缺少必需列"""
        # 设置mock DataFrame - 缺少question列
        mock_df = Mock()
        mock_df.__len__ = Mock(return_value=1)
        mock_df.columns = ['invalid_question', 'answer']
        mock_load_excel.return_value = mock_df

        # 应该抛出ValueError
        with pytest.raises(ValueError, match="Excel文件中不存在列: question"):
            processor.process_excel("dummy_path.xlsx")

    @pytest.mark.asyncio
    async def test_rag_eval_concurrent_control(self, sample_config):
        """测试 RAG 评测模式的并发控制是否生效"""
        import asyncio
        from unittest.mock import patch, Mock
        from obd.models import RAGEvalSchemaConfig, RoutingConfig, LLMEvalConfig, StandardSchemaConfig, ExecutionModeConfig

        # 创建 RAG schema 配置
        rag_schema = RAGEvalSchemaConfig(
            col_question='question',
            col_scope='scope',
            col_ref_answer='ref_answer',
            col_history_eval='history_eval'
        )

        # 创建配置，设置 max_workers=2 来测试并发控制
        from obd.models import WorkflowConfig
        config_with_workers = WorkflowConfig(
            api_key=sample_config.api_key,
            base_url=sample_config.base_url,
            timeout=sample_config.timeout,
            max_workers=2,  # 设置为2以测试并发控制
            response_mode=sample_config.response_mode,
            input_variable_name=sample_config.input_variable_name,
            output_variable_name=sample_config.output_variable_name,
            workflow_mapping=sample_config.workflow_mapping
        )

        # 创建完整的配置
        processor = WorkflowBatchProcessor(
            config_with_workers,  # 使用修改后的配置
            routing_config=RoutingConfig(),
            llm_eval_config=LLMEvalConfig(
                enabled=True,
                api_key="test",
                base_url="https://test.com",
                model="gpt-4",
                judgment_mode="detailed",
                temperature=0.0
            ),
            execution_mode_config=ExecutionModeConfig(mode="rag_eval"),
            standard_schema_config=StandardSchemaConfig(
                col_question="question",
                col_ground_truth="answer",
                col_knowledge_base="kb",
                col_answer_state="state",
                col_feedback_answer="feedback"
            ),
            rag_eval_schema_config=rag_schema
        )

        # 创建 semantic_judge 的 mock
        mock_semantic_judge = Mock()
        processor.semantic_judge = mock_semantic_judge

        # 创建测试数据（5行，超过默认的 max_workers=5）
        test_df = pd.DataFrame({
            'question': ['q1', 'q2', 'q3', 'q4', 'q5'],
            'scope': ['', '', '', '', ''],
            'ref_answer': ['a1', 'a2', 'a3', 'a4', 'a5'],
            'history_eval': ['', '', '', '', '']
        })

        # 记录并发数
        max_concurrent = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        # 创建带并发跟踪的 mock 方法
        async def tracked_api_call(*args, **kwargs):
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            await asyncio.sleep(0.2)  # 模拟耗时操作
            async with lock:
                current_concurrent -= 1
            return "mocked_answer"

        async def tracked_eval(*args, **kwargs):
            nonlocal max_concurrent, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent:
                    max_concurrent = current_concurrent
            await asyncio.sleep(0.1)
            async with lock:
                current_concurrent -= 1
            from obd.comparator.llm_comparator import LLMEvalResult
            return LLMEvalResult(
                is_correct=True,
                category="fully_correct",
                analysis="Test analysis",
                missing_info=None,
                important_info=None
            )

        # Mock API 调用和评测
        with patch.object(processor, '_call_dify_api_for_rag', side_effect=tracked_api_call):
            with patch.object(processor.semantic_judge, 'evaluate_with_context', side_effect=tracked_eval):
                # 执行处理
                await processor._process_excel_rag_eval_mode(test_df)

                # 验证：最大并发数不应超过 max_workers * 2（API调用 + 评测）
                # 注意：由于信号量保护API调用和评测，实际并发可能达到 2*max_workers
                assert max_concurrent <= 4, \
                    f"并发数 {max_concurrent} 超过了预期限制 4 (2*max_workers)"

                # 验证：至少受到了某种限制（不应该等于任务总数5）
                assert max_concurrent < 5, \
                    f"并发控制未生效，所有任务同时执行 (max_concurrent={max_concurrent})"

    @pytest.mark.asyncio
    async def test_rag_eval_semaphore_release_on_error(self, sample_config):
        """测试异常情况下信号量正确释放"""
        import asyncio
        from unittest.mock import patch, Mock
        from obd.models import RAGEvalSchemaConfig, RoutingConfig, LLMEvalConfig, StandardSchemaConfig, ExecutionModeConfig

        # 创建 RAG schema 配置
        rag_schema = RAGEvalSchemaConfig(
            col_question='question',
            col_scope='scope',
            col_ref_answer='ref_answer',
            col_history_eval='history_eval'
        )

        processor = WorkflowBatchProcessor(
            sample_config,
            routing_config=RoutingConfig(),
            llm_eval_config=LLMEvalConfig(
                enabled=True,
                api_key="test",
                base_url="https://test.com",
                model="gpt-4",
                judgment_mode="detailed",
                temperature=0.0
            ),
            execution_mode_config=ExecutionModeConfig(mode="rag_eval"),
            standard_schema_config=StandardSchemaConfig(
                col_question="question",
                col_ground_truth="answer",
                col_knowledge_base="kb",
                col_answer_state="state",
                col_feedback_answer="feedback"
            ),
            rag_eval_schema_config=rag_schema
        )

        # 创建 semantic_judge 的 mock
        mock_semantic_judge = Mock()
        processor.semantic_judge = mock_semantic_judge

        test_df = pd.DataFrame({
            'question': ['q1', 'q2', 'q3'],
            'scope': ['', '', ''],
            'ref_answer': ['a1', 'a2', 'a3'],
            'history_eval': ['', '', '']
        })

        call_count = 0

        async def sometimes_failing_api(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # 第二次调用失败
                raise Exception("API Error")
            await asyncio.sleep(0.1)
            return "mocked_answer"

        from obd.comparator.llm_comparator import LLMEvalResult

        async def mock_eval(*args, **kwargs):
            return LLMEvalResult(
                is_correct=True,
                category="fully_correct",
                analysis="Test",
                missing_info=None,
                important_info=None
            )

        with patch.object(processor, '_call_dify_api_for_rag', side_effect=sometimes_failing_api):
            with patch.object(processor.semantic_judge, 'evaluate_with_context', side_effect=mock_eval):
                # 执行处理（应该能完成，即使中间有错误）
                results = await processor._process_excel_rag_eval_mode(test_df)

                # 验证：所有任务都被尝试执行
                assert len(results) == 3, "应该返回3个结果（包括失败的）"
                assert call_count == 3, "应该尝试调用3次API"

                # 验证：第二个任务有错误
                assert results[1].error is not None, "第二个任务应该有错误"


    @pytest.mark.asyncio
    async def test_results_saver_accumulates_results(self, sample_config):
        """验证后台保存任务能正确累积并保存结果"""
        import asyncio
        from obd.models import QuestionAnswer
        
        # 创建一个简单的处理器
        processor = WorkflowBatchProcessor(sample_config)
        
        # 创建队列和结果列表
        result_queue: asyncio.Queue = asyncio.Queue()
        all_results: List[QuestionAnswer] = []
        stop_event = asyncio.Event()
        
        # Mock _save_incremental_all 方法
        save_calls = []
        async def mock_save(results, output_path):
            save_calls.append(len(results))
        
        processor._save_incremental_all = mock_save
        
        # 启动后台保存任务
        saver_task = asyncio.create_task(
            processor._results_saver(result_queue, all_results, "dummy_path.xlsx", stop_event)
        )
        
        # 创建测试结果
        qa1 = QuestionAnswer(question="q1", expected_answer="a1", original_index=0)
        qa2 = QuestionAnswer(question="q2", expected_answer="a2", original_index=1)
        qa3 = QuestionAnswer(question="q3", expected_answer="a3", original_index=2)
        
        # 放入结果
        await result_queue.put(qa1)
        await asyncio.sleep(0.1)  # 等待保存
        
        await result_queue.put(qa2)
        await asyncio.sleep(0.1)
        
        await result_queue.put(qa3)
        await asyncio.sleep(0.1)
        
        # 停止后台任务
        stop_event.set()
        await saver_task
        
        # 验证：所有结果都被累积
        assert len(all_results) == 3, f"应该有3个结果，实际有 {len(all_results)}"
        assert all_results[0].question == "q1"
        assert all_results[1].question == "q2"
        assert all_results[2].question == "q3"
        
        # 验证：每次保存都包含累积的结果
        assert save_calls == [1, 2, 3], f"保存调用记录应该是 [1,2,3]，实际是 {save_calls}"

    @pytest.mark.asyncio
    async def test_concurrent_saving_no_overwrite(self, sample_config):
        """验证并发任务的结果不会相互覆盖"""
        import asyncio
        from obd.models import QuestionAnswer, RAGEvalSchemaConfig, RoutingConfig, LLMEvalConfig, ExecutionModeConfig
        from obd.models import StandardSchemaConfig
        from unittest.mock import patch, Mock
        
        # 创建 RAG schema 配置
        rag_schema = RAGEvalSchemaConfig(
            col_question='question',
            col_scope='scope',
            col_ref_answer='ref_answer',
            col_history_eval='history_eval'
        )
        
        # 创建配置，设置较大的 max_workers 以测试并发
        from obd.models import WorkflowConfig
        config_with_workers = WorkflowConfig(
            api_key=sample_config.api_key,
            base_url=sample_config.base_url,
            timeout=sample_config.timeout,
            max_workers=5,  # 高并发
            response_mode=sample_config.response_mode,
            input_variable_name=sample_config.input_variable_name,
            output_variable_name=sample_config.output_variable_name,
            workflow_mapping=sample_config.workflow_mapping
        )
        
        # 创建完整的配置
        processor = WorkflowBatchProcessor(
            config_with_workers,
            routing_config=RoutingConfig(),
            llm_eval_config=LLMEvalConfig(
                enabled=True,
                api_key="test",
                base_url="https://test.com",
                model="gpt-4",
                judgment_mode="detailed",
                temperature=0.0
            ),
            execution_mode_config=ExecutionModeConfig(mode="rag_eval"),
            standard_schema_config=StandardSchemaConfig(
                col_question="question",
                col_ground_truth="answer",
                col_knowledge_base="kb",
                col_answer_state="state",
                col_feedback_answer="feedback"
            ),
            rag_eval_schema_config=rag_schema
        )
        
        # 创建 semantic_judge 的 mock
        mock_semantic_judge = Mock()
        processor.semantic_judge = mock_semantic_judge
        
        # 创建测试数据（10行，测试高并发）
        test_df = pd.DataFrame({
            'question': [f'q{i}' for i in range(10)],
            'scope': [''] * 10,
            'ref_answer': [f'a{i}' for i in range(10)],
            'history_eval': [''] * 10
        })
        
        # Mock 文件保存操作以避免实际 I/O（异步函数）
        save_calls = []
        async def mock_save(results, path):
            save_calls.append(len(results))
        
        # Mock API 调用和评测
        async def mock_api(*args, **kwargs):
            await asyncio.sleep(0.05)  # 短延迟增加并发竞争
            return f"answer_for_{args}"
        
        from obd.comparator.llm_comparator import LLMEvalResult
        async def mock_eval(*args, **kwargs):
            return LLMEvalResult(
                is_correct=True,
                category="fully_correct",
                analysis="Test",
                missing_info=None,
                important_info=None
            )
        
        with patch.object(processor, '_call_dify_api_for_rag', side_effect=mock_api):
            with patch.object(processor.semantic_judge, 'evaluate_with_context', side_effect=mock_eval):
                with patch.object(processor, '_save_incremental_all', side_effect=mock_save):
                    # 执行处理
                    results = await processor._process_excel_rag_eval_mode(
                        test_df,
                        output_path="dummy_path.xlsx"  # 使用虚拟路径，save_results 被 mock
                    )
        
        # 验证：所有结果都被保存
        assert len(results) == 10, f"应该有10个结果，实际有 {len(results)}"
        
        # 验证：结果顺序正确（按 original_index 排序）
        for i, result in enumerate(results):
            assert result.original_index == i, f"结果 {i} 的索引应该是 {i}，实际是 {result.original_index}"
            assert result.question == f'q{i}', f"结果 {i} 的问题应该是 q{i}"
        
        # 验证：保存被调用了多次（增量保存）
        assert len(save_calls) > 0, "应该至少有一次保存调用"

    @pytest.mark.asyncio
    async def test_resume_from_checkpoint(self, sample_config):
        """验证断点恢复能正确加载已处理记录"""
        import asyncio
        from obd.models import RAGEvalSchemaConfig, RoutingConfig, LLMEvalConfig, ExecutionModeConfig, StandardSchemaConfig
        from unittest.mock import patch, Mock
        
        # 创建 RAG schema 配置
        rag_schema = RAGEvalSchemaConfig(
            col_question='question',
            col_scope='scope',
            col_ref_answer='ref_answer',
            col_history_eval='history_eval'
        )
        
        processor = WorkflowBatchProcessor(
            sample_config,
            routing_config=RoutingConfig(),
            llm_eval_config=LLMEvalConfig(
                enabled=True,
                api_key="test",
                base_url="https://test.com",
                model="gpt-4",
                judgment_mode="detailed",
                temperature=0.0
            ),
            execution_mode_config=ExecutionModeConfig(mode="rag_eval"),
            standard_schema_config=StandardSchemaConfig(
                col_question="question",
                col_ground_truth="answer",
                col_knowledge_base="kb",
                col_answer_state="state",
                col_feedback_answer="feedback"
            ),
            rag_eval_schema_config=rag_schema
        )
        
        # 创建 semantic_judge 的 mock
        mock_semantic_judge = Mock()
        processor.semantic_judge = mock_semantic_judge
        
        # 创建测试数据（5行）
        test_df = pd.DataFrame({
            'question': ['q1', 'q2', 'q3', 'q4', 'q5'],
            'scope': ['', '', '', '', ''],
            'ref_answer': ['a1', 'a2', 'a3', 'a4', 'a5'],
            'history_eval': ['', '', '', '', '']
        })
        
        # 存储已保存的结果，模拟断点恢复
        saved_results = []
        
        # Mock _load_results_from_excel 返回空（第一次运行）
        def mock_load(path):
            return saved_results.copy()

        # Mock _save_incremental_all 记录保存的结果（异步函数）
        async def mock_save(results, path):
            # 只保存新的结果
            for r in results:
                if r.original_index not in [sr.original_index for sr in saved_results]:
                    saved_results.append(r)
        
        # Mock API 调用和评测
        api_call_count = 0
        async def mock_api(*args, **kwargs):
            nonlocal api_call_count
            api_call_count += 1
            await asyncio.sleep(0.01)
            return f"answer_{api_call_count}"
        
        from obd.comparator.llm_comparator import LLMEvalResult
        async def mock_eval(*args, **kwargs):
            return LLMEvalResult(
                is_correct=True,
                category="fully_correct",
                analysis="Test",
                missing_info=None,
                important_info=None
            )
        
        with patch.object(processor, '_call_dify_api_for_rag', side_effect=mock_api):
            with patch.object(processor.semantic_judge, 'evaluate_with_context', side_effect=mock_eval):
                with patch.object(processor, '_save_incremental_all', side_effect=mock_save):
                    with patch('os.path.exists', return_value=True):
                        with patch.object(processor, '_load_results_from_excel', side_effect=mock_load):
                            # 第一次处理：处理前3行
                            results1 = await processor._process_excel_rag_eval_mode(
                                test_df,
                                start_row=0,
                                end_row=3,
                                output_path="dummy.xlsx"
                            )
        
        assert len(results1) == 3, "第一次处理应该有3个结果"
        assert api_call_count == 3, "第一次应该调用3次API"
        
        # 重置计数器
        api_call_count = 0
        
        with patch.object(processor, '_call_dify_api_for_rag', side_effect=mock_api):
            with patch.object(processor.semantic_judge, 'evaluate_with_context', side_effect=mock_eval):
                with patch.object(processor, '_save_incremental_all', side_effect=mock_save):
                    with patch('os.path.exists', return_value=True):
                        with patch.object(processor, '_load_results_from_excel', side_effect=mock_load):
                            # 第二次处理：处理全部5行（应该跳过前3行）
                            results2 = await processor._process_excel_rag_eval_mode(
                                test_df,
                                start_row=0,
                                end_row=5,
                                output_path="dummy.xlsx"
                            )
        
        # 验证：只处理了新的2行
        assert len(results2) == 5, f"第二次处理应该有5个结果（包括之前加载的），实际有 {len(results2)}"
        assert api_call_count == 2, f"第二次应该只调用2次API（跳过已处理的3行），实际调用 {api_call_count} 次"

    @pytest.mark.asyncio
    async def test_error_doesnt_block_saving(self, sample_config):
        """验证处理错误不会阻止其他结果的保存"""
        import asyncio
        from obd.models import RAGEvalSchemaConfig, RoutingConfig, LLMEvalConfig, ExecutionModeConfig, StandardSchemaConfig
        from unittest.mock import patch, Mock
        
        # 创建 RAG schema 配置
        rag_schema = RAGEvalSchemaConfig(
            col_question='question',
            col_scope='scope',
            col_ref_answer='ref_answer',
            col_history_eval='history_eval'
        )
        
        processor = WorkflowBatchProcessor(
            sample_config,
            routing_config=RoutingConfig(),
            llm_eval_config=LLMEvalConfig(
                enabled=True,
                api_key="test",
                base_url="https://test.com",
                model="gpt-4",
                judgment_mode="detailed",
                temperature=0.0
            ),
            execution_mode_config=ExecutionModeConfig(mode="rag_eval"),
            standard_schema_config=StandardSchemaConfig(
                col_question="question",
                col_ground_truth="answer",
                col_knowledge_base="kb",
                col_answer_state="state",
                col_feedback_answer="feedback"
            ),
            rag_eval_schema_config=rag_schema
        )
        
        # 创建 semantic_judge 的 mock
        mock_semantic_judge = Mock()
        processor.semantic_judge = mock_semantic_judge
        
        # 创建测试数据（5行）
        test_df = pd.DataFrame({
            'question': ['q1', 'q2', 'q3', 'q4', 'q5'],
            'scope': ['', '', '', '', ''],
            'ref_answer': ['a1', 'a2', 'a3', 'a4', 'a5'],
            'history_eval': ['', '', '', '', '']
        })
        
        # Mock 文件保存操作以避免实际 I/O（异步函数）
        save_call_count = 0
        async def mock_save(results, path):
            nonlocal save_call_count
            save_call_count += 1
        
        # Mock API 调用：第2和第4个会失败
        call_count = 0
        async def mock_api(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count in [2, 4]:  # 第二和第四次调用失败
                raise Exception(f"API Error {call_count}")
            await asyncio.sleep(0.01)
            return f"answer_{call_count}"
        
        from obd.comparator.llm_comparator import LLMEvalResult
        async def mock_eval(*args, **kwargs):
            return LLMEvalResult(
                is_correct=True,
                category="fully_correct",
                analysis="Test",
                missing_info=None,
                important_info=None
            )
        
        with patch.object(processor, '_call_dify_api_for_rag', side_effect=mock_api):
            with patch.object(processor.semantic_judge, 'evaluate_with_context', side_effect=mock_eval):
                with patch.object(processor, '_save_incremental_all', side_effect=mock_save):
                    # 执行处理
                    results = await processor._process_excel_rag_eval_mode(
                        test_df,
                        output_path="dummy.xlsx"
                    )
        
        # 验证：所有结果都返回了（包括错误记录）
        assert len(results) == 5, f"应该有5个结果，实际有 {len(results)}"
        
        # 验证：成功的任务没有错误
        assert results[0].error is None, "第一个结果不应该有错误"
        assert results[2].error is None, "第三个结果不应该有错误"
        assert results[4].error is None, "第五个结果不应该有错误"
        
        # 验证：失败的任务有错误
        assert results[1].error is not None, "第二个结果应该有错误"
        assert results[3].error is not None, "第四个结果应该有错误"
        
        # 验证：保存被调用了多次（即使有错误）
        assert save_call_count > 0, "应该至少有一次保存调用"
