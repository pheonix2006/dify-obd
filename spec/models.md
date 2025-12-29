# 数据模型文档

## 📋 概述

本文档详细说明OBD项目中的所有数据结构定义，包括类型注解和字段说明。

## 🏗️ 核心模型

### 1. WorkflowConfig

#### 基本信息
- **文件**: `src/obd/models.py`
- **用途**: Dify工作流API配置
- **类型**: `dataclass`

#### 定义

```python
@dataclass
class WorkflowConfig:
    """工作流配置"""

    # --- 必需参数 ---
    api_key: str                    # Dify API密钥

    # --- 可选参数（带默认值） ---
    base_url: str = "https://api.dify.ai/v1"  # API基础URL
    response_mode: str = "blocking"  # 响应模式
    timeout: int = 60               # 请求超时时间（秒）
    user: str = "batch_processor"   # 用户标识
```

#### 字段说明

| 字段名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `api_key` | `str` | ✓ | - | Dify API密钥，格式为 `app-xxxxxxxx` |
| `base_url` | `str` | ✗ | `"https://api.dify.ai/v1"` | Dify API的基础URL |
| `response_mode` | `str` | ✗ | `"blocking"` | 响应模式：`blocking`（阻塞）或 `streaming`（流式） |
| `timeout` | `int` | ✗ | `60` | HTTP请求超时时间（秒） |
| `user` | `str` | ✗ | `"batch_processor"` | 用户标识，用于API调用追踪 |

#### 示例

```python
# 基础配置
config = WorkflowConfig(
    api_key="app-2Fc9P3zdLTX1bkB9l6cbiv3y"
)

# 完整配置
config = WorkflowConfig(
    api_key="app-2Fc9P3zdLTX1bkB9l6cbiv3y",
    base_url="http://localhost/v1",  # 本地部署
    response_mode="blocking",
    timeout=120,
    user="my_batch_processor"
)
```

### 2. QuestionAnswer

#### 基本信息
- **文件**: `src/obd/models.py`
- **用途**: 存储问题-答案对及处理结果
- **类型**: `dataclass`

#### 定义

```python
@dataclass
class QuestionAnswer:
    """问题-答案对"""

    # --- 基础字段 ---
    question: str                   # 问题文本
    expected_answer: str            # 期望答案

    # --- API处理结果 ---
    workflow_result: Optional[str] = None   # 工作流返回结果
    workflow_run_id: Optional[str] = None  # 工作流运行ID

    # --- 对比结果 ---
    is_correct: bool = False         # 是否匹配
    match_type: Optional[str] = None       # 匹配类型

    # --- 错误处理 ---
    error: Optional[str] = None     # 错误信息
```

#### 字段说明

| 字段名 | 类型 | 必需 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `question` | `str` | ✓ | - | 用户输入的问题文本 |
| `expected_answer` | `str` | ✓ | - | Excel中的期望答案 |
| `workflow_result` | `Optional[str]` | ✗ | `None` | Dify API返回的回答内容 |
| `workflow_run_id` | `Optional[str]` | ✗ | `None` | API调用的任务ID或工作流ID |
| `is_correct` | `bool` | ✗ | `False` | 是否与期望答案匹配 |
| `match_type` | `Optional[str]` | ✗ | `None` | 匹配类型：`exact`/`fuzzy`/`keyword` |
| `error` | `Optional[str]` | ✗ | `None` | 调用API时的错误信息 |

#### 匹配类型说明

| 类型 | 说明 | 触发条件 |
|------|------|----------|
| `exact` | 精确匹配 | 字符串完全相同（忽略大小写和首尾空格） |
| `fuzzy` | 模糊匹配 | 使用相似度算法计算，默认阈值0.8 |
| `keyword` | 关键词匹配 | 期望答案的关键词出现在工作流结果中 |
| `no_match` | 无匹配 | 所有匹配算法都失败 |

#### 示例

```python
# 成功匹配
qa = QuestionAnswer(
    question="请计算123 + 456 = ?",
    expected_answer="579",
    workflow_result="123 + 456 = 579",
    is_correct=True,
    match_type="exact",
    workflow_run_id="task_123"
)

# 失败匹配
qa = QuestionAnswer(
    question="北京是中国的首都吗？",
    expected_answer="是",
    workflow_result="是的，北京是中国的首都。",
    is_correct=False,
    match_type="keyword",
    workflow_run_id="task_124"
)

# API调用失败
qa = QuestionAnswer(
    question="什么是机器学习？",
    expected_answer="AI的分支",
    error="API调用失败: 401 Unauthorized",
    workflow_run_id=None
)
```

## 🔧 扩展模型

### 3. ComparisonMethod

#### 基本信息
- **文件**: `src/obd/comparator/answer_comparator.py`
- **用途**: 答案对比方法枚举
- **类型**: `Enum`

#### 定义

```python
from enum import Enum

class ComparisonMethod(Enum):
    """答案对比方法"""
    EXACT = "exact"          # 精确匹配
    FUZZY = "fuzzy"          # 模糊匹配
    KEYWORD = "keyword"      # 关键词匹配
    AUTO = "auto"           # 自动选择（按优先级尝试）
```

### 4. Statistics

#### 基本信息
- **文件**: `src/obd/processor/batch_processor.py`
- **用途**: 批处理统计信息
- **类型**: `Dict[str, Any]`

#### 结构定义

```python
Statistics = Dict[str, Any]
```

#### 字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `total` | `int` | 总处理数量 |
| `correct` | `int` | 正确数量 |
| `incorrect` | `int` | 错误数量（成功但答案不匹配） |
| `failed` | `int` | 失败数量（API调用失败） |
| `accuracy` | `float` | 准确率（correct/total） |
| `success_rate` | `float` | 成功率（(total-failed)/total） |
| `match_type_stats` | `Dict[str, int]` | 各匹配类型的数量统计 |

#### 示例

```python
statistics = {
    "total": 10,
    "correct": 9,
    "incorrect": 1,
    "failed": 0,
    "accuracy": 0.9,
    "success_rate": 1.0,
    "match_type_stats": {
        "exact": 5,
        "keyword": 4,
        "fuzzy": 0,
        "no_match": 1
    }
}
```

### 5. ResultRow

#### 基本信息
- **文件**: `src/obd/processor/batch_processor.py`
- **用途**: Excel结果行数据
- **类型**: `Dict[str, Any]`

#### 结构定义

```python
ResultRow = Dict[str, Any]
```

#### 字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `序号` | `int` | 行号 |
| `问题` | `str` | 原始问题 |
| `期望答案` | `str` | Excel中的期望答案 |
| `工作流结果` | `str` | Dify API返回的结果 |
| `是否正确` | `str` | "✓" 或 "✗" |
| `匹配类型` | `str` | exact/fuzzy/keyword/no_match |
| `错误信息` | `str` | API调用错误信息 |
| `工作流运行ID` | `str` | 任务ID |

#### 示例

```python
result_row = {
    "序号": 1,
    "问题": "请计算123 + 456 = ?",
    "期望答案": "579",
    "工作流结果": "123 + 456 = 579",
    "是否正确": "✓",
    "匹配类型": "exact",
    "错误信息": "",
    "工作流运行ID": "task_123"
}
```

## 🔄 数据流

### 批处理数据流

```
Excel文件
    ↓
读取到DataFrame
    ↓
转换为QuestionAnswer对象
    ↓
调用Dify API
    ↓
更新workflow_result和workflow_run_id
    ↓
使用AnswerComparator进行对比
    ↓
更新is_correct和match_type
    ↓
收集结果并计算Statistics
    ↓
写入Excel输出文件
```

### 数据转换示例

```python
# 1. 从Excel读取
row = {"question": "1+1=?", "answer": "2"}

# 2. 转换为QuestionAnswer
qa = QuestionAnswer(
    question=row["question"],
    expected_answer=row["answer"]
)

# 3. 调用API后
qa.workflow_result = "1+1=2"
qa.workflow_run_id = "task_456"

# 4. 对比后
qa.is_correct = True
qa.match_type = "exact"

# 5. 统计
statistics = {
    "total": 1,
    "correct": 1,
    "incorrect": 0,
    "failed": 0,
    "accuracy": 1.0,
    "success_rate": 1.0
}
```

## 🎯 最佳实践

### 1. 类型安全
- 始终使用类型注解
- 对可选字段使用 `Optional[type]`
- 使用 `@dataclass` 简化数据类定义

### 2. 错误处理
- 对可能失败的字段设置默认值
- 使用 `Optional` 类型表示可能为空的字段
- 在序列化时处理 `None` 值

### 3. 数据验证
- 在创建实例时验证必需字段
- 对字符串字段进行trim处理
- 验证枚举值的有效性

### 4. 序列化
- 确保所有数据类型可以被JSON序列化
- 处理日期时间的序列化
- 处理嵌套对象的序列化

---

## 📝 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v0.1.0 | 2025-12-29 | 初始版本，定义核心数据模型 |
| v0.1.1 | 2025-12-29 | 修正API响应处理逻辑，更新匹配类型说明 |

---

## 📞 相关文档

- [API接口文档](api.md) - Dify API调用规范
- [批处理模块文档](processor.md) - 批处理流程说明
- [答案对比模块文档](comparator.md) - 匹配算法详解