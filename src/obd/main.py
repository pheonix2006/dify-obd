"""主程序入口"""

import asyncio
import configparser
import sys
import os
from obd.models import (
    WorkflowConfig,
    RoutingConfig,
    LLMEvalConfig,
    ExecutionModeConfig,
    StandardSchemaConfig,
    RAGEvalSchemaConfig,
    DualWorkflowConfig,
    DualWorkflowSchemaConfig,
)
from obd.processor.batch_processor import WorkflowBatchProcessor

os.environ["NO_PROXY"] = (
    "localhost,127.0.0.1" + ("," + os.environ.get("NO_PROXY", ""))
    if os.environ.get("NO_PROXY")
    else "localhost,127.0.0.1"
)


def load_config(config_path: str = "config.ini") -> dict:
    """
    加载配置文件（支持路由映射和双模式）

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典
    """
    config = configparser.ConfigParser()
    config.read(config_path, encoding="utf-8")

    # 解析工作流映射
    workflow_mapping = {}
    if config.has_section("WORKFLOW_MAPPING"):
        for kb_name, api_key in config.items("WORKFLOW_MAPPING"):
            # 标准化键名
            standardized_kb = kb_name.strip().lower()
            workflow_mapping[standardized_kb] = api_key

    # workflow_id是可选的
    workflow_id = None
    if config.has_option("Workflow", "workflow_id"):
        workflow_id = config.get("Workflow", "workflow_id")

    # ===== 新增：执行模式配置 =====
    execution_mode = config.get("EXECUTION_MODE", "mode", fallback="standard")

    # 标准模式列配置
    standard_question_col = config.get(
        "SCHEMA_STANDARD", "col_question", fallback="Question"
    )
    standard_ground_truth_col = config.get(
        "SCHEMA_STANDARD", "col_ground_truth", fallback="Ground Truth"
    )
    standard_kb_col = config.get("SCHEMA_STANDARD", "col_knowledge_base", fallback=None)
    standard_state_col = config.get(
        "SCHEMA_STANDARD", "col_answer_state", fallback=None
    )
    standard_feedback_col = config.get(
        "SCHEMA_STANDARD", "col_feedback_answer", fallback=None
    )

    # RAG 评测模式列配置
    rag_question_col = config.get(
        "SCHEMA_RAG_EVAL", "col_question", fallback="Question"
    )
    rag_scope_col = config.get("SCHEMA_RAG_EVAL", "col_scope", fallback="Scope")
    rag_ref_answer_col = config.get(
        "SCHEMA_RAG_EVAL", "col_ref_answer", fallback="Ref_Answer"
    )
    rag_history_eval_col = config.get(
        "SCHEMA_RAG_EVAL", "col_history_eval", fallback="Evaluation_Notes"
    )

    # 双工作流对比评测模式列配置
    dual_question_col = config.get(
        "SCHEMA_DUAL_WORKFLOW", "col_question", fallback="Question"
    )

    # 兼容旧配置：从 Excel 节读取（如果存在）
    excel_path = None
    question_column = "question"
    answer_column = "answer"

    if config.has_section("Excel"):
        excel_path = config.get("Excel", "file_path", fallback=None)
        question_column = config.get("Excel", "question_column", fallback="question")
        answer_column = config.get("Excel", "answer_column", fallback="answer")
    elif config.has_section("Output"):
        # 使用新的配置节
        excel_path = config.get("Output", "input_file_path", fallback=None)

    # ===== 双工作流配置（新架构：单工作流+双模型输出）=====
    dual_workflow_config = {}
    if config.has_section("DUAL_WORKFLOW"):
        dual_workflow_config = {
            "api_key": config.get("DUAL_WORKFLOW", "api_key", fallback=""),
            "workflow_id": config.get("DUAL_WORKFLOW", "workflow_id", fallback=None),
            "label_1": config.get("DUAL_WORKFLOW", "label_1", fallback="LLM1"),
            "label_2": config.get("DUAL_WORKFLOW", "label_2", fallback="LLM2"),
            "label_history": config.get(
                "DUAL_WORKFLOW", "label_history", fallback="历史回答"
            ),
            "base_url": config.get(
                "DUAL_WORKFLOW", "base_url", fallback="https://api.dify.ai/v1"
            ),
            "response_mode": config.get(
                "DUAL_WORKFLOW", "response_mode", fallback="blocking"
            ),
            "timeout": config.getint("DUAL_WORKFLOW", "timeout", fallback=60),
        }

    return {
        "api_key": config.get("Dify", "api_key"),
        "base_url": config.get("Dify", "base_url"),
        "response_mode": config.get("Dify", "response_mode"),
        "timeout": config.getint("Dify", "timeout"),
        "excel_path": excel_path,
        "question_column": question_column,
        "answer_column": answer_column,
        "input_variable_name": config.get(
            "Workflow", "input_variable_name", fallback="query"
        ),
        "output_variable_name": config.get(
            "Workflow", "output_variable_name", fallback="answer"
        ),
        "comparison_method": config.get(
            "Workflow", "comparison_method", fallback="auto"
        ),
        "delay": config.getfloat("Workflow", "delay", fallback=0.5),
        "max_workers": config.getint("Workflow", "max_workers", fallback=5),
        "output_path": config.get("Output", "file_path"),
        "workflow_id": workflow_id,
        "workflow_mapping": workflow_mapping,
        "llm_eval": {
            "enabled": config.getboolean("LLM_EVAL", "enabled", fallback=False),
            "api_key": config.get("LLM_EVAL", "api_key", fallback=""),
            "base_url": config.get(
                "LLM_EVAL", "base_url", fallback="https://api.openai.com/v1"
            ),
            "model": config.get("LLM_EVAL", "model", fallback="gpt-4o"),
            "timeout": config.getint("LLM_EVAL", "timeout", fallback=30),
            "prompt_template": config.get("LLM_EVAL", "prompt_template", fallback=None),
            "judgment_mode": config.get(
                "LLM_EVAL", "judgment_mode", fallback="detailed"
            ),
            "temperature": config.getfloat("LLM_EVAL", "temperature", fallback=0.0),
            "api_type": config.get("LLM_EVAL", "api_type", fallback="standard"),
            # 评测记录配置
            "eval_record_enabled": config.getboolean(
                "LLM_EVAL", "eval_record_enabled", fallback=False
            ),
            "eval_record_path": config.get(
                "LLM_EVAL", "eval_record_path", fallback="logs/eval_records"
            ),
        },
        # 新增：执行模式配置
        "execution_mode": execution_mode,
        "standard_schema": {
            "col_question": standard_question_col,
            "col_ground_truth": standard_ground_truth_col,
            "col_knowledge_base": standard_kb_col,
            "col_answer_state": standard_state_col,
            "col_feedback_answer": standard_feedback_col,
        },
        "rag_eval_schema": {
            "col_question": rag_question_col,
            "col_scope": rag_scope_col,
            "col_ref_answer": rag_ref_answer_col,
            "col_history_eval": rag_history_eval_col,
        },
        # 双工作流模式列配置
        "dual_workflow_schema": {
            "col_question": dual_question_col,
            "col_history": config.get(
                "SCHEMA_DUAL_WORKFLOW", "col_history", fallback=None
            ),
        },
        "dual_workflow": dual_workflow_config,
    }


async def main():
    """主函数"""
    print("=" * 60)
    print("Dify工作流批处理器 - 动态路由并发版本")
    print("=" * 60)
    print()

    # 加载配置
    config_data = load_config()
    print("加载配置...")

    # 创建工作流配置
    workflow_config = WorkflowConfig(
        api_key=config_data["api_key"],
        base_url=config_data["base_url"],
        response_mode=config_data["response_mode"],
        timeout=config_data["timeout"],
        max_workers=config_data["max_workers"],
        input_variable_name=config_data["input_variable_name"],
        output_variable_name=config_data["output_variable_name"],
        workflow_mapping=config_data.get("workflow_mapping", {}),
    )

    # 创建路由配置
    routing_config = RoutingConfig(
        knowledge_base_column=config_data.get(
            "knowledge_base_column", "KNOWLEDGE_BASE"
        ),
        answer_state_column=config_data.get("answer_state_column", "ANSWER_STATE"),
        feedback_answer_column=config_data.get(
            "feedback_answer_column", "FEEDBACK_ANSWER"
        ),
        problem_value_column=config_data.get("question_column", "question"),
        answer_value_column=config_data.get("answer_column", "answer"),
    )

    # 创建 LLM 评测配置
    llm_eval_config = LLMEvalConfig(**config_data["llm_eval"])

    # 新增：创建执行模式配置
    execution_mode_config = ExecutionModeConfig(mode=config_data["execution_mode"])

    standard_schema_config = StandardSchemaConfig(
        col_question=config_data["standard_schema"]["col_question"],
        col_ground_truth=config_data["standard_schema"]["col_ground_truth"],
        col_knowledge_base=config_data["standard_schema"]["col_knowledge_base"],
        col_answer_state=config_data["standard_schema"]["col_answer_state"],
        col_feedback_answer=config_data["standard_schema"]["col_feedback_answer"],
    )

    rag_eval_schema_config = RAGEvalSchemaConfig(
        col_question=config_data["rag_eval_schema"]["col_question"],
        col_scope=config_data["rag_eval_schema"]["col_scope"],
        col_ref_answer=config_data["rag_eval_schema"]["col_ref_answer"],
        col_history_eval=config_data["rag_eval_schema"]["col_history_eval"],
    )

    # 新增：创建双工作流配置
    dual_workflow_config = None
    dual_workflow_schema_config = None
    if config_data["dual_workflow"]:
        dual_workflow_config = DualWorkflowConfig(**config_data["dual_workflow"])
        dual_workflow_schema_config = DualWorkflowSchemaConfig(
            col_question=config_data["dual_workflow_schema"]["col_question"],
            col_history=config_data["dual_workflow_schema"].get("col_history"),
        )

    # 创建批处理器（传入新的配置对象）
    processor = WorkflowBatchProcessor(
        workflow_config,
        routing_config,
        llm_eval_config=llm_eval_config,
        execution_mode_config=execution_mode_config,
        standard_schema_config=standard_schema_config,
        rag_eval_schema_config=rag_eval_schema_config,
        dual_workflow_config=dual_workflow_config,
        dual_workflow_schema_config=dual_workflow_schema_config,
    )

    try:
        print(f"Excel文件: {config_data['excel_path']}")
        print(f"执行模式: {execution_mode_config.mode}")
        print(f"对比方法: {config_data['comparison_method']}")
        print(f"并发数量: {config_data['max_workers']}")
        if llm_eval_config.enabled:
            print(
                f"LLM 评测: 已启用 (模型: {llm_eval_config.model}, 模式: {llm_eval_config.judgment_mode}, 温度: {llm_eval_config.temperature})"
            )
        else:
            print("LLM 评测: 未启用")
        if config_data.get("workflow_mapping"):
            print(f"已加载 {len(config_data['workflow_mapping'])} 个工作流映射")
        # 新增：双工作流模式输出（单工作流+双模型输出）
        if (
            execution_mode_config.mode == "dual_workflow_compare"
            and dual_workflow_config
        ):
            print("双工作流模式:")
            print(
                f"  - {dual_workflow_config.label_1} vs {dual_workflow_config.label_2} vs {dual_workflow_config.label_history}"
            )
            print(f"  - API Key: {dual_workflow_config.api_key[:20]}...")
        print()
        print("-" * 60)

        # 处理Excel（内部根据模式选择逻辑）
        results = await processor.process_excel(
            excel_path=config_data["excel_path"],
            output_path=config_data["output_path"],
            question_column=config_data["question_column"],
            answer_column=config_data["answer_column"],
            input_variable_name=config_data["input_variable_name"],
            output_variable_name=config_data["output_variable_name"],
            comparison_method=config_data["comparison_method"],
            delay=config_data["delay"],
            workflow_id=config_data["workflow_id"],
        )

        # 计算统计信息
        statistics = processor.calculate_statistics(results)

        print()
        print("=" * 60)
        print("统计结果:")

        # 根据模式输出不同的统计信息
        if execution_mode_config.mode == "dual_workflow_compare":
            # 双工作流模式统计
            label_1 = (
                dual_workflow_config.label_1 if dual_workflow_config else "Workflow_A"
            )
            label_2 = (
                dual_workflow_config.label_2 if dual_workflow_config else "Workflow_B"
            )
            label_history = (
                dual_workflow_config.label_history
                if dual_workflow_config
                else "历史回答"
            )
            print(f"  总数量: {statistics['total']}")
            print(f"  {label_1}获胜次数: {statistics['llm1_wins']}")
            print(f"  {label_2}获胜次数: {statistics['llm2_wins']}")
            print(f"  {label_history}获胜次数: {statistics['history_wins']}")
            print(f"  平局次数: {statistics['ties']}")
            print(f"  {label_1}获胜率: {statistics['llm1_win_rate']:.2%}")
            print(f"  {label_2}获胜率: {statistics['llm2_win_rate']:.2%}")
            print(f"  {label_history}获胜率: {statistics['history_win_rate']:.2%}")
        else:
            # 标准模式和 RAG 模式统计
            print(f"  总数量: {statistics['total']}")
            print(f"  评测数量: {statistics['evaluated']}")
            print(f"  异常模式数量: {statistics['feedback_mode']}")
            print(f"  正确数量: {statistics['correct']}")
            print(f"  错误数量: {statistics['incorrect']}")
            print(f"  失败数量: {statistics['failed']}")
            print(f"  准确率: {statistics['accuracy']:.2%}")
            print(f"  成功率: {statistics['success_rate']:.2%}")
            # 4级分类统计
            if statistics.get("category_details"):
                print("  4级分类统计:")
                for category, details in statistics["category_details"].items():
                    print(
                        f"    - {details['label']}: {details['count']} ({details['percentage']:.2%})"
                    )
            else:
                if statistics.get("match_type_stats"):
                    print("  匹配类型统计:")
                    for match_type, count in statistics["match_type_stats"].items():
                        print(f"    - {match_type}: {count}")
        print("=" * 60)

        # 保存结果
        processor.save_results(results, statistics, config_data["output_path"])
        print(f"\n测试完成！结果已保存到: {config_data['output_path']}")

        return 0

    except FileNotFoundError as e:
        print(f"错误: {e}")
        return 1
    except ValueError as e:
        print(f"配置错误: {e}")
        return 1
    except Exception as e:
        print(f"处理失败: {e}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        await processor.close()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        pass
