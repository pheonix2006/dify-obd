# 5分钟快速开始指南

## 🚀 快速上手

本指南将帮助你在5分钟内快速运行OBD批处理器。

---

## 📋 步骤1: 准备工作 (1分钟)

### 1.1 确认环境
```bash
# 检查Python版本 (需要3.11+)
python --version
# 输出类似: Python 3.11.0

# 检查是否安装了uv
uv --version
# 如果没有安装，请访问 https://astral.sh/uv/
```

### 1.2 下载项目文件
确保你有以下文件：
- `questions.xlsx` - 包含问题和答案的Excel文件
- `config.ini` - 配置文件

**Excel文件格式要求:**
```
|     question     |    answer     |
|------------------|---------------|
| 请计算123+456=? | 579           |
| 北京是首都吗？   | 是            |
| 5的立方是多少？   | 125           |
```

---

## 📝 步骤2: 配置API (1分钟)

### 2.1 编辑 `config.ini`
打开配置文件，修改以下关键项：

```ini
[Dify]
# ✅ 替换为你的API密钥
api_key = app-your-actual-api-key-here

# ✅ 根据你的环境选择URL
# 云端Dify (默认)
base_url = https://api.dify.ai/v1
# 或本地Dify
# base_url = http://localhost/v1

[Workflow]
# ✅ 确认变量名与Dify工作流一致
input_variable_name = query
output_variable_name = answer

[Excel]
# ✅ 确认列名与Excel文件一致
file_path = questions.xlsx
question_column = question
answer_column = answer
```

### 2.2 验证配置
```bash
# 进入项目目录
cd E:\Project\obd

# 激活虚拟环境 (如果使用)
.venv\Scripts\activate  # Windows
# 或
source .venv/bin/activate  # macOS/Linux

# 安装依赖
uv pip install -r requirements.txt
```

---

## 🏃 步骤3: 运行测试 (1分钟)

### 3.1 基础测试
```bash
# 运行批处理器
uv run python -m obd.main
```

**预期输出:**
```
============================================================
Dify工作流批处理器 - 真实API测试
============================================================

加载配置: {...}
处理Excel文件: questions.xlsx
问题列: question
答案列: answer
对比方法: auto
请求延迟: 0.5秒

------------------------------------------------------------
共 3 行，处理第 0 行到第 2 行
------------------------------------------------------------
[1/3] 处理问题: 请计算123+456=?...
  ✓ 正确 (keyword)
[2/3] 处理问题: 北京是首都吗？...
  ✓ 正确 (keyword)
[3/3] 处理问题: 5的立方是多少？...
  ✓ 正确 (keyword)

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

### 3.2 检查结果
运行完成后，查看生成的 `results.xlsx` 文件：

- **Sheet1 "处理结果"**: 详细的每行处理结果
- **Sheet2 "统计信息"**: 整体统计指标

---

## 🔧 步骤4: 自定义配置 (1分钟)

### 4.1 修改对比方法
```ini
[Workflow]
# 尝试不同的对比方法
comparison_method = exact    # 精确匹配
# 或
comparison_method = fuzzy   # 模糊匹配
# 或
comparison_method = keyword  # 关键词匹配
```

### 4.2 调整请求参数
```ini
[Workflow]
# 减少延迟以加快处理速度
delay = 0.3

# 增加超时时间（如果处理复杂问题）
timeout = 120

[Dify]
# 使用流式模式（如果支持）
response_mode = streaming
```

### 4.3 处理部分数据
在代码中修改处理范围：
```python
# 在main.py中修改process_excel参数
results = processor.process_excel(
    excel_path="questions.xlsx",
    start_row=0,        # 从第0行开始
    end_row=5,         # 只处理前5行
    delay=0.5
)
```

---

## 🎯 步骤5: 高级用法 (1分钟)

### 5.1 程序化调用
创建 `test.py`:
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

# 处理单个问题
result = processor.process_question(
    question="Python是什么？",
    comparison_method="keyword"
)
print(f"答案: {result.workflow_result}")

# 批量处理
results = processor.process_excel(
    "questions.xlsx",
    comparison_method="auto"
)

# 查看统计
stats = processor.calculate_statistics(results)
print(f"准确率: {stats['accuracy']:.1%}")
```

运行测试：
```bash
uv run python test.py
```

### 5.2 错误处理
```python
from obd.models import WorkflowConfig
from obd.processor import WorkflowBatchProcessor

try:
    config = WorkflowConfig(api_key="app-your-key")
    processor = WorkflowBatchProcessor(config)
    results = processor.process_excel("questions.xlsx")

    # 检查失败项
    failed = [r for r in results if r.error]
    if failed:
        print(f"有 {len(failed)} 个调用失败")
        for r in failed:
            print(f"错误: {r.error}")

except FileNotFoundError as e:
    print(f"文件不存在: {e}")
except Exception as e:
    print(f"发生错误: {e}")
```

---

## 🎉 完成检查清单

- [ ] ✅ Python 3.11+ 已安装
- [ ] ✅ uv 包管理器已安装
- [ ] ✅ 项目依赖已安装 (`uv pip install -r requirements.txt`)
- [ ] ✅ `config.ini` 中的 API 密钥已配置
- [ ] ✅ Excel 文件路径和列名已确认
- [ ] ✅ 成功运行 `uv run python -m obd.main`
- [ ] ✅ 查看了生成的 `results.xlsx` 结果文件

---

## 🚀 下一步

### 1. 探索更多功能
- 阅读 [API接口文档](api.md) 了解更多API选项
- 查看 [使用示例](examples.md) 学习高级用法
- 了解 [答案对比算法](comparator.md) 的原理

### 2. 优化性能
- 调整 `delay` 参数平衡速度和稳定性
- 使用 `start_row` 和 `end_row` 处理大文件
- 启用日志查看详细执行信息

### 3. 故障排除
如果遇到问题，请查看：
- [问题排查指南](troubleshooting.md)
- [测试报告](test-results.md) 了解已知问题

### 4. 参与贡献
- 发现Bug？请在Issues中报告
- 有改进建议？欢迎提交PR
- 需要新功能？请提出需求

---

## 📞 获取帮助

### 快速问题
- 检查 `config.ini` 中的配置
- 确认API密钥是否有效
- 验证Excel文件格式

### 技术支持
- 查看 [完整文档](README.md)
- 阅读 [架构设计](architecture.md)
- 了解 [开发规范](coding-standards.md)

---

**恭喜！你已经成功运行了OBD批处理器！** 🎉

现在你可以开始处理更多的问题，并根据需要调整配置参数。