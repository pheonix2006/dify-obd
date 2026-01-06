"""LLM 答案对比器"""

import httpx
import json
import logging
from typing import Tuple, Optional
from obd.models import LLMEvalConfig

logger = logging.getLogger(__name__)

DEFAULT_PROMPT = """你是一个专业的自动化测试评测员。请对比【问题】、【期望答案】和【实际回答】，判断实际回答是否在语义上与期望答案一致且正确。

【问题】
{question}

【期望答案】
{expected}

【实际回答】
{actual}

请按以下格式输出你的评判：
判断：[正确/错误]
分析：[请简洁分析为什么正确或错误，如果实际回答包含了期望答案的关键信息但表述不同，应判定为正确]
"""

class LLMComparator:
    """基于 LLM 的答案对比分析器"""

    def __init__(self, config: LLMEvalConfig):
        self.config = config
        self.prompt_template = config.prompt_template or DEFAULT_PROMPT

    async def evaluate(self, question: str, expected: str, actual: str) -> Tuple[bool, str]:
        """
        调用 LLM 进行评测分析

        Returns:
            (是否正确, 分析结果文本)
        """
        if not self.config.enabled or not self.config.api_key:
            return False, "LLM 评测未启用或未配置 API Key"

        url = f"{self.config.base_url.rstrip('/')}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.config.api_key}"
        }

        prompt = self.prompt_template.format(
            question=question,
            expected=expected,
            actual=actual
        )

        data = {
            "model": self.config.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.0  # 评测需要确定性
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=data, timeout=self.config.timeout)
                response.raise_for_status()
                result = response.json()

            if "choices" in result and len(result["choices"]) > 0:
                content = result["choices"][0]["message"]["content"].strip()
                
                # 简单解析判断结果
                is_correct = "判断：正确" in content or "判断：[正确]" in content
                return is_correct, content
            else:
                return False, f"API 返回格式异常: {json.dumps(result, ensure_ascii=False)}"

        except Exception as e:
            error_msg = f"LLM 评测请求失败: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
