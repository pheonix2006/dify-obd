# Claude 开发规范

> **本文档目的**: 帮助 Claude AI 智能体快速了解项目框架，建立统一的开发规范，确保代码质量和一致性。

---

## 📋 文档说明

### 本文档的定位

**CLAUDE.md** 是专门为 Claude AI 智能体设计的开发规范文档，重点包括：

1. **项目架构概览**：快速理解整体结构和技术选型
2. **开发规范制定**：编码风格、测试策略、设计原则
3. **工作流程指导**：分支管理、代码审查、发布流程
4. **技术债务管理**：已知问题和改进方向

**重要原则**：
- 保持简洁，避免过多的代码示例
- 侧重规范和原则，而非具体实现
- 帮助智能体快速理解项目上下文
- 为自动化工具提供决策依据

### 与其他文档的分工

| 文档 | 定位 | 目标读者 | 内容重点 |
|------|------|----------|----------|
| **CLAUDE.md** | 开发规范 | Claude AI | 项目框架、开发规范、工作流程 |
| **README.md** | 使用指南 | 终端用户 | 项目介绍、配置教程、使用说明 |
| **.spec/** | 详细设计 | 开发者 | 架构设计、API文档、模块详解 |

---

## 🎯 项目概述

### 项目定位

**OBD (Open Batch Processor)** 是一个 Dify 工作流批量处理工具，专注于：

- **批量 API 调用**：从 Excel 批量读取问题并调用 Dify API
- **智能答案评测**：基于 LLM 的语义级答案质量评估
- **结果分析导出**：生成分类统计和详细分析报告

### 技术栈

- **语言**: Python 3.11+
- **核心框架**: 异步 I/O (httpx)
- **数据处理**: pandas, openpyxl
- **评测引擎**: LLM 语义评测 (OpenAI 兼容 API)
- **包管理**: uv
- **测试**: pytest

### 架构设计理念

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

**关键设计原则**：
- **分层架构**：清晰的职责分离
- **依赖注入**：通过构造函数注入依赖
- **异步优先**：I/O 操作使用异步模式
- **类型安全**：严格的类型注解和验证

---

## 📁 项目结构规范

### 标准布局 (src-layout)

```
obd/
├── .spec/                           # 📖 项目详细文档
│   ├── README.md                     # 文档导航
│   ├── api.md                        # API 接口文档
│   ├── models.md                     # 数据模型文档
│   ├── processor.md                  # 批处理模块文档
│   ├── comparator.md                 # 答案对比模块文档
│   ├── architecture.md              # 架构设计文档
│   ├── setup.md                      # 安装配置指南
│   ├── quickstart.md                 # 快速开始指南
│   ├── examples.md                   # 使用示例
│   ├── testing-strategy.md          # 测试策略
│   ├── coding-standards.md           # 开发规范
│   └── troubleshooting.md            # 问题排查
│
├── src/                             # 🔧 源代码目录
│   └── obd/                         # 主包
│       ├── __init__.py               # 包初始化
│       ├── main.py                   # 🚨 程序入口
│       ├── models.py                 # 📊 数据模型
│       ├── client/                   # 🌐 API 客户端模块
│       │   ├── __init__.py
│       │   └── dify_client.py        # Dify API 封装
│       ├── comparator/              # 🎯 答案对比模块
│       │   ├── __init__.py
│       │   ├── answer_comparator.py  # 匹配算法（已废弃）
│       │   └── llm_comparator.py     # LLM 语义评测器
│       └── processor/                # 📦 批处理模块
│           ├── __init__.py
│           └── batch_processor.py    # 批处理核心逻辑
│
├── tests/                           # 🧪 测试目录
│   ├── conftest.py                  # pytest fixtures
│   ├── test_models.py
│   ├── test_client.py
│   ├── test_comparator.py
│   ├── test_llm_comparator.py
│   ├── test_processor.py
│   └── test_integration_llm.py
│
├── config.ini                       # ⚙️ 配置文件 (gitignore)
├── config.ini.example              # 📄 配置模板
├── requirements.txt                # 📦 依赖列表
├── pyproject.toml                   # 🔧 项目配置
├── pytest.ini                      # 🧪 pytest 配置
└── .gitignore                      # 🚫 Git 忽略规则
```

### 目录命名规范

- **小写字母 + 下划线**: 模块和包名 (如 `batch_processor.py`)
- **PascalCase**: 类名 (如 `WorkflowBatchProcessor`)
- **snake_case**: 函数和变量名 (如 `process_excel`)

---

## 🏗️ 开发规范

### 1. 类型系统规范

#### 类型注解要求

**原则**：所有公共接口必须使用类型注解

**类型选择**：
- 基本类型：`str`, `int`, `float`, `bool`
- 容器类型：`List[T]`, `Dict[K, V]`, `Set[T]`
- 可选类型：`Optional[T]` 等价于 `Union[T, None]`
- 联合类型：`Union[T1, T2, ...]`
- 任意类型：`Any`（尽量避免使用）

#### 数据模型设计

使用 `@dataclass` 定义数据模型：

**设计原则**：
- 必需字段：不提供默认值
- 可选字段：使用 `Optional[T]` 或提供默认值
- 验证逻辑：在 `__post_init__()` 中实现

---

### 2. 分层架构规范

#### 各层职责

**应用层 (main.py)**:
- 配置文件解析和验证
- 依赖注入和组件组装
- 程序入口和用户交互
- 错误处理和日志输出

**业务逻辑层 (processor/)**:
- 核心业务流程编排
- 状态管理和事务控制
- 结果计算和统计汇总
- 数据导入导出

**服务层 (client/, comparator/)**:
- 专业服务组件封装
- 单一职责原则
- 可复用的功能模块
- 外部接口适配

**数据层 (models.py)**:
- 数据结构定义
- 类型安全保证
- 序列化和反序列化
- 数据验证逻辑

#### 模块间交互

**依赖注入原则**：
- 通过构造函数注入依赖
- 避免硬编码依赖
- 使用接口隔离组件

---

### 3. 错误处理规范

#### 分层错误处理

**服务层**：抛出特定异常
**业务层**：捕获并处理异常
**应用层**：记录日志和用户提示

#### 异常分类

- **业务异常**: 可预期的业务错误（如配置错误、API 限流）
- **系统异常**: 不可预期的系统错误（如网络故障、服务宕机）
- **自定义异常**: 项目特定的异常类型

---

### 4. 测试驱动开发规范

#### TDD 流程

```
红 → 绿 → 重构
```

1. **红色阶段**：编写失败的测试，明确需求
2. **绿色阶段**：编写最少代码让测试通过
3. **重构阶段**：优化代码结构，保持测试通过

#### 测试结构

- 测试文件与源文件对应
- 使用统一的测试命名规范
- 遵循 Arrange-Act-Assert 模式

#### 测试覆盖率要求

- **单元测试**: 覆盖率 ≥ 80%
- **集成测试**: 覆盖主要业务流程
- **边界测试**: 测试各种边界条件

---

### 5. 代码质量规范

#### 工具链配置

- **格式化**: 使用 Black 自动格式化
- **静态检查**: 使用 Ruff 进行代码检查
- **类型检查**: 使用 MyPy 进行类型验证
- **命名规范**: 遵循 PEP 8 标准

---

## 🔧 Serena LSP 工具使用规范

### 核心原则

**优先使用 Serena 符号工具，避免读取整个文件！**

Serena 提供的 LSP 工具可以精确提取代码符号信息，大幅减少上下文使用量。对于代码探索和编辑任务，必须遵循以下策略：

### 符号探索流程

#### 1. 快速获取概览

**场景**：需要了解某个文件的结构

```
使用 get_symbols_overview(rel_path)
→ 获取该文件所有顶级符号及其类型
→ 按需深入特定符号
```

**示例**：
```
查询 src/obd/models.py 的结构
→ 得到类列表：Config、ProcessConfig、EvaluationResult 等
→ 决定需要读取哪个类的详细信息
```

#### 2. 查找特定符号

**场景**：知道符号名称，需要定位和了解它

```
使用 find_symbol(
    name_path_pattern="类名/方法名",
    relative_path="文件路径",
    depth=0/1,           # 0=仅符号信息, 1=包含子符号
    include_body=False   # 暂不读取实现
)
```

**路径模式规则**：
- **简单名称**: `"process"` 匹配任何名为 process 的符号
- **相对路径**: `"BatchProcessor/process"` 匹配 BatchProcessor 类中的 process 方法
- **绝对路径**: `"/BatchProcessor/process"` 要求完整路径匹配
- **重载方法**: `"Foo/process[1]"` 匹配特定重载

#### 3. 读取符号实现

**仅在选择出目标后，使用 include_body=True**

```python
# 错误：一次性读取所有方法
find_symbol("Foo", include_body=True, depth=1)

# 正确：先概览，再选择性读取
find_symbol("Foo", depth=1)  # 仅获取方法列表
# 用户确认需要读取哪个方法后
find_symbol("Foo/process", include_body=True)
```

#### 4. 理解符号关系

**场景**：找出谁使用了某个符号

```
使用 find_referencing_symbols(
    name_path="目标符号路径",
    relative_path="文件路径"
)
→ 获取所有引用位置和上下文代码片段
```

### 非代码文件搜索

**场景**：不知道符号名称，或搜索非代码内容

```
使用 search_for_pattern(
    substring_pattern="正则表达式",
    relative_path="目录路径",        # 限制搜索范围
    context_lines_before=2,          # 前后行数
    context_lines_after=2
)
→ 获取匹配行及上下文
```

### 代码编辑最佳实践

#### 符号级编辑（推荐）

**适用场景**：修改整个函数/类/方法

```
1. find_symbol 获取符号
2. replace_symbol_body 替换整个定义
3. find_referencing_symbols 检查引用，确保兼容性
```

#### 插入式编辑

**在文件开头插入**：
```python
insert_before_symbol(
    name_path="第一个顶级符号",
    relative_path="文件.py",
    body="import statements\n"
)
```

**在文件末尾插入**：
```python
insert_after_symbol(
    name_path="最后一个顶级符号",
    relative_path="文件.py",
    body="new class/function\n"
)
```

#### 文件级编辑（谨慎使用）

仅适用于小规模、局部的代码修改（如修正几个变量名）

### 工具选择决策树

```
开始探索代码
    │
    ├─ 知道文件路径？
    │   ├─ 是 → get_symbols_overview(rel_path)
    │   │       ├─ 需要特定符号？ → find_symbol(name_path)
    │   │       └─ 已足够？
    │   └─ 否 → 搜索文件 → find_file(mask, path)
    │
    ├─ 知道符号名称？
    │   └─ 是 → find_symbol(name_path, substring_matching=True)
    │
    └─ 仅知道代码特征？
        └─ 是 → search_for_pattern(regex, restrict_search_to_code_files=True)
```

### 禁用操作

**不要这样做**：

❌ 直接读取整个文件：`Read(file_path)`
❌ 使用 Bash grep/rg：`Bash("grep pattern file.py")`
❌ 不必要的全文搜索：未限制 `relative_path` 的模式搜索

### Memory 系统

**场景**：需要在多次会话间共享的项目级知识

```python
# 创建项目记忆（如架构决策）
write_memory(
    memory_file_name="architecture_decisions.md",
    content="## 为什么选择 httpx\n..."
)

# 需要时读取
read_memory(memory_file_name="architecture_decisions.md")
```

### 性能优化技巧

1. **限制搜索范围**：始终提供 `relative_path` 参数
2. **分步探索**：先概览，再深入
3. **按需读取**：只在确定目标后才 `include_body=True`
4. **优先符号搜索**：比模式搜索更精确、更快
5. **利用 depth 参数**：控制子符号层级获取

### 实际示例

**示例 1：修改 BatchProcessor 的 process 方法**

```python
# 1. 找到符号
find_symbol("BatchProcessor/process", relative_path="processor/batch_processor.py")

# 2. 读取实现（仅在选择该目标后）
find_symbol("BatchProcessor/process", include_body=True, relative_path="...")

# 3. 检查引用
find_referencing_symbols(name_path="BatchProcessor/process", relative_path="...")

# 4. 替换实现
replace_symbol_body(name_path="BatchProcessor/process", relative_path="...", body="...")
```

**示例 2：查找所有使用 Config 的地方**

```python
# 1. 先找到 Config 类
find_symbol("Config", relative_path="models.py")

# 2. 查找所有引用
find_referencing_symbols(
    name_path="Config",
    relative_path="models.py",
    max_answer_chars=50000  # 限制结果大小
)
**示例 3：在未知位置搜索 Dify API 调用**

```python
# 1. 模式搜索
search_for_pattern(
    substring_pattern="def.*workflow.*run|DifyClient",
    restrict_search_to_code_files=True,
    paths_include_glob="**/*.py"
)

# 2. 从结果中选择目标文件
# 3. 对目标文件使用符号工具深入探索
```

---

### 6. 设计原则应用

**SOLID 原则**:
- **S** (单一职责): 每个类/函数只做一件事
- **O** (开闭原则): 对扩展开放，对修改封闭
- **L** (里氏替换): 子类可替换父类
- **I** (接口隔离): 接口专一，避免胖接口
- **D** (依赖倒置): 依赖抽象而非具体实现

**DRY 原则**: 避免代码重复，提取公共逻辑

**KISS 原则**: 保持简单直接，避免过度设计

**YAGNI 原则**: 不做未来可能用不到的功能

---

## 🎯 评测模式规范

### 双层分类体系

**2级分类（用于计算正确率）**:
- **正确**: 重要信息全覆盖，可忽略非重要信息缺失
- **错误**: 任何不符合正确标准的情况

**4级分类（用于详细分析）**:
- **完全正确** (`fully_correct`): 重要信息全覆盖
- **部分缺失** (`partial_missing`): 有少量重要信息缺失
- **大量缺失** (`large_missing`): 很多信息（参数等）缺少
- **完全错误** (`completely_wrong`): 完全错误/未回答

### LLM 评测配置

**判断模式**:
- **detailed**: 详细标准模式，明确定义每种错误类型的判断标准
- **autonomous**: 自主判断模式，让 LLM 智能判断

**温度参数**:
- **0.0**: 最确定，适合需要严格判断的场景
- **0.3-0.7**: 平衡，适合需要一定灵活性的场景
- **1.0**: 最随机，适合探索性场景（不推荐评测使用）

---

## 🔄 版本控制规范

### 分支管理

- **main**: 主分支，保持稳定，可发布状态
- **develop**: 开发分支，集成最新功能
- **feature/***: 功能分支，从 develop 分出
- **hotfix/***: 紧急修复分支，从 main 分出

### 提交规范

**格式**: `<type>(<scope>): <subject>`

**类型**:
- `feat`: 新功能
- `fix`: 修复 bug
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具相关

---

## 📊 技术债务管理

### 已知问题

1. **answer_comparator.py**: 已废弃，保留用于历史参考
2. **字符匹配逻辑**: 已移除，完全依赖 LLM 评测
3. **流式响应支持**: 未实现，仅支持阻塞模式

### 改进方向

1. **性能优化**: 批量请求并发控制
2. **缓存机制**: 重复问题缓存评测结果
3. **异步批量处理**: 提升大文件处理效率
4. **配置热重载**: 无需重启即可更新配置

---

## 📝 文档更新日志

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v0.1.0 | 2025-12-29 | 初始版本，定义开发规范 |
| v0.1.1 | 2025-12-29 | 完善TDD规范和类型系统要求 |
| v0.2.0 | 2025-12-29 | 重构为概述性规范，增强可维护性 |
| v0.3.0 | 2026-01-09 | 重新设计文档结构，明确文档定位和分工 |

---

**重要**: 本文档会随着项目发展持续更新，请定期查看最新版本。规范的重点是提供原则性指导，而非具体的实现细节，以保持代码的灵活性和可维护性。
