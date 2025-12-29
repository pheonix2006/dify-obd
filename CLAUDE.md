# Claude 开发规范

本文档为 Claude AI 模型在 OBD 项目中的开发规范，确保代码质量、类型安全和开发流程的一致性。

---

## 🎯 项目概述

**OBD (Open Batch Processor)** - Dify 工作流批处理器

- **目标**: 批量调用 Dify API，处理 Excel 问答，对比答案并生成报告
- **技术栈**: Python 3.11+, pandas, requests, uv
- **架构**: 分层架构 + 模块化设计
- **开发模式**: TDD (测试驱动开发)

---

## 📁 项目结构规范

### 标准布局 (src-layout)

```
obd/
├── .spec/                           # 📖 项目文档目录
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
│       ├── main.py                   # 🚨 程序入口 (严格类型检查)
│       ├── models.py                 # 📊 数据模型 (使用 dataclass)
│       ├── client/                   # 🌐 API 客户端模块
│       │   ├── __init__.py
│       │   └── dify_client.py        # Dify API 封装
│       ├── comparator/              # 🎯 答案对比模块
│       │   ├── __init__.py
│       │   └── answer_comparator.py  # 匹配算法实现
│       └── processor/                # 📦 批处理模块
│           ├── __init__.py
│           └── batch_processor.py    # 批处理核心逻辑
│
├── tests/                           # 🧪 测试目录 (与 src 平级)
│   ├── __init__.py
│   ├── conftest.py                  # pytest fixtures
│   ├── test_models.py               # 模型测试
│   ├── test_client.py               # 客户端测试
│   ├── test_comparator.py            # 对比器测试
│   ├── test_processor.py             # 处理器测试
│   └── test_integration.py          # 集成测试
│
├── scripts/                         # 📝 脚本目录
├── data/                            # 📁 数据目录
├── config.ini                       # ⚙️ 配置文件 (gitignore)
├── config.ini.example              # 📄 配置模板
├── requirements.txt                # 📦 依赖列表
├── pyproject.toml                   # 🔧 项目配置
├── pytest.ini                      # 🧪 pytest 配置
├── .gitignore                      # 🚫 Git 忽略规则
├── README.md                       # 📖 项目说明
└── CLAUDE.md                       # 🤖 Claude 规范 (本文件)
```

---

## 🔧 类型系统规范

### 1. 严格类型注解

**所有公共接口必须使用类型注解**：

```python
# ✅ 正确示例
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

@dataclass
class WorkflowConfig:
    """工作流配置"""
    api_key: str                    # 必需字段
    base_url: str = "https://api.dify.ai/v1"  # 带默认值
    response_mode: str = "blocking"
    timeout: int = 60
    user: str = "batch_processor"

class DifyWorkflowClient:
    def __init__(self, config: WorkflowConfig) -> None:
        self.config: WorkflowConfig = config
        self.session: requests.Session = requests.Session()

    def execute_workflow(
        self,
        inputs: Dict[str, Any],
        user: Optional[str] = None,
        workflow_id: Optional[str] = None
    ) -> Dict[str, Any]:
        # ...
```

### 2. 泛型使用规范

```python
from typing import TypeVar, Generic, List

T = TypeVar('T')

class ResultProcessor(Generic[T]):
    """通用结果处理器"""

    def process_results(self, results: List[T]) -> Dict[str, Any]:
        count: int = len(results)
        # 类型安全的处理
        return {"total": count, "items": results}
```

### 3. Union 和 Optional 使用

```python
from typing import Union

def handle_response(response: Union[Dict[str, Any], str]) -> str:
    """处理联合类型响应"""
    if isinstance(response, dict):
        return response.get("answer", "")
    return str(response)
```

---

## 🏗️ 模块开发规范

### 1. 数据层 (models.py)

**职责**: 定义核心数据结构，确保类型安全

```python
# ✅ 必须使用 dataclass
from dataclasses import dataclass
from typing import Optional

@dataclass
class QuestionAnswer:
    """问题-答案对"""
    question: str                   # 问题文本 (必需)
    expected_answer: str            # 期望答案 (必需)
    workflow_result: Optional[str] = None   # API 返回结果 (可选)
    is_correct: bool = False        # 是否匹配 (默认 False)
    match_type: Optional[str] = None       # 匹配类型 (可选)
    workflow_run_id: Optional[str] = None   # 任务 ID (可选)
    error: Optional[str] = None    # 错误信息 (可选)

    # 验证方法
    def validate(self) -> bool:
        """验证数据有效性"""
        if not self.question or not self.expected_answer:
            return False
        return True
```

### 2. 服务层 (client/, comparator/)

**职责**: 提供专业服务，单一职责原则

```python
# ✅ client 模块示例
from abc import ABC, abstractmethod
from typing import Protocol

class APIClient(Protocol):
    """API 客户端协议"""

    @abstractmethod
    def execute_workflow(self, inputs: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """执行工作流"""
        pass

class DifyWorkflowClient:
    """Dify API 客户端实现"""

    def __init__(self, config: WorkflowConfig) -> None:
        self.config = config
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """创建 HTTP 会话"""
        session = requests.Session()
        session.headers.update({
            'Authorization': f'Bearer {self.config.api_key}',
            'Content-Type': 'application/json'
        })
        return session

    def execute_workflow(self, inputs: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """实现 API 调用"""
        # ...
```

### 3. 业务层 (processor/)

**职责**: 核心业务流程，协调服务层

```python
# ✅ processor 模块示例
from typing import List, Dict, Any

class WorkflowBatchProcessor:
    """工作流批处理器"""

    def __init__(self, config: WorkflowConfig, client: Optional[APIClient] = None):
        self.config: WorkflowConfig = config
        self.client: APIClient = client or DifyWorkflowClient(config)
        self.comparator: AnswerComparator = AnswerComparator()

    def process_excel(
        self,
        excel_path: str,
        **kwargs
    ) -> List[QuestionAnswer]:
        """处理 Excel 文件"""
        # 1. 加载文件
        df: pd.DataFrame = self._load_excel(excel_path)

        # 2. 批量处理
        results: List[QuestionAnswer] = []
        for idx, row in df.iterrows():
            qa: QuestionAnswer = self._process_row(row, **kwargs)
            results.append(qa)

        return results
```

### 4. 应用层 (main.py)

**职责**: 程序入口，配置管理，错误处理

```python
# ✅ main.py 示例
from typing import Dict, Any
from pathlib import Path

def load_config(config_path: str = "config.ini") -> Dict[str, Any]:
    """加载配置文件"""
    config = configparser.ConfigParser()
    config.read(config_path)
    # ... 转换为字典返回

def main() -> int:
    """主函数"""
    try:
        # 1. 加载配置
        config_data: Dict[str, Any] = load_config()

        # 2. 创建配置对象
        workflow_config: WorkflowConfig = WorkflowConfig(
            api_key=config_data["api_key"],
            base_url=config_data.get("base_url", "https://api.dify.ai/v1"),
            # ...
        )

        # 3. 创建处理器
        processor: WorkflowBatchProcessor = WorkflowBatchProcessor(workflow_config)

        # 4. 执行处理
        results: List[QuestionAnswer] = processor.process_excel(
            excel_path=config_data["excel_path"]
        )

        # 5. 输出结果
        stats: Dict[str, Any] = processor.calculate_statistics(results)
        print(f"准确率: {stats['accuracy']:.1%}")

        return 0

    except FileNotFoundError as e:
        print(f"文件不存在: {e}")
        return 1
    except ValueError as e:
        print(f"配置错误: {e}")
        return 1
    except Exception as e:
        print(f"未知错误: {e}")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
```

---

## 🧪 测试驱动开发 (TDD) 规范

### 1. 测试结构

**测试目录必须与 src 平级**：

```
tests/
├── __init__.py
├── conftest.py                  # pytest fixtures
├── test_models.py               # 测试数据模型
├── test_client.py               # 测试 API 客户端
├── test_comparator.py            # 测试答案对比
├── test_processor.py             # 测试批处理器
└── test_integration.py          # 测试集成
```

### 2. TDD 开发流程

**红 → 绿 → 重构**

```python
# 1. 红色阶段 - 写失败的测试
def test_exact_match():
    """测试精确匹配功能"""
    from obd.comparator import AnswerComparator

    comparator = AnswerComparator()

    # 这个测试会失败，因为我们还没有实现
    assert comparator.exact_match("579", "579") == True
    assert comparator.exact_match("是", "是") == True
    assert comparator.exact_match("Hello", "hello") == True  # 应该忽略大小写

# 2. 绿色阶段 - 写最少代码让测试通过
class AnswerComparator:
    @staticmethod
    def exact_match(answer1: str, answer2: str) -> bool:
        """精确匹配（忽略大小写和空格）"""
        return str(answer1).strip().lower() == str(answer2).strip().lower()

# 3. 重构阶段 - 优化代码
# 可以添加更多测试用例，优化性能等
```

### 3. 测试规范

```python
# ✅ 使用 pytest fixtures
import pytest
from obd.models import WorkflowConfig

@pytest.fixture
def test_config():
    """测试配置 fixture"""
    return WorkflowConfig(
        api_key="test-api-key",
        base_url="http://localhost/v1"
    )

# ✅ 使用 mock
from unittest.mock import Mock, patch

def test_api_call_with_mock(test_config):
    """测试 API 调用（使用 mock）"""
    with patch('requests.Session.post') as mock_post:
        # 设置 mock 返回值
        mock_response = Mock()
        mock_response.json.return_value = {"answer": "579"}
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        # 调用测试代码
        client = DifyWorkflowClient(test_config)
        result = client.execute_workflow({"query": "1+1=?"})

        # 验证结果
        assert result["answer"] == "579"
```

### 4. 测试覆盖率要求

- **单元测试**: ≥ 80%
- **集成测试**: 覆盖主要业务流程
- **API 测试**: 真实 API 调用测试

```bash
# 运行测试并生成覆盖率报告
uv run pytest --cov=src --cov-report=html --cov-report=term-missing

# 持续测试
uv run pytest --watch
```

---

## 📝 代码风格规范

### 1. 格式化工具配置

**pyproject.toml**:
```toml
[tool.black]
line-length = 88
target-version = ['py311']
include = '\.pyi?$'
extend-exclude = '''
/(
  # directories
  \.eggs
  | \.git
  | \.hg
  | \.mypy_cache
  | \.tox
  | \.venv
  | build
  | dist
)/
'''

[tool.ruff]
line-length = 88
target-version = "py311"
select = [
    "E",  # pycodestyle errors
    "W",  # pycodestyle warnings
    "F",  # pyflakes
    "I",  # isort
    "B",  # flake8-bugbear
    "C4", # flake8-comprehensions
    "UP", # pyupgrade
]
ignore = [
    "E501",  # line too long, handled by black
    "B008",  # do not perform function calls in argument defaults
    "W191",  # indentation contains tabs
    "B904",  # Allow raising exceptions without from e, for HTTP
]

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true
```

### 2. 编码规范

```python
# ✅ 良好的代码示例
from typing import List, Dict, Any, Optional

class AnswerComparator:
    """答案对比器 - 支持多种匹配算法"""

    @staticmethod
    def exact_match(answer1: str, answer2: str) -> bool:
        """精确匹配（忽略大小写和空格）

        Args:
            answer1: 第一个答案
            answer2: 第二个答案

        Returns:
            bool: 是否匹配
        """
        return (str(answer1).strip().lower() ==
                str(answer2).strip().lower())

    def compare(
        self,
        expected: str,
        actual: str,
        method: str = "auto"
    ) -> tuple[bool, str]:
        """对比答案

        Args:
            expected: 期望答案
            actual: 实际答案
            method: 匹配方法

        Returns:
            tuple[是否匹配, 匹配类型]
        """
        # ... 实现逻辑
```

### 3. 命名规范

```python
# ✅ 类名使用 PascalCase
class WorkflowBatchProcessor:
    pass

# ✅ 函数和变量使用 snake_case
def process_excel_file():
    excel_data = pd.read_excel("file.xlsx")

# ✅ 常量使用 UPPER_CASE
MAX_RETRIES = 3
DEFAULT_TIMEOUT = 60

# ✅ 私有成员使用单下划线前缀
class DataLoader:
    def _load_private_data(self):
        pass
```

---

## 🔗 模块交互规范

### 1. 依赖注入

```python
# ✅ 使用依赖注入
class WorkflowBatchProcessor:
    def __init__(
        self,
        config: WorkflowConfig,
        client: Optional[APIClient] = None,
        comparator: Optional[AnswerComparator] = None
    ):
        self.config = config
        self.client = client or DifyWorkflowClient(config)
        self.comparator = comparator or AnswerComparator()
```

### 2. 接口隔离

```python
# ✅ 定义清晰的接口
from abc import ABC, abstractmethod

class DataProcessor(ABC):
    @abstractmethod
    def process_data(self, data: Any) -> Any:
        pass

class APIClient(ABC):
    @abstractmethod
    def call_api(self, request: Any) -> Any:
        pass
```

### 3. 错误处理

```python
# ✅ 自定义异常
class OBDError(Exception):
    """OBD 基础异常"""
    pass

class APIError(OBDError):
    """API 调用异常"""
    pass

class ConfigError(OBDError):
    """配置错误"""
    pass

# ✅ 适当的异常处理
def process_excel(excel_path: str) -> List[QuestionAnswer]:
    try:
        # 尝试处理
        pass
    except FileNotFoundError as e:
        raise ConfigError(f"Excel文件不存在: {e}")
    except ValueError as e:
        raise OBDError(f"数据处理错误: {e}")
    except Exception as e:
        raise OBDError(f"未知错误: {e}")
```

---

## 📊 文档规范

### 1. 代码文档

```python
# ✅ 模块文档
"""答案对比模块

提供多种答案匹配算法，用于判断Dify API返回的答案与期望答案是否一致。

Classes:
    AnswerComparator: 答案对比器，提供多种匹配算法

Functions:
    exact_match: 精确匹配
    fuzzy_match: 模糊匹配
    keyword_match: 关键词匹配
"""

# ✅ 类文档
class AnswerComparator:
    """答案对比器

    提供精确、模糊、关键词等多种答案匹配算法。

    Attributes:
        None

    Methods:
        exact_match: 精确匹配
        fuzzy_match: 模糊匹配
        keyword_match: 关键词匹配
        compare: 综合对比
    """
```

### 2. API 文档

使用 `spec/` 目录存放所有文档：
- `api.md` - API 接口文档
- `models.md` - 数据模型文档
- `architecture.md` - 架构设计文档
- `quickstart.md` - 快速开始指南

### 3. 更新日志

**spec/README.md** 中的版本历史追踪：

| 版本 | 日期 | 修改内容 | 作者 |
|------|------|----------|------|
| v0.1.0 | 2025-12-29 | 初始版本 | Claude |
| v0.1.1 | 2025-12-29 | 修正API调用端点 | Claude |

---

## 🚀 开发工作流

### 1. 分支策略

```
main (主分支，保持稳定)
├── develop (开发分支)
├── feature/* (功能分支)
├── hotfix/* (热修复分支)
└── release/* (发布分支)
```

### 2. 提交信息规范

```bash
# ✅ 良好的提交信息
git commit -m "feat: 添加模糊匹配算法"

# ✅ 详细提交信息
git commit -m "feat(comparator): 实现模糊匹配算法

- 添加 fuzzy_match 方法
- 使用 difflib.SequenceMatcher 计算相似度
- 默认阈值设为 0.8
- 添加相应的单元测试

Addresses #123
Closes #45"
```

### 3. Pull Request 规范

```markdown
## 变更描述
- 添加了新的答案对比算法
- 优化了 API 调用性能
- 修复了 #123 号问题

## 测试结果
- 所有单元测试通过
- 测试覆盖率: 92%
- 集成测试通过

## 变更影响
- 破坏性变更: 无
- 新功能: 是
- 文档更新: 是

## 检查清单
- [x] 代码符合项目规范
- [x] 添加了测试用例
- [x] 更新了相关文档
- [x] 提交信息规范
```

---

## 🎯 质量保证

### 1. 自动化检查

```bash
# 代码格式化
uv run black src/ tests/
uv run ruff check src/ tests/ --fix

# 类型检查
uv run mypy src/

# 安全检查
uv run bandit -r src/

# 依赖检查
uv run safety check
```

### 2. CI/CD 流水线

```yaml
# .github/workflows/ci.yml
name: CI/CD

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v3
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        uv pip install -r requirements.txt

    - name: Run tests
      run: |
        uv run pytest --cov=src

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

---

## 📞 开发支持

### 1. 问题排查

- 查看 [问题排查指南](spec/troubleshooting.md)
- 查看测试报告
- 检查类型错误

### 2. 代码审查

- 遵循 TDD 原则
- 确保类型安全
- 检查测试覆盖率
- 验证文档完整性

### 3. 持续改进

- 定期更新依赖
- 优化性能
- 改进代码结构
- 完善文档

---

## 📝 更新日志

| 版本 | 日期 | 更新内容 |
|------|------|----------|
| v0.1.0 | 2025-12-29 | 初始版本，定义开发规范 |
| v0.1.1 | 2025-12-29 | 完善TDD规范和类型系统要求 |

---

**重要**: 本文档会随着项目发展持续更新，请定期查看最新版本。