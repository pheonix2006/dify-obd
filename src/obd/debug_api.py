"""Dify API 调试脚本

提供交互式命令行界面用于快速测试 Dify API 调用。

支持两种模式：
1. Standard 模式：支持动态路由（根据知识库名称选择 API Key）
2. RAG Eval 模式：使用默认 API Key（固定路由）
"""

import asyncio
import configparser
import json
import os
from typing import Optional, Dict
from obd.models import WorkflowConfig
from obd.client.dify_client import DifyWorkflowClient

# 设置 NO_PROXY 确保可以访问本地服务
os.environ["NO_PROXY"] = "localhost,127.0.0.1,host.docker.internal"
os.environ["no_proxy"] = "localhost,127.0.0.1,host.docker.internal"


def load_config(config_path: str = "config.ini") -> dict:
    """
    加载配置文件

    Args:
        config_path: 配置文件路径

    Returns:
        包含所有配置的字典
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

    # 读取执行模式
    execution_mode = config.get("EXECUTION_MODE", "mode", fallback="standard")

    return {
        # Dify 基础配置
        "api_key": config.get("Dify", "api_key"),
        "base_url": config.get("Dify", "base_url"),
        "response_mode": config.get("Dify", "response_mode"),
        "timeout": config.getint("Dify", "timeout"),
        # 工作流配置
        "input_variable_name": config.get(
            "Workflow", "input_variable_name", fallback="query"
        ),
        "output_variable_name": config.get(
            "Workflow", "output_variable_name", fallback="answer"
        ),
        "max_workers": config.getint("Workflow", "max_workers", fallback=5),
        # 工作流映射（用于 Standard 模式的动态路由）
        "workflow_mapping": workflow_mapping,
        # 执行模式
        "execution_mode": execution_mode,
    }


def print_available_knowledge_bases(workflow_mapping: Dict[str, str]):
    """打印可用的知识库列表"""
    if not workflow_mapping:
        print("  (未配置工作流映射)")
        return

    print(f"  可用知识库 ({len(workflow_mapping)} 个):")
    for kb_name in sorted(workflow_mapping.keys()):
        api_key_suffix = workflow_mapping[kb_name][-4:]
        print(f"    - {kb_name} (API Key: ...{api_key_suffix})")


def print_mode_info(config_data: dict):
    """打印当前模式信息"""
    mode = config_data["execution_mode"]
    print(f"执行模式: {mode}")

    if mode == "standard":
        print("  模式特性: 动态路由支持")
        if config_data["workflow_mapping"]:
            print("  可选: 输入 'kb:<知识库名>' 使用特定 API Key")
        else:
            print("  提示: 未配置 WORKFLOW_MAPPING，将使用默认 API Key")
    elif mode == "rag_eval":
        print("  模式特性: 固定路由（使用默认 API Key）")
        print("  说明: RAG 评测模式，不支持动态路由")


async def call_api_with_routing(
    client: DifyWorkflowClient,
    question: str,
    input_variable_name: str,
    workflow_mapping: Optional[Dict[str, str]] = None,
    knowledge_base: Optional[str] = None,
) -> dict:
    """
    调用 Dify API（支持路由）

    Args:
        client: Dify 客户端
        question: 问题文本
        input_variable_name: 输入变量名
        workflow_mapping: 工作流映射（知识库名 -> API Key）
        knowledge_base: 指定的知识库名称（可选）

    Returns:
        API 响应结果
    """
    # Standard 模式：支持动态路由
    if workflow_mapping and knowledge_base:
        # 标准化知识库名称
        standardized_kb = knowledge_base.strip().lower()

        if standardized_kb not in workflow_mapping:
            available = ", ".join(sorted(workflow_mapping.keys()))
            raise ValueError(
                f"未找到知识库 '{knowledge_base}' 的配置\n" f"可用知识库: {available}"
            )

        # 获取特定 API Key
        api_key = workflow_mapping[standardized_kb]
        print(f"  使用路由: {knowledge_base} (API Key: ...{api_key[-4:]})")

        # 创建临时配置和客户端
        from obd.models import WorkflowConfig

        temp_config = WorkflowConfig(
            api_key=api_key,
            base_url=client.config.base_url,
            response_mode=client.config.response_mode,
            timeout=client.config.timeout,
            user=client.config.user,
            input_variable_name=input_variable_name,
            output_variable_name=client.config.output_variable_name,
        )

        # 创建临时客户端
        temp_client = DifyWorkflowClient(temp_config)

        # 调用 API
        result = await temp_client.execute_workflow(
            inputs={input_variable_name: question}, user="debug-user"
        )

        # 关闭临时客户端
        await temp_client.close()

        return result

    # RAG Eval 模式或未指定知识库：使用默认客户端
    if knowledge_base:
        print("  提示: 当前模式不支持路由，使用默认 API Key")

    result = await client.execute_workflow(
        inputs={input_variable_name: question}, user="debug-user"
    )

    return result


def print_usage_guide(workflow_mapping: Dict[str, str]):
    """打印使用指南"""
    print("\n使用说明:")
    print("  基础用法:")
    print("    - 直接输入问题并按回车发送")
    print("    - 输入 'quit'、'exit' 或 'q' 退出")

    if workflow_mapping:
        print("\n  路由功能 (Standard 模式):")
        print("    - 输入 'kb:<知识库名>' 使用指定 API Key")
        print("    - 例如: 'kb:workflow1' 后续问题将使用 workflow1 的 API Key")
        print("    - 输入 'kb:default' 切换回默认 API Key")

    print("\n  命令:")
    print("    - 'help' 或 'h': 显示此帮助信息")
    print("    - 'list' 或 'l': 列出可用的知识库")
    print("    - 'mode' 或 'm': 显示当前模式信息")


async def main():
    """主函数 - 交互式 Dify API 调试"""
    # 打印欢迎信息
    print("=" * 60)
    print("Dify API 调试工具")
    print("=" * 60)
    print()

    # 加载配置
    try:
        config_data = load_config()
        print("✓ 配置加载成功")
        print(f"  - API 基础URL: {config_data['base_url']}")
        print(f"  - 响应模式: {config_data['response_mode']}")
        print(f"  - 超时时间: {config_data['timeout']}秒")
        print(f"  - 输入变量名: {config_data['input_variable_name']}")
        print(f"  - 输出变量名: {config_data['output_variable_name']}")
        print()

        # 打印模式信息
        print_mode_info(config_data)

        # 如果有工作流映射，列出可用的知识库
        if config_data["workflow_mapping"]:
            print()
            print_available_knowledge_bases(config_data["workflow_mapping"])

    except Exception as e:
        print(f"✗ 配置加载失败: {e}")
        print("请确保 config.ini 文件存在且包含正确的配置")
        return 1

    print()
    print("-" * 60)

    # 打印使用指南
    print_usage_guide(config_data["workflow_mapping"])
    print("-" * 60)

    # 创建配置对象和客户端（使用默认 API Key）
    # 过滤掉 WorkflowConfig 不接受的参数（如 execution_mode）
    workflow_config_params = {
        k: v for k, v in config_data.items() if k in WorkflowConfig.__dataclass_fields__
    }
    workflow_config = WorkflowConfig(**workflow_config_params)
    client = DifyWorkflowClient(workflow_config)

    # 当前使用的知识库（用于 Standard 模式的路由）
    current_knowledge_base: Optional[str] = None

    # 交互式循环
    while True:
        # 显示提示符（包含当前路由信息）
        prompt = "\n问题"
        if current_knowledge_base:
            prompt += f" [KB: {current_knowledge_base}]"
        prompt += ": "

        # 输入命令
        try:
            user_input = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\n退出调试工具")
            break

        # 退出检查
        if user_input.lower() in ["quit", "exit", "q"]:
            print("\n再见!")
            break

        # 跳过空输入
        if not user_input:
            continue

        # 处理命令
        if user_input.lower() in ["help", "h"]:
            print_usage_guide(config_data["workflow_mapping"])
            print("-" * 60)
            continue

        if user_input.lower() in ["list", "l"]:
            print("\n可用的知识库:")
            print_available_knowledge_bases(config_data["workflow_mapping"])
            print("-" * 60)
            continue

        if user_input.lower() in ["mode", "m"]:
            print()
            print_mode_info(config_data)
            if current_knowledge_base:
                print(f"  当前路由: {current_knowledge_base}")
            else:
                print("  当前路由: 默认 API Key")
            print("-" * 60)
            continue

        # 处理路由切换（仅 Standard 模式支持）
        if user_input.lower().startswith("kb:"):
            if config_data["execution_mode"] != "standard":
                print("\n⚠ 当前模式不支持路由功能")
                print(f"  当前模式: {config_data['execution_mode']}")
                print("  提示: 只有 Standard 模式支持动态路由")
                print("-" * 60)
                continue

            kb_name = user_input[3:].strip()

            # 切换到默认
            if kb_name.lower() == "default":
                print("\n✓ 切换到默认 API Key")
                current_knowledge_base = None
                print("-" * 60)
                continue

            # 验证知识库是否存在
            standardized_kb = kb_name.lower()
            if standardized_kb not in config_data["workflow_mapping"]:
                print(f"\n✗ 未找到知识库 '{kb_name}'")
                print("\n可用的知识库:")
                print_available_knowledge_bases(config_data["workflow_mapping"])
                print("-" * 60)
                continue

            # 切换路由
            print(f"\n✓ 切换到知识库: {kb_name}")
            current_knowledge_base = kb_name
            print("-" * 60)
            continue

        # 调用 API
        question = user_input
        print("\n正在调用 Dify API...")

        # 显示路由信息
        if current_knowledge_base:
            print(f"  使用路由: {current_knowledge_base}")
        else:
            print("  使用路由: 默认 API Key")

        try:
            result = await call_api_with_routing(
                client=client,
                question=question,
                input_variable_name=config_data["input_variable_name"],
                workflow_mapping=config_data["workflow_mapping"],
                knowledge_base=current_knowledge_base,
            )

            # 打印结果
            print("\n" + "=" * 60)
            print("✓ API 调用成功")
            print("=" * 60)

            # 提取答案
            output_var = config_data["output_variable_name"]
            if output_var in result:
                print(f"\n【输出变量: {output_var}】")
                print(result[output_var])

            # 打印完整响应（如果有其他字段）
            if len(result) > 1 or (len(result) == 1 and output_var not in result):
                print("\n【完整响应】")
                print(json.dumps(result, indent=2, ensure_ascii=False))

            print("=" * 60)

        except Exception as e:
            print("\n" + "-" * 60)
            print(f"✗ API 调用失败: {e}")
            print("-" * 60)

    # 关闭客户端
    await client.close()

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(asyncio.run(main()))
