# API使用示例

本文档提供OBD项目的各种使用场景代码示例。

---

## 📋 基础示例

### 示例1: 基本批处理

```python
from obd.models import WorkflowConfig
from obd.processor import WorkflowBatchProcessor

# 创建配置
config = WorkflowConfig(
    api_key="app-your-api-key",
    base_url="https://api.dify.ai/v1",
    response_mode="blocking",
    timeout=60,
    user="batch_processor_001"
)

# 创建处理器
processor = WorkflowBatchProcessor(config)

# 执行批处理
results = processor.process_excel(
    excel_path="questions.xlsx",
    question_column="question",
    answer_column="answer",
    comparison_method="keyword",
    delay=0.5
)

# 查看结果
for qa in results:
    print(f"问题: {qa.question}")
    print(f"期望: {qa.expected_answer}")
    print(f"实际: {qa.workflow_result}")
    print(f"结果: {'✓' if qa.is_correct else '✗'} ({qa.match_type})")
    print("---")

# 计算统计
stats = processor.calculate_statistics(results)
print(f"准确率: {stats['accuracy']:.1%}")
print(f"成功率: {stats['success_rate']:.1%}")
```

### 示例2: 处理单个问题

```python
from obd.models import WorkflowConfig
from obd.processor import WorkflowBatchProcessor

config = WorkflowConfig(api_key="app-your-api-key")
processor = WorkflowBatchProcessor(config)

# 处理单个问题
qa = processor.process_question(
    question="什么是机器学习？",
    input_variable_name="query",
    output_variable_name="answer",
    comparison_method="auto"
)

print(f"问题: {qa.question}")
print(f"答案: {qa.workflow_result}")
print(f"是否成功: {'是' if not qa.error else '否'}")
if qa.error:
    print(f"错误: {qa.error}")
```

---

## 🎯 高级示例

### 示例3: 自定义对比策略

```python
from obd.comparator import AnswerComparator
from obd.models import QuestionAnswer

class CustomComparator(AnswerComparator):
    """自定义答案对比器"""

    def compare(self, expected: str, actual: str, method="auto") -> tuple:
        # 数字答案必须精确匹配
        if expected.isdigit():
            return self.exact_match(expected, actual), "exact"

        # 中文问题使用关键词匹配
        if any('\u4e00' <= char <= '\u9fff' for char in expected):
            return self.keyword_match(expected, actual), "keyword"

        # 默认使用自动匹配
        return super().compare(expected, actual, method)

# 使用自定义对比器
comparator = CustomComparator()
expected = "579"
actual = "五百七十九"

is_match, match_type = comparator.compare(expected, actual)
print(f"匹配结果: {is_match}, 类型: {match_type}")
```

### 示例4: 批量处理优化

```python
import asyncio
import aiohttp
from typing import List, Dict, Any

async def async_api_call(session: aiohttp.ClientSession,
                        config: Dict[str, Any],
                        question: str) -> QuestionAnswer:
    """异步API调用"""
    url = f"{config['base_url']}/chat-messages"

    payload = {
        "query": question,
        "inputs": {},
        "response_mode": "blocking",
        "user": config["user"]
    }

    headers = {
        'Authorization': f'Bearer {config["api_key"]}',
        'Content-Type': 'application/json'
    }

    try:
        async with session.post(url, json=payload, headers=headers) as response:
            data = await response.json()
            answer = data.get("answer", "")

            return QuestionAnswer(
                question=question,
                expected_answer="",
                workflow_result=answer,
                is_correct=False,  # 需要后续对比
                workflow_run_id=data.get("task_id")
            )
    except Exception as e:
        return QuestionAnswer(
            question=question,
            expected_answer="",
            error=str(e)
        )

async def batch_process_async(questions: List[str],
                            config: Dict[str, Any],
                            max_concurrent: int = 3) -> List[QuestionAnswer]:
    """异步批量处理"""
    connector = aiohttp.TCPConnector(limit=max_concurrent)

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for question in questions:
            task = asyncio.create_task(async_api_call(session, config, question))
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        return results

# 使用示例
async def main():
    config = {
        "api_key": "app-your-api-key",
        "base_url": "https://api.dify.ai/v1",
        "user": "async_processor"
    }

    questions = [
        "1+1等于几？",
        "中国的首都是哪里？",
        "5的平方是多少？"
    ]

    results = await batch_process_async(questions, config)
    print(f"处理了 {len(results)} 个问题")

    # 后续处理...
    for qa in results:
        print(f"问题: {qa.question}, 结果: {qa.workflow_result}")

# 运行
# asyncio.run(main())
```

---

## 🔧 配置示例

### 示例5: 多环境配置

```python
import configparser
from pathlib import Path
from obd.models import WorkflowConfig

def load_config(env: str = "development") -> WorkflowConfig:
    """加载不同环境的配置"""
    config_path = Path("config.ini")

    if not config_path.exists():
        # 创建默认配置
        create_default_config(config_path, env)

    config_parser = configparser.ConfigParser()
    config_parser.read(config_path)

    # 根据环境选择配置节
    if env == "production":
        dify_section = "Dify_Production"
    elif env == "staging":
        dify_section = "Dify_Staging"
    else:
        dify_section = "Dify_Development"

    # 加载配置
    dify_config = config_parser[dify_section]

    return WorkflowConfig(
        api_key=dify_config.get("api_key"),
        base_url=dify_config.get("base_url"),
        response_mode=dify_config.get("response_mode", "blocking"),
        timeout=dify_config.getint("timeout", 60),
        user=dify_config.get("user", "batch_processor")
    )

def create_default_config(path: Path, env: str):
    """创建默认配置文件"""
    config_content = f"""[Dify_Development]
api_key = dev-your-api-key
base_url = http://localhost/v1
response_mode = blocking
timeout = 60
user = dev_processor

[Dify_Staging]
api_key = staging-your-api-key
base_url = https://api.staging.dify.ai/v1
response_mode = blocking
timeout = 60
user = staging_processor

[Dify_Production]
api_key = prod-your-api-key
base_url = https://api.dify.ai/v1
response_mode = blocking
timeout = 120
user = prod_processor

[Excel]
file_path = questions.xlsx
question_column = question
answer_column = answer

[Workflow]
input_variable_name = query
output_variable_name = answer
comparison_method = auto
delay = 0.5

[Output]
file_path = results.xlsx
"""

    with open(path, 'w', encoding='utf-8') as f:
        f.write(config_content)

# 使用示例
config = load_config("production")
processor = WorkflowBatchProcessor(config)
```

### 示例6: 动态配置

```python
from obd.models import WorkflowConfig
from typing import Optional

class DynamicWorkflowConfig(WorkflowConfig):
    """动态配置类"""

    def __init__(self, api_key: str, **kwargs):
        super().__init__(api_key=api_key, **kwargs)
        self._retry_count = kwargs.get('retry_count', 3)
        self._retry_delay = kwargs.get('retry_delay', 1)

    @property
    def retry_count(self) -> int:
        return self._retry_count

    @retry_count.setter
    def retry_count(self, value: int):
        self._retry_count = max(1, value)

    def validate(self) -> bool:
        """验证配置有效性"""
        if not self.api_key.startswith(('app-', 'workflow-')):
            raise ValueError("API密钥格式无效")

        if self.timeout <= 0:
            raise ValueError("超时时间必须大于0")

        if self.delay < 0:
            raise ValueError("延迟时间不能为负数")

        return True

# 使用示例
try:
    config = DynamicWorkflowConfig(
        api_key="app-your-api-key",
        base_url="https://api.dify.ai/v1",
        timeout=60,
        delay=0.5,
        retry_count=5  # 自定义重试次数
    )

    config.validate()
    processor = WorkflowBatchProcessor(config)
    print("配置验证通过")

except ValueError as e:
    print(f"配置验证失败: {e}")
```

---

## 📊 统计和分析示例

### 示例7: 详细统计分析

```python
import pandas as pd
from obd.processor import WorkflowBatchProcessor
from obd.models import WorkflowConfig

def analyze_results(results: List[QuestionAnswer]) -> Dict[str, Any]:
    """详细分析处理结果"""

    # 基础统计
    stats = {
        "total": len(results),
        "successful": sum(1 for r in results if not r.error),
        "failed": sum(1 for r in results if r.error),
        "correct": sum(1 for r in results if r.is_correct),
        "incorrect": sum(1 for r in results if not r.is_correct and not r.error)
    }

    # 按匹配类型统计
    match_stats = {}
    for r in results:
        if r.match_type:
            match_stats[r.match_type] = match_stats.get(r.match_type, 0) + 1

    # 按问题长度分析
    length_stats = {
        "avg_question_length": sum(len(r.question) for r in results) / len(results),
        "avg_answer_length": sum(len(r.workflow_result or "") for r in results) / len(results)
    }

    # 错误分析
    error_types = {}
    for r in results:
        if r.error:
            error_type = r.error.split(":")[0]
            error_types[error_type] = error_types.get(error_type, 0) + 1

    return {
        "basic_stats": stats,
        "match_types": match_stats,
        "length_stats": length_stats,
        "error_analysis": error_types
    }

# 使用示例
config = WorkflowConfig(api_key="app-your-api-key")
processor = WorkflowBatchProcessor(config)

# 处理数据
results = processor.process_excel("questions.xlsx")

# 分析结果
analysis = analyze_results(results)

print("=== 详细分析报告 ===")
print(f"总数量: {analysis['basic_stats']['total']}")
print(f"成功率: {analysis['basic_stats']['successful']/analysis['basic_stats']['total']:.1%}")
print(f"准确率: {analysis['basic_stats']['correct']/analysis['basic_stats']['total']:.1%}")
print("\n匹配类型分布:")
for match_type, count in analysis['match_types'].items():
    print(f"  {match_type}: {count}")

if analysis['error_analysis']:
    print("\n错误类型分布:")
    for error_type, count in analysis['error_analysis'].items():
        print(f"  {error_type}: {count}")
```

### 示例8: 结果可视化

```python
import matplotlib.pyplot as plt
from obd.processor import WorkflowBatchProcessor

def plot_results(results: List[QuestionAnswer]):
    """可视化处理结果"""

    # 准备数据
    labels = ['Correct', 'Incorrect', 'Failed']
    sizes = [
        sum(1 for r in results if r.is_correct),
        sum(1 for r in results if not r.is_correct and not r.error),
        sum(1 for r in results if r.error)
    ]

    # 创建饼图
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # 结果分布
    ax1.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90)
    ax1.set_title('Results Distribution')

    # 匹配类型分布
    match_types = {}
    for r in results:
        if r.match_type:
            match_types[r.match_type] = match_types.get(r.match_type, 0) + 1

    ax2.bar(match_types.keys(), match_types.values())
    ax2.set_title('Match Types Distribution')
    ax2.set_xlabel('Match Type')
    ax2.set_ylabel('Count')

    plt.tight_layout()
    plt.savefig('results_analysis.png')
    plt.close()

# 使用示例
config = WorkflowConfig(api_key="app-your-api-key")
processor = WorkflowBatchProcessor(config)
results = processor.process_excel("questions.xlsx")
plot_results(results)
print("图表已保存为 results_analysis.png")
```

---

## 🛠️ 错误处理示例

### 示例9: 完善的错误处理

```python
import logging
from obd.models import WorkflowConfig, QuestionAnswer
from obd.processor import WorkflowBatchProcessor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def robust_batch_processing(config: WorkflowConfig,
                           excel_path: str,
                           max_retries: int = 3) -> List[QuestionAnswer]:
    """健壮的批处理"""
    processor = WorkflowBatchProcessor(config)
    all_results = []

    try:
        # 加载Excel文件
        df = processor.load_excel(excel_path)

        # 分批处理以避免内存问题
        batch_size = 100
        total_batches = (len(df) + batch_size - 1) // batch_size

        for batch_idx in range(total_batches):
            start_row = batch_idx * batch_size
            end_row = min((batch_idx + 1) * batch_size, len(df))

            logger.info(f"处理批次 {batch_idx + 1}/{total_batches} "
                       f"(行 {start_row + 1}-{end_row})")

            # 处理当前批次
            try:
                batch_results = processor.process_excel(
                    excel_path=excel_path,
                    start_row=start_row,
                    end_row=end_row,
                    delay=1.0  # 增加延迟避免限流
                )

                # 重试失败的项
                for qa in batch_results:
                    if qa.error and max_retries > 0:
                        logger.warning(f"重试问题: {qa.question[:50]}...")
                        for retry in range(max_retries):
                            try:
                                new_qa = processor.process_question(qa.question)
                                if not new_qa.error:
                                    qa = new_qa
                                    break
                            except Exception as e:
                                logger.error(f"重试 {retry + 1} 失败: {e}")

                all_results.extend(batch_results)

                # 记录批次统计
                batch_success = sum(1 for r in batch_results if not r.error)
                logger.info(f"批次完成: {batch_success}/{len(batch_results)} 成功")

            except Exception as e:
                logger.error(f"批次 {batch_idx + 1} 处理失败: {e}")
                # 继续处理下一批次
                continue

    except Exception as e:
        logger.error(f"批处理失败: {e}")
        raise

    # 最终统计
    total = len(all_results)
    successful = sum(1 for r in all_results if not r.error)

    logger.info(f"处理完成: {successful}/{total} 成功 "
               f"({successful/total:.1%})")

    return all_results

# 使用示例
try:
    config = WorkflowConfig(api_key="app-your-api-key")
    results = robust_batch_processing(config, "questions.xlsx", max_retries=2)

    # 保存结果
    processor = WorkflowBatchProcessor(config)
    stats = processor.calculate_statistics(results)
    processor.save_results(results, stats, "robust_results.xlsx")

except Exception as e:
    logger.error(f"程序异常退出: {e}")
```

---

## 📝 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v0.1.0 | 2025-12-29 | 初始版本，提供基础和高级使用示例 |
| v0.1.1 | 2025-12-29 | 增加异步处理、错误处理、统计分析示例 |

---

## 📞 相关资源

- [快速开始指南](quickstart.md) - 5分钟快速上手
- [API接口文档](api.md) - 完整API文档
- [数据模型文档](models.md) - 数据结构说明
- [问题排查指南](troubleshooting.md) - 常见问题解决方案