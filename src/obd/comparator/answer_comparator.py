"""答案对比器"""

import re
from difflib import SequenceMatcher
from typing import Tuple


class AnswerComparator:
    """答案对比器"""

    @staticmethod
    def exact_match(answer1: str, answer2: str) -> bool:
        """精确匹配"""
        return str(answer1).strip().lower() == str(answer2).strip().lower()

    @staticmethod
    def fuzzy_match(answer1: str, answer2: str, threshold: float = 0.8) -> bool:
        """
        模糊匹配（基于相似度）

        Args:
            answer1: 答案1
            answer2: 答案2
            threshold: 相似度阈值

        Returns:
            是否匹配
        """
        answer1 = str(answer1).strip()
        answer2 = str(answer2).strip()

        if len(answer1) == 0 or len(answer2) == 0:
            return False

        similarity = SequenceMatcher(None, answer1, answer2).ratio()
        return similarity >= threshold

    @staticmethod
    def keyword_match(answer1: str, answer2: str) -> bool:
        """
        关键词匹配（检查是否包含关键信息）

        Args:
            answer1: 答案1（通常用于查找关键词）
            answer2: 答案2（通常用于检查是否包含）

        Returns:
            是否匹配
        """
        answer1 = str(answer1).strip().lower()
        answer2 = str(answer2).strip().lower()

        # 提取answer1中的关键词
        keywords = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+|[0-9]+', answer1)

        # 检查这些关键词是否在answer2中出现
        for keyword in keywords:
            if len(keyword) > 1 and keyword in answer2:
                return True

        return False

    @staticmethod
    def compare(
        expected: str,
        actual: str,
        method: str = "auto"
    ) -> Tuple[bool, str]:
        """
        对比答案

        Args:
            expected: 期望答案
            actual: 实际答案
            method: 匹配方法 (exact, fuzzy, keyword, auto)

        Returns:
            (是否匹配, 匹配类型)
        """
        if not expected or not actual:
            return False, "empty"

        # 空白匹配
        if not expected.strip() and not actual.strip():
            return True, "empty_match"

        if method == "exact":
            is_match = AnswerComparator.exact_match(expected, actual)
            return is_match, "exact"

        elif method == "fuzzy":
            is_match = AnswerComparator.fuzzy_match(expected, actual)
            return is_match, "fuzzy"

        elif method == "keyword":
            is_match = AnswerComparator.keyword_match(expected, actual)
            return is_match, "keyword"

        elif method == "auto":
            # 自动选择匹配方法
            # 1. 先尝试精确匹配
            if AnswerComparator.exact_match(expected, actual):
                return True, "exact"

            # 2. 尝试模糊匹配
            if AnswerComparator.fuzzy_match(expected, actual):
                return True, "fuzzy"

            # 3. 尝试关键词匹配
            if AnswerComparator.keyword_match(expected, actual):
                return True, "keyword"

            return False, "no_match"

        return False, "unknown"
