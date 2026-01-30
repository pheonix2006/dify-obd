# OBD - Dify 工作流批处理器

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Production--Ready-brightgreen.svg)

**批量调用 Dify 工作流 API，智能评测答案质量，生成详细分析报告**

</div>

---

## 📖 目录

- [项目概述](#项目概述)
- [核心功能](#核心功能)
- [快速开始](#快速开始)
- [开发环境搭建](#开发环境搭建)
- [架构设计](#架构设计)
- [模块说明](#模块说明)
- [开发指南](#开发指南)
- [测试](#测试)
- [常见问题](#常见问题)

---

## 项目概述

**OBD (Open Batch Processor)** 是一个专业的 Dify 工作流批量处理和评测工具，支持：

- 从 Excel 批量读取问题并调用 Dify API
- 基于 LLM 的语义级答案质量评测
- 双工作流对比评测（LLM1 vs LLM2 vs 历史版本）
- RAG 综合评测（无标准答案场景）
- 详细的分类统计和改进分析报告

### 技术栈

| 组件 | 技术 |
|------|------|
| **语言** | Python 3.11+ |
| **异步框架** | asyncio |
| **HTTP 客户端** | httpx |
| **数据处理** | pandas, openpyxl |
| **测试框架** | pytest |
| **代码质量** | Black, Ruff, MyPy |
| **包管理** | uv |

---

## 核心功能

### 两种运行模式

| 模式 | 说明 | 适用场景 | DSL 文件 |
|------|------|----------|----------|
| **rag_eval** | RAG 语义评测，基于召回片段的5步评测框架 | 无标准答案的 RAG 系统优化 | `全量测试milvus_rag_eval.yml` |
| **dual_workflow_compare** | 双工作流对比评测（LLM1 vs LLM2 vs History） | 对比两个模型/工作流的输出质量 | `全量测试milvus_dual_compare.yml` |

---

## 评测模式详解

### 1. RAG 评测模式 (rag_eval)

#### 工作原理

RAG 评测模式采用**5步评测决策框架**，完全基于召回文档片段进行事实性判断：

```
┌─────────────────────────────────────────────────────────────┐
│                    RAG 评测决策流程                          │
├─────────────────────────────────────────────────────────────┤
│  Step 1: 召回质量评估 → 召回片段是否包含回答问题所需信息    │
│  Step 2: 基于性判断 → 回答是否严格基于召回片段（不瞎编）    │
│  Step 3: 准确性判断 → 回答是否符合召回片段的事实            │
│  Step 4: 完整性判断 → 是否回答了问题的所有方面              │
│  Step 5: 版本对比 → 相比历史版本是否有改进（可选）          │
└─────────────────────────────────────────────────────────────┘
```

#### 提示词工程

RAG 评测的核心在于精心设计的提示词模板（位于 `src/obd/comparator/semantic_judge.py`）：

```python
RAG_EVAL_PROMPT_TEMPLATE = """你是一个专业的 RAG 系统评测员。请基于【召回文档片段】对【实际回答】进行多维度评测。

【问题】
{question}

【召回文档片段】（rerank 后的资料）
{rerank_sources}

【实际回答】
{actual_answer}

【评测决策框架】
第一步：召回质量评估
- 检查召回片段是否包含回答问题所需的核心信息
- 如果召回不足，应标记为"召回不足"，不应过度惩罚回答质量

第二步：基于性判断
- 检查回答是否严格基于召回片段
- 标记任何"瞎编"（hallucination）内容
- 即使回答合理，但不是基于召回片段的，也应指出

第三步：准确性判断
- 回答是否符合召回片段的事实
- 是否存在事实性错误或曲解

第四步：完整性判断
- 是否回答了问题的所有方面
- 是否遗漏了重要信息

第五步：版本对比（如果有上一版回答）
- 新版本相比旧版本是否有改进
- 在召回质量、准确性、完整性上的变化

【4级分类标准】
1. **fully_correct**: 基于召回，回答完整准确，无瞎编
2. **partial_missing**: 基于召回，有少量信息缺失或轻微偏差
3. **large_missing**: 基于召回，有大量信息缺失或显著偏差
4. **completely_wrong**: 未回答、完全瞎编、或完全错误

【输出格式】
基于性：[是/否]
召回质量：[充足/不足/无法判断]
瞎编检测：[无/有瞎编内容...]
准确性：[准确/有偏差/完全错误]
完整性：[完整/部分缺失/大量缺失]
分类：[fully_correct / partial_missing / large_missing / completely_wrong]
详细分析：[具体分析内容]
"""
```

#### 评测标准

从提示词中提炼出的评测标准：

| 维度 | 标准 | 说明 |
|------|------|------|
| **基于性** | 严格基于召回片段 | 任何超出召回范围的内容视为"瞎编" |
| **召回质量** | 充足/不足 | 先判断召回是否足够，再判断回答质量 |
| **准确性** | 符合事实 | 回答必须与召回片段一致 |
| **完整性** | 全面覆盖 | 必须回答问题的所有方面 |

#### 分类判断逻辑

```
if 完全瞎编 or 未回答:
    return completely_wrong
elif 召回不足 but 尽力回答:
    return partial_missing  # 召回不足时宽容处理
elif 有少量缺失 or 轻微偏差:
    return partial_missing
elif 有大量缺失 or 显著偏差:
    return large_missing
else:  # 基于召回，完整准确
    return fully_correct
```

---

### 2. 双工作流对比模式 (dual_workflow_compare)

#### 工作原理

双工作流对比模式支持**三方对比评测**（LLM1 vs LLM2 vs History），适用于：

- 对比两个不同模型的输出质量
- A/B 测试不同的提示词策略
- 评估新版本相比历史版本的改进

```
┌─────────────────────────────────────────────────────────────┐
│                  双工作流对比评测架构                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│    ┌──────────┐    ┌──────────┐    ┌──────────┐           │
│    │  LLM1    │    │  LLM2    │    │ History  │           │
│    │ 回答     │    │ 回答     │    │ 回答     │           │
│    └────┬─────┘    └────┬─────┘    └────┬─────┘           │
│         │              │              │                   │
│         └──────────────┼──────────────┘                   │
│                        ▼                                   │
│              ┌──────────────────┐                         │
│              │  LLM 评测引擎     │                         │
│              │  4 维度对比分析   │                         │
│              └────────┬─────────┘                         │
│                       ▼                                   │
│              推荐答案 + 置信度 + 详细分析                  │
└─────────────────────────────────────────────────────────────┘
```

#### 提示词工程

双工作流对比的提示词模板（位于 `src/obd/comparator/dual_workflow_comparator.py`）：

```python
COMPARISON_PROMPT_TEMPLATE = """你是一个专业的答案质量评测员。请对比三个答案的质量。

【问题】
{question}

【召回片段】（作为事实依据）
{rerank_sources}

【{label1} 回答】
{llm1_answer}

【{label2} 回答】
{llm2_answer}

【{label_history} 回答】（历史版本，用于对比）
{history_answer}

【评测标准】
1. 召回质量：是否充分利用了召回片段
2. 准确性：是否符合召回片段的事实
3. 完整性：是否回答了问题的所有方面
4. 版本改进：相比历史版本是否有改进

【输出格式】
推荐答案：[llm1 / llm2 / history / tie]
置信度：[high / medium / low]
总体分析：[综合三个答案的质量对比]
{label1}评价：[简述优缺点]
{label2}评价：[简述优缺点]
{label_history}评价：[简述优缺点]
推荐理由：[具体理由]

注意:
- llm1 代表 {label1}
- llm2 代表 {label2}
- history 代表 {label_history}
- tie 表示三个答案质量相当
"""
```

#### 评测标准

从提示词中提炼出的评测标准：

| 维度 | 说明 | 评分要点 |
|------|------|----------|
| **召回质量** | 利用召回片段的程度 | 是否充分检索和利用了召回信息 |
| **准确性** | 事实符合度 | 是否符合召回片段的事实 |
| **完整性** | 问题覆盖度 | 是否回答了问题的所有方面 |
| **版本改进** | 相对历史版本 | 新版本是否有实质性改进 |

#### 输出格式说明

评测结果包含以下字段：

| 字段 | 说明 | 可能值 |
|------|------|--------|
| `winner` | 推荐答案 | `llm1`, `llm2`, `history`, `tie` |
| `confidence` | 置信度 | `high`, `medium`, `low` |
| `overall_analysis` | 总体分析 | 综合对比分析 |
| `llm1_comment` | LLM1评价 | 优缺点描述 |
| `llm2_comment` | LLM2评价 | 优缺点描述 |
| `history_comment` | 历史评价 | 优缺点描述 |
| `recommendation` | 推荐理由 | 具体推荐依据 |

---

## Dify 工作流配置

### DSL 文件说明

项目在 `dify_dsl/` 目录下提供了两个预配置的工作流 DSL 文件：

| 文件 | 模式 | LLM 配置 | 说明 |
|------|------|----------|------|
| `全量测试milvus_rag_eval.yml` | rag_eval | gpt-4o-chatbi | 单模型 RAG 评测 |
| `全量测试milvus_dual_compare.yml` | dual_workflow_compare | deepseek-chat + deepseek-reasoner | 双模型对比评测 |

### 工作流结构

两个工作流采用相同的基础架构，区别在于 LLM 节点数量：

```
用户输入
    │
    ▼
┌──────────────┐
│ Milvus 搜索  │ → http://host.docker.internal:8000/search
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Rerank 重排序 │ → http://host.docker.internal:8000/rerank
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 代码格式化   │ → 提取 formatted_result
└──────┬───────┘
       │
   ┌───┴──────────────┐
   ▼                  ▼
┌──────┐         ┌──────┐
│ LLM1 │         │ LLM2 │  (仅 dual_compare 模式)
└───┬──┘         └───┬──┘
    │               │
    └───────┬───────┘
            ▼
      ┌──────────┐
      │ 输出答案 │
      └──────────┘
```

### 部署步骤

#### 1. 启动 Milvus 测试 API

工作流依赖 Milvus 测试 API 服务：

```bash
# 确保 Milvus 测试 API 已启动
# 服务地址: http://host.docker.internal:8000
```

**API 端点**：
- `/search` - 向量搜索接口
- `/rerank` - 重排序接口（使用 bge-reranker-v2-m3 模型）

#### 2. 导入 DSL 到 Dify 工作区

1. 打开 Dify 工作区
2. 进入"工作室" → "创建工作流"
3. 选择"从 DSL 导入"
4. 上传对应的 `.yml` 文件
5. 配置 API Key 和其他参数
6. 保存并发布工作流

#### 3. 配置 OBD 连接工作流

在 `config.ini` 中配置：

```ini
[EXECUTION_MODE]
mode = rag_eval          # 或 dual_workflow_compare

[Dify]
api_key = app-your-dify-workflow-api-key
base_url = https://api.dify.ai/v1
response_mode = blocking
timeout = 60

[LLM_EVAL]
enabled = true
api_key = sk-your-evaluation-llm-api-key
base_url = https://api.openai.com/v1/chat/completions
model = gpt-4o
temperature = 0.0
```

### 参数说明

| 参数 | rag_eval | dual_compare | 说明 |
|------|----------|--------------|------|
| `search top_k` | 60 | 5 | Milvus 搜索返回数量 |
| `rerank top_k` | 20 | 5 | Rerank 后保留数量 |
| `LLM` | gpt-4o | deepseek-chat | 主模型 |
| `LLM 2` | - | deepseek-reasoner | 副模型（仅 dual_compare） |

---

## 双层分类体系

**2 级分类**（用于计算正确率）：
- ✅ **正确**：重要信息全覆盖，基于召回片段
- ❌ **错误**：不符合正确标准

**4 级分类**（用于详细分析）：
- `fully_correct` - 完全正确
- `partial_missing` - 部分缺失
- `large_missing` - 大量缺失
- `completely_wrong` - 完全错误

---

## 快速开始

### 30 秒运行示例

```bash
# 1. 克隆项目
git clone <repository-url>
cd obd

# 2. 安装依赖
uv pip install -r requirements.txt

# 3. 配置文件
cp config.ini.example config.ini
# 编辑 config.ini，填入你的 API Key

# 4. 运行
uv run python -m obd.main
```

---

## 开发环境搭建

### 环境要求

- **Python**: 3.11 或更高版本
- **操作系统**: Windows 10/11, macOS 10.15+, Linux (Ubuntu 18.04+)
- **内存**: 最小 512MB，推荐 2GB+
- **网络**: 需要访问 Dify 服务

### 安装步骤

#### 1. 安装 uv（推荐）

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### 2. 创建虚拟环境

```bash
cd obd
uv venv
```

#### 3. 激活虚拟环境

```bash
# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

#### 4. 安装依赖

```bash
# 生产依赖
uv pip install -r requirements.txt

# 开发依赖（可选，用于贡献代码）
uv pip install -e ".[dev]"
```

#### 5. 验证安装

```bash
# 运行测试
uv run pytest

# 检查代码风格
uv run black --check src/obd
uv run ruff check src/obd
uv run mypy src/obd
```

### 配置文件说明

复制 `config.ini.example` 为 `config.ini`，根据需要配置：

```ini
[EXECUTION_MODE]
mode = rag_eval          # rag_eval / dual_workflow_compare

[Dify]
api_key = app-your-dify-workflow-api-key
base_url = https://api.dify.ai/v1
response_mode = blocking
timeout = 60

[LLM_EVAL]
enabled = true
api_key = sk-your-evaluation-llm-api-key
base_url = https://api.openai.com/v1/chat/completions
model = gpt-4o
temperature = 0.0

[Output]
file_path = results.xlsx
input_file_path = questions.xlsx
```

### IDE 配置建议

**VSCode** (.vscode/settings.json):

```json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/Scripts/python",
    "python.formatting.provider": "black",
    "python.linting.enabled": true,
    "python.linting.ruffEnabled": true,
    "python.analysis.typeCheckingMode": "basic"
}
```

**PyCharm**:
- 设置 Python 解释器指向 `.venv/python`
- 启用 Black 作为格式化工具
- 启用 MyPy 作为类型检查工具

### 调试技巧

```bash
# 查看日志输出
uv run python -m obd.main

# 使用 pdb 调试
uv run python -m pdb -m obd.main

# 检查配置
uv run python -c "from obd.main import load_config; import json; print(json.dumps(load_config(), indent=2))"
```

---

## 架构设计

### 分层架构

```
┌─────────────────────────────────────────────┐
│          应用层 (main.py)                  │
│  配置管理 + 用户交互 + 组件组装             │
└──────────────┬──────────────────────────────┘
               │
    ┌──────────┴──────────┐
    │                     │
┌───▼──────────────┐  ┌──▼─────────────────┐
│ 业务逻辑层       │  │ 服务层            │
│ (processor/)    │  │ (client/,         │
│  流程编排       │  │  comparator/)     │
│  状态管理       │  │  专业服务组件     │
└───┬──────────────┘  └───────────────────┘
    │
┌───▼──────────────┐
│ 数据层          │
│ (models.py)     │
│ 数据结构定义    │
│ 类型安全保证    │
└──────────────────┘
```

### 目录结构

```
obd/
├── src/
│   └── obd/
│       ├── __init__.py
│       ├── main.py                   # 程序入口
│       ├── models.py                 # 数据模型（dataclass）
│       │
│       ├── client/                   # API 客户端模块
│       │   └── dify_client.py        # Dify API 封装
│       │
│       ├── comparator/               # 答案对比模块
│       │   ├── semantic_judge.py     # RAG 综合评测器
│       │   └── dual_workflow_comparator.py  # 双工作流对比
│       │
│       ├── processor/                # 批处理模块
│       │   ├── batch_processor.py    # 批处理核心逻辑
│       │   ├── routing.py            # 路由分发
│       │   └── evaluation.py         # 评测分支
│       │
│       └── utils/                    # 工具模块
│           ├── dual_model_parser.py  # 双模型输出解析
│           ├── rag_response_parser.py # RAG 响应解析
│           └── eval_recorder.py      # 评测记录
│
├── dify_dsl/                         # Dify 工作流 DSL 文件
│   ├── 全量测试milvus_rag_eval.yml       # RAG 评测模式工作流
│   └── 全量测试milvus_dual_compare.yml   # 双工作流对比模式工作流
│
├── tests/                            # 测试目录
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_client.py
│   ├── test_comparator.py
│   ├── test_batch_processor.py
│   └── test_integration_llm.py
│
├── .spec/                            # 项目文档
│   ├── README.md
│   ├── quickstart.md
│   ├── comparator.md
│   └── examples.md
│
├── config.ini.example                # 配置模板
├── requirements.txt
├── pyproject.toml
├── pytest.ini
├── CLAUDE.md                         # 开发规范
└── README.md
```

### 核心数据流

```
Excel 输入
    │
    ▼
┌─────────────┐
│ load_excel  │ 读取数据
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│ process_excel   │ 根据模式选择逻辑
└────────┬────────┘
         │
    ┌────┴─────────────┐
    │                  │
    ▼                  ▼
rag_eval        dual_workflow_compare
    │                  │
    └────┬─────────────┘
         │
         ▼
┌──────────────────┐
│ Dify API 调用    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ LLM 评测（可选） │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 保存结果 Excel   │
└──────────────────┘
```

---

## 模块说明

### models.py - 数据模型

使用 `@dataclass` 定义核心数据结构：

- `WorkflowConfig` - Dify 工作流配置
- `LLMEvalConfig` - LLM 评测配置
- `ExecutionModeConfig` - 执行模式配置
- `QuestionAnswer` - 问题-答案结果
- `DualWorkflowEvalResult` - 双工作流评测结果

### client/dify_client.py - Dify API 客户端

```python
from obd.client.dify_client import DifyWorkflowClient

client = DifyWorkflowClient(api_key="...", base_url="...")
result = await client.execute_workflow(
    inputs={"query": "问题"},
    user="batch_processor"
)
```

### processor/batch_processor.py - 批处理核心

```python
from obd.processor.batch_processor import WorkflowBatchProcessor

processor = WorkflowBatchProcessor(
    workflow_config=...,
    routing_config=...,
    llm_eval_config=...
)

results = await processor.process_excel(
    excel_path="input.xlsx",
    output_path="output.xlsx"
)
```

### comparator/ - 评测模块

- `semantic_judge.py` - RAG 评测器（5步评测决策框架）
- `dual_workflow_comparator.py` - 双工作流对比评测器（三方对比）

---

## 开发指南

### 代码风格

```bash
# 格式化代码
uv run black src/obd

# 静态检查
uv run ruff check src/obd --fix

# 类型检查
uv run mypy src/obd
```

### 运行测试

```bash
# 运行所有测试
uv run pytest

# 运行特定测试文件
uv run pytest tests/test_batch_processor.py

# 显示详细输出
uv run pytest -v

# 生成覆盖率报告
uv run pytest --cov=obd --cov-report=html
```

### 添加新功能

1. 在 `models.py` 中定义数据模型
2. 在对应模块中实现功能
3. 添加单元测试
4. 运行测试确保通过
5. 更新文档

### 设计原则

- **SOLID**: 单一职责、开闭原则、依赖倒置
- **DRY**: 避免代码重复
- **KISS**: 保持简单
- **YAGNI**: 只实现当前需要的功能

---

## 测试

### 测试结构

```
tests/
├── conftest.py                    # pytest fixtures
├── test_models.py                 # 数据模型测试
├── test_client.py                 # API 客户端测试
├── test_comparator.py             # 评测器测试
├── test_batch_processor.py        # 批处理器测试
└── test_integration_llm.py        # 集成测试
```

### 运行测试

```bash
# 快速测试（跳过慢速测试）
uv run pytest -m "not slow"

# 并行运行测试
uv run pytest -n auto

# 只运行失败的测试
uv run pytest --lf
```

---

## 常见问题

### 配置相关

**Q: 提示 "API Key 无效" 怎么办？**
A: 检查 `[Dify]` 和 `[LLM_EVAL]` 中的 `api_key` 配置是否正确。

**Q: 如何配置多个知识库？**
A: 使用 `[WORKFLOW_MAPPING]` 节点，格式为 `知识库名 = API Key`。

**Q: Excel 列名和配置不一致怎么办？**
A: 确保配置文件中的列名与 Excel 实际列名完全一致（区分大小写）。

### 运行相关

**Q: 处理速度太慢怎么办？**
A: 可以调整 `[Workflow]` 中的 `max_workers` 参数（默认 5），适当增加并发数可提升速度。

**Q: 遇到 API 限流怎么办？**
A: 增大 `delay` 参数，或分批次处理大文件。

**Q: LLM 评测不准确怎么办？**
A: 尝试设置 `temperature` 为 `0.0` 提高一致性，或更换更强大的评测模型（如 gpt-4o）。

### 开发相关

**Q: 如何调试单个函数？**
A: 使用 `uv run python -m pdb -m obd.main` 或在 IDE 中设置断点。

**Q: 如何查看详细日志？**
A: 修改代码中的日志级别为 `DEBUG`，或使用 `logging` 模块。

---

## 📁 文档导航

| 文档 | 说明 |
|------|------|
| [.spec/quickstart.md](.spec/quickstart.md) | 详细快速开始指南 |
| [.spec/comparator.md](.spec/comparator.md) | 评测模块详细说明 |
| [.spec/examples.md](.spec/examples.md) | 使用示例 |
| [CLAUDE.md](CLAUDE.md) | 开发规范（面向开发者） |

---

## 🤝 贡献指南

欢迎贡献代码！请遵循以下流程：

1. Fork 项目并创建功能分支
2. 遵循开发规范（[CLAUDE.md](CLAUDE.md)）
3. 运行测试确保通过：`uv run pytest`
4. 运行代码检查：`black`, `ruff`, `mypy`
5. 提交更改并创建 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

## 📞 联系我们

- **问题反馈**: [GitHub Issues](../../issues)
- **功能建议**: [GitHub Discussions](../../discussions)

---

<div align="center">
Made with ❤️ by OBD Team
</div>
