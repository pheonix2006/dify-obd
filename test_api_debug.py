"""API调试脚本"""

import requests
import configparser

# 加载配置
config = configparser.ConfigParser()
config.read("config.ini")

api_key = config.get("Dify", "api_key")
base_url = config.get("Dify", "base_url")

print(f"API Key: {api_key}")
print(f"Base URL: {base_url}")
print()

# 测试1: 尝试 /workflows/run 端点
print("测试 /workflows/run 端点...")
url = f"{base_url}/workflows/run"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "inputs": {"query": "测试"},
    "response_mode": "blocking",
    "user": "test_user"
}

print(f"URL: {url}")
print(f"Headers: {headers}")
print(f"Payload: {payload}")
print()

try:
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    print(f"状态码: {response.status_code}")
    print(f"响应头: {dict(response.headers)}")
    print(f"响应内容: {response.text}")
except Exception as e:
    print(f"请求失败: {e}")

print()
print("=" * 60)

# 测试2: 尝试 /chat-messages 端点（参考您的示例）
print("测试 /chat-messages 端点...")
url = f"{base_url}/chat-messages"

payload = {
    "inputs": {},
    "query": "测试消息",
    "response_mode": "blocking",
    "conversation_id": "",
    "user": "test_user"
}

print(f"URL: {url}")
print(f"Payload: {payload}")
print()

try:
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {response.text}")
except Exception as e:
    print(f"请求失败: {e}")

print()
print("=" * 60)

# 测试3: 测试 workflows 端点（列出工作流）
print("测试 /workflows 端点...")
url = f"{base_url}/workflows"
print(f"URL: {url}")
print()

try:
    response = requests.get(url, headers=headers, timeout=30)
    print(f"状态码: {response.status_code}")
    print(f"响应内容: {response.text}")
except Exception as e:
    print(f"请求失败: {e}")
