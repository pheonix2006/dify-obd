"""Dify API 调试脚本

提供交互式命令行界面用于快速测试 Dify API 调用。
"""

import configparser
import json
from obd.models import WorkflowConfig
from obd.client.dify_client import DifyWorkflowClient


def load_config(config_path: str = "config.ini") -> dict:
    """
    加载配置文件 - 只读取 Dify 相关配置

    Args:
        config_path: 配置文件路径

    Returns:
        包含 Dify API 配置的字典
    """
    config = configparser.ConfigParser()
    config.read(config_path)

    return {
        "api_key": config.get("Dify", "api_key"),
        "base_url": config.get("Dify", "base_url"),
        "response_mode": config.get("Dify", "response_mode"),
        "timeout": config.getint("Dify", "timeout"),
    }


def main():
    """主函数 - 交互式 Dify API 调试"""
    # 打印欢迎信息
    print("=" * 60)
    print("Dify API 调试工具")
    print("=" * 60)
    print()

    # 加载配置
    try:
        config_data = load_config()
        print(f"✓ 配置加载成功")
        print(f"  - API 基础URL: {config_data['base_url']}")
        print(f"  - 响应模式: {config_data['response_mode']}")
        print(f"  - 超时时间: {config_data['timeout']}秒")
    except Exception as e:
        print(f"✗ 配置加载失败: {e}")
        print("请确保 config.ini 文件存在且包含正确的 Dify 配置")
        return 1

    print()
    print("使用说明:")
    print("  - 输入问题并按回车发送")
    print("  - 输入 'quit'、'exit' 或 'q' 退出")
    print("-" * 60)

    # 创建配置对象和客户端
    workflow_config = WorkflowConfig(**config_data)
    client = DifyWorkflowClient(workflow_config)

    # 交互式循环
    while True:
        # 输入问题
        try:
            question = input("\n请输入问题: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n退出调试工具")
            break

        # 退出检查
        if question.lower() in ['quit', 'exit', 'q']:
            print("\n再见!")
            break

        # 跳过空输入
        if not question:
            print("⚠ 问题不能为空，请重新输入")
            continue

        # 调用 API
        print(f"\n正在调用 Dify API...")
        try:
            result = client.execute_workflow(
                inputs={"query": question},
                user="debug-user"
            )

            # 打印结果
            print("\n" + "=" * 60)
            print("✓ API 调用成功")
            print("=" * 60)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            print("=" * 60)

        except Exception as e:
            print("\n" + "-" * 60)
            print(f"✗ API 调用失败: {e}")
            print("-" * 60)

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
