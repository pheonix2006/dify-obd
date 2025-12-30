"""
测试 Xinference Rerank 模型的原生调用
"""

from xinference_client import RESTfulClient as Client

def test_xinference_rerank():
    """测试 Xinference 原生 API 调用 rerank 模型"""
    try:
        # 连接到 Xinference 服务
        print("📡 正在连接到 Xinference 服务...")
        client = Client("http://localhost:9997")
        print("✅ 连接成功！")

        # 列出已有模型
        print("\n📋 正在列出已有模型...")
        existing_models = client.list_models()
        if existing_models:
            print(f"✅ 找到 {len(existing_models)} 个已有模型:")
            for uid, model_info in existing_models.items():
                print(f"  - UID: {uid}, 类型: {model_info.get('model_type')}, 名称: {model_info.get('model_name')}")

        # 查找已存在的 rerank 模型
        model_uid = None
        for uid, model_info in existing_models.items():
            if model_info.get('model_type') == 'rerank':
                model_uid = uid
                print(f"\n🎯 使用已存在的 rerank 模型: {model_uid}")
                break

        # 如果没有找到，尝试启动新模型
        if not model_uid:
            print("\n🚀 正在启动 bge-reranker-v2-m3 模型...")
            model_uid = client.launch_model(
                model_name="bge-reranker-v2-m3",
                model_type="rerank"
            )
            print(f"✅ 模型启动成功！Model UID: {model_uid}")

        # 获取模型实例
        print("\n🔍 正在获取模型实例...")
        model = client.get_model(model_uid)
        print("✅ 模型实例获取成功！")

        # 测试 rerank
        print("\n🧪 正在测试 rerank 功能...")
        query = "A man is eating pasta."
        corpus = [
            "A man is eating food.",
            "A man is eating a piece of bread.",
            "The girl is carrying a baby.",
            "A man is riding a horse.",
            "A woman is playing violin."
        ]

        result = model.rerank(corpus, query)
        print("\n📊 Rerank 结果:")
        for i, item in enumerate(result, 1):
            print(f"  {i}. [{item['index']}] {item['document']}")
            print(f"     相关性分数: {item['relevance_score']:.4f}\n")

        print("✅ 测试完成！")

        # 可选：清理模型
        # client.terminate_model(model_uid)
        # print("🧹 模型已终止")

        return True

    except Exception as e:
        print(f"❌ 错误: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    test_xinference_rerank()
