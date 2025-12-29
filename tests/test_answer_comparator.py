"""测试答案对比器"""

import pytest
from obd.comparator.answer_comparator import AnswerComparator


class TestAnswerComparator:
    """测试AnswerComparator类"""

    def test_exact_match(self):
        """测试精确匹配"""
        # 相同答案应该匹配
        assert AnswerComparator.exact_match("Hello", "Hello") is True
        assert AnswerComparator.exact_match("Hello", "hello") is True  # 大小写不同也会匹配（因为会转小写）
        assert AnswerComparator.exact_match(" Hello ", "Hello") is True  # 空格会被去掉

        # 空白处理
        assert AnswerComparator.exact_match("", "") is True
        assert AnswerComparator.exact_match("  ", "") is True  # 空格会被去掉后比较

    def test_fuzzy_match(self):
        """测试模糊匹配"""
        # 相同答案应该匹配
        assert AnswerComparator.fuzzy_match("Hello", "Hello") is True

        # 相似的答案应该匹配（默认阈值0.8）
        assert AnswerComparator.fuzzy_match("Hello world", "Hello, world!") is True

        # 不相似的答案不匹配
        assert AnswerComparator.fuzzy_match("Hello", "Goodbye") is False

        # 自定义阈值
        assert AnswerComparator.fuzzy_match("Hello", "Helo", threshold=0.5) is True
        assert AnswerComparator.fuzzy_match("Hello", "Helo", threshold=0.9) is False

        # 空白处理
        assert AnswerComparator.fuzzy_match("", "") is False
        assert AnswerComparator.fuzzy_match("", "Hello") is False

    def test_keyword_match(self):
        """测试关键词匹配"""
        # 包含关键词应该匹配
        assert AnswerComparator.keyword_match("Python编程", "我喜欢Python语言") is True
        assert AnswerComparator.keyword_match("机器学习", "机器学习是人工智能的一部分") is True

        # 不包含关键词不匹配
        assert AnswerComparator.keyword_match("Python", "我爱Java") is False

        # 中文关键词
        assert AnswerComparator.keyword_match("人工智能", "人工智能是一门学科") is True

        # 数字关键词
        assert AnswerComparator.keyword_match("123", "答案是123456") is True

        # 单个字符关键词不匹配
        assert AnswerComparator.keyword_match("P", "Python") is False

        # 空白处理
        assert AnswerComparator.keyword_match("", "") is False
        assert AnswerComparator.keyword_match("", "Hello") is False

    def test_compare_exact_method(self):
        """测试exact对比方法"""
        # 匹配的情况
        is_match, match_type = AnswerComparator.compare("Hello", "Hello", "exact")
        assert is_match is True
        assert match_type == "exact"

        # "不匹配"的情况（实际会匹配，因为exact方法会转小写）
        is_match, match_type = AnswerComparator.compare("Hello", "hello", "exact")
        assert is_match is True
        assert match_type == "exact"

        # 空白情况
        is_match, match_type = AnswerComparator.compare("", "", "exact")
        assert is_match is False
        assert match_type == "empty"

    def test_compare_fuzzy_method(self):
        """测试fuzzy对比方法"""
        # 匹配的情况
        is_match, match_type = AnswerComparator.compare("Hello", "Hello", "fuzzy")
        assert is_match is True
        assert match_type == "fuzzy"

        # 相似但不同
        is_match, match_type = AnswerComparator.compare("Hello", "Helo", "fuzzy")
        assert is_match is True
        assert match_type == "fuzzy"

        # 不匹配
        is_match, match_type = AnswerComparator.compare("Hello", "Goodbye", "fuzzy")
        assert is_match is False
        assert match_type == "fuzzy"

    def test_compare_keyword_method(self):
        """测试keyword对比方法"""
        # 匹配的情况
        is_match, match_type = AnswerComparator.compare("Python", "I love Python", "keyword")
        assert is_match is True
        assert match_type == "keyword"

        # 不匹配
        is_match, match_type = AnswerComparator.compare("Python", "I love Java", "keyword")
        assert is_match is False
        assert match_type == "keyword"

    def test_compare_auto_method(self):
        """测试auto对比方法"""
        # 精确匹配
        is_match, match_type = AnswerComparator.compare("Hello", "Hello", "auto")
        assert is_match is True
        assert match_type == "exact"

        # 相似匹配
        is_match, match_type = AnswerComparator.compare("Hello", "Hello!", "auto")
        assert is_match is True
        assert match_type == "fuzzy"

        # 关键词匹配
        is_match, match_type = AnswerComparator.compare("Python", "I like Python", "auto")
        assert is_match is True
        assert match_type == "keyword"

        # 不匹配
        is_match, match_type = AnswerComparator.compare("Python", "Java", "auto")
        assert is_match is False
        assert match_type == "no_match"

    def test_compare_unknown_method(self):
        """测试未知方法"""
        is_match, match_type = AnswerComparator.compare("Hello", "Hello", "unknown")
        assert is_match is False
        assert match_type == "unknown"

    def test_compare_empty_values(self):
        """测试空值情况"""
        # 两个空字符串
        is_match, match_type = AnswerComparator.compare("", "", "auto")
        assert is_match is False
        assert match_type == "empty"

        # 一个空一个非空
        is_match, match_type = AnswerComparator.compare("", "Hello", "auto")
        assert is_match is False
        assert match_type == "empty"