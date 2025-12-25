# [算法名称] - 请修改为你的算法名称

## 算法简介

请在这里描述你的算法：

- 算法的基本原理
- 适用场景
- 主要特点

## 参数说明

### 必需参数

- **param1**: 参数 1 的详细说明
- **param2**: 参数 2 的详细说明

### 可选参数

- **param3**: 参数 3 的详细说明，默认值：None

## 数据要求

1. 至少需要 X 行数据
2. 至少需要 X 个特征列
3. 其他特殊要求...

## 使用示例

### 示例 1

```
用户问题: "示例问题1"
预期输出:
{
  "parameter_mapping": {
    "param1": "实际列名1",
    "param2": ["实际列名2", "实际列名3"],
    "param3": null
  }
}
```

### 示例 2

```
用户问题: "示例问题2"
预期输出:
{
  "parameter_mapping": {
    "param1": "实际列名1",
    "param2": ["实际列名2"],
    "param3": 5
  }
}
```

## 开发指南

### 1. 复制模板

```bash
cp -r algorithm/template algorithm/your_algorithm_name
```

### 2. 修改文件名

- `extractor_template.py` → `extractor.py`
- `processor_template.py` → `processor.py`
- `config_template.py` → `config.py`
- `README_template.md` → `README.md`

### 3. 修改代码

1. **修改提取器** (`extractor.py`)：

   - 更新 `algorithm_type` 和 `algorithm_name`
   - 设计算法特定的提示词
   - 实现响应解析和参数验证逻辑

2. **修改处理器** (`processor.py`)：

   - 更新 `algorithm_type` 和 `algorithm_name`
   - 实现数据转换和清洗逻辑
   - 实现数据验证逻辑

3. **修改配置** (`config.py`)：

   - 更新算法信息和参数定义
   - 添加使用示例

4. **更新文档** (`README.md`)：
   - 完善算法说明和使用指南

### 4. 创建测试用例

在 `tests/` 目录下创建测试文件：

- `test_extractor.py`
- `test_processor.py`

### 5. 注册算法

在 `algorithm/base/registry.py` 中添加：

```python
from algorithm.your_algorithm_name.extractor import YourAlgorithmExtractor
from algorithm.your_algorithm_name.processor import YourAlgorithmProcessor
algorithm_registry.register_algorithm(YourAlgorithmExtractor(), YourAlgorithmProcessor())
```

## 开发规范

### 提示词设计规范

- 必须要求 LLM 使用数据库中实际存在的列名
- 提供完整的数据库 schema 信息
- 明确标记特殊类型的列（如数值型、分类型）
- 严格定义 JSON 输出格式
- 包含具体的使用示例

### 数据处理规范

- 使用 `_simple_data_fill` 方法进行数据填充
- 实现算法特定的数据清洗逻辑
- 严格验证输入数据的完整性和质量
- 提供详细的错误日志

### 测试规范

- 测试正常的参数提取流程
- 测试异常情况的处理
- 测试数据转换的正确性
- 测试数据验证的严格性

## 注意事项

1. 确保提取器和处理器的 `algorithm_type` 和 `algorithm_name` 完全一致
2. 提示词中要求 LLM 使用数据库中实际存在的列名
3. 数据处理时要进行适当的类型转换和清洗
4. 验证逻辑要严格检查数据质量和参数有效性
5. 添加充分的日志记录，便于调试

## 文件结构

```
algorithm/your_algorithm_name/
├── __init__.py          # 模块初始化
├── extractor.py         # 参数提取器
├── processor.py         # 数据处理器
├── config.py           # 算法配置
├── tests/              # 测试用例
│   ├── __init__.py
│   ├── test_extractor.py
│   └── test_processor.py
└── README.md           # 算法说明文档
```

## 测试

运行测试用例：

```bash
python -m pytest algorithm/your_algorithm_name/tests/
```

## 贡献

开发完成后，请：

1. 确保所有测试通过
2. 更新相关文档
3. 提交代码审查
