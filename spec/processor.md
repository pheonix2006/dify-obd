# 批处理模块文档

## 📋 概述

批处理模块（`WorkflowBatchProcessor`）是OBD项目的核心组件，负责读取Excel文件、批量调用Dify API、对比答案并生成统计报告。

## 🏗️ 模块架构

### 核心类

```python
class WorkflowBatchProcessor:
    """工作流批处理器"""

    def __init__(self, config: WorkflowConfig, client=None):
        # 初始化配置和客户端
```

### 依赖关系

```
WorkflowBatchProcessor
├── DifyWorkflowClient (API调用)
├── AnswerComparator (答案对比)
├── pandas (Excel处理)
└── WorkflowConfig (配置管理)
```

## 🔧 详细接口

### 1. 初始化方法

```python
def __init__(self, config: WorkflowConfig, client=None):
    """
    初始化批处理器

    Args:
        config: 工作流配置
        client: 可选的Dify客户端，默认创建新实例
    """
    self.config = config
    self.client = client or DifyWorkflowClient(config)
    self.comparator = AnswerComparator()
```

### 2. Excel文件处理

#### load_excel(excel_path: str) -> pd.DataFrame

**功能**: 加载Excel或CSV文件

**参数**:
- `excel_path`: 文件路径（支持 .xlsx, .csv）

**返回**: pandas DataFrame

**实现逻辑**:
```python
def load_excel(self, excel_path: str) -> pd.DataFrame:
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Excel文件不存在: {excel_path}")

    try:
        # 尝试读取Excel
        df = pd.read_excel(excel_path)
    except Exception:
        # 如果不是Excel，尝试读取CSV
        df = pd.read_csv(excel_path)

    return df
```

**异常处理**:
- `FileNotFoundError`: 文件不存在
- `ValueError`: 文件格式不支持

### 3. 单问题处理

#### process_question(...) -> QuestionAnswer

**功能**: 处理单个问题，调用API并返回结果

**签名**:
```python
def process_question(
    self,
    question: str,
    input_variable_name: str = "query",
    output_variable_name: str = "answer",
    comparison_method: str = "auto",
    user: Optional[str] = None,
    workflow_id: Optional[str] = None
) -> QuestionAnswer:
```

**参数说明**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `question` | `str` | - | 要处理的问题文本 |
| `input_variable_name` | `str` | `"query"` | 工作流输入变量名 |
| `output_variable_name` | `str` | `"answer"` | 工作流输出变量名 |
| `comparison_method` | `str` | `"auto"` | 答案对比方法 |
| `user` | `Optional[str]` | `None` | 用户标识 |
| `workflow_id` | `Optional[str]` | `None` | 工作流ID |

**实现流程**:
```python
def process_question(self, question: str, **kwargs) -> QuestionAnswer:
    # 1. 创建QuestionAnswer对象
    qa = QuestionAnswer(question=question, expected_answer="")

    try:
        # 2. 准备API调用参数
        inputs = {kwargs.get('input_variable_name', 'query'): question}

        # 3. 调用Dify API
        result = self.client.execute_workflow(
            inputs,
            kwargs.get('user'),
            kwargs.get('workflow_id')
        )

        # 4. 提取结果
        qa.workflow_run_id = result.get("task_id")
        if "answer" in result:
            qa.workflow_result = str(result["answer"])
        else:
            qa.workflow_result = json.dumps(result, ensure_ascii=False)

    except Exception as e:
        qa.error = str(e)

    return qa
```

### 4. 批量处理

#### process_excel(...) -> List[QuestionAnswer]

**功能**: 批量处理Excel文件中的所有问题

**签名**:
```python
def process_excel(
    self,
    excel_path: str,
    question_column: str = "question",
    answer_column: str = "answer",
    input_variable_name: str = "query",
    output_variable_name: str = "answer",
    comparison_method: str = "auto",
    start_row: int = 0,
    end_row: Optional[int] = None,
    delay: float = 0.5,
    workflow_id: Optional[str] = None
) -> List[QuestionAnswer]:
```

**参数说明**:
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `excel_path` | `str` | - | Excel文件路径 |
| `question_column` | `str` | `"question"` | 问题列名 |
| `answer_column` | `str` | `"answer"` | 答案列名 |
| `start_row` | `int` | `0` | 起始行（0-based） |
| `end_row` | `Optional[int]` | `None` | 结束行（不包含） |
| `delay` | `float` | `0.5` | 请求延迟（秒） |
| `workflow_id` | `Optional[str]` | `None` | 工作流ID |

**实现逻辑**:
```python
def process_excel(self, excel_path: str, **kwargs) -> List[QuestionAnswer]:
    # 1. 加载Excel文件
    df = self.load_excel(excel_path)

    # 2. 检查必需列
    required_columns = [kwargs.get('question_column', 'question'),
                      kwargs.get('answer_column', 'answer')]
    for col in required_columns:
        if col not in df.columns:
            raise ValueError(f"Excel文件中不存在列: {col}")

    # 3. 确定处理范围
    total_rows = len(df)
    end_row = kwargs.get('end_row') or total_rows
    end_row = min(end_row, total_rows)

    print(f"共 {total_rows} 行，处理第 {start_row} 行到第 {end_row-1} 行")

    # 4. 批量处理
    results = []
    for idx in range(start_row, end_row):
        row = df.iloc[idx]
        question = str(row[kwargs.get('question_column', 'question')])
        expected_answer = str(row[kwargs.get('answer_column', 'answer')])

        # 处理单个问题
        qa = self.process_question(
            question,
            input_variable_name=kwargs.get('input_variable_name', 'query'),
            output_variable_name=kwargs.get('output_variable_name', 'answer'),
            comparison_method=kwargs.get('comparison_method', 'auto'),
            workflow_id=kwargs.get('workflow_id')
        )
        qa.expected_answer = expected_answer

        # 对比答案
        if qa.workflow_result and not qa.error:
            is_match, match_type = self.comparator.compare(
                expected_answer,
                qa.workflow_result,
                method=kwargs.get('comparison_method', 'auto')
            )
            qa.is_correct = is_match
            qa.match_type = match_type

        results.append(qa)

        # 延迟以避免请求过快
        delay = kwargs.get('delay', 0.5)
        if delay > 0 and idx < end_row - 1:
            time.sleep(delay)

    return results
```

### 5. 统计计算

#### calculate_statistics(results: List[QuestionAnswer]) -> Dict[str, Any]

**功能**: 计算批处理结果的统计信息

**返回结构**:
```python
{
    "total": int,                    # 总数量
    "correct": int,                  # 正确数量
    "incorrect": int,                # 错误数量
    "failed": int,                   # 失败数量
    "accuracy": float,               # 准确率
    "success_rate": float,           # 成功率
    "match_type_stats": dict         # 匹配类型统计
}
```

**实现逻辑**:
```python
def calculate_statistics(self, results: List[QuestionAnswer]) -> Dict[str, Any]:
    total = len(results)
    if total == 0:
        return {}

    # 计算各种数量
    correct = sum(1 for qa in results if qa.is_correct)
    failed = sum(1 for qa in results if qa.error is not None)
    incorrect = total - correct - failed

    # 按匹配类型统计
    match_type_stats = {}
    for qa in results:
        if qa.match_type:
            match_type_stats[qa.match_type] = match_type_stats.get(qa.match_type, 0) + 1

    return {
        "total": total,
        "correct": correct,
        "incorrect": incorrect,
        "failed": failed,
        "accuracy": correct / total,
        "success_rate": (total - failed) / total,
        "match_type_stats": match_type_stats
    }
```

### 6. 结果保存

#### save_results(...) -> None

**功能**: 将处理结果保存到Excel文件

**实现逻辑**:
```python
def save_results(self, results: List[QuestionAnswer], statistics: Dict[str, Any], output_path: str):
    # 1. 转换为DataFrame
    data = []
    for idx, qa in enumerate(results):
        data.append({
            "序号": idx + 1,
            "问题": qa.question,
            "期望答案": qa.expected_answer,
            "工作流结果": qa.workflow_result,
            "是否正确": "✓" if qa.is_correct else "✗",
            "匹配类型": qa.match_type or "",
            "错误信息": qa.error or "",
            "工作流运行ID": qa.workflow_run_id or ""
        })

    df = pd.DataFrame(data)

    # 2. 保存到Excel
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        # 保存结果Sheet
        df.to_excel(writer, sheet_name="处理结果", index=False)

        # 保存统计信息Sheet
        stats_data = [
            ["总数量", statistics.get("total", 0)],
            ["正确数量", statistics.get("correct", 0)],
            ["错误数量", statistics.get("incorrect", 0)],
            ["失败数量", statistics.get("failed", 0)],
            ["准确率", f"{statistics.get('accuracy', 0):.2%}"],
            ["成功率", f"{statistics.get('success_rate', 0):.2%}"]
        ]

        stats_df = pd.DataFrame(stats_data, columns=["指标", "数值"])
        stats_df.to_excel(writer, sheet_name="统计信息", index=False)
```

## 🚀 使用示例

### 基础用法

```python
from obd.models import WorkflowConfig
from obd.processor import WorkflowBatchProcessor

# 1. 创建配置
config = WorkflowConfig(
    api_key="app-your-api-key",
    base_url="http://localhost/v1"
)

# 2. 创建批处理器
processor = WorkflowBatchProcessor(config)

# 3. 批量处理
results = processor.process_excel(
    excel_path="questions.xlsx",
    question_column="question",
    answer_column="answer",
    comparison_method="keyword"
)

# 4. 计算统计
stats = processor.calculate_statistics(results)

# 5. 保存结果
processor.save_results(results, stats, "results.xlsx")
```

### 高级用法

```python
# 指定工作流版本
results = processor.process_excel(
    excel_path="large_dataset.xlsx",
    question_column="问题",
    answer_column="标准答案",
    input_variable_name="query",
    output_variable_name="response",
    comparison_method="auto",
    start_row=0,
    end_row=100,  # 只处理前100行
    delay=1.0,    # 1秒延迟
    workflow_id="your-workflow-id"
)

# 自定义用户标识
for qa in results:
    qa.user = "test_user_001"
```

## 🎯 性能优化

### 1. 请求控制
- **延迟设置**: 建议设置0.5-1秒的请求间隔
- **超时配置**: 根据API响应速度调整timeout
- **错误重试**: 对临时错误实现自动重试

### 2. 内存管理
- **分批处理**: 大文件时使用分批处理
- **及时清理**: 处理完成后及时释放资源
- **数据压缩**: 对大文本结果进行压缩存储

### 3. 进度显示
- **实时反馈**: 显示处理进度和状态
- **错误统计**: 实时统计成功/失败数量
- **预估时间**: 根据延迟计算剩余时间

## 🐛 常见问题

### 1. Excel文件格式问题
```python
# 错误：文件不存在
try:
    df = processor.load_excel("not_exist.xlsx")
except FileNotFoundError as e:
    print(f"文件不存在: {e}")

# 错误：列名不存在
try:
    results = processor.process_excel("data.xlsx", question_column="问题")
except ValueError as e:
    print(f"列名错误: {e}")
```

### 2. API调用失败处理
```python
# 检查失败数量
failed_count = sum(1 for qa in results if qa.error)
if failed_count > 0:
    print(f"有 {failed_count} 个调用失败")
    # 可以选择重试失败的项
```

### 3. 内存不足处理
```python
# 大文件分批处理
def process_large_excel(excel_path: str, batch_size=100):
    df = pd.read_excel(excel_path)
    total_rows = len(df)

    all_results = []
    for i in range(0, total_rows, batch_size):
        batch = df.iloc[i:i+batch_size]
        # 处理当前批次
        results = process_batch(batch)
        all_results.extend(results)

    return all_results
```

## 📊 监控指标

### 关键指标
1. **处理速度**: 行/分钟
2. **成功率**: (total - failed) / total
3. **准确率**: correct / total
4. **平均延迟**: 平均每个请求的处理时间
5. **错误率**: failed / total

### 日志记录
```python
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 在关键位置记录日志
logger.info(f"开始处理Excel文件: {excel_path}")
logger.info(f"处理完成，总耗时: {elapsed_time}秒")
logger.warning(f"发现 {failed_count} 个失败请求")
```

---

## 📝 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v0.1.0 | 2025-12-29 | 初始版本，支持基础批处理功能 |
| v0.1.1 | 2025-12-29 | 修正API调用格式，支持chat-messages端点 |

---

## 📞 相关文档

- [API接口文档](api.md) - Dify API调用规范
- [数据模型文档](models.md) - 数据结构定义
- [答案对比模块文档](comparator.md) - 匹配算法详解