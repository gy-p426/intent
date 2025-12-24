# 趋势分析算法

## 算法简介

趋势分析算法用于分析时间序列数据的趋势特征，包括两种主要功能：

1. **趋势分解（Decomposition）**：将时间序列分解为趋势、季节性和残差三个组成部分
2. **趋势检测（Detection）**：检测时间序列是否存在显著的上升或下降趋势

## 支持的算法

### 趋势分解算法
| 算法 | 说明 | 适用场景 |
|------|------|----------|
| STL分解 | Seasonal and Trend decomposition using Loess | 对异常值更鲁棒，推荐使用 |
| 经典分解 | Classical decomposition | 支持加法和乘法模型，计算简单 |

### 趋势检测算法
| 算法 | 说明 | 适用场景 |
|------|------|----------|
| Mann-Kendall检验 | 非参数检验方法 | 对数据分布无假设，适合非正态数据 |
| 线性回归检验 | 参数检验方法 | 假设线性趋势，适合正态分布数据 |

## 参数说明

### 必需参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| timestamp_column | string | 时间戳列名，用于标识时间序列的时间点 |
| value_column | string | 数值列名，用于趋势分析的目标数值 |

### 可选参数

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| analysis_type | string | decomposition | 分析类型：`decomposition`（趋势分解）或 `detection`（趋势检测） |
| period | integer | 自动检测 | 季节周期长度，如24（小时数据的日周期）、7（日数据的周周期） |
| decomposition_model | string | additive | 分解模型类型：`additive`（加法模型）或 `multiplicative`（乘法模型） |
| algorithm | string | auto | 分解算法：`auto`、`stl` 或 `classical` |
| detection_method | string | auto | 趋势检测方法：`auto`、`mann_kendall` 或 `linear_regression` |
| confidence_level | float | 0.95 | 置信水平，范围 0.5-0.99 |

## 数据要求

1. 至少需要 **10个** 数据点
2. 趋势分解需要至少 **2个完整周期** 的数据
3. 数值数据比例应大于 **80%**
4. 需要包含时间列和数值列
5. 数据应按时间顺序排列

## 使用示例

### 趋势分解
```
用户问题: "分析销售数据的趋势和季节性变化"
预期输出:
{
  "parameter_mapping": {
    "timestamp_column": "日期",
    "value_column": "销售额",
    "analysis_type": "decomposition",
    "period": 7,
    "decomposition_model": "additive",
    "algorithm": "auto"
  }
}
```

### 趋势检测
```
用户问题: "检测用户活跃度是否有上升趋势"
预期输出:
{
  "parameter_mapping": {
    "timestamp_column": "统计日期",
    "value_column": "活跃用户数",
    "analysis_type": "detection",
    "detection_method": "mann_kendall",
    "confidence_level": 0.95
  }
}
```

## 输出结果

详细的返回参数说明请参考 [算法返回参数规范文档](../API_RESPONSE_SPEC.md)。

### 趋势分解输出
```json
{
  "data_characteristics": {
    "mean": 1234.56,
    "std": 123.45,
    "trend_strength": 0.85,
    "seasonal_strength": 0.72
  },
  "decomposition": {
    "trend": [{"timestamp": "2024-01-01", "value": 1200}, ...],
    "seasonal": [{"timestamp": "2024-01-01", "value": 34.56}, ...],
    "residual": [{"timestamp": "2024-01-01", "value": 0.0}, ...]
  },
  "analysis_type": "decomposition",
  "algorithm_used": "stl",
  "period_used": 7,
  "data_points": 100
}
```

### 趋势检测输出
```json
{
  "data_characteristics": {
    "mean": 1234.56,
    "std": 123.45
  },
  "detection": {
    "trend_direction": "increasing",
    "sen_slope": 0.0234,
    "p_value": 0.0012,
    "statistical_significance": true,
    "interpretation": "检测到明显的上升趋势，趋势斜率: 0.0234"
  },
  "analysis_type": "detection",
  "method_used": "mann_kendall",
  "data_points": 100
}
```

## 文件结构

```
algorithm/trend_analysis/
├── __init__.py          # 模块初始化，导出主要类
├── config.py            # 算法配置定义
├── extractor.py         # 参数提取器（TrendAnalysisExtractor）
├── processor.py         # 数据处理器（TrendAnalysisProcessor）
└── README.md            # 本文档
```

## 核心组件

### TrendAnalysisExtractor (extractor.py)
参数提取器，负责从用户自然语言查询中提取趋势分析所需的参数。

### TrendAnalysisProcessor (processor.py)
数据处理器，负责：
1. 将SQL查询结果转换为时间序列格式
2. 数据清洗和预处理
3. 验证算法输入
4. 调用核心趋势分析模块执行分析

## 依赖模块

本算法整合模块依赖 `algorithm/forecast_core/trend_analysis` 中的核心实现：
- `TrendService`: 趋势分析核心服务类

## 注意事项

1. 趋势分解对数据长度有要求，需要至少2个完整周期
2. Mann-Kendall检验对异常值更鲁棒，适合非正态分布数据
3. 线性回归检验假设线性趋势，适合正态分布数据
4. 自动周期检测可能不准确，建议根据业务知识指定周期
5. 乘法模型要求数据全为正值

## 测试

运行测试用例：
```bash
# 运行趋势分析专项测试
python -m pytest tests/algorithm/test_trend_analysis.py -v

# 运行所有预测算法集成测试
python -m pytest tests/test_forecast_integration.py -k "trend" -v
```

## 开发指南

### 修改提示词
在 `extractor.py` 的 `build_extraction_prompt` 方法中修改系统提示词和用户提示词。

### 修改数据处理逻辑
在 `processor.py` 中修改数据转换和验证逻辑。

### 添加新的分析方法
1. 在 `config.py` 中添加新方法的配置
2. 在 `processor.py` 的 `execute_trend_analysis` 方法中添加新方法的调用逻辑
3. 更新本文档
