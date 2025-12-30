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