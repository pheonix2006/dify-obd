"""
Dify工作流批处理主程序
"""

import configparser
from obd import WorkflowConfig, WorkflowBatchProcessor


def load_config(config_path: str = "config.ini") -> WorkflowConfig:
    """
    从配置文件加载配置

    Args:
        config_path: 配置文件路径

    Returns:
        WorkflowConfig对象
    """
    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')

    return WorkflowConfig(
        api_key=config.get('Dify', 'api_key'),
        base_url=config.get('Dify', 'base_url', fallback='https://api.dify.ai/v1'),
        response_mode=config.get('Dify', 'response_mode', fallback='blocking'),
        timeout=config.getint('Dify', 'timeout', fallback=60)
    )


def main():
    """主函数"""
    # 加载配置
    config = load_config("config.ini")

    # 创建批处理器
    processor = WorkflowBatchProcessor(config)

    # 读取Excel配置
    cfg = configparser.ConfigParser()
    cfg.read('config.ini', encoding='utf-8')

    excel_path = cfg.get('Excel', 'file_path')
    question_column = cfg.get('Excel', 'question_column', fallback='question')
    answer_column = cfg.get('Excel', 'answer_column', fallback='answer')
    input_variable_name = cfg.get('Workflow', 'input_variable_name', fallback='query')
    output_variable_name = cfg.get('Workflow', 'output_variable_name', fallback='answer')
    comparison_method = cfg.get('Workflow', 'comparison_method', fallback='auto')
    delay = cfg.getfloat('Workflow', 'delay', fallback=0.5)

    # 处理Excel
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
    output_path = cfg.get('Output', 'file_path', fallback='results.xlsx')
    processor.save_results(results, statistics, output_path)

    print("\n处理完成！")


if __name__ == "__main__":
    main()
