# Technology Stack

## Project Type

**CLI 工具 + 可编程库**

OBD 既可作为独立的命令行工具运行，也可以作为 Python 库集成到其他项目中使用。这种设计提供了最大的灵活性：
- **独立运行**: 通过 CLI 直接使用，适合快速批处理
- **库集成**: 通过 Python API 调用，适合嵌入到自动化测试流程

## Core Technologies

### Primary Language(s)

- **Language**: Python 3.11+
  - 选择原因: 类型系统改进（Self 类型、TypeGuard）、性能提升、丰富的生态系统
  - 要求: 仅限 Python 3.11+，不支持更低版本

- **Runtime**: CPython 3.11+
  - 官方解释器，确保最佳兼容性和性能

- **Package Manager**: uv (推荐) / pip (备选)
  - **uv**: 快速的 Python 包管理器，推荐用于开发和部署
  - **pip**: 标准包管理器，作为备选方案

- **Build System**: pyproject.toml (PEP 621 标准)
  - 现代化的 Python 项目配置方式
  - 包含依赖管理、构建配置、元数据

### Key Dependencies/Libraries

#### 核心运行时依赖

- **requests** (≥2.31.0)
  - **用途**: HTTP 客户端，用于调用 Dify API
  - **版本要求**: 2.31.0+ 以确保安全性修复
  - **替代方案**: 考虑未来迁移到 `aiohttp` (异步)

- **pandas** (≥2.0.0)
  - **用途**: 数据处理，Excel/CSV 读写、数据分析
  - **版本要求**: 2.0.0+ 以使用最新 API
  - **替代方案**: 仅使用 `openpyxl`（功能受限）

- **openpyxl** (≥3.1.0)
  - **用途**: Excel 文件支持（.xlsx 格式）
  - **版本要求**: 3.1.0+ 以支持较新的 Excel 特性
  - **集成**: 通过 pandas 自动调用

#### 开发依赖

- **pytest** (≥7.0.0)
  - **用途**: 单元测试和集成测试框架
  - **特性**: 参数化测试、fixtures、插件系统

- **pytest-cov** (≥4.0.0)
  - **用途**: 测试覆盖率报告生成
  - **输出格式**: HTML, XML, terminal

- **pytest-mock** (≥3.10.0)
  - **用途**: Mock 外部依赖（Dify API 调用）
  - **用途场景**: 单元测试、集成测试

### Application Architecture

#### 整体架构模式

**分层架构 (Layered Architecture)**

OBD 采用清晰的分层架构，遵循单一职责原则和依赖倒置原则：

```
┌─────────────────────────────────────────────┐
│          应用层 (main.py)            │
│  - 程序入口和配置管理              │
│  - 依赖注入和组件组装              │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│     业务逻辑层 (processor/)           │
│  - 批处理核心逻辑                 │
│  - 状态管理和事务控制               │
│  - 结果计算和统计                   │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│        服务层 (client/, comparator/) │
│  - API 客户端封装                 │
│  - 答案对比算法                   │
│  - 专业服务组件                     │
└─────────────┬───────────────────────────┘
              │
┌─────────────▼───────────────────────────┐
│        数据层 (models.py)             │
│  - 数据结构定义                     │
│  - 类型安全保证                     │
│  - 序列化和反序列化                 │
└───────────────────────────────────────┘
```

#### 设计模式应用

1. **依赖注入 (Dependency Injection)**
   - **实现**: `WorkflowBatchProcessor` 接受可选的 `client` 参数
   - **目的**: 便于测试，可注入 mock client
   - **示例**:
     ```python
     def __init__(self, config: WorkflowConfig, client=None):
         self.client = client or DifyWorkflowClient(config)
     ```

2. **策略模式 (Strategy Pattern)**
   - **实现**: `AnswerComparator` 支持多种匹配算法
   - **目的**: 运行时选择匹配算法，易于扩展
   - **示例**:
     ```python
     def compare(self, expected: str, actual: str, method: str):
         if method == "exact":
             return self._exact_match(expected, actual)
         elif method == "fuzzy":
             return self._fuzzy_match(expected, actual)
         # ...
     ```

3. **工厂模式 (Factory Pattern)**
   - **实现**: 自动选择最佳匹配方法（auto 模式）
   - **目的**: 简化用户配置，自动优化
   - **示例**:
     ```python
     def compare(self, expected: str, actual: str, method: str = "auto"):
         if method == "auto":
             return self._auto_select_match(expected, actual)
         return self._select_by_method(expected, actual, method)
     ```

### Data Storage

#### 输入数据

- **Primary storage**: Excel/CSV 文件
  - 支持格式: .xlsx, .xls, .csv
  - 读取方式: pandas `read_excel()` / `read_csv()`
  - 数据量: 支持 10-1000 行（分批处理可扩展）

#### 输出数据

- **Output format**: Excel (.xlsx)
  - 双 sheet 结构:
    - **Sheet 1**: 详细结果（问题、期望答案、实际答案、匹配类型、状态）
    - **Sheet 2**: 统计摘要（总数、准确率、成功率、匹配类型分布）
  - 写入方式: pandas `ExcelWriter`

- **Data formats**:
  - **配置文件**: INI 格式（config.ini）
  - **API 响应**: JSON 格式（Dify API 返回）

### External Integrations

#### API 集成

- **API Endpoint**: Dify Workflow API
  - **端点**: `POST {base_url}/chat-messages`
  - **版本**: v1
  - **文档**: https://docs.dify.ai/

- **Protocol**: HTTP/REST (JSON)
  - **Content-Type**: application/json
  - **Encoding**: UTF-8

- **Authentication**:
  - **方式**: Bearer Token
  - **Header**: `Authorization: Bearer {api_key}`
  - **密钥来源**: config.ini 配置文件（本地存储）

- **请求配置**:
  - **response_mode**: blocking（同步）或 streaming（异步，未来）
  - **timeout**: 可配置（默认 60 秒）
  - **user**: 用户标识符（默认 "batch_processor"）

### Monitoring & Dashboard Technologies

#### 当前实现（CLI 模式）

- **Dashboard Type**: 命令行界面（CLI）
- **Progress Display**: 实时进度条（逐行处理）
- **Logging**: print 输出（未来升级为 logging 模块）

#### 未来扩展（Dashboard 可视化）

- **Dashboard Framework**: 待定
  - **候选**:
    - Flask (轻量级，适合小型项目)
    - FastAPI (高性能，异步支持)
    - Django (功能丰富，适合大型应用)

- **Frontend**: 待定
  - **候选**:
    - React (现代，生态丰富)
    - Vue (学习曲线平缓，中文友好)
    - Vanilla JS (简单，适合小型项目)

- **Real-time Communication**:
  - **WebSocket**: 双向实时通信
  - **Server-Sent Events**: 单向推送，轻量级

- **Visualization Libraries**:
  - **Chart.js**: 前端图表库
  - **Matplotlib**: Python 后端生成图表
  - **Plotly**: 交互式图表

- **State Management**:
  - **当前**: File system as source of truth
  - **未来**: 可选 Redis 缓存（多用户场景）

## Development Environment

### Build & Development Tools

- **Package Management**: uv (主要) / pip (备选)
  - **uv 命令**:
    ```bash
    uv pip install -r requirements.txt
    uv venv
    uv run pytest
    ```

- **Development workflow**:
  - **直接运行**: `uv run python -m obd.main`
  - **Watch 模式**: `pytest --watch`（文件变化时自动运行测试）

### Code Quality Tools

- **Static Analysis**:
  - **Ruff**: 快速的 Python linter
    - 检查: 代码风格、错误、复杂度
    - 命令: `ruff check src/ tests/`

  - **MyPy**: 类型检查器
    - 检查: 类型注解一致性
    - 模式: 严格模式（disallow_untyped_defs）
    - 命令: `mypy src/`

- **Formatting**:
  - **Black**: 代码格式化工具
    - 配置: line-length=88, target-version=py311
    - 命令: `black src/ tests/`

- **Testing Framework**:
  - **pytest**: 测试框架
  - **pytest-mock**: Mock 外部依赖
  - **pytest-cov**: 覆盖率报告
  - 命令:
    ```bash
    uv run pytest                    # 运行所有测试
    uv run pytest tests/test_client.py   # 运行特定测试
    uv run pytest --cov=src --cov-report=html  # 生成覆盖率报告
    ```

- **Documentation**:
  - **Markdown**: 手动维护的文档
  - **Docstrings**: Google/NumPy 风格
  - **文档位置**: .spec/, .spec-workflow/, README.md

### Version Control & Collaboration

- **VCS**: Git
  - 主分支: main
  - 开发分支: develop（可选）
  - 功能分支: feature/*
  - 修复分支: hotfix/*

- **Branching Strategy**: Git Flow
  - **main**: 生产就绪代码
  - **develop**: 最新开发版本
  - feature/*: 功能开发
  - hotfix/*: 紧急修复

- **Code Review Process**: Pull Request
  - **检查项**:
    - 代码风格（Black 格式化）
    - 类型检查（MyPy 无错误）
    - 测试通过（pytest 全部通过）
    - 测试覆盖率（目标 ≥ 80%）

### Dashboard Development (Future)

- **Live Reload**: Hot module replacement
  - 开发时自动刷新前端资源
  - 使用工具: watchfiles 或类似工具

- **Port Management**: 可配置端口
  - 配置项: dashboard_port (默认 5000)
  - 检测: 自动选择可用端口（如配置端口被占用）

- **Multi-instance Support**: 待评估
  - 场景: 同时运行多个 Dashboard 实例
  - 实现: 使用不同的数据目录或 workspace

## Deployment & Distribution

- **Target Platform(s)**:
  - **Windows**: 10/11 (x64)
  - **macOS**: 10.15+ (Intel, Apple Silicon)
  - **Linux**: Ubuntu 18.04+, Debian 10+, CentOS 7+

- **Distribution Method**:
  - **当前**: GitHub Release
    - 源代码压缩包
    - 手动安装步骤
  - **未来**: PyPI package
    - `pip install obd`
    - 自动依赖管理
  - **开发模式**: `pip install -e .` 或 `uv pip install -e .`

- **Installation Requirements**:
  - **Python**: 3.11+
  - **Package Manager**: uv (推荐) / pip
  - **Git**: 用于克隆源代码（可选）

- **Update Mechanism**:
  - **当前**: 手动更新
    ```bash
    git pull origin main
    uv pip install -r requirements.txt
    ```
  - **未来**: pip 自动升级
    ```bash
    pip install --upgrade obd
    ```

## Technical Requirements & Constraints

### Performance Requirements

- **Response time**: 单个 API 调用 < 60 秒（可配置）
  - 测量方法: API 响应时间记录
  - 优化目标: 平均 < 30 秒

- **Throughput**: 每分钟处理 ≥ 60 个问题
  - 测量方法: 实际运行速度统计
  - 优化目标: ≥ 100 个问题/分钟
  - 影响因素: 网络延迟、API 限流、请求延迟配置

- **Memory usage**: 峰值 < 500MB（单次运行）
  - 测量方法: `memory_profiler` 或系统监控
  - 场景: 处理 1000 行数据

- **Startup time**: < 3 秒
  - 测量方法: 从命令执行到首次日志输出
  - 包含: 配置加载、模块初始化

### Compatibility Requirements

- **Platform Support**: Windows, macOS, Linux
  - 测试覆盖: 每个平台定期测试
  - 已知问题: 无跨平台特定问题

- **Python versions**: 3.11+ (仅限 3.11+)
  - 原因: 类型系统特性、性能改进
  - 测试覆盖: 3.11, 3.12

- **Dependency versions**:
  - **最低版本**: 见 requirements.txt
  - **推荐版本**: 最新稳定版
  - **更新策略**: 定期更新（每季度）

- **Standards Compliance**:
  - **PEP 8**: 代码风格（通过 Black 强制）
  - **PEP 484**: 类型注解（typing 模块）
  - **PEP 621**: pyproject.toml 标准
  - **PEP 517**: 构建系统接口

### Security & Compliance

- **Security Requirements**:
  - **API 密钥存储**: 本地配置文件（config.ini）
  - **配置隔离**: config.ini 加入 .gitignore
  - **配置模板**: 提供 config.ini.example（无敏感数据）
  - **密钥轮换**: 建议定期更换 API 密钥（文档说明）
  - **传输加密**: HTTPS (TLS 1.2+)

- **Compliance Standards**:
  - 无特殊合规要求（GDPR, HIPAA, SOC2 不适用）
  - 未来扩展: 如涉及企业数据，需评估合规需求

- **Threat Model**:
  - **配置文件泄露**:
    - **威胁**: 意外提交 config.ini 到 Git
    - **缓解**: .gitignore 配置，提供示例模板
    - **检测**: CI 检查（待实现）

  - **API 密钥泄露**:
    - **威胁**: 日志或调试信息中暴露密钥
    - **缓解**: 密钥脱敏（`*` 掩盖后几位）
    - **检测**: 代码审查 + 自动化扫描（待实现）

  - **中间人攻击**:
    - **威胁**: 网络传输被拦截
    - **缓解**: 强制 HTTPS，证书验证（requests 默认）

### Scalability & Reliability

- **Expected Load**:
  - **单次运行**: 10-1000 个问题
  - **并发用户**: 单用户（CLI 工具）
  - **未来目标**: 多用户支持（Dashboard 版本）

- **Availability Requirements**:
  - **单次运行成功率**: > 98%
    - 测量方法: 失败率统计
    - 计算: (total - failed) / total

  - **支持中断恢复**: 待实现
    - 方案: checkpoint 机制
    - 存储: 进度文件（.progress.json）
    - 恢复: 从上次中断处继续

  - **大文件支持**: 支持 >1000 条数据处理
    - 方案: 分批处理
    - 实现: pandas `chunksize` 参数

- **Growth Projections**:
  - **数据规模**: 支持单次处理 >10000 条数据（分批）
  - **用户规模**: 未来支持多用户（Dashboard）
  - **API 调用**: 支持高频调用（异步 + 限流控制）

## Technical Decisions & Rationale

### Decision Log

#### 1. Python 3.11+ 选择

**决策**: 使用 Python 3.11+ 作为最低版本

**原因**:
- 类型系统改进: Self 类型、TypeGuard、泛型语法增强
- 性能提升: 更快的启动时间和运行时性能
- 现代特性: match 语句、参数化泛型、改进的错误消息

**替代方案**:
- Python 3.8-3.10: 类型系统功能不足
- Python 3.12+: 兼容性考虑，生态系统成熟度待验证

**权衡**:
- 较新的 Python 版本，可能限制部分用户
- 但收益远大于成本（类型安全、开发体验）

#### 2. 分层架构

**决策**: 采用清晰的三层架构（应用层 → 业务逻辑层 → 服务层 → 数据层）

**原因**:
- 单一职责原则: 每层职责明确
- 模块化: 易于测试和维护
- 依赖倒置: 高层不依赖低层实现细节

**替代方案**:
- 扁平结构: 所有代码在一个模块（难以扩展）
- 微服务: 多个独立服务（过度设计，增加复杂度）

**权衡**:
- 轻量级分层，保持简单
- 避免过度工程化

#### 3. pandas vs openpyxl

**决策**: 使用 pandas 进行数据处理，底层使用 openpyxl

**原因**:
- pandas 功能丰富: 分批处理、过滤、统计
- API 统一: pandas 自动处理 Excel/CSV
- 生态支持: 丰富的第三方库集成

**替代方案**: 仅使用 openpyxl

**权衡**:
- pandas 依赖较重（包括 numpy）
- 但功能和性能优势明显

#### 4. blocking vs streaming API 响应

**决策**: 使用 blocking 模式（同步）调用 Dify API

**原因**:
- 简化实现: 代码简洁，易于理解
- 批处理场景: 需要逐个处理，并发收益有限
- 依赖简单: requests 库原生支持

**替代方案**: streaming 模式（异步）

**权衡**:
- 性能稍低: 无法并发调用
- 但代码简洁，易于维护
- 未来可迁移到 aiohttp + asyncio

#### 5. 多种匹配算法

**决策**: 支持多种匹配算法（exact, fuzzy, keyword, auto）

**原因**:
- 适应不同问题: 数字、文本、混合类型
- 提高准确率: 针对性匹配策略
- 灵活性: 用户可选择最合适的算法

**替代方案**: 单一算法（如仅精确匹配）

**权衡**:
- 增加复杂度: 需要维护多个算法
- 但显著提高准确率和用户体验

#### 6. requests vs aiohttp

**决策**: 当前使用 requests，未来考虑 aiohttp

**原因（requests）**:
- 成熟稳定: 广泛使用，文档完善
- 同步简单: 代码直观，易于调试
- 生态丰富: 与各种库集成良好

**替代方案（aiohttp）**:
- 异步性能: 并发处理能力强
- 学习曲线: 需要理解 async/await
- 代码复杂度: 需要重构现有代码

**权衡**:
- 当前性能足够: 每分钟 60+ 个问题
- 未来升级路径: 清晰，可平滑迁移

#### 7. INI vs JSON 配置文件

**决策**: 使用 INI 格式（config.ini）

**原因**:
- 简洁: 易于手工编辑
- 标准库: Python 内置 `configparser`
- 分段清晰: [Dify], [Excel], [Workflow] 分组

**替代方案**: JSON, YAML, TOML

**权衡**:
- 功能受限: 不支持嵌套结构
- 但满足当前需求，简单直观

## Known Limitations

### 当前局限性

#### 1. 同步 API 调用

**描述**: 当前使用 requests 同步调用 Dify API，没有并发支持

**影响**:
- 处理大文件较慢: 1000 条数据需要 15-20 分钟
- 网络等待时间浪费: 每个请求必须等待响应

**未来方案**:
- 使用 asyncio + aiohttp 实现异步调用
- 控制并发数（3-10）避免 API 限流
- 预期提升: 3-5 倍处理速度

**优先级**: 高
**复杂度**: 中等（需要重构 WorkflowBatchProcessor）

---

#### 2. 无重试机制

**描述**: API 调用失败时直接跳过，没有自动重试

**影响**:
- 网络波动时成功率下降
- 临时性错误导致数据丢失

**未来方案**:
- 集成 `tenacity` 库实现自动重试
- 指数退避策略（exponential backoff）
- 最大重试次数可配置（3-5 次）

**优先级**: 高
**复杂度**: 低（封装 API 调用即可）

---

#### 3. 简单日志系统

**描述**: 当前使用 print 输出日志，缺乏结构化和持久化

**影响**:
- 调试困难: 无法追溯历史日志
- 无法持久化: 运行结束后日志丢失
- 缺乏分级: 无法区分 DEBUG/INFO/WARNING/ERROR

**未来方案**:
- 实现 logging 模块（Python 标准库）
- JSON 格式日志（便于解析和分析）
- 日志轮转和归档（避免日志文件过大）
- 日志级别可配置（DEBUG/INFO/WARNING/ERROR）

**优先级**: 中
**复杂度**: 低（替换 print 为 logging）

---

#### 4. 无持久化状态

**描述**: 处理过程中失败，无法从上次中断处恢复

**影响**:
- 处理 1000 条数据时 800 条失败，需重新运行
- 浪费 API 调用次数和费用
- 用户体验差: 重复劳动

**未来方案**:
- checkpoint 机制: 每处理 N 行保存进度
- 断点续传: 重启时从上次中断处继续
- 进度文件: .progress.json（保存已处理的索引）

**优先级**: 中
**复杂度**: 中等（需要状态管理和错误恢复）

---

#### 5. 固定匹配算法

**描述**: 仅支持预定义的匹配算法，无法自定义

**影响**:
- 特殊场景准确率不足: 如特定领域的专业知识匹配
- 扩展性差: 无法集成第三方匹配服务

**未来方案**:
- 插件化架构: 支持自定义 comparator
- 抽象接口: 定义 `ComparatorProtocol`
- 动态加载: 从配置文件加载自定义算法

**优先级**: 低
**复杂度**: 高（需要重构 AnswerComparator）

---

### 技术债务

#### 1. 测试覆盖率

**当前状态**: 约 70% 测试覆盖率

**目标**: ≥ 80%（核心模块 ≥ 90%）

**改进计划**:
- 为每个新功能编写测试（TDD 原则）
- 为现有代码补充测试用例
- 添加集成测试和端到端测试

**影响**: 中等（需要额外开发时间）

---

#### 2. 类型注解

**当前状态**: 某些内部函数缺少类型注解

**目标**: 所有公共接口有完整类型注解

**改进计划**:
- 启用 MyPy 严格模式（disallow_untyped_defs）
- 为私有方法添加类型注解
- 使用泛型提高类型安全性

**影响**: 低（开发时即可完成）

---

#### 3. 文档完整性

**当前状态**: 部分 API 缺少详细说明

**目标**: 所有公共 API 有完整文档字符串

**改进计划**:
- 为每个公共函数添加 Google/NumPy 风格文档
- 补充使用示例（Example:）
- 更新 README 和 .spec/ 文档

**影响**: 低（文档工作）

---

#### 4. 错误处理

**当前状态**: 某些边界情况未处理

**问题**:
- 空文件处理
- 异常 Excel 格式
- 网络超时（超时配置不够灵活）
- API 错误响应（401, 429, 500）

**改进计划**:
- 添加输入验证（文件存在性、格式正确性）
- 完善异常捕获和用户提示
- 添加错误代码说明和解决方案

**优先级**: 高
**复杂度**: 中等

---

#### 5. 性能优化

**当前状态**: 性能基本满足需求，但未优化

**改进方向**:
- 使用 async/await 提升并发
- 减少不必要的 pandas 操作（如内存使用）
- 优化字符串匹配算法（fuzzy match 使用更快的实现）

**优先级**: 中
**复杂度**: 高（需要深入性能分析）

---

## 未来技术路线图

### 短期（1-3 个月）

1. **重试机制**: 集成 tenacity，提升稳定性
2. **日志系统**: 实现 logging 模块，结构化日志输出
3. **错误处理**: 完善边界情况处理和用户提示

### 中期（3-6 个月）

1. **持久化状态**: checkpoint 机制，支持断点续传
2. **测试覆盖率**: 提升到 ≥ 80%
3. **类型注解**: 完善所有公共接口类型

### 长期（6-12 个月）

1. **异步支持**: asyncio + aiohttp，提升并发性能
2. **插件化架构**: 支持自定义匹配算法
3. **Dashboard**: Web 界面，实时监控和可视化
4. **多用户支持**: 团队协作和权限管理
