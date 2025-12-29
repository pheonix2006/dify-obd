"""测试不同的API调用方式"""

import requests
import configparser

# 加载配置
config = configparser.ConfigParser()
config.read("config.ini")

api_key = config.get("Dify", "api_key")
base_url = config.get("Dify", "base_url")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

print(f"API Key: {api_key}")
print("=" * 60)

# 根据Dify文档，调用workflow可能需要workflow ID
# workflow API key通常以"workflow-"开头
# 应用API key以"app-"开头

print("\n测试不同的API端点格式...")
print()

# 方式1: 原始的 /workflows/run
print("1. 测试 /workflows/run (当前方式)")
url = f"{base_url}/workflows/run"
print(f"URL: {url}")
try:
    response = requests.post(
        url,
        json={"inputs": {"query": "测试"}, "response_mode": "blocking", "user": "test"},
        headers=headers,
        timeout=10
    )
    print(f"状态码: {response.status_code}")
    print(f"响应: {response.text[:200]}")
except Exception as e:
    print(f"错误: {e}")
print()

# 方式2: 尝试使用 /workflows/{id}/run 格式
print("2. 测试 /workflows/{id}/run (可能需要workflow ID)")
print("注意: 这种方式需要从Dify控制台获取workflow ID")
workflow_id = "your-workflow-id"  # 需要从Dify控制台获取
url = f"{base_url}/workflows/{workflow_id}/run"
print(f"URL: {url}")
print("(跳过测试，需要workflow ID)")
print()

# 方式3: 检查API key格式
print("3. 检查API key类型")
if api_key.startswith("app-"):
    print("   - 这是应用API key (app-)")
    print("   - 通常用于 chat-messages 端点")
    print("   - 可能不适合直接调用 workflows API")
elif api_key.startswith("workflow-"):
    print("   - 这是工作流API key (workflow-)")
    print("   - 用于 workflows 端点")
else:
    print("   - 未知的API key格式")
print()

# 建议
print("=" * 60)
print("建议：")
print("1. 检查Dify控制台中工作流的API密钥设置")
print("2. 确认是否需要使用workflow ID而不是直接调用/workflows/run")
print("3. 查看Dify文档中关于workflow API的调用方式")
print("4. 确认在Dify平台中启用了API访问权限")
print()

# 根据文档，Dify的workflow API调用可能需要:
# 1. 使用workflow ID
# 2. 使用不同的端点格式
# 让我们检查是否有workflow ID配置
try:
    if config.has_option("Workflow", "id"):
        workflow_id = config.get("Workflow", "id")
        print(f"配置中找到workflow ID: {workflow_id}")
    else:
        print("config.ini中没有配置workflow ID")
        print("请检查是否需要在config.ini中添加: [Workflow] id = <your-workflow-id>")
except:
    pass
