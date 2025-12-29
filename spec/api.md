# Dify API 接口文档

## 📋 概述

本模块负责与Dify API进行交互，支持调用工作流和聊天应用。

## 🔗 API端点

### 1. Chat Messages API (聊天消息)

#### 基本信息
- **URL**: `POST {base_url}/chat-messages`
- **认证**: Bearer Token
- **Content-Type**: `application/json`

#### 请求参数

```python
@dataclass
class ChatRequestPayload:
    query: str                          # 用户输入的问题 (必需)
    inputs: Dict[str, Any] = {}         # 输入变量字典 (可选)
    response_mode: str = "blocking"     # 响应模式: "blocking" 或 "streaming"
    conversation_id: str = ""            # 会话ID (可选)
    user: str = ""                      # 用户标识 (可选)
    files: List[Dict] = []              # 文件列表 (可选)
    auto_generate_name: bool = True      # 是否自动生成标题 (可选)
    workflow_id: Optional[str] = None   # 工作流ID (可选)
    trace_id: Optional[str] = None      # 链路追踪ID (可选)
```

#### 请求示例

```json
{
    "query": "请计算123 + 456 = ?",
    "inputs": {},
    "response_mode": "blocking",
    "user": "batch_processor",
    "conversation_id": "",
    "auto_generate_name": true
}
```

#### 响应结构

```python
@dataclass
class ChatResponse:
    event: str                          # 事件类型: "message"
    task_id: str                        # 任务ID
    id: str                            # 消息ID
    message_id: str                    # 消息唯一ID
    conversation_id: str                # 会话ID
    mode: str                          # 应用模式: "advanced-chat"
    answer: str                        # 完整回复内容
    metadata: Dict[str, Any]           # 元数据
    usage: Usage                       # 使用量信息
    retriever_resources: List[RetrieverResource]  # 引用资源
    created_at: int                    # 创建时间戳
```

#### 响应示例

```json
{
    "event": "message",
    "task_id": "d60bce47-9c50-4ba4-9f99-50acee439cdc",
    "id": "dc07bf05-b119-456b-8e0b-d53cfc2e18fa",
    "message_id": "dc07bf05-b119-456b-8e0b-d53cfc2e18fa",
    "conversation_id": "c9e1c173-918e-4894-a10b-a03bf507aa8b",
    "mode": "advanced-chat",
    "answer": "123 + 456 = 579",
    "metadata": {
        "annotation_reply": null,
        "retriever_resources": []
    },
    "usage": {
        "prompt_tokens": 1085,
        "prompt_unit_price": "2",
        "prompt_price_unit": "0.000001",
        "prompt_price": "0.00217",
        "completion_tokens": 8,
        "completion_unit_price": "3",
        "completion_price_unit": "0.000001",
        "completion_price": "0.000024",
        "total_tokens": 1093,
        "total_price": "0.002194",
        "currency": "RMB",
        "latency": 1.681,
        "time_to_first_token": 2.945,
        "time_to_generate": 0.673
    },
    "created_at": 1766997316
}
```

### 2. Workflow Run Detail API (工作流详情)

#### 基本信息
- **URL**: `GET {base_url}/workflows/run/{workflow_run_id}`
- **认证**: Bearer Token
- **Content-Type**: `application/json`

#### 响应结构

```python
@dataclass
class WorkflowDetailResponse:
    workflow_run_id: str                # 工作流运行ID
    workflow_id: str                    # 关联的Workflow ID
    status: str                         # 执行状态
    outputs: Dict[str, Any]             # 输出内容
    error: Optional[str] = None         # 错误信息 (如果有)
    elapsed_time: float                 # 耗时(秒)
    created_at: int                     # 开始时间
    finished_at: Optional[int] = None   # 结束时间
```

## 🔐 认证方式

### Bearer Token

```python
headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}
```

- `api_key`: 从Dify控制台获取的应用API密钥
- 格式: `app-xxxxxxxxxxxxxxxxxxxxxxxxxxxx`

## 📊 错误处理

### 常见错误码

| 状态码 | 错误码 | 错误信息 | 解决方案 |
|--------|--------|----------|----------|
| 401 | unauthorized | Access token is invalid | 检查API密钥是否正确 |
| 400 | invalid_param | Field validation error | 检查请求参数格式 |
| 400 | app_unavailable | App configuration is unavailable | 检查应用是否已发布 |
| 404 | not_found | App or workflow not found | 检查应用ID或工作流ID |
| 429 | rate_limit_exceeded | Rate limit exceeded | 降低请求频率 |
| 500 | internal_server_error | Server error | 稍后重试 |

### 错误处理示例

```python
try:
    response = client.execute_workflow({"query": "你好"})
except requests.exceptions.HTTPError as e:
    if response.status_code == 401:
        print("API密钥无效")
    elif response.status_code == 400:
        print("请求参数错误")
    else:
        print(f"HTTP错误: {e}")
```

## 🚀 客户端封装

### DifyWorkflowClient 类

#### 初始化

```python
from obd.models import WorkflowConfig

config = WorkflowConfig(
    api_key="app-xxxxxxxxxxxxxxxx",
    base_url="https://api.dify.ai/v1",
    response_mode="blocking",
    timeout=60,
    user="batch_processor"
)

client = DifyWorkflowClient(config)
```

#### 调用示例

```python
# 基础调用
result = client.execute_workflow(
    inputs={"query": "请计算123 + 456"},
    user="test_user"
)
answer = result["answer"]

# 带工作流ID的调用
result = client.execute_workflow(
    inputs={"query": "你好"},
    user="test_user",
    workflow_id="your-workflow-id"
)
```

#### 获取详情

```python
detail = client.get_workflow_run_detail("task_id_123")
print(f"状态: {detail['status']}")
print(f"输出: {detail['outputs']}")
```

## ⚡ 性能优化

### 1. 请求延迟
- 建议设置0.5-1秒的请求间隔
- 避免触发API限流

### 2. 超时设置
- blocking模式建议60-120秒超时
- streaming模式建议30-60秒超时

### 3. 错误重试
- 对于5xx错误，实现指数退避重试
- 对于4xx错误，立即停止并提示

### 4. 并发控制
- 不建议高并发调用
- 建议串行处理以避免限流

---

## 📝 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v0.1.0 | 2025-12-29 | 初始版本，支持/chat-messages端点 |
| v0.1.1 | 2025-12-29 | 修正API调用格式，添加query字段支持 |

---

## 📞 技术支持

如有问题，请参考：
- [Dify官方文档](https://docs.dify.ai/)
- [项目问题排查指南](../troubleshooting.md)