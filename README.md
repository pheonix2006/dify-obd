# OBD - Dify工作流批处理器

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)

**一个强大的Dify API批处理工具，支持Excel问答批量处理和答案对比分析**

</div>

---

## 📋 项目简介

OBD (Open Batch Processor) 是一个专门用于批量调用Dify工作流API的Python工具。它可以：

- 📖 **批量处理**: 从Excel文件读取问题，批量调用Dify API
- 🎯 **答案对比**: 支持精确、模糊、关键词等多种答案匹配算法
- 📊 **统计分析**: 自动计算准确率、成功率等关键指标
- 📈 **结果导出**: 生成详细的Excel处理报告
- ⚡ **高性能**: 支持本地和云端Dify部署，灵活配置

### 🎯 适用场景

- **教育评估**: 自动批改作业和考试题目
- **质量检测**: 对比AI回答与标准答案的一致性
- **数据标注**: 批量验证AI生成内容的质量
- **API测试**: 测试Dify工作流的响应准确性

---

## 🚀 快速开始

### 环境要求

- **Python**: 3.11 或更高版本
- **操作系统**: Windows 10/11, macOS 10.15+, Linux (Ubuntu 18.04+)
- **内存**: 最小 512MB，推荐 2GB+
- **网络**: 需要访问 Dify 服务（本地或云端）

### 安装步骤

#### 1. 环境准备
```bash
# 检查 Python 版本
python --version  # 需要 3.11+

# 安装 uv (推荐) 或 pip
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 2. 克隆项目
```bash
git clone <repository-url>
cd obd

# 创建虚拟环境
uv venv

# 激活虚拟环境
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

#### 3. 安装依赖
```bash
# 安装项目依赖
uv pip install -r requirements.txt

# 或安装开发依赖（包含测试工具）
uv pip install -e ".[dev]"
```

### 配置设置

#### 1. 创建配置文件
```bash
# 复制配置模板
cp config.ini.example config.ini
```

#### 2. 编辑配置文件
```ini
[Dify]
# ✅ 替换为你的Dify API密钥
api_key = app-your-api-key-here

# ✅ 选择Dify服务地址
# 云端Dify (默认)
base_url = https://api.dify.ai/v1
# 或本地Dify
# base_url = http://localhost/v1

[Excel]
# Excel文件路径
file_path = questions.xlsx

# ✅ 确认列名与Excel文件一致
question_column = question
answer_column = answer

[Workflow]
# 答案对比方法
# exact: 精确匹配 | fuzzy: 模糊匹配 | keyword: 关键词匹配 | auto: 自动选择
comparison_method = auto

# 请求间隔（秒，避免限流）
delay = 0.5
```

#### 3. 准备Excel文件
```excel
|     question     |    answer     |
|------------------|---------------|
| 请计算123+456=? | 579           |
| 北京是首都吗？   | 是            |
| 5的立方是多少？   | 125           |
```

### 运行示例

#### 命令行运行
```bash
# 基础运行
uv run python -m obd.main

# 指定配置文件
uv run python -m obd.main --config custom_config.ini
```

**预期输出:**
```
============================================================
Dify工作流批处理器 - 真实API测试
============================================================
加载配置: {...}
处理Excel文件: questions.xlsx
共 3 行，处理第 0 行到第 2 行
------------------------------------------------------------
[1/3] 处理问题: 请计算123+456=?...  ✓ 正确 (keyword)
[2/3] 处理问题: 北京是首都吗？...    ✓ 正确 (keyword)
[3/3] 处理问题: 5的立方是多少？...    ✓ 正确 (keyword)

============================================================
统计结果:
  总数量: 3
  正确数量: 3
  错误数量: 0
  失败数量: 0
  准确率: 100.00%
  成功率: 100.00%
============================================================

结果已保存到: results.xlsx
```

#### 程序化调用
```python
from obd.models import WorkflowConfig
from obd.processor import WorkflowBatchProcessor

# 创建配置
config = WorkflowConfig(
    api_key="app-your-api-key",
    base_url="http://localhost/v1"
)

# 创建处理器
processor = WorkflowBatchProcessor(config)

# 批量处理
results = processor.process_excel(
    excel_path="questions.xlsx",
    comparison_method="keyword"
)

# 查看统计
stats = processor.calculate_statistics(results)
print(f"准确率: {stats['accuracy']:.1%}")
```

---

## 🔧 API文档

### 核心接口

#### 1. Dify API端点

**POST** `{base_url}/chat-messages`

**请求参数:**
```json
{
    "query": "用户输入的问题",
    "inputs": {},
    "response_mode": "blocking",
    "user": "用户标识",
    "conversation_id": "",
    "workflow_id": "可选的工作流ID"
}
```

**响应示例:**
```json
{
    "event": "message",
    "task_id": "task_123",
    "answer": "123 + 456 = 579",
    "mode": "advanced-chat"
}
```

#### 2. 答案对比算法

| 算法 | 说明 | 适用场景 |
|------|------|----------|
| **exact** | 精确匹配（忽略大小写和空格） | 数字、代码、标准化答案 |
| **fuzzy** | 模糊匹配（相似度≥0.8） | 表述相近的答案 |
| **keyword** | 关键词匹配 | 包含关键信息的答案 |
| **auto** | 自动选择（推荐） | 按优先级尝试所有算法 |

#### 3. 配置参数详解

```python
@dataclass
class WorkflowConfig:
    api_key: str                    # Dify API密钥
    base_url: str = "https://api.dify.ai/v1"  # API地址
    response_mode: str = "blocking" # 响应模式
    timeout: int = 60               # 超时时间(秒)
    user: str = "batch_processor"   # 用户标识
```

### 错误处理

| 错误码 | 说明 | 解决方案 |
|--------|------|----------|
| 401 | API密钥无效 | 检查api_key配置 |
| 400 | 参数错误 | 检查请求格式 |
| 429 | 请求过频 | 增加delay参数 |
| 500 | 服务器错误 | 稍后重试 |

---

## 📁 项目结构

```
obd/
├── .spec/                           # 项目文档
│   ├── README.md                     # 文档导航
│   ├── api.md                        # API接口文档
│   ├── models.md                     # 数据模型文档
│   └── ...
├── src/
│   └── obd/                         # 主包
│       ├── __init__.py
│       ├── main.py                   # 程序入口
│       ├── models.py                 # 数据模型
│       ├── client/                   # API客户端
│       │   └── dify_client.py        # Dify API封装
│       ├── comparator/              # 答案对比
│       │   └── answer_comparator.py  # 匹配算法
│       └── processor/                # 批处理
│           └── batch_processor.py    # 批处理核心
├── tests/                           # 测试目录
├── config.ini                       # 配置文件(请勿提交)
├── config.ini.example              # 配置模板
├── requirements.txt                # 依赖列表
└── pyproject.toml                   # 项目配置
```

---

## 🛠️ 开发指南

### 本地开发

```bash
# 克隆项目
git clone <repo-url>
cd obd
uv venv
source .venv/bin/activate

# 安装开发依赖
uv pip install -e ".[dev]"

# 运行测试
uv run pytest

# 代码格式化
uv run black src/ tests/
uv run ruff check src/ tests/

# 类型检查
uv run mypy src/
```

### TDD开发流程

1. **红**: 写测试，看到失败
2. **绿**: 写最少的代码让测试通过
3. **重构**: 优化代码结构

```bash
# 运行特定测试
uv run pytest tests/test_client.py -v

# 运行测试并生成覆盖率
uv run pytest --cov=src --cov-report=html

# 持续测试（文件变化时自动运行）
uv run pytest --watch
```

---

## 📊 性能优化

### 大文件处理
```python
# 分批处理大文件
def process_large_file(file_path, batch_size=500):
    processor = WorkflowBatchProcessor(config)

    for chunk in pd.read_excel(file_path, chunksize=batch_size):
        temp_file = f"temp_{chunk_index}.xlsx"
        chunk.to_excel(temp_file, index=False)
        results = processor.process_excel(temp_file)
        # 合并结果...
        os.remove(temp_file)
```

### 并发处理（实验性）
```python
import asyncio
import aiohttp

async def async_process(questions, config, max_concurrent=3):
    # 实现异步API调用
    # 注意：不要设置过高的并发数
    pass
```

---

## 📈 监控指标

- **处理速度**: 行/分钟
- **成功率**: (total - failed) / total
- **准确率**: correct / total
- **平均延迟**: API响应时间
- **内存使用**: 峰值内存占用

---

## 🤝 贡献指南

### 开发流程
1. Fork 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 遵循 TDD 开发
4. 运行测试 (`uv run pytest`)
5. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
6. 推送到分支 (`git push origin feature/AmazingFeature`)
7. 创建 Pull Request

### 代码规范
- 使用 Black 格式化代码
- 遵循 PEP 8 命名规范
- 添加类型注解
- 编写测试用例

---

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

## 📞 联系我们

- **问题反馈**: [GitHub Issues](../../issues)
- **功能建议**: [GitHub Discussions](../../discussions)
- **技术支持**: [邮箱](mailto:support@example.com)

---

## 🙏 致谢

- [Dify](https://docs.dify.ai/) - 强大的AI应用平台
- [uv](https://docs.astral.sh/uv/) - 快速的Python包管理器
- [pandas](https://pandas.pydata.org/) - 强大的数据处理库

---

<div align="center">
Made with ❤️ by OBD Team
</div>