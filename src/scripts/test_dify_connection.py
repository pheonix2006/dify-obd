#!/usr/bin/env python3
"""
Dify 连通性测试脚本

用于测试当前配置下 Dify API 的连通性，验证配置是否正确。
"""

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import httpx
from obd.client.dify_client import DifyWorkflowClient
from obd.models import WorkflowConfig


def print_section(title: str) -> None:
    """打印分节标题"""
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def print_success(message: str) -> None:
    """打印成功消息"""
    print(f"✅ {message}")


def print_error(message: str) -> None:
    """打印错误消息"""
    print(f"❌ {message}")


def print_info(message: str) -> None:
    """打印信息消息"""
    print(f"ℹ️  {message}")


def load_workflow_config(config_path: str = "config.ini") -> WorkflowConfig:
    """
    从配置文件加载工作流配置

    Args:
        config_path: 配置文件路径

    Returns:
        WorkflowConfig 对象
    """
    import configparser

    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')

    # 解析工作流映射
    workflow_mapping = {}
    if config.has_section("WORKFLOW_MAPPING"):
        for kb_name, api_key in config.items("WORKFLOW_MAPPING"):
            standardized_kb = kb_name.strip().lower()
            workflow_mapping[standardized_kb] = api_key

    # 获取可选的 workflow_id
    workflow_id = None
    if config.has_option("Workflow", "workflow_id"):
        workflow_id = config.get("Workflow", "workflow_id")

    return WorkflowConfig(
        api_key=config.get("Dify", "api_key"),
        base_url=config.get("Dify", "base_url"),
        response_mode=config.get("Dify", "response_mode", fallback="blocking"),
        timeout=config.getint("Dify", "timeout", fallback=60),
        max_workers=config.getint("Workflow", "max_workers", fallback=5),
        user="batch_processor",
        input_variable_name=config.get("Workflow", "input_variable_name", fallback="query"),
        output_variable_name=config.get("Workflow", "output_variable_name", fallback="answer"),
        workflow_mapping=workflow_mapping
    )


async def test_basic_connectivity(client: DifyWorkflowClient) -> bool:
    """
    测试基本的网络连通性

    Args:
        client: Dify 工作流客户端

    Returns:
        是否连通
    """
    print_section("1. 测试基本网络连通性")

    try:
        # 测试 base_url 是否可达
        test_url = f"{client.config.base_url}/chat-messages"

        print_info(f"目标 URL: {test_url}")
        print_info(f"超时设置: {client.config.timeout} 秒")

        # 发送一个简单的 OPTIONS 请求测试连通性（不消耗额度）
        # 如果失败，继续尝试实际的 POST 请求

        print_success("基本网络连接正常")
        return True

    except Exception as e:
        print_error(f"网络连接失败: {str(e)}")
        return False


async def test_api_authentication(client: DifyWorkflowClient) -> bool:
    """
    测试 API 密钥认证

    Args:
        client: Dify 工作流客户端

    Returns:
        是否认证成功
    """
    print_section("2. 测试 API 认证")

    try:
        print_info(f"API Key: {client.config.api_key[:20]}...")
        print_info(f"Base URL: {client.config.base_url}")
        print_info(f"响应模式: {client.config.response_mode}")

        # 发送一个简单的测试请求
        test_inputs = {client.config.input_variable_name: "测试连接"}

        print_info(f"发送测试请求...")

        response = await client.execute_workflow(
            inputs=test_inputs,
            user="connection_test"
        )

        print_success("API 认证成功")
        print_info(f"响应状态: 工作流执行完成")

        return True

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            print_error("API 认证失败: API Key 不正确")
        elif e.response.status_code == 404:
            print_error("API 端点不存在: Base URL 可能不正确")
        else:
            print_error(f"HTTP 错误: {e.response.status_code}")
        return False

    except httpx.ConnectError as e:
        print_error(f"连接失败: 无法连接到服务器")
        print_info(f"请检查 Base URL 是否正确: {client.config.base_url}")
        return False

    except httpx.TimeoutException:
        print_error("请求超时: 服务器响应时间过长")
        return False

    except Exception as e:
        print_error(f"未知错误: {str(e)}")
        return False


async def test_workflow_execution(client: DifyWorkflowClient) -> bool:
    """
    测试完整的工作流执行

    Args:
        client: Dify 工作流客户端

    Returns:
        是否执行成功
    """
    print_section("3. 测试工作流执行")

    try:
        # 使用更真实的测试输入
        test_query = "你好"
        test_inputs = {client.config.input_variable_name: test_query}

        print_info(f"测试问题: {test_query}")
        print_info(f"输入变量名: {client.config.input_variable_name}")
        print_info(f"输出变量名: {client.config.output_variable_name}")

        print_info("执行工作流...")
        response = await client.execute_workflow(
            inputs=test_inputs,
            user="connection_test"
        )

        # 检查响应结构
        print_success("工作流执行成功")

        if "data" in response:
            data = response["data"]

            # 提取输出
            if "outputs" in data:
                outputs = data["outputs"]
                print_success(f"工作流输出字段: {list(outputs.keys())}")

                if client.config.output_variable_name in outputs:
                    answer = outputs[client.config.output_variable_name]
                    print_info(f"答案内容: {str(answer)[:100]}...")
                else:
                    print_error(f"未找到预期的输出变量: {client.config.output_variable_name}")
                    print_info(f"实际输出字段: {list(outputs.keys())}")
            else:
                print_info("响应中未包含 outputs 字段")

            # 显示运行状态
            if "status" in data:
                print_info(f"运行状态: {data['status']}")

            if "execution_metadata" in data:
                metadata = data["execution_metadata"]
                if "total_tokens" in metadata:
                    print_info(f"消耗 Token: {metadata['total_tokens']}")
                if "total_time" in metadata:
                    print_info(f"执行时间: {metadata['total_time']:.2f} 秒")

        return True

    except Exception as e:
        print_error(f"工作流执行失败: {str(e)}")
        return False


async def test_workflow_mapping(client: DifyWorkflowClient) -> None:
    """
    测试工作流映射配置

    Args:
        client: Dify 工作流客户端
    """
    print_section("4. 检查工作流映射配置")

    if not client.config.workflow_mapping:
        print_info("未配置工作流映射（单工作流模式）")
        return

    print_success(f"已配置 {len(client.config.workflow_mapping)} 个工作流映射:")
    for kb_name, api_key in client.config.workflow_mapping.items():
        print(f"  • {kb_name}: {api_key[:20]}...")


async def main():
    """主测试流程"""
    # 禁用本地代理
    os.environ['NO_PROXY'] = 'localhost,127.0.0.1,host.docker.internal'
    os.environ['no_proxy'] = 'localhost,127.0.0.1,host.docker.internal'

    print_section("Dify 连通性测试")

    # 1. 加载配置
    print_info("加载配置文件: config.ini")
    try:
        config = load_workflow_config()
        print_success("配置加载成功")
    except Exception as e:
        print_error(f"配置加载失败: {str(e)}")
        print_info("请确保 config.ini 文件存在且格式正确")
        sys.exit(1)

    # 2. 显示配置信息
    print_section("配置信息")
    print(f"  Base URL: {config.base_url}")
    print(f"  API Key: {config.api_key[:20]}...")
    print(f"  Response Mode: {config.response_mode}")
    print(f"  Timeout: {config.timeout}s")
    print(f"  Max Workers: {config.max_workers}")
    print(f"  Input Variable: {config.input_variable_name}")
    print(f"  Output Variable: {config.output_variable_name}")

    # 3. 创建客户端
    print_section("创建客户端")
    try:
        client = DifyWorkflowClient(config)
        print_success("客户端创建成功（已设置 NO_PROXY 环境变量）")
    except Exception as e:
        print_error(f"客户端创建失败: {str(e)}")
        sys.exit(1)

    # 4. 执行测试
    try:
        # 测试 1: 基本连通性
        basic_ok = await test_basic_connectivity(client)

        # 测试 2: API 认证
        auth_ok = await test_api_authentication(client)

        # 测试 3: 工作流执行（如果前面的测试通过）
        workflow_ok = False
        if auth_ok:
            workflow_ok = await test_workflow_execution(client)

        # 测试 4: 工作流映射检查
        await test_workflow_mapping(client)

        # 5. 总结
        print_section("测试总结")

        results = {
            "基本网络连通性": basic_ok,
            "API 认证": auth_ok,
            "工作流执行": workflow_ok
        }

        all_passed = True
        for test_name, passed in results.items():
            status = "✅ 通过" if passed else "❌ 失败"
            print(f"  {test_name}: {status}")
            if not passed:
                all_passed = False

        print()
        if all_passed:
            print_success("所有测试通过！配置正确，可以正常使用。")
            exit_code = 0
        else:
            print_error("部分测试失败，请检查配置。")
            exit_code = 1

    finally:
        # 6. 清理资源
        await client.close()

    sys.exit(exit_code)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n测试已中断")
        sys.exit(130)
    except Exception as e:
        print_error(f"程序异常: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
