# RAG模块测试文档

## 测试概述

本测试套件验证RAG模块的核心功能，包括知识库加载、向量检索和完整的RAG流程。

## 运行测试

```bash
# 安装测试依赖
pip install pytest pytest-asyncio

# 运行所有测试
python -m pytest tests/test_rag_module.py -v

# 运行特定测试类
python -m pytest tests/test_rag_module.py::TestKnowledgeBaseLoader -v
```

## 测试覆盖

### 1. 知识库加载器测试 (TestKnowledgeBaseLoader)

- ✅ `test_load_valid_knowledge_base`: 测试加载有效的知识库文件
- ✅ `test_load_nonexistent_file`: 测试加载不存在的文件（返回空列表）
- ✅ `test_load_malformed_file`: 测试加载格式错误的文件（跳过错误行）
- ✅ `test_load_empty_fields`: 测试包含空字段的文件（跳过空字段行）
- ✅ `test_reload_knowledge_base`: 测试重新加载知识库功能

### 2. 向量检索测试 (TestVectorStoreRetrieval)

- ✅ `test_search_returns_sorted_results`: 测试检索结果按相似度从高到低排序
- ✅ `test_search_with_top_k`: 测试top_k参数限制返回结果数量

### 3. RAG模块集成测试 (TestRAGModule)

- ✅ `test_rag_initialization`: 测试RAG模块初始化
- ✅ `test_retrieve_returns_candidates`: 测试检索返回候选结果
- ✅ `test_retrieve_sorted_by_similarity`: 测试检索结果按相似度排序
- ✅ `test_retrieve_empty_question`: 测试空问题返回空结果
- ✅ `test_retrieve_before_initialization`: 测试未初始化时检索抛出异常

## 测试结果

所有12个测试用例均通过 ✅

## 注意事项

- 测试使用 `paraphrase-MiniLM-L3-v2` 模型以加快测试速度
- 生产环境应使用 `shibing624/text2vec-base-chinese` 模型以获得更好的中文语义理解
- 测试使用临时文件，测试完成后自动清理
