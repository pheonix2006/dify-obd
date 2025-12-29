"""测试批处理器"""

import pytest
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
            "workflow_run_id": "test-run-id",
            "task_id": "test-task-id",
            "data": {
                "outputs": {
                    "answer": "这是处理结果"
                }
            }
        }
        mock_client_class.return_value = mock_client

        # 创建使用mock客户端的处理器
        processor_with_mock = WorkflowBatchProcessor(processor.config, client=mock_client)

        # 处理问题
        question = "测试问题"
        result = processor_with_mock.process_question(question, input_variable_name="query", output_variable_name="answer")

        # 验证结果
        assert result.question == question
        assert result.workflow_run_id == "test-run-id"
        assert result.workflow_result == "这是处理结果"
        assert result.error is None

        # 验证调用参数
        mock_client.execute_workflow.assert_called_once_with(
            {"query": question},
            None
        )

    @patch('obd.client.dify_client.DifyWorkflowClient')
    def test_process_question_without_output_var(self, mock_client_class, processor):
        """测试工作流输出没有指定变量名的情况"""
        # 设置mock - 输出中没有指定的变量名
        mock_client = Mock()
        mock_client.execute_workflow.return_value = {
            "workflow_run_id": "test-run-id",
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

        # 验证结果 - 应该使用第一个输出
        assert result.workflow_result == "这是处理结果"

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

    @patch('obd.processor.batch_processor.WorkflowBatchProcessor.process_question')
    @patch('pandas.DataFrame.iloc')
    @patch('pandas.DataFrame')
    def test_process_excel_basic(self, mock_df_class, mock_df_iloc, mock_process_question, processor):
        """测试基本Excel处理"""
        # 设置mock DataFrame
        mock_df = Mock()
        mock_df.__len__ = Mock(return_value=2)
        mock_df.columns = ['question', 'answer']
        mock_df.iloc.__getitem__ = Mock(return_value=pd.Series({
            'question': '测试问题1',
            'answer': '期望答案1'
        }))
        mock_df_class.return_value = mock_df
        mock_df.iloc = mock_df.iloc

        # 设置mock process_question
        qa = QuestionAnswer(
            question="测试问题1",
            expected_answer="期望答案1",
            workflow_result="实际答案1",
            is_correct=True,
            match_type="exact"
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
            comparison_method="auto"
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
    def test_save_results(self, mock_excel_writer, processor, sample_results):
        """测试保存结果"""
        # 准备统计信息
        stats = {
            "total": 4,
            "correct": 2,
            "accuracy": 0.5,
            "success_rate": 0.75
        }

        # 调用save_results
        processor.save_results(sample_results, stats, "output.xlsx")

        # 验证调用了ExcelWriter
        mock_excel_writer.assert_called_once_with("output.xlsx", engine='openpyxl')

        # 获取调用参数
        writer_instance = mock_excel_writer.return_value.__enter__.return_value

        # 验证两个sheet都被调用
        expected_sheets = ["处理结果", "统计信息"]
        for sheet_name in expected_sheets:
            writer_instance.to_excel.assert_any_call(sheet_name=sheet_name, index=False)

    def test_process_excel_with_range(self, processor, mock_process_question, sample_excel_file):
        """测试处理指定范围的Excel"""
        # 设置mock DataFrame
        from unittest.mock import patch
        with patch('obd.processor.batch_processor.pd.read_excel') as mock_read_excel:
            mock_df = Mock()
            mock_df.__len__ = Mock(return_value=5)
            mock_df.columns = ['question', 'answer']

            # 模拟iloc返回
            def mock_iloc_getitem(self, idx):
                # 返回一个模拟的Series
                mock_series = Mock()
                mock_series.__getitem__ = Mock(side_effect=lambda key: {
                    'question': f'问题{idx+1}',
                    'answer': f'答案{idx+1}'
                }[key])
                return mock_series

            mock_df.iloc.__getitem__ = mock_iloc_getitem
            mock_read_excel.return_value = mock_df

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
                sample_excel_file,
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