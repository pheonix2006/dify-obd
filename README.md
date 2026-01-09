# OBD - Dify 工作流批处理器

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg)

**批量调用 Dify API，智能评测答案质量，生成详细分析报告**

</div>

---

## 📋 项目简介

OBD (Open Batch Processor) 是一个专业的 Dify 工作流批量处理工具，能够自动从 Excel 文件读取问题，批量调用 Dify API，并使用 LLM 进行语义级的答案质量评测。

### 核心功能

- 📖 **批量处理**: 从 Excel 文件批量读取问题并调用 Dify API
- 🎯 **智能评测**: 基于 LLM 的语义级答案质量评估
- 📊 **双层分类**: 支持 2 级分类（正确率）和 4 级分类（详细分析）
- 📈 **结果导出**: 生成包含分类标签和缺失信息的 Excel 报告
- ⚡ **高性能**: 支持本地和云端 Dify 部署，灵活配置
- 🎛️ **双模式提示**: 支持详细标准和智能判断两种 LLM 评测模式

### 适用场景

- **教育评估**: 自动批改作业和考试题目，提供详细评分依据
- **质量检测**: 对比 AI 回答与标准答案的一致性，识别缺失信息
- **数据标注**: 批量验证 AI 生成内容的质量，提供改进建议
- **API 测试**: 测试 Dify 工作的响应准确性，支持多维度评测
- **RAG 优化**: 评估检索增强生成系统的答案质量和完整性

---

## 🚀 快速开始

### 环境要求

- **Python**: 3.11 或更高版本
- **操作系统**: Windows 10/11, macOS 10.15+, Linux (Ubuntu 18.04+)
- **内存**: 最小 512MB，推荐 2GB+
- **网络**: 需要访问 Dify 服务（本地或云端）

### 安装步骤

```bash
# 1. 克隆项目
git clone <repository-url>
cd obd

# 2. 创建虚拟环境
uv venv

# 3. 激活虚拟环境
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate

# 4. 安装依赖
uv pip install -r requirements.txt
```

---

## ⚙️ 配置指南

### 1. 创建配置文件

```bash
cp config.ini.example config.ini
```

### 2. 配置关键参数

编辑 `config.ini`，至少配置以下参数：

```ini
[Dify]
# 必填：Dify API密钥
api_key = app-your-api-key-here

# 必填：Dify服务地址
base_url = https://api.dify.ai/v1

[Excel]
# 必填：Excel文件路径
file_path = questions.xlsx

# 必填：问题和答案的列名
question_column = PROBLEM_VALUE
answer_column = ANSWER_VALUE

[LLM_EVAL]
# 可选：启用LLM智能评测
enabled = true
api_key = sk-your-openai-key-here
base_url = https://api.openai.com/v1
model = gpt-4o
```

### 3. 准备 Excel 文件

确保 Excel 文件包含问题和答案两列（列名需与配置一致）：

| PROBLEM_VALUE | ANSWER_VALUE |
|--------------|--------------|
| 请计算123+456=? | 579 |
| 北京是首都吗？ | 是 |

> 💡 **更多配置选项**：查看完整配置说明请参考 [.spec/setup.md](.spec/setup.md)

---

## 📖 使用方法

### 命令行运行

```bash
# 使用默认配置文件 config.ini
uv run python -m obd.main

# 指定自定义配置文件
uv run python -m obd.main --config my_config.ini
```

### 输出说明

程序运行后会生成 Excel 文件，包含：

- **主工作表**：每道题的评测结果、4级分类、缺失信息
- **统计工作表**：总体正确率、4级分类分布

---

## 🤖 LLM 智能评测

### 双层分类体系

**2 级分类（用于计算正确率）**:
- **正确**: 重要信息全覆盖，可忽略非重要信息缺失
- **错误**: 任何不符合正确标准的情况

**4 级分类（用于详细分析）**:
- **完全正确** (`fully_correct`): 重要信息全覆盖
- **部分缺失** (`partial_missing`): 有少量重要信息缺失
- **大量缺失** (`large_missing`): 很多信息（参数等）缺少
- **完全错误** (`completely_wrong`): 完全错误/未回答

### 判断模式

| 模式 | 说明 | 适用场景 |
|------|------|----------|
| **detailed** | 明确定义每种错误类型的判断标准 | 需要严格评判标准 |
| **autonomous** | 让 LLM 根据语义自主判断 | 需要灵活理解 |

**温度参数建议**：
- `0.0`: 最确定（推荐评测使用）
- `0.3-0.7`: 平衡
- `1.0`: 最随机（不推荐评测使用）

> 💡 **详细说明**：查看 [.spec/comparator.md](.spec/comparator.md) 了解 LLM 评测原理

---

## ❓ 常见问题

### 配置相关

**Q: 提示 "API Key 无效" 怎么办？**
A: 检查 `[Dify]` 和 `[LLM_EVAL]` 中的 `api_key` 配置是否正确。

**Q: 如何配置多个知识库？**
A: 使用 `[WORKFLOW_MAPPING]` 节点，格式为 `知识库名 = API Key`。

**Q: Excel 列名和配置不一致怎么办？**
A: 确保配置文件中的 `question_column` 和 `answer_column` 与 Excel 实际列名完全一致（区分大小写）。

### 运行相关

**Q: 处理速度太慢怎么办？**
A: 可以调整 `[Workflow]` 中的 `delay` 参数（默认 0.5 秒），适当减少延迟可提升速度。

**Q: 遇到 API 限流怎么办？**
A: 增大 `delay` 参数，或分批次处理大文件。

**Q: LLM 评测不准确怎么办？**
A: 尝试切换 `judgment_mode` 为 `detailed`，或设置 `temperature` 为 `0.0` 提高一致性。

### 输出相关

**Q: 如何解读 4 级分类结果？**
A:
- **完全正确**: 答案质量优秀，无需改进
- **部分缺失**: 缺少少量重要信息，可以补充完善
- **大量缺失**: 缺少多个关键信息，需要大幅改进
- **完全错误**: 答案完全错误或未回答，需要重新生成

> 💡 **更多问题**：查看 [.spec/troubleshooting.md](.spec/troubleshooting.md)

---

## 📁 文档导航

| 文档 | 说明 |
|------|------|
| [.spec/setup.md](.spec/setup.md) | 完整配置教程 |
| [.spec/quickstart.md](.spec/quickstart.md) | 详细快速开始指南 |
| [.spec/api.md](.spec/api.md) | API 接口文档 |
| [.spec/examples.md](.spec/examples.md) | 使用示例（含程序化调用）|
| [.spec/troubleshooting.md](.spec/troubleshooting.md) | 问题排查指南 |
| [CLAUDE.md](CLAUDE.md) | 开发规范（面向开发者）|

---

## 🤝 贡献指南

欢迎贡献代码！请遵循以下流程：

1. Fork 项目并创建功能分支
2. 遵循开发规范（[CLAUDE.md](CLAUDE.md)）
3. 运行测试确保通过：`uv run pytest`
4. 提交更改并创建 Pull Request

---

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

---

## 📞 联系我们

- **问题反馈**: [GitHub Issues](../../issues)
- **功能建议**: [GitHub Discussions](../../discussions)

---

## 🙏 致谢

- [Dify](https://docs.dify.ai/) - 强大的 AI 应用平台
- [uv](https://docs.astral.sh/uv/) - 快速的 Python 包管理器
- [pandas](https://pandas.pydata.org/) - 强大的数据处理库

---

<div align="center">
Made with ❤️ by OBD Team
</div>
