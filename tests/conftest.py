"""pytest配置文件"""

import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def sample_config():
    """测试用的配置对象"""
    from obd.models import WorkflowConfig
    return WorkflowConfig(
        api_key="test_api_key",
        base_url="https://api.test.com/v1",
        timeout=10
    )


@pytest.fixture
def sample_excel_file():
    """测试用的Excel文件"""
    # 创建临时CSV文件
    csv_content = """question,answer
问题1：1+1=?,2
问题2：Python是什么？,Python是一种编程语言
问题3：中国的首都？,北京"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as tmp:
        tmp.write(csv_content)
        tmp.flush()
        # 关闭文件后再重命名
        tmp.close()
        # 创建一个假的.xlsx文件名以兼容测试
        excel_path = tmp.name.replace('.csv', '.xlsx')
        os.rename(tmp.name, excel_path)
        yield excel_path

    # 清理临时文件
    try:
        if os.path.exists(excel_path):
            os.unlink(excel_path)
    except:
        pass


@pytest.fixture
def sample_results():
    """测试用的处理结果列表"""
    from obd.models import QuestionAnswer

    results = [
        QuestionAnswer(
            question="问题1：1+1=?",
            expected_answer="2",
            workflow_result="2",
            is_correct=True,
            match_type="exact"
        ),
        QuestionAnswer(
            question="问题2：Python是什么？",
            expected_answer="Python是一种编程语言",
            workflow_result="Python是广泛使用的高级编程语言",
            is_correct=True,
            match_type="fuzzy"
        ),
        QuestionAnswer(
            question="问题3：中国的首都？",
            expected_answer="北京",
            workflow_result="上海",
            is_correct=False,
            match_type="keyword"
        ),
        QuestionAnswer(
            question="问题4：无效问题？",
            expected_answer="正常答案",
            error="API调用失败"
        )
    ]

    return results