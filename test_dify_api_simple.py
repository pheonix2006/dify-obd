import httpx
import asyncio
import json
import os

# 设置 NO_PROXY 确保可以访问本地服务
os.environ["NO_PROXY"] = "localhost,127.0.0.1" + ("," + os.environ.get("NO_PROXY", "")) if os.environ.get("NO_PROXY") else "localhost,127.0.0.1"

# 配置参数 (参考 config.ini)
API_KEY = "app-z4xFEhXMeemCQQbC5mcymxX9"
BASE_URL = "http://localhost:8088/v1"
USER_ID = "test_user_001"


async def test_dify_api():
    url = f"{BASE_URL}/chat-messages"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 模拟工作流调用载荷
    payload = {
        "inputs": {"query": "你好，请问你是谁？"}, # 工作流所需的变量
        "query": "你好，请问你是谁？",              # 必须包含 query 字段
        "response_mode": "blocking",
        "user": USER_ID,
    }
    print(f"系统 NO_PROXY: {os.environ.get('no_proxy', os.environ.get('NO_PROXY', '未设置'))}")
    print(f"正在请求 {url}...")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                url, 
                headers=headers, 
                json=payload, 
                timeout=120.0
            )
            
            # 状态码检查
            if response.status_code == 200:
                result = response.json()
                print("--- 请求成功 ---")
                print(f"任务 ID: {result.get('task_id')}")
                print(f"回复内容: {result.get('answer')}")
            else:
                print(f"--- 请求失败 ---")
                print(f"状态码: {response.status_code}")
                print(f"错误详情: {response.text}")
                
        except Exception as e:
            print(f"发生异常: {str(e)}")

if __name__ == "__main__":
    asyncio.run(test_dify_api())
