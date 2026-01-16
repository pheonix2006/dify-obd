"""主程序入口"""

import asyncio
import configparser
import sys
from pathlib import Path
from typing import Dict
import os
from obd.models import WorkflowConfig, RoutingConfig, LLMEvalConfig
from obd.processor.batch_processor import WorkflowBatchProcessor
os.environ["NO_PROXY"] = "localhost,127.0.0.1" + ("," + os.environ.get("NO_PROXY", "")) if os.environ.get("NO_PROXY") else "localhost,127.0.0.1"

def load_config(config_path: str = "config.ini") -> dict:
    """
    加载配置文件（支持路由映射）

    Args:
        config_path: 配置文件路径

    Returns:
        配置字典
    """
    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')

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
        "max_workers": config.getint("Workflow", "max_workers", fallback=5),
        "output_path": config.get("Output", "file_path"),
        "workflow_id": workflow_id,
        "workflow_mapping": workflow_mapping,
        "llm_eval": {
            "enabled": config.getboolean("LLM_EVAL", "enabled", fallback=False),
            "api_key": config.get("LLM_EVAL", "api_key", fallback=""),
            "base_url": config.get("LLM_EVAL", "base_url", fallback="https://api.openai.com/v1"),
            "model": config.get("LLM_EVAL", "model", fallback="gpt-4o"),
            "timeout": config.getint("LLM_EVAL", "timeout", fallback=30),
            "prompt_template": config.get("LLM_EVAL", "prompt_template", fallback=None),
            "judgment_mode": config.get("LLM_EVAL", "judgment_mode", fallback="detailed"),
            "temperature": config.getfloat("LLM_EVAL", "temperature", fallback=0.0),
        }
    }


async def main():
    """主函数"""
    print("=" * 60)
    print("Dify工作流批处理器 - 动态路由并发版本")
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
        max_workers=config_data["max_workers"],
        input_variable_name=config_data["input_variable_name"],
        output_variable_name=config_data["output_variable_name"],
        workflow_mapping=config_data.get("workflow_mapping", {})
    )

    # 创建路由配置
    routing_config = RoutingConfig(
        knowledge_base_column=config_data.get("knowledge_base_column", "KNOWLEDGE_BASE"),
        answer_state_column=config_data.get("answer_state_column", "ANSWER_STATE"),
        feedback_answer_column=config_data.get("feedback_answer_column", "FEEDBACK_ANSWER"),
        problem_value_column=config_data["question_column"],
        answer_value_column=config_data["answer_column"]
    )

    # 创建 LLM 评测配置
    llm_eval_config = LLMEvalConfig(**config_data["llm_eval"])

    # 创建批处理器
    processor = WorkflowBatchProcessor(
        workflow_config, 
        routing_config, 
        llm_eval_config=llm_eval_config
    )

    try:
        print(f"Excel文件: {config_data['excel_path']}")
        print(f"对比方法: {config_data['comparison_method']}")
        print(f"并发数量: {config_data['max_workers']}")
        if llm_eval_config.enabled:
            print(f"LLM 评测: 已启用 (模型: {llm_eval_config.model}, 模式: {llm_eval_config.judgment_mode}, 温度: {llm_eval_config.temperature})")
        else:
            print(f"LLM 评测: 未启用")
        if config_data.get('workflow_mapping'):
            print(f"已加载 {len(config_data['workflow_mapping'])} 个工作流映射")
        print()
        print("-" * 60)

        # 处理Excel
        results = await processor.process_excel(
            excel_path=config_data["excel_path"],
            output_path=config_data["output_path"],
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
        # 4级分类统计
        if statistics.get('category_details'):
            print(f"  4级分类统计:")
            for category, details in statistics['category_details'].items():
                print(f"    - {details['label']}: {details['count']} ({details['percentage']:.2%})")
        else:
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
    finally:
        await processor.close()


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        pass
