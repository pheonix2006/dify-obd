"""主程序入口"""

import configparser
import sys
from pathlib import Path
from typing import Dict

from obd.models import WorkflowConfig, RoutingConfig
from obd.processor.batch_processor import WorkflowBatchProcessor


def load_config(config_path: str = "config.ini") -> dict:
    """
    加载配置文件（支持路由映射）

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典
    """
    config = configparser.ConfigParser()
    config.read(config_path)

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

    return {
        "api_key": config.get("Dify", "api_key"),
        "base_url": config.get("Dify", "base_url"),
        "response_mode": config.get("Dify", "response_mode"),
        "timeout": config.getint("Dify", "timeout"),
        "excel_path": config.get("Excel", "file_path"),
        "question_column": config.get("Excel", "question_column", fallback="question"),
        "answer_column": config.get("Excel", "answer_column", fallback="answer"),
        "input_variable_name": config.get("Workflow", "input_variable_name", fallback="query"),
        "output_variable_name": config.get("Workflow", "output_variable_name", fallback="answer"),
        "comparison_method": config.get("Workflow", "comparison_method", fallback="auto"),
        "delay": config.getfloat("Workflow", "delay", fallback=0.5),
        "output_path": config.get("Output", "file_path"),
        "workflow_id": workflow_id,
        "workflow_mapping": workflow_mapping,
    }


def main():
    """主函数"""
    print("=" * 60)
    print("Dify工作流批处理器 - 动态路由版本")
    print("=" * 60)
    print()

    # 加载配置
    config_data = load_config()
    print(f"加载配置...")

    # 创建工作流配置
    workflow_config = WorkflowConfig(
        api_key=config_data["api_key"],
        base_url=config_data["base_url"],
        response_mode=config_data["response_mode"],
        timeout=config_data["timeout"],
        workflow_mapping=config_data.get("workflow_mapping", {})
    )

    # 创建路由配置
    routing_config = RoutingConfig(
        knowledge_base_column=config_data.get("knowledge_base_column", "KNOWLEDGE_BASE"),
        answer_state_column=config_data.get("answer_state_column", "ANSWER_STATE"),
        feedback_answer_column=config_data.get("feedback_answer_column", "FEEDBACK_ANSWER"),
        problem_value_column=config_data.get("problem_value_column", "PROBLEM_VALUE"),
        answer_value_column=config_data.get("answer_value_column", "ANSWER_VALUE")
    )

    # 创建批处理器
    processor = WorkflowBatchProcessor(workflow_config, routing_config)

    print(f"Excel文件: {config_data['excel_path']}")
    print(f"对比方法: {config_data['comparison_method']}")
    print(f"请求延迟: {config_data['delay']}秒")
    if config_data.get('workflow_mapping'):
        print(f"已加载 {len(config_data['workflow_mapping'])} 个工作流映射")
    print()
    print("-" * 60)

    # 处理Excel
    try:
        results = processor.process_excel(
            excel_path=config_data["excel_path"],
            question_column=config_data["question_column"],
            answer_column=config_data["answer_column"],
            input_variable_name=config_data["input_variable_name"],
            output_variable_name=config_data["output_variable_name"],
            comparison_method=config_data["comparison_method"],
            delay=config_data["delay"],
            workflow_id=config_data["workflow_id"]
        )

        # 计算统计信息
        statistics = processor.calculate_statistics(results)

        print()
        print("=" * 60)
        print("统计结果:")
        print(f"  总数量: {statistics['total']}")
        print(f"  评测数量: {statistics['evaluated']}")
        print(f"  异常模式数量: {statistics['feedback_mode']}")
        print(f"  正确数量: {statistics['correct']}")
        print(f"  错误数量: {statistics['incorrect']}")
        print(f"  失败数量: {statistics['failed']}")
        print(f"  准确率: {statistics['accuracy']:.2%}")
        print(f"  成功率: {statistics['success_rate']:.2%}")
        if statistics.get('match_type_stats'):
            print(f"  匹配类型统计:")
            for match_type, count in statistics['match_type_stats'].items():
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


if __name__ == "__main__":
    sys.exit(main())
