# 安装和配置指南

## 📋 系统要求

### 基础环境
- **操作系统**: Windows 10/11, macOS 10.15+, Linux (Ubuntu 18.04+)
- **Python版本**: 3.11 或更高版本
- **内存**: 最小 512MB，推荐 2GB+
- **存储**: 最小 100MB 可用空间

### 网络要求
- **Dify API**: 需要访问 Dify 服务（本地或云端）
- **网络协议**: HTTP/HTTPS
- **端口**: 80 (HTTP), 443 (HTTPS), 或自定义端口

---

## 🚀 安装步骤

### 1. 环境准备

#### 检查 Python 版本
```bash
python --version
# 或
python3 --version
```
确保版本为 3.11 或更高。

#### 安装 uv（如果尚未安装）
```bash
# Windows (通过 PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux (通过 Shell)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 验证安装
uv --version
```

### 2. 项目克隆

```bash
# 克隆项目
git clone <repository-url>
cd obd

# 创建虚拟环境
uv venv

# 激活虚拟环境
# Windows
.obd\Scripts\activate
# macOS/Linux
source .obd/bin/activate
```

### 3. 依赖安装

```bash
# 安装项目依赖
uv pip install -r requirements.txt

# 或安装开发依赖（包括测试工具）
uv pip install -e ".[dev]"
```

### 4. 验证安装

```bash
# 运行测试套件
uv run pytest

# 验证程序运行
uv run python -m obd.main --help 2>/dev/null || echo "配置文件缺失，请继续下一步"
```

---

## ⚙️ 配置设置

### 1. 配置文件详解

创建 `config.ini` 文件：

```ini
[Dify]
# Dify API密钥（必需）
# 从 Dify 控制台的应用设置中获取
api_key = app-your-api-key-here

# Dify API基础URL
# 默认值：https://api.dify.ai/v1
# 如果使用本地部署，请修改为 http://localhost/v1
base_url = https://api.dify.ai/v1

# 响应模式
# blocking: 阻塞模式，等待完整响应
# streaming: 流式模式，实时接收响应
response_mode = blocking

# 请求超时时间（秒）
timeout = 60

[Workflow]
# 工作流ID（可选）
# 如果使用特定版本的工作流，请填写ID
# workflow_id = your-workflow-id

# 工作流输入变量名
# 确保与Dify工作流中定义的变量名一致
input_variable_name = query

# 工作流输出变量名
# 确保与Dify工作流输出的变量名一致
output_variable_name = answer

# 答案对比方法
# exact: 精确匹配
# fuzzy: 模糊匹配
# keyword: 关键词匹配
# auto: 自动选择（推荐）
comparison_method = auto

# 请求之间的延迟（秒）
# 避免API限流，推荐0.5-1.0
delay = 0.5

[Excel]
# Excel文件路径
# 支持相对路径和绝对路径
file_path = questions.xlsx

# 问题列名
question_column = question

# 答案列名
answer_column = answer

[Output]
# 结果输出文件路径
file_path = results.xlsx
```

### 2. API密钥获取

#### 云端 Dify
1. 登录 [Dify 控制台](https://cloud.dify.ai)
2. 选择你的应用
3. 进入「设置」→「API访问」
4. 复制 API 密钥

#### 本地 Dify
1. 打开本地 Dify 管理界面
2. 进入应用管理
3. 找到 API 设置页面
4. 生成或获取 API 密钥

### 3. Excel文件格式

#### 标准格式
```
|     question     |    answer     |
|------------------|---------------|
| 请计算1+1=?     | 2             |
| 北京是首都吗？   | 是            |
| 5的立方是多少？   | 125           |
```

#### 文件要求
- 支持 `.xlsx` 和 `.csv` 格式
- 第一行必须是列名
- 列名可以在配置文件中指定
- 建议文件大小不超过 10MB

---

## 🔧 本地开发环境

### 1. 开发工具配置

#### VS Code 推荐插件
```json
{
    "python.analysis.typeCheckingMode": "strict",
    "python.testing.unittestEnabled": false,
    "python.testing.pytestEnabled": true,
    "editor.formatOnSave": true,
    "python.formatting.provider": "black"
}
```

#### pre-commit 钩子
```bash
# 安装 pre-commit
uv pip install pre-commit

# 安装钩子
pre-commit install
```

### 2. 代码格式化

```bash
# 格式化代码
uv run black src/ tests/

# 检查代码
uv run ruff check src/ tests/

# 类型检查
uv run mypy src/
```

### 3. 运行测试

```bash
# 运行所有测试
uv run pytest

# 运行特定测试
uv run pytest tests/test_client.py

# 生成覆盖率报告
uv run pytest --cov=src --cov-report=html
```

---

## 🚀 运行示例

### 1. 命令行运行

```bash
# 基础运行（使用配置文件）
uv run python -m obd.main

# 指定配置文件
uv run python -m obd.main --config custom_config.ini
```

### 2. 程序化调用

```python
from obd.models import WorkflowConfig
from obd.processor import WorkflowBatchProcessor

# 创建配置
config = WorkflowConfig(
    api_key="app-your-api-key",
    base_url="http://localhost/v1",
    timeout=60
)

# 创建处理器
processor = WorkflowBatchProcessor(config)

# 处理Excel
results = processor.process_excel(
    excel_path="questions.xlsx",
    question_column="问题",
    answer_column="答案",
    comparison_method="keyword"
)

# 获取统计
stats = processor.calculate_statistics(results)
print(f"准确率: {stats['accuracy']:.2%}")

# 保存结果
processor.save_results(results, stats, "results.xlsx")
```

### 3. 批处理示例

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

def process_with_threading(processor, excel_path, max_workers=3):
    """使用多线程提高处理速度"""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交任务
        futures = [
            executor.submit(processor.process_excel, excel_path, start_row=i, end_row=i+100)
            for i in range(0, 1000, 100)  # 假设1000行，每批100行
        ]

        # 收集结果
        results = []
        for future in futures:
            results.extend(future.result())

        return results
```

---

## 🐛 故障排除

### 1. 常见错误

#### API密钥错误
```
错误: API调用失败: 401 Client Error: Unauthorized
解决: 检查 config.ini 中的 api_key 是否正确
```

#### 文件不存在
```
错误: FileNotFoundError: Excel文件不存在
解决: 检查 file_path 路径是否正确
```

#### 列名不存在
```
错误: ValueError: Excel文件中不存在列
解决: 检查 question_column 和 answer_column 是否正确
```

#### 依赖问题
```bash
# 更新依赖
uv pip install --upgrade -r requirements.txt

# 重新安装依赖
uv pip install --force-reinstall -r requirements.txt
```

### 2. 调试模式

```python
import logging

# 启用调试日志
logging.basicConfig(level=logging.DEBUG)

# 查看详细API调用信息
import os
os.environ["OBD_DEBUG"] = "1"
```

### 3. 网络问题

#### 代理设置
```bash
# 设置环境变量
export HTTP_PROXY="http://proxy.example.com:8080"
export HTTPS_PROXY="http://proxy.example.com:8080"
```

#### 证书问题
```python
# 忽略证书验证（仅开发环境）
import requests
requests.packages.urllib3.disable_warnings()
```

---

## 📊 性能优化

### 1. 大文件处理

```python
# 分批处理大文件
def process_large_file(file_path, batch_size=500):
    processor = WorkflowBatchProcessor(config)

    # 分批读取
    for chunk in pd.read_excel(file_path, chunksize=batch_size):
        # 保存临时文件
        temp_file = f"temp_{chunk_index}.xlsx"
        chunk.to_excel(temp_file, index=False)

        # 处理当前批次
        results = processor.process_excel(temp_file)

        # 合并结果
        # ...

        # 清理临时文件
        os.remove(temp_file)
```

### 2. 内存优化

```python
# 及时释放资源
def process_with_memory_optimization():
    # 使用上下文管理器
    with WorkflowBatchProcessor(config) as processor:
        results = processor.process_excel("large_file.xlsx")

    # processor 对象会被自动清理
```

### 3. 缓存机制

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_answer_comparison(expected, actual):
    """缓存对比结果"""
    return comparator.compare(expected, actual)
```

---

## 🔒 安全考虑

### 1. API密钥安全

- 不要在代码中硬编码密钥
- 使用环境变量或配置文件
- 定期更换API密钥
- 权限最小化原则

### 2. 数据安全

- 处理完成后及时清理临时文件
- 敏感信息不要记录到日志
- 使用HTTPS进行API通信

### 3. 输入验证

```python
def validate_excel_file(file_path):
    """验证Excel文件"""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    if file_path.size > 10 * 1024 * 1024:  # 10MB
        raise ValueError("文件大小超过10MB限制")
```

---

## 📝 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v0.1.0 | 2025-12-29 | 初始版本，基础安装配置说明 |
| v0.1.1 | 2025-12-29 | 增加本地部署配置和故障排除指南 |

---

## 📞 技术支持

### 获取帮助
- 查看 [快速开始指南](quickstart.md)
- 参考 [API使用示例](examples.md)
- 阅读 [问题排查指南](troubleshooting.md)

### 报告问题
- 在 GitHub Issues 中提交
- 提供完整的错误信息和环境
- 附上重现步骤和配置文件