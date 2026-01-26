"""
验证 RAG 模式 API 调用修复

检查 _call_dify_api_for_rag 方法是否正确调用 execute_workflow
"""
import inspect
from src.obd.processor.batch_processor import WorkflowBatchProcessor
from src.obd.models import WorkflowConfig
from src.obd.client.dify_client import DifyWorkflowClient


def test_method_signature():
    """验证方法签名正确"""
    # 检查 _call_dify_api_for_rag 方法存在
    assert hasattr(WorkflowBatchProcessor, '_call_dify_api_for_rag')
    print("✅ _call_dify_api_for_rag 方法存在")

    # 检查方法是异步的
    method = getattr(WorkflowBatchProcessor, '_call_dify_api_for_rag')
    assert inspect.iscoroutinefunction(method)
    print("✅ 方法是异步的")

    # 检查方法签名
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())
    assert params == ['self', 'question']
    print(f"✅ 方法签名正确: {params}")


def test_client_has_execute_workflow():
    """验证 DifyWorkflowClient 有 execute_workflow 方法"""
    assert hasattr(DifyWorkflowClient, 'execute_workflow')
    print("✅ DifyWorkflowClient.execute_workflow 方法存在")

    # 检查方法是异步的
    method = getattr(DifyWorkflowClient, 'execute_workflow')
    assert inspect.iscoroutinefunction(method)
    print("✅ execute_workflow 是异步方法")

    # 检查方法签名
    sig = inspect.signature(method)
    params = list(sig.parameters.keys())
    assert 'inputs' in params
    assert 'user' in params
    assert 'workflow_id' in params
    print(f"✅ execute_workflow 签名正确: {params}")


def test_client_does_not_have_run_workflow():
    """验证 DifyWorkflowClient 没有 run_workflow 方法（这是要修复的问题）"""
    has_run_workflow = hasattr(DifyWorkflowClient, 'run_workflow')
    if has_run_workflow:
        print("⚠️  DifyWorkflowClient.run_workflow 方法存在（不应该存在）")
    else:
        print("✅ DifyWorkflowClient.run_workflow 方法不存在（正确）")


def test_source_code_contains_correct_call():
    """验证源代码中包含正确的调用"""
    import inspect

    # 获取 _call_dify_api_for_rag 方法的源代码
    method = getattr(WorkflowBatchProcessor, '_call_dify_api_for_rag')
    source = inspect.getsource(method)

    # 检查包含 execute_workflow 调用
    assert 'execute_workflow' in source
    print("✅ 源代码包含 execute_workflow 调用")

    # 检查不包含 run_workflow 调用（旧的错误调用）
    if 'run_workflow' in source:
        print("⚠️  源代码仍包含 run_workflow 调用（应该移除）")
    else:
        print("✅ 源代码不包含 run_workflow 调用")

    # 检查参数格式正确
    assert 'inputs=inputs' in source or 'inputs = inputs' in source
    print("✅ 参数格式正确: inputs=inputs")

    assert 'workflow_id=None' in source or 'workflow_id = None' in source
    print("✅ 参数格式正确: workflow_id=None")


if __name__ == "__main__":
    print("=" * 60)
    print("RAG 模式 API 调用修复验证")
    print("=" * 60)
    print()

    try:
        print("1. 验证方法签名...")
        test_method_signature()
        print()

        print("2. 验证客户端方法...")
        test_client_has_execute_workflow()
        test_client_does_not_have_run_workflow()
        print()

        print("3. 验证源代码...")
        test_source_code_contains_correct_call()
        print()

        print("=" * 60)
        print("✅ 所有验证通过！修复成功！")
        print("=" * 60)

    except AssertionError as e:
        print()
        print("=" * 60)
        print(f"❌ 验证失败: {e}")
        print("=" * 60)
        raise
