import requests
import json
import configparser
import os

def test_dify_api_sync():
    # 打印代理环境变量
    print(f"系统 NO_PROXY: {os.environ.get('no_proxy', os.environ.get('NO_PROXY', '未设置'))}")
    
    # 获取当前脚本所在目录
    base_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir, 'config.ini')
    
    # 如果 config.ini 不存在，则使用默认值或提示
    if not os.path.exists(config_path):
        print(f"配置文件 {config_path} 不存在，请根据 config.ini.example 创建。")
        # 备选软硬编码（参考 test_dify_api_simple.py）
        API_KEY = "app-3nLTdXKOIfONflheHujqlkYa"
        BASE_URL = "http://localhost/v1"
        TIMEOUT = 60
    else:
        # 读取配置
        config = configparser.ConfigParser()
        config.read(config_path, encoding='utf-8')
        
        API_KEY = config.get('Dify', 'api_key', fallback="YOUR_DIFY_API_KEY")
        BASE_URL = config.get('Dify', 'base_url', fallback="http://localhost/v1")
        TIMEOUT = config.getint('Dify', 'timeout', fallback=60)
    
    url = f"{BASE_URL}/chat-messages"
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 载荷内容
    payload = {
        "inputs": {"query": "你好，请问你是谁？"}, 
        "query": "你好，请问你是谁？",              
        "response_mode": "blocking",
        "user": "test_user_sync_001",
    }
    
    print(f"正在进行同步请求: {url}")
    
    try:
        # 使用 requests 发送同步 POST 请求
        response = requests.post(
            url, 
            headers=headers, 
            json=payload, 
            timeout=TIMEOUT
        )
        
        # 检查响应
        if response.status_code == 200:
            result = response.json()
            print("--- 请求成功 ---")
            print(f"任务 ID: {result.get('task_id')}")
            print(f"回复内容: {result.get('answer')}")
        else:
            print(f"--- 请求失败 ---")
            print(f"状态码: {response.status_code}")
            print(f"错误详情: {response.text}")
            
    except requests.exceptions.Timeout:
        print("请求超时，请检查 Dify 服务是否正常运行。")
    except Exception as e:
        print(f"发生异常: {str(e)}")

if __name__ == "__main__":
    test_dify_api_sync()
