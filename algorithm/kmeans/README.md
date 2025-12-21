# K-Means聚类算法

## 算法简介

K-Means是一种基于距离的聚类算法，将数据点分成K个簇，使得每个簇内的数据点尽可能相似，不同簇之间的数据点尽可能不同。

## 参数说明

### 必需参数

- **id_column**: 用于标识每个数据点的ID列
- **feature_columns**: 用于聚类计算的数值型特征列列表

### 可选参数

- **k_value**: 聚类数量，如果不指定则使用肘部法则自动确定

## 数据要求

1. 至少需要2行数据
2. 至少需要1个数值型特征列
3. 特征列的数值比例应大于70%
4. K值不能大于等于数据行数

## 使用示例

### 员工绩效聚类
```
用户问题: "对员工绩效数据进行聚类分析"
预期输出:
{
  "parameter_mapping": {
    "id_column": "员工ID",
    "feature_columns": ["工作效率评分", "工作质量评分", "工作态度评分"],
    "k_value": null
  }
}
```

### 客户分群
```
用户问题: "将客户按消费行为分成3类"
预期输出:
{
  "parameter_mapping": {
    "id_column": "客户ID",
    "feature_columns": ["消费金额", "消费频次", "客单价"],
    "k_value": 3
  }
}
```

## 开发指南

### 修改提示词
在 `extractor.py` 的 `build_extraction_prompt` 方法中修改系统提示词和用户提示词。

### 修改数据处理逻辑
在 `processor.py` 中修改数据转换和验证逻辑。

### 添加测试用例
在 `tests/` 目录下添加相应的测试用例。

## 注意事项

1. 确保提示词中要求LLM使用数据库中实际存在的列名
2. 数据处理时要进行适当的数值化和清洗
3. 验证逻辑要严格检查数据质量和参数有效性

## 文件结构

```
algorithm/kmeans/
├── __init__.py          # 模块初始化
├── extractor.py         # 参数提取器
├── processor.py         # 数据处理器
├── config.py           # 算法配置
├── tests/              # 测试用例
│   ├── __init__.py
│   ├── test_extractor.py
│   └── test_processor.py
└── README.md           # 本文档
```

## 测试

运行测试用例：
```bash
python -m pytest algorithm/kmeans/tests/
```

## 贡献

如需修改K-Means算法逻辑，请：
1. 修改相应的代码文件
2. 更新测试用例
3. 更新本文档
4. 提交代码审查