# DTW 动态时间规整算法

## 算法简介

DTW（动态时间规整）是一种用于测量两个时间序列之间相似度的算法，通过动态规划找到两个序列的最优对齐路径。
适用场景：时间序列分析、语音识别、手势识别、传感器数据匹配、金融时间序列对比等
主要特点：（1）能够处理长度不同的时间序列（2）对时间轴上的非线性扭曲具有鲁棒性（3）相比欧氏距离更适合衡量时间序列的相似性.

## 参数说明

### 必需参数

- **time_column**:时间列名：用于数据排序
- **time_series1**: 第一个时间序列数据所在的列名，该列应为数值型数据
- **time_series2**: 第二个时间序列数据所在的列名，该列应为数值型数据

### 可选参数

- **window_size**: 规整窗口大小，用于限制路径搜索范围以提高计算效率，默认值：None（表示不限制窗口）
- **distance_metric**: 距离度量方式，支持 "euclidean"（欧氏距离）、"manhattan"（曼哈顿距离）等，默认值："euclidean"
- **normalize**:是否对序列进行归一化处理（缩放到 0-1 范围），默认值："True"
- **step_pattern**:可选值"symmetric1"：标准对称模式，"symmetric2"：改进对称模式（推荐），"asymmetric"：非对称模式。默认值："symmetric2"

## 数据要求

1.最小数据量：每个序列至少需要 2 个数据点 2.数据类型：time_series1 和 time_series2 必须是数值型 3.列的唯一性：time_series1 和 time_series2 不能是同一列 4.数据完整性：缺失值会被自动跳过，但建议预先处理

## 使用示例

### 示例 1

```
用户问题: "分析过去一周温度和湿度的变化趋势相似度"
预期输出:
{
  "parameter_mapping": {
    "time_column": "record_time",
    "time_series1": "temperature",
    "time_series2": "humidity",
    "window_size": null,
    "distance_metric": "euclidean",
    "normalize": true,
    "step_pattern": "symmetric2"
  },
  "required_columns": ["record_time", "temperature", "humidity"],
  "normalized_query": "使用DTW算法分析温度和湿度两列数值序列的相似度"
}
```

### 示例 2

```
用户问题："对比 11 月份和 12 月份实际销量的匹配程度"
预期输出:
{
"parameter_mapping": {
"time_column": "sale_date",
"time_series1": "11_sales",
"time_series2": "12_sales",
"window_size": 5,
"distance_metric": "euclidean",
"normalize": false,
"step_pattern": "symmetric2"
},
"required_columns": ["sale_date", "11_sales", "12_sales"],
"normalized_query": "使用 DTW 算法分析 11 月和 12 月实际销量的相似度"
}
```

## 开发指南

### 1. 复制模板

```bash
cp -r algorithm/template algorithm/dtw
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
