# Project Structure

## Directory Organization

```
obd/
├── .spec-workflow/              # Spec Workflow 目录
│   ├── steering/               # 核心指导文档
│   │   ├── product.md          # 产品愿景和目标
│   │   ├── tech.md            # 技术栈和架构决策
│   │   └── structure.md       # 代码结构规范（本文件）
│   ├── specs/                 # 功能规格文档（用户创建）
│   ├── templates/             # Spec 模板（系统生成）
│   ├── approvals/             # 审批记录（系统管理）
│   ├── archive/               # 归档的规格（系统管理）
│   └── user-templates/       # 用户自定义模板
│
├── .spec/                   # 项目文档（遗留，逐步迁移）
│   ├── README.md             # 文档导航
│   ├── api.md                # API 接口文档
│   ├── models.md             # 数据模型文档
│   ├── processor.md          # 批处理模块文档
│   ├── comparator.md         # 答案对比模块文档
│   ├── architecture.md        # 架构设计文档
│   ├── setup.md             # 安装配置指南
│   ├── quickstart.md         # 快速开始指南
│   ├── examples.md           # 使用示例
│   ├── testing-strategy.md    # 测试策略
│   ├── coding-standards.md   # 开发规范
│   ├── troubleshooting.md    # 问题排查
│   └── rerank.md            # Rerank 模块文档
│
├── src/                     # 源代码目录
│   └── obd/               # 主包
│       ├── __init__.py         # 包初始化，导出公共 API
│       ├── main.py            # 程序入口（CLI 接口）
│       ├── models.py          # 数据模型定义
│       ├── debug_api.py       # API 调试工具
│       ├── client/           # API 客户端模块
│       │   ├── __init__.py
│       │   └── dify_client.py  # Dify API 封装
│       ├── comparator/        # 答案对比模块
│       │   ├── __init__.py
│       │   ├── answer_comparator.py  # 字符匹配对比器（已废弃）
│       │   └── llm_comparator.py     # LLM 语义评测器
│       └── processor/        # 批处理模块
│           ├── __init__.py
│           ├── batch_processor.py  # 核心批处理逻辑
│           ├── evaluation.py       # 评测相关功能
│           └── routing.py          # 路由相关功能
│
├── tests/                  # 测试目录（与 src 平级）
│   ├── __init__.py
│   ├── conftest.py         # pytest fixtures
│   ├── test_models.py       # 模型测试
│   ├── test_client.py       # 客户端测试
│   ├── test_comparator.py   # 对比器测试
│   ├── test_llm_comparator.py  # LLM 评测器测试
│   ├── test_processor.py    # 处理器测试
│   └── test_integration_llm.py  # LLM 集成测试
│
├── scripts/               # 工具脚本目录
│   └── rerank_test.py    # Rerank 测试脚本（实验性）
│
├── data/                 # 数据目录
│   └── (临时测试数据，不提交到 Git)
│
├── config.ini            # 配置文件（加入 .gitignore，不提交）
├── config.ini.example    # 配置模板（提交到 Git）
├── requirements.txt       # 依赖列表
├── pyproject.toml       # 项目配置（PEP 621 标准）
├── pytest.ini           # pytest 配置
├── .gitignore           # Git 忽略规则
├── README.md            # 项目说明
└── CLAUDE.md           # 开发规范
```

### 组织原则

#### 1. 分层布局
- **src/obd/** 按功能模块划分
- 应用层、业务逻辑层、服务层、数据层清晰分离

#### 2. 测试平级
- **tests/** 与 **src/** 平级（pytest 最佳实践）
- 测试文件与源文件对应命名（test_*.py）

#### 3. 配置分离
- **config.ini.example** 提交到 Git 作为模板
- **config.ini** 加入 .gitignore，本地配置不泄露

#### 4. 文档隔离
- **.spec/** 保存技术文档（遗留，逐步迁移到 .spec-workflow）
- **.spec-workflow/** 保存流程文档（Spec Workflow）
- **README.md** 作为项目入口文档

#### 5. 实验代码隔离
- **scripts/** 存放实验性脚本
- 不影响核心功能，可随时删除

## Naming Conventions

### Files

#### Components/Modules
- **命名方式**: `snake_case`
- **示例**:
  - `dify_client.py`
  - `answer_comparator.py`
  - `batch_processor.py`

#### Services/Handlers
- **命名方式**: `snake_case` + `_client`/`_processor` 后缀
- **示例**:
  - `dify_client.py` (API 客户端）
  - `batch_processor.py` (批处理逻辑）

#### Utilities/Helpers
- **命名方式**: `snake_case` + `_utils`/`_helper` 后缀
- **示例** (当前无，未来扩展）:
  - `excel_utils.py`
  - `logging_helper.py`

#### Tests
- **命名方式**: `test_*.py` 或 `test_*.py` (与 pytest 约定一致）
- **示例**:
  - `test_models.py`
  - `test_dify_client.py`
  - `test_answer_comparator.py`
  - `test_batch_processor.py`

#### Directories
- **命名方式**: `snake_case`
- **示例**:
  - `client/`
  - `processor/`
  - `comparator/`

### Code

#### Classes/Types
- **命名方式**: `PascalCase` (首字母大写）
- **示例**:
  - `WorkflowConfig`
  - `QuestionAnswer`
  - `DifyWorkflowClient`
  - `AnswerComparator`
  - `WorkflowBatchProcessor`

#### Functions/Methods
- **命名方式**: `snake_case` (全小写，下划线分隔）
- **示例**:
  - `execute_workflow`
  - `exact_match`
  - `fuzzy_match`
  - `process_excel`
  - `calculate_statistics`

#### Constants
- **命名方式**: `UPPER_SNAKE_CASE` (全大写，下划线分隔）
- **示例** (未来扩展）:
  - `DEFAULT_TIMEOUT = 60`
  - `MAX_RETRIES = 3`
  - `API_VERSION = "v1"`

#### Variables
- **命名方式**: `snake_case` (全小写，下划线分隔）
- **示例**:
  - `api_key`
  - `base_url`
  - `is_correct`
  - `match_type`

#### Private Members
- **命名方式**: `_snake_case` (前导下划线）
- **示例**:
  - `_api_client` (私有属性）
  - `_validate_config` (私有方法）
  - `_extract_keywords` (内部辅助函数）

## Import Patterns

### Import Order

遵循 PEP 8 标准，按以下顺序导入：

1. **标准库导入** (e.g., `import os`, `from typing import Optional`)
2. **第三方库导入** (e.g., `import requests`, `import pandas as pd`)
3. **本地模块导入** (e.g., `from .models import WorkflowConfig`)
4. **类型导入** (e.g., `from typing import Dict, List, Optional`)

**分组规范**:
- 使用空行分隔不同组的导入
- 同组内的导入按字母顺序排列
- 使用 `from ... import ...` 而非 `import ... as module_name.xxx`

### Module/Package Organization

#### 绝对导入 vs 相对导入

**包内导入**: 使用相对导入（`from .xxx import yyy`）
**包外导入**: 使用绝对导入（`from obd.xxx import yyy`）

**原则**:
- src/ 内部使用相对导入
- tests/ 使用绝对导入
- 避免使用 `import obd.xxx.yyy as z` 的长路径导入

#### 依赖管理

- **声明位置**: `requirements.txt` 和 `pyproject.toml`
- **管理工具**: uv (推荐) / pip
- **版本锁定**: 使用精确版本（如 `requests==2.31.0`）
- **开发依赖**: 在 `pyproject.toml` 的 `[project.optional-dependencies]` 中声明

## Code Structure Patterns

### Module/Class Organization

每个 Python 文件遵循以下结构：

1. **导入语句**（标准库 → 第三方 → 本地）
2. **常量和配置**
3. **类型定义**（如需要）
4. **类/函数定义**（公共 API 在前）
5. **辅助函数**（内部使用，私有）
6. **公共 API 导出**（可选）

### Function/Method Organization

每个函数包含以下部分：

1. **文档字符串**（Google/NumPy 风格）
   - Args: 参数说明
   - Returns: 返回值说明
   - Raises: 异常说明
   - Example: 使用示例（可选）

2. **参数验证**（函数开头）
3. **核心逻辑**（中间部分）
4. **返回结果**（明确的返回点）

**要点**:
- 参数验证在函数开头
- 核心逻辑在中间
- 清晰的返回点
- 使用类型注解
- 提供文档字符串

### File Organization Principles

1. **一个类一个文件**: 每个主要类独占一个文件
   - 示例: `DifyWorkflowClient` 在 `dify_client.py` 中
   - 原因: 保持文件聚焦，易于导航

2. **相关功能分组**: 辅助函数放在主类后面
   - 示例: `AnswerComparator` 的辅助方法（`_extract_keywords`）放在类中
   - 原因: 保持上下文关联

3. **公共 API 清晰**: `__all__` 导出公共接口
   - 示例: 模块的 `__init__.py` 中定义 `__all__`
   - 原因: 明确公开接口，隐藏实现细节

4. **实现细节隐藏**: 私有函数/方法使用 `_` 前缀
   - 示例: `_validate_config`, `_build_request_headers`
   - 原因: 防止外部依赖内部实现

## Code Organization Principles

### 1. Single Responsibility (单一职责)

每个文件/类只有一个明确的职责：

- **`dify_client.py`**: 仅负责 Dify API 调用
- **`llm_comparator.py`**: 仅负责 LLM 语义评测
- **`batch_processor.py`**: 仅负责批处理编排

**原则**:
- 一个类不应混合多个职责（如 API 调用、答案对比、Excel 写入）
- 职责分离提高代码可维护性

### 2. Modularity (模块化)

代码组织成可复用的模块：

- **`processor/`**: 独立的批处理模块
- **`client/`**: 独立的 API 客户端模块
- **`comparator/`**: 独立的答案对比模块

**好处**:
- 模块可独立测试
- 模块可独立替换
- 模块可在其他项目中复用

### 3. Testability (可测试性)

结构设计便于测试：

- **依赖注入支持**: 类接受可选的依赖参数
- **Mock 友好的接口**: 所有外部依赖（如 API 调用）易于 mock

### 4. Consistency (一致性)

遒循代码库中已建立的模式：

- **所有 `dataclass` 使用类型注解**
- **所有公共方法有文档字符串**
- **所有异常使用自定义异常类**（未来扩展）
- **所有导入遵循标准顺序**

## Module Boundaries

### 依赖方向规则

```
┌─────────────────────────────────────────────┐
│      应用层 (main.py)               │
│  - 依赖: 业务逻辑层               │
│  - 不依赖: 服务层、数据层（间接依赖）│
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│    业务逻辑层 (processor/)           │
│  - 依赖: 服务层、数据层          │
│  - 不依赖: 应用层               │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│        服务层 (client/, comparator/)  │
│  - 依赖: 数据层                  │
│  - 不依赖: 业务逻辑层、应用层      │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│        数据层 (models.py)            │
│  - 依赖: 标准库、typing 模块   │
│  - 不依赖: 任何应用层             │
└───────────────────────────────────────┘
```

**原则**:
- 上层可以依赖下层（main.py 依赖 processor/）
- 下层不可依赖上层（models.py 不可依赖 main.py）
- 同层之间可以依赖（processor/ 依赖 client/ 和 comparator/）

### 边界模式

#### Core vs Utilities
- **核心逻辑**: `processor/`, `client/`, `comparator/`
- **辅助工具**: (当前无，未来可创建 `utils/` 或 `helpers/`）
- **边界**: 工具函数不应包含业务逻辑

#### Public API vs Internal
- **公共接口**: 通过 `__all__` 导出，模块的 `__init__.py`
- **实现细节**: 使用 `_` 前缀标记为私有
- **边界**: 外部代码仅依赖公共接口

#### Stable vs Experimental
- **生产代码**: `src/obd/` 下的所有模块
- **实验功能**: `scripts/` 下的脚本（如 `rerank_test.py`）
- **边界**: 实验功能不加入公共 API，可随时删除

#### Dependencies Direction
- **明确依赖方向**: 从高到低
- **避免循环依赖**: 使用接口（Protocol）解耦（如需要）

### 接口定义

**明确模块间的交互接口**:

1. **`DifyWorkflowClient`**:
   - 职责: 封装所有 Dify API 交互
   - 公共方法: `execute_workflow()`, `get_workflow_run_detail()`

2. **`AnswerComparator`**:
   - 职责: 定义匹配算法接口
   - 公共方法: `compare()`, `exact_match()`, `fuzzy_match()`, `keyword_match()`

3. **`WorkflowBatchProcessor`**:
   - 职责: 暴露批处理公共方法
   - 公共方法: `process_excel()`, `calculate_statistics()`, `save_results()`

## Code Size Guidelines

### 强制约束（基于用户要求）

#### File Size
- **限制**: 每个文件不超过 400 行
- **测量方法**: 使用 `wc -l filename` 或 IDE 统计
- **违规处理**: 拆分为多个小文件

#### Function Size
- **限制**: 每个函数不超过 60 行
- **测量方法**: IDE 统计或手动计数
- **违规处理**: 提取子函数

#### Method Size
- **限制**: 每个方法不超过 50 行
- **测量方法**: IDE 统计或手动计数
- **违规处理**: 提取私有方法

#### Complexity
- **限制**: 圈复杂度 < 10
- **测量工具**: 使用 `radon` 或 `mccabe`
- **简化方法**:
  - 减少嵌套层级
  - 提前返回（guard clauses）
  - 使用策略模式替换复杂 if/else

#### Nesting Depth
- **限制**: 最大嵌套 4 层
- **测量方法**: IDE 缩进可视化
- **违规处理**: 提取函数或使用 guard clauses

## Documentation Standards

### 文档字符串风格

#### 公共 API
- **必须提供**: Google/NumPy 风格文档字符串
- **位置**: 函数/类定义的下一行
- **内容**: Args, Returns, Raises, Example

#### 私有方法
- **可选**: 建议添加简短说明
- **内容**: 仅描述用途和关键参数

#### 复杂逻辑
- **必须添加**: 行内注释说明算法或业务规则
- **位置**: 关键步骤上方

### README 要求

#### 模块 README
- **需要时**: 每个主要模块应有 `README.md`
- **位置**: 模块目录下（如 `src/obd/client/README.md`）
- **内容**:
  - 模块用途
  - 公共 API 列表
  - 使用示例
  - 配置说明

#### 复杂算法文档
- **需要时**: 复杂算法应有详细说明文档
- **位置**: `.spec/` 或 `.spec-workflow/specs/` 中
- **内容**:
  - 算法原理
  - 时间复杂度
  - 空间复杂度
  - 示例

#### API 变更
- **要求**: API 变更需更新对应文档
- **更新内容**:
  - `README.md`: 项目入口文档
  - `.spec/api.md`: API 详细文档
  - `*.py` 的 docstrings: 函数/方法文档

**变更流程**:
1. 修改代码
2. 更新 docstrings
3. 更新 `.spec/api.md`
4. 更新 `README.md` 中的示例
5. 运行测试验证

## Dashboard/Monitoring Structure (Future)

### 预期结构（待实现）

```
src/obd/
└── dashboard/              # 独立子系统
    ├── server/            # 后端服务器
    │   ├── __init__.py
    │   ├── app.py         # FastAPI/Flask 应用入口
    │   ├── routes.py      # API 路由定义
    │   └── websocket.py   # WebSocket 处理
    ├── client/            # 前端资源
    │   ├── index.html
    │   ├── assets/
    │   │   ├── css/
    │   │   └── js/
    │   └── components/  # (如使用 React）
    ├── shared/            # 共享类型/工具
    │   ├── __init__.py
    │   ├── types.py       # 共享类型定义
    │   └── utils.py      # 共享工具函数
    └── public/            # 静态资源
        └── favicon.ico
```

### Separation of Concerns

1. **Dashboard 独立于核心业务逻辑**
   - Dashboard 可独立启动（`obd.dashboard.main`）
   - 不影响 CLI 模式的运行

2. **独立 CLI 入口点**
   - 使用不同的入口: `python -m obd.dashboard.main`
   - 配置隔离: `dashboard_port`, `dashboard_host`

3. **最小化对主应用的依赖**
   - 通过导入复用核心逻辑（`from obd.processor import ...`）
   - 不修改核心代码

4. **可禁用而不影响核心功能**
   - 如果不需要 Dashboard，可不安装前端依赖
   - 核心批处理功能完全独立

### 技术栈（未来）

- **Backend**: FastAPI 或 Flask
- **Frontend**: React, Vue, 或 Vanilla JS
- **Real-time**: WebSocket 或 Server-Sent Events
- **Visualization**: Chart.js, D3.js, 或 ECharts
