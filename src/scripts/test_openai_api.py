import requests
import json
import sys

# ================= 配置部分 =================
# 在这里设置你的 OpenAI API 配置
API_KEY = "YOUR_AZURE_OPENAI_KEY"
BASE_URL = "https://your-resource.openai.azure.com/openai/deployments/your-deployment/chat/completions?api-version=2025-01-01-preview"
MODEL_NAME = "gpt-4o"           # 或者你想要测试的模型名称，如 gpt-4
# ===========================================

def test_openai_chat():
    """
    测试 OpenAI 兼容接口的问答功能
    """
    url = f"{BASE_URL.rstrip('/')}"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    data = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "user", "content": "你好，请做一个简单的自我介绍。"}
        ],
        "temperature": 0.7
    }

    print(f"正在请求: {url}")
    print(f"使用模型: {MODEL_NAME}")
    print("-" * 30)

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        # 检查 HTTP 状态码
        response.raise_for_status()
        
        result = response.json()
        
        # 提取回答内容
        if "choices" in result and len(result["choices"]) > 0:
            answer = result["choices"][0]["message"]["content"]
            print("收到回答：")
            print(answer)
        else:
            print("API 返回格式不符合预期：")
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
    except requests.exceptions.RequestException as e:
        print(f"请求发生错误: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"错误详情: {e.response.text}")
    except Exception as e:
        print(f"解析响应时发生错误: {e}")

if __name__ == "__main__":
    test_openai_chat()
