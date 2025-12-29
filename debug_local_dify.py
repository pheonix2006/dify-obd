"""本地Dify服务调试脚本"""

import json
import requests
import configparser

# 加载配置
config = configparser.ConfigParser()
config.read("config.ini")

api_key = config.get("Dify", "api_key")
base_url = config.get("Dify", "base_url")

print("=" * 70)
print("本地Dify服务调试")
print("=" * 70)
print(f"API Key: {api_key}")
print(f"Base URL: {base_url}")
print()

# 先测试连接性
print("-" * 70)
print("1. 测试服务连接性")
print("-" * 70)
try:
    response = requests.get(f"{base_url}/ping", timeout=10)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        print("✓ Dify服务可访问")
    else:
        print(f"✗ Dify服务返回异常状态: {response.status_code}")
except requests.exceptions.ConnectionError:
    print("✗ 无法连接到本地Dify服务")
    print("请确保Dify服务已启动，并且监听在正确的端口上")
    exit(1)
except Exception as e:
    print(f"✗ 连接测试失败: {e}")
    exit(1)

print()

# 测试API密钥有效性
print("-" * 70)
print("2. 测试API密钥")
print("-" * 70)
url = f"{base_url}/chat-messages"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# 最小化payload
payload = {
    "inputs": {},
    "query": "你好",
    "response_mode": "blocking",
    "user": "debug"
}

print(f"URL: {url}")
print(f"Headers: {headers}")
print(f"Payload: {json.dumps(payload, ensure_ascii=False)}")
print()

try:
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    print(f"状态码: {response.status_code}")
    print(f"响应头: {dict(response.headers)}")
    print(f"响应内容: {response.text}")
    print()

    if response.status_code == 400:
        print("400 Bad Request 分析:")
        print("可能的原因:")
        print("  1. 应用未正确配置")
        print("  2. 输入变量不匹配")
        print("  3. 工作流未发布")
        print("  4. API密钥权限不足")
        print()
        print("请检查:")
        print("  - 确认Dify控制台中已正确配置应用")
        print("  - 检查工作流是否已发布")
        print("  - 确认API密钥具有正确的权限")
    elif response.status_code == 401:
        print("401 Unauthorized - API密钥无效")
    elif response.status_code == 403:
        print("403 Forbidden - 权限不足")
    elif response.status_code == 404:
        print("404 Not Found - 应用不存在")
    elif response.status_code == 200:
        print("✓ API调用成功!")

except Exception as e:
    print(f"请求失败: {e}")

print()

# 尝试获取工作流列表（如果有权限）
print("-" * 70)
print("3. 尝试获取工作流信息")
print("-" * 70)
try:
    response = requests.get(f"{base_url}/workflows", headers=headers, timeout=10)
    print(f"状态码: {response.status_code}")
    if response.status_code == 200:
        try:
            workflows = response.json()
            print("工作流列表:")
            print(json.dumps(workflows, ensure_ascii=False, indent=2))
        except:
            print("响应内容:", response.text)
    else:
        print(f"获取工作流失败: {response.text}")
except Exception as e:
    print(f"获取工作流失败: {e}")

print()
print("=" * 70)
print("调试完成")
print("=" * 70)
print()
print("如果遇到400错误，请检查:")
print("1. Dify控制台中的应用设置")
print("2. 工作流的输入变量配置")
print("3. 是否需要workflow_id参数")
print("4. API密钥的权限设置")
print()
print("确保本地Dify服务已正确启动并配置了您的应用。")
