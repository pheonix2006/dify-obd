"""Dify API 诊断脚本"""

import json
import requests
import configparser

# 加载配置
config = configparser.ConfigParser()
config.read("config.ini")

api_key = config.get("Dify", "api_key")
base_url = config.get("Dify", "base_url")

print("=" * 70)
print("Dify API 诊断工具")
print("=" * 70)
print()

print(f"API Key: {api_key}")
print(f"Base URL: {base_url}")
print()

# 检查API key类型
print("-" * 70)
print("1. API Key 类型检查")
print("-" * 70)
if api_key.startswith("app-"):
    print("✓ 这是应用 API Key (app-*)")
    print("  说明: 用于通过API调用Dify应用")
    print("  适用端点: /chat-messages, /completion-messages")
elif api_key.startswith("dataset-"):
    print("✓ 这是数据集 API Key (dataset-*)")
    print("  说明: 用于数据集管理")
elif api_key.startswith("tool-"):
    print("✓ 这是工具 API Key (tool-*)")
    print("  说明: 用于外部工具调用")
else:
    print("✗ 未知的API Key格式")
print()

# 测试最简单的请求
print("-" * 70)
print("2. 测试最小化请求")
print("-" * 70)

url = f"{base_url}/chat-messages"
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# 最小化payload
payload = {
    "inputs": {},
    "query": "测试",
    "response_mode": "blocking",
    "user": "test"
}

print(f"URL: {url}")
print(f"Headers: {json.dumps({k: v[:20] + '...' if len(str(v)) > 20 else v for k, v in headers.items()}, indent=2)}")
print(f"Payload: {json.dumps(payload, ensure_ascii=False)}")
print()

try:
    response = requests.post(url, json=payload, headers=headers, timeout=30)
    print(f"状态码: {response.status_code}")

    if response.status_code == 401:
        print("✗ 401 Unauthorized - API密钥无效或已过期")
        print()
        print("可能的解决方案:")
        print("  1. 检查Dify控制台中的应用设置")
        print("  2. 确认API密钥是否已启用")
        print("  3. 检查API密钥是否已复制完整")
        print("  4. 确认API密钥是否已过期")
        print()
        print("请检查以下内容:")
        print("  - 在Dify控制台中，进入应用设置 -> API访问")
        print("  - 确认'启用API访问'已开启")
        print("  - 复制完整的API密钥（包括app-前缀）")
        print("  - 检查密钥是否有过期时间限制")
    elif response.status_code == 200:
        print("✓ 200 OK - API调用成功!")
        print(f"响应: {response.text[:500]}")
    else:
        print(f"响应状态: {response.status_code}")
        print(f"响应内容: {response.text[:500]}")

except Exception as e:
    print(f"请求失败: {e}")

print()
print("=" * 70)
print("诊断建议")
print("=" * 70)
print()
print("如果遇到401错误，请按以下步骤检查:")
print()
print("1️⃣ 打开Dify控制台 (https://cloud.dify.ai)")
print("2️⃣ 找到您的应用/工作流")
print("3️⃣ 进入'设置' -> 'API访问'页面")
print("4️⃣ 确认以下内容:")
print("   - ✓ 启用API访问 (Enable API Access) 已开启")
print("   - ✓ 已创建并复制了正确的API密钥")
print("   - ✓ API密钥以'app-'开头")
print("   - ✓ 检查密钥是否设置了过期时间")
print()
print("5️⃣ 如果是工作流应用，还需要确认:")
print("   - ✓ 工作流已发布")
print("   - ✓ 工作流中定义了'query'输入变量")
print()
print("6️⃣ 更新config.ini中的API密钥后重新运行测试")
print()
