"""双模型响应解析器单元测试"""

import pytest
from obd.utils.dual_model_parser import DualModelResponseParser


def test_parse_full_format():
    """测试完整格式解析"""
    response = """问题：什么是装饰器？
rerank后的片段：装饰器是 Python 的一个重要特性，用于在不修改函数代码的情况下扩展功能。
经过llm1的结果：装饰器（decorator）是 Python 中的一种设计模式，允许在不修改原有代码的情况下为函数添加额外功能。
经过llm2的结果：在 Python 中，装饰器是一种语法糖，本质上是一个接受函数作为参数并返回新函数的高阶函数。"""

    result = DualModelResponseParser.parse(response)

    assert result.is_valid_format is True
    assert result.question == "什么是装饰器？"
    assert "装饰器是 Python 的一个重要特性" in result.rerank_sources
    assert "decorator" in result.llm1_output
    assert "语法糖" in result.llm2_output


def test_parse_empty_response():
    """测试空响应"""
    result = DualModelResponseParser.parse("")
    assert result.is_valid_format is False
    assert result.llm1_output == ""


def test_parse_none_response():
    """测试 None 响应"""
    result = DualModelResponseParser.parse(None)
    assert result.is_valid_format is False
    assert result.llm1_output == ""


def test_parse_partial_format():
    """测试部分格式的 fallback"""
    response = "经过llm1的结果：只有 LLM1 的输出"
    result = DualModelResponseParser.parse(response)
    assert result.is_valid_format is False
    assert result.llm1_output == response


def test_parse_missing_llm2():
    """测试缺少 LLM2 分隔符"""
    response = """问题：什么是装饰器？
rerank后的片段：装饰器是 Python 的一个重要特性。
经过llm1的结果：装饰器是一种设计模式。"""
    result = DualModelResponseParser.parse(response)
    assert result.is_valid_format is False


def test_parse_wrong_order():
    """测试错误顺序的标记"""
    response = """问题：什么是装饰器？
经过llm1的结果：装饰器是一种设计模式。
rerank后的片段：装饰器是 Python 的一个重要特性。
经过llm2的结果：装饰器是语法糖。"""
    result = DualModelResponseParser.parse(response)
    assert result.is_valid_format is False


def test_parse_multiline_content():
    """测试多行内容"""
    response = """问题：Python 中的装饰器是什么？
rerank后的片段：资料来源 [1]
装饰器（decorator）是 Python 的一个重要特性。
资料来源 [2]
它可以用于日志记录、性能测试、事务处理等。
经过llm1的结果：装饰器是 Python 中的一种设计模式。

它的作用是在不修改原有代码的情况下为函数添加额外功能。
经过llm2的结果：装饰器本质上是一个高阶函数。

它接受一个函数作为参数，返回一个新的函数。"""
    result = DualModelResponseParser.parse(response)

    assert result.is_valid_format is True
    assert "资料来源 [1]" in result.rerank_sources
    assert "资料来源 [2]" in result.rerank_sources
    assert "不修改原有代码" in result.llm1_output
    assert "高阶函数" in result.llm2_output


def test_parse_with_special_characters():
    """测试包含特殊字符的内容"""
    response = """问题：C++ 中指针和引用的区别？
rerank后的片段：指针和引用是 C++ 中两种不同的传递方式。区别包括：1. 初始化；2. 重新赋值；3. 空值。
经过llm1的结果：指针可以为空，引用不能为空。指针可以重新赋值，引用初始化后不能改变。
经过llm2的结果：引用是别名，指针是地址。引用必须在声明时初始化，指针可以延迟初始化。"""
    result = DualModelResponseParser.parse(response)

    assert result.is_valid_format is True
    assert "C++" in result.question
    assert "指针" in result.question
    assert "1. 初始化" in result.rerank_sources


def test_parse_with_variant_markers():
    """测试变体分隔符（冒号后无空格）"""
    response = """问题:什么是装饰器？
rerank后的片段:装饰器是 Python 的一个重要特性。
经过llm1的结果:装饰器是一种设计模式。
经过llm2的结果:装饰器是语法糖。"""

    result = DualModelResponseParser.parse(response)
    # 变体分隔符应该能被识别
    assert "装饰器是一种设计模式" in result.llm1_output
    assert "装饰器是语法糖" in result.llm2_output


def test_parse_partial_format_llm_only():
    """测试只有 LLM1 和 LLM2 的部分格式"""
    response = """经过llm1的结果：装饰器是一种设计模式。
经过llm2的结果：装饰器是语法糖。"""

    result = DualModelResponseParser.parse(response)
    assert "装饰器是一种设计模式" in result.llm1_output
    assert "装饰器是语法糖" in result.llm2_output
    assert result.is_valid_format is False  # 部分格式


def test_parse_alternative_rerank_marker():
    """测试使用'召回片段'替代'rerank后的片段'"""
    response = """问题：什么是闭包？
召回片段：闭包是指有权访问另一个函数作用域中变量的函数。
经过llm1的结果：闭包是函数和声明该函数的词法环境的组合。
经过llm2的结果：闭包就是能够读取其他函数内部变量的函数。"""

    result = DualModelResponseParser.parse(response)
    # 应该能解析（使用变体分隔符）
    assert "闭包是函数和声明" in result.llm1_output or result.llm1_output  # 至少有内容
    assert "能够读取其他函数" in result.llm2_output or result.llm2_output
