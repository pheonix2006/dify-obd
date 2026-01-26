"""
评测记录器 - 记录 LLM 评测的输入输出用于调试和分析

此模块提供了记录 LLM 评测过程的功能，包括：
- 完整的 prompt（输入）
- LLM 的原始响应（输出）
- 上下文信息（问题、召回文档、实际回答）

记录按时间戳分文件夹存储，每个问题一个 JSON 文件。
"""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

import aiofiles


@dataclass
class EvalRecord:
    """单条评测记录数据结构"""

    question: str
    """问题内容"""

    context: Optional[str]
    """召回文档片段"""

    actual_answer: str
    """实际回答"""

    prompt: str
    """LLM 输入的完整 prompt"""

    raw_response: str
    """LLM 原始响应（JSON 格式）"""

    parsed_result: Dict[str, Any]
    """解析后的结构化结果"""

    timestamp: str
    """ISO 格式时间戳"""

    question_index: int
    """问题索引（用于生成文件名）"""

    model: str
    """使用的模型名称"""

    category: Optional[str] = None
    """4级分类结果"""

    is_correct: Optional[bool] = None
    """2级分类结果"""


class EvalRecorder:
    """
    评测记录器

    按时间戳创建会话目录，将每次 LLM 评测的输入输出保存为 JSON 文件。

    示例目录结构:
        logs/eval_records/
        └── 2026-01-24_143025/
            ├── question_000001.json
            ├── question_000002.json
            └── ...
    """

    DEFAULT_BASE_DIR = "logs/eval_records"

    def __init__(
        self,
        base_dir: str = DEFAULT_BASE_DIR,
        enabled: bool = True,
        session_prefix: Optional[str] = None
    ):
        """
        初始化记录器

        Args:
            base_dir: 基础记录目录（相对于项目根目录或绝对路径）
            enabled: 是否启用记录
            session_prefix: 会话前缀（用于区分不同批次）
        """
        self.base_dir = Path(base_dir)
        self.enabled = enabled
        self.session_prefix = session_prefix

        # 创建会话目录
        self.session_dir: Optional[Path] = None
        if self.enabled:
            self.session_dir = self._create_session_dir()

    def _create_session_dir(self) -> Path:
        """
        创建按时间戳命名的会话目录

        Returns:
            会话目录路径
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        if self.session_prefix:
            dir_name = f"{self.session_prefix}_{timestamp}"
        else:
            dir_name = timestamp

        session_path = self.base_dir / dir_name
        session_path.mkdir(parents=True, exist_ok=True)
        return session_path

    def get_record_path(self, question_index: int) -> Path:
        """
        获取记录文件路径

        Args:
            question_index: 问题索引

        Returns:
            记录文件的完整路径
        """
        filename = f"question_{question_index:06d}.json"
        return self.session_dir / filename

    async def save_record(
        self,
        question: str,
        context: Optional[str],
        actual_answer: str,
        prompt: str,
        raw_response: str,
        parsed_result: Dict[str, Any],
        question_index: int,
        model: str,
        category: Optional[str] = None,
        is_correct: Optional[bool] = None
    ) -> Optional[Path]:
        """
        保存单条评测记录（异步）

        Args:
            question: 问题内容
            context: 召回文档片段
            actual_answer: 实际回答
            prompt: LLM 输入的完整 prompt
            raw_response: LLM 原始响应（JSON 格式）
            parsed_result: 解析后的结构化结果
            question_index: 问题索引
            model: 使用的模型名称
            category: 4级分类结果
            is_correct: 2级分类结果

        Returns:
            保存的文件路径，如果未启用则返回 None
        """
        if not self.enabled:
            return None

        record = EvalRecord(
            question=question,
            context=context,
            actual_answer=actual_answer,
            prompt=prompt,
            raw_response=raw_response,
            parsed_result=parsed_result,
            timestamp=datetime.now().isoformat(),
            question_index=question_index,
            model=model,
            category=category,
            is_correct=is_correct
        )

        file_path = self.get_record_path(question_index)

        # 异步写入文件
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            await f.write(json.dumps(asdict(record), ensure_ascii=False, indent=2))

        return file_path

    def save_record_sync(
        self,
        question: str,
        context: Optional[str],
        actual_answer: str,
        prompt: str,
        raw_response: str,
        parsed_result: Dict[str, Any],
        question_index: int,
        model: str,
        category: Optional[str] = None,
        is_correct: Optional[bool] = None
    ) -> Optional[Path]:
        """
        保存单条评测记录（同步版本）

        用于非异步上下文。

        Args:
            question: 问题内容
            context: 召回文档片段
            actual_answer: 实际回答
            prompt: LLM 输入的完整 prompt
            raw_response: LLM 原始响应（JSON 格式）
            parsed_result: 解析后的结构化结果
            question_index: 问题索引
            model: 使用的模型名称
            category: 4级分类结果
            is_correct: 2级分类结果

        Returns:
            保存的文件路径，如果未启用则返回 None
        """
        if not self.enabled:
            return None

        record = EvalRecord(
            question=question,
            context=context,
            actual_answer=actual_answer,
            prompt=prompt,
            raw_response=raw_response,
            parsed_result=parsed_result,
            timestamp=datetime.now().isoformat(),
            question_index=question_index,
            model=model,
            category=category,
            is_correct=is_correct
        )

        file_path = self.get_record_path(question_index)

        # 同步写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(record), f, ensure_ascii=False, indent=2)

        return file_path

    async def save_batch(self, records: List[EvalRecord]) -> List[Optional[Path]]:
        """
        批量保存记录

        Args:
            records: 评测记录列表

        Returns:
            保存的文件路径列表
        """
        if not self.enabled or not records:
            return []

        tasks = []
        for record in records:
            task = self.save_record(
                question=record.question,
                context=record.context,
                actual_answer=record.actual_answer,
                prompt=record.prompt,
                raw_response=record.raw_response,
                parsed_result=record.parsed_result,
                question_index=record.question_index,
                model=record.model,
                category=record.category,
                is_correct=record.is_correct
            )
            tasks.append(task)

        return await asyncio.gather(*tasks)

    def get_session_dir(self) -> Optional[Path]:
        """
        获取当前会话目录

        Returns:
            会话目录路径，如果未启用则返回 None
        """
        return self.session_dir if self.enabled else None
