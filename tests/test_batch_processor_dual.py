"""双工作流批处理器集成测试（单工作流+双模型输出架构）"""

import pytest
import asyncio
import pandas as pd
import os
from unittest.mock import AsyncMock, MagicMock, patch, Mock
from obd.models import (
    WorkflowConfig, LLMEvalConfig, ExecutionModeConfig,
    DualWorkflowConfig, DualWorkflowSchemaConfig, DualWorkflowEvalResult,
    DualModelResponseParts
)
from obd.processor.batch_processor import WorkflowBatchProcessor


class TestDualWorkflowBatchProcessor:
    """双工作流批处理器测试（新架构：单工作流+双模型输出）"""

    @pytest.fixture
    def mock_dify_client(self):
        """模拟 Dify 客户端"""
        client = AsyncMock()
        client.execute_workflow = AsyncMock(return_value={"answer": "测试回答"})
        return client

    @pytest.fixture
    def mock_dual_workflow_comparator(self):
        """模拟双工作流对比评测器（三方对比）"""
        comparator = MagicMock()
        # 返回新格式的 DualWorkflowEvalResult
        comparator.compare_answers = AsyncMock(return_value=DualWorkflowEvalResult(
            winner='llm1',
            confidence='high',
            overall_analysis='LLM1更好',
            llm1_comment='信息准确、结构清晰',
            llm2_comment='略显简略',
            history_comment='部分过时',
            recommendation='推荐LLM1',
            prompt=None,
            raw_response=None
        ))
        return comparator

    @pytest.fixture
    def dual_workflow_config(self):
        """双工作流配置（新架构：单一 api_key）"""
        return DualWorkflowConfig(
            api_key="app-single-key",
            workflow_id="workflow-id",
            label_1="LLM1",
            label_2="LLM2",
            label_history="历史回答",
            base_url="https://api.test.ai/v1",
            response_mode="blocking",
            timeout=30
        )

    @pytest.fixture
    def dual_workflow_schema_config(self):
        """双工作流模式配置（新架构：使用 col_history）"""
        return DualWorkflowSchemaConfig(
            col_question="Question",
            col_history="Historical Answer"
        )

    @pytest.fixture
    def llm_eval_config(self):
        """LLM 评测配置"""
        return LLMEvalConfig(
            enabled=True,
            api_key="llm-key",
            model="gpt-4o",
            temperature=0.0
        )

    @pytest.fixture
    def processor(
        self,
        mock_dify_client,
        mock_dual_workflow_comparator,
        dual_workflow_config,
        dual_workflow_schema_config,
        llm_eval_config
    ):
        """创建批处理器实例"""
        workflow_config = WorkflowConfig(
            api_key="test-key",
            max_workers=2,
            timeout=30
        )

        proc = WorkflowBatchProcessor(
            config=workflow_config,
            client=mock_dify_client,
            llm_eval_config=llm_eval_config,
            execution_mode_config=ExecutionModeConfig(mode="dual_workflow_compare"),
            dual_workflow_config=dual_workflow_config,
            dual_workflow_schema_config=dual_workflow_schema_config
        )
        # 手动注入 mock comparator
        proc.dual_workflow_comparator = mock_dual_workflow_comparator
        return proc

    @pytest.fixture
    def sample_dataframe(self):
        """创建示例数据框（含历史回答列）"""
        return pd.DataFrame([
            {
                "Question": "什么是Python？",
                "Historical Answer": "Python是脚本语言"
            },
            {
                "Question": "什么是机器学习？",
                "Historical Answer": "机器学习是数据驱动的方法"
            }
        ])

    def test_processor_initialization(
        self,
        processor,
        mock_dual_workflow_comparator,
        dual_workflow_config,
        dual_workflow_schema_config
    ):
        """测试批处理器初始化"""
        assert processor.execution_mode_config.mode == "dual_workflow_compare"
        assert processor.dual_workflow_config == dual_workflow_config
        assert processor.dual_workflow_schema_config == dual_workflow_schema_config
        assert processor.dual_workflow_comparator == mock_dual_workflow_comparator

    @pytest.mark.asyncio
    async def test_process_excel_dual_workflow_mode(
        self,
        processor,
        sample_dataframe,
        mock_dual_workflow_comparator
    ):
        """测试双工作流模式处理 Excel（单次 API 调用 + 解析双模型输出）"""
        # 使用 patch 来 mock DifyWorkflowClient 类
        with patch('obd.processor.batch_processor.DifyWorkflowClient') as mock_client_class:
            # 创建 mock 实例
            mock_client_instance = AsyncMock()

            # 模拟结构化的双模型输出
            structured_response_1 = """问题：什么是Python？
rerank后的片段：Python是高级编程语言
经过llm1的结果：Python是一种编程语言
经过llm2的结果：Python是解释型语言"""

            structured_response_2 = """问题：什么是机器学习？
rerank后的片段：机器学习是AI的一个分支
经过llm1的结果：机器学习是AI分支
经过llm2的结果：机器学习是数据驱动的方法"""

            mock_client_instance.execute_workflow = AsyncMock()
            mock_client_instance.execute_workflow.side_effect = [
                {"answer": structured_response_1},
                {"answer": structured_response_2}
            ]
            mock_client_class.return_value = mock_client_instance

            # 测试处理
            results = await processor._process_excel_dual_workflow_mode(
                df=sample_dataframe,
                start_row=0,
                end_row=2
            )

            # 验证结果
            assert len(results) == 2
            assert results[0].question == "什么是Python？"
            assert results[0].workflow_1_result == "Python是一种编程语言"
            assert results[0].workflow_2_result == "Python是解释型语言"
            assert results[0].rerank_sources == "Python是高级编程语言"
            assert results[0].history_answer == "Python是脚本语言"
            assert results[0].winner == "llm1"
            assert results[0].comparison_analysis == "LLM1更好"

            assert results[1].question == "什么是机器学习？"
            assert results[1].workflow_1_result == "机器学习是AI分支"
            assert results[1].workflow_2_result == "机器学习是数据驱动的方法"

            # 验证 API 调用次数（新架构：每个问题只需 1 次调用）
            assert mock_client_instance.execute_workflow.call_count == 2
            # 验证 LLM 评测调用
            assert mock_dual_workflow_comparator.compare_answers.call_count == 2

    @pytest.mark.asyncio
    async def test_process_excel_without_history_column(
        self,
        processor,
        mock_dual_workflow_comparator
    ):
        """测试处理没有历史回答列的数据"""
        # 创建没有历史回答列的数据框
        df_no_history = pd.DataFrame([
            {"Question": "什么是Python？"},
            {"Question": "什么是机器学习？"}
        ])

        with patch('obd.processor.batch_processor.DifyWorkflowClient') as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_instance.execute_workflow = AsyncMock(
                return_value={"answer": "问题：测试\nrerank后的片段：片段\n经过llm1的结果：回答1\n经过llm2的结果：回答2"}
            )
            mock_client_class.return_value = mock_client_instance

            results = await processor._process_excel_dual_workflow_mode(
                df=df_no_history,
                start_row=0,
                end_row=1
            )

            assert len(results) == 1
            assert results[0].history_answer is None  # 没有历史回答列

    @pytest.mark.asyncio
    async def test_process_excel_with_error(
        self,
        processor,
        sample_dataframe
    ):
        """测试处理过程中的错误处理"""
        with patch('obd.processor.batch_processor.DifyWorkflowClient') as mock_client_class:
            mock_client_instance = AsyncMock()
            mock_client_class.return_value = mock_client_instance

            # 模拟 API 调用抛出异常
            mock_client_instance.execute_workflow.side_effect = Exception("API 调用失败")

            # 处理应该不会抛出异常
            results = await processor._process_excel_dual_workflow_mode(
                df=sample_dataframe,
                start_row=0,
                end_row=1
            )

            # 验证结果
            assert len(results) == 1
            # 异常被 _call_dify_api_dual 内部捕获
            # llm1_output 会包含错误消息
            assert "调用 Dify API 失败" in results[0].workflow_1_result

    def test_load_dual_workflow_results_from_excel(self, processor):
        """测试从 Excel 加载双工作流结果"""
        # 创建模拟 Excel 数据（新格式）
        # 注意：列名需要与 dual_workflow_config 中的 label 匹配
        data = {
            "序号": [1, 2],
            "问题": ["问题1", "问题2"],
            "召回片段": ["片段1", "片段2"],
            "历史回答": ["历史1", "历史2"],
            "LLM1回答": ["回答1", "回答2"],
            "LLM2回答": ["回答1-2", "回答2-2"],
            "推荐答案": ["llm1", "llm2"],  # 内部值使用小写
            "错误信息": ["", "测试错误"]
        }
        df = pd.DataFrame(data)

        # 测试加载
        results = processor._load_dual_workflow_results_from_df(df)

        assert len(results) == 2
        assert results[0].question == "问题1"
        assert results[0].workflow_1_result == "回答1"
        assert results[0].workflow_2_result == "回答1-2"
        assert results[0].rerank_sources == "片段1"
        assert results[0].history_answer == "历史1"
        assert results[0].winner == "llm1"  # winner 保持原始值
        assert results[1].error == "测试错误"

    def test_calculate_dual_workflow_stats(self, processor):
        """测试计算双工作流统计信息（新格式）"""
        from collections import namedtuple
        QA = namedtuple('QA', ['winner', 'error', 'dual_workflow_eval'])

        # 创建 mock eval results
        eval_llm1 = type('Eval', (), {'winner': 'llm1'})()
        eval_llm2 = type('Eval', (), {'winner': 'llm2'})()
        eval_history = type('Eval', (), {'winner': 'history'})()
        eval_tie = type('Eval', (), {'winner': 'tie'})()

        # 创建测试结果（新格式）
        results = [
            QA(winner='llm1', error=None, dual_workflow_eval=eval_llm1),
            QA(winner='llm2', error=None, dual_workflow_eval=eval_llm2),
            QA(winner='llm2', error=None, dual_workflow_eval=eval_llm2),
            QA(winner='history', error=None, dual_workflow_eval=eval_history),
            QA(winner='tie', error=None, dual_workflow_eval=eval_tie),
            QA(winner='llm1', error="API 错误", dual_workflow_eval=None)  # 有错误的结果应被排除
        ]

        # 计算统计
        stats = processor._calculate_dual_workflow_stats(results)

        assert stats["total"] == 6  # 总数包括所有记录
        assert stats["llm1_wins"] == 1  # 只统计有效结果
        assert stats["llm2_wins"] == 2
        assert stats["history_wins"] == 1  # 新增 history 统计
        assert stats["ties"] == 1
        assert stats["llm1_win_rate"] == 0.2  # 1/5 = 0.2
        assert stats["llm2_win_rate"] == 0.4  # 2/5 = 0.4
        assert stats["history_win_rate"] == 0.2  # 1/5 = 0.2

    def test_calculate_dual_workflow_stats_legacy_format(self, processor):
        """测试计算旧格式 winner 的统计信息（向后兼容）"""
        from collections import namedtuple
        QA = namedtuple('QA', ['winner', 'error', 'dual_workflow_eval'])

        # 使用旧格式的 winner 值
        results = [
            QA(winner='workflow_1', error=None, dual_workflow_eval=None),
            QA(winner='workflow_2', error=None, dual_workflow_eval=None),
            QA(winner='tie', error=None, dual_workflow_eval=None),
        ]

        stats = processor._calculate_dual_workflow_stats(results)

        # 应该能正确映射旧格式到新格式
        assert stats["llm1_wins"] == 1  # workflow_1 → llm1
        assert stats["llm2_wins"] == 1  # workflow_2 → llm2
        assert stats["ties"] == 1

    def test_calculate_dual_workflow_stats_no_results(self, processor):
        """测试计算空结果的统计信息"""
        stats = processor._calculate_dual_workflow_stats([])
        assert stats == {}

    def test_save_results_dual_workflow_mode(self, processor, tmp_path):
        """测试双工作流模式保存结果（新格式 Excel 输出）"""
        from collections import namedtuple
        QA = namedtuple('QA', [
            'original_index', 'question', 'rerank_sources', 'history_answer',
            'workflow_1_result', 'workflow_2_result',
            'winner', 'comparison_analysis', 'error', 'dual_workflow_eval'
        ])

        # 创建新格式的 mock eval result
        mock_eval = type('EvalResult', (), {
            'winner': 'llm1',
            'confidence': 'high',
            'overall_analysis': '质量分析1',
            'llm1_comment': '优点1',
            'llm2_comment': '缺点2',
            'history_comment': '历史评价',
            'recommendation': '推荐1'
        })()

        results = [
            QA(
                original_index=0,
                question='问题1',
                rerank_sources='召回片段1',
                history_answer='历史回答1',
                workflow_1_result='LLM1回答',
                workflow_2_result='LLM2回答',
                winner='llm1',
                comparison_analysis='分析1',
                error=None,
                dual_workflow_eval=mock_eval
            )
        ]

        # 创建新格式的统计信息
        stats = {
            'total': 1,
            'llm1_wins': 1,
            'llm2_wins': 0,
            'history_wins': 0,
            'ties': 0,
            'llm1_win_rate': 1.0,
            'llm2_win_rate': 0.0,
            'history_win_rate': 0.0
        }

        # 测试保存
        output_path = tmp_path / "dual_results.xlsx"
        processor._save_results_dual_workflow(results, stats, str(output_path))

        # 验证文件创建
        assert output_path.exists()

        # 验证文件内容
        xl_file = pd.ExcelFile(output_path)
        assert "双工作流对比结果" in xl_file.sheet_names
        assert "统计信息" in xl_file.sheet_names

        # 检查结果 sheet
        df = pd.read_excel(output_path, sheet_name="双工作流对比结果")
        assert len(df) == 1
        assert df.iloc[0]["问题"] == "问题1"
        # 新增列
        assert df.iloc[0]["召回片段"] == "召回片段1"
        assert df.iloc[0]["历史回答"] == "历史回答1"  # 实际值
        # 列名根据 dual_workflow_config 的 label 生成
        assert df.iloc[0]["LLM1回答"] == "LLM1回答"  # label_1 = "LLM1"
        assert df.iloc[0]["LLM2回答"] == "LLM2回答"  # label_2 = "LLM2"
        # "推荐答案" 会显示为标签值（"LLM1"）而非内部标识（"llm1"）
        assert df.iloc[0]["推荐答案"] == "LLM1"  # winner='llm1' → 显示为 label_1

    def test_load_results_from_excel_dual_workflow_mode(self, processor, tmp_path):
        """测试从 Excel 加载双工作流结果文件（向后兼容）"""
        # 创建测试文件（新格式）
        results = pd.DataFrame({
            "序号": [1, 2],
            "问题": ["问题1", "问题2"],
            "召回片段": ["片段1", "片段2"],
            "历史回答": ["历史1", "历史2"],
            "LLM1回答": ["回答1", "回答2"],
            "LLM2回答": ["回答1-2", "回答2-2"],
            "推荐答案": ["llm1", "llm2"],  # 内部值使用小写
            "总体分析": ["分析1", "分析2"],
            "错误信息": ["", "错误"]
        })
        output_path = tmp_path / "dual_results.xlsx"
        results.to_excel(output_path, sheet_name="双工作流对比结果", index=False)

        # 加载结果
        loaded_results = processor._load_results_from_excel(str(output_path))

        assert len(loaded_results) == 2
        assert loaded_results[0].question == "问题1"
        assert loaded_results[0].workflow_1_result == "回答1"
        assert loaded_results[0].workflow_2_result == "回答1-2"
        assert loaded_results[0].rerank_sources == "片段1"
        assert loaded_results[0].history_answer == "历史1"
        assert loaded_results[1].error == "错误"


class TestDualWorkflowIntegration:
    """双工作流模式集成测试"""

    def test_full_workflow_simulation(self):
        """模拟完整双工作流流程（新架构）"""
        # 创建配置（新格式）
        workflow_config = WorkflowConfig(api_key="test", max_workers=2)
        dual_workflow_config = DualWorkflowConfig(
            api_key="single-key",  # 单一 API Key
            label_1="LLM1",
            label_2="LLM2",
            label_history="历史回答"
        )
        dual_workflow_schema_config = DualWorkflowSchemaConfig(
            col_question="Question",
            col_history="Historical Answer"
        )
        llm_eval_config = LLMEvalConfig(enabled=True, api_key="llm-key")

        # 创建处理器
        processor = WorkflowBatchProcessor(
            config=workflow_config,
            llm_eval_config=llm_eval_config,
            execution_mode_config=ExecutionModeConfig(mode="dual_workflow_compare"),
            dual_workflow_config=dual_workflow_config,
            dual_workflow_schema_config=dual_workflow_schema_config
        )

        # 验证配置
        assert processor.execution_mode_config.mode == "dual_workflow_compare"
        assert processor.dual_workflow_config == dual_workflow_config
        assert processor.dual_workflow_schema_config == dual_workflow_schema_config
        assert processor.dual_workflow_comparator is not None  # 因为配置了 llm_eval_config

        # 验证配置字段（新格式）
        assert processor.dual_workflow_config.api_key == "single-key"
        assert processor.dual_workflow_config.label_1 == "LLM1"
        assert processor.dual_workflow_config.label_2 == "LLM2"
        assert processor.dual_workflow_config.label_history == "历史回答"
        assert processor.dual_workflow_schema_config.col_question == "Question"
        assert processor.dual_workflow_schema_config.col_history == "Historical Answer"
