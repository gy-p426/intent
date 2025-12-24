# 趋势分析算法

## 算法简介

趋势分析算法用于分析时间序列数据的趋势特征，包括两种主要功能：

1. **趋势分解（Decomposition）**：将时间序列分解为趋势、季节性和残差三个组成部分
2. **趋势检测（Detection）**：检测时间序列是否存在显著的上升或下降趋势

## 支持的算法

### 趋势分解算法
- **STL分解**：Seasonal and Trend decomposition using Loess，对异常值更鲁棒
- **经典分解**：Classical decomposition，支持加法和乘法模型

### 趋势检测算法
- **Mann-Kendall检验**：非参数检验方法，对数据分布无假设
- **线性回归检验**：参数检验方法，假设线性趋势

## 参数说明

### 必需参数

- **timestamp_column**: 时间戳列名，用于标识时间序列的时间点
- **value_column**: 数值列名，用于趋势分析的目标数值

### 可选参数

- **analysis_type**: 分析类型，`decomposition`（趋势分解）或 `detection`（趋势检测），默认 `decomposition`
- **period**: 季节周期长度，如24（小时数据的日周期）、7（日数据的周周期），不指定则自动检测
- **decomposition_model**: 分解模型类型，`additive`（加法模型）或 `multiplicative`（乘法模型），默认 `additive`
- **algorithm**: 分解算法，`auto`、`stl` 或 `classical`，默认 `auto`
- **detection_method**: 趋势检测方法，`auto`、`mann_kendall` 或 `linear_regression`，默认 `auto`
- **confidence_level**: 置信水平，默认 0.95

## 数据要求

1. 至少需要10个数据点
2. 趋势分解需要至少2个完整周期的数据
3. 数值数据比例应大于80%
4. 需要包含时间列和数值列

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

### 趋势分解输出
```json
{
  "decomposition": {
    "trend": [{"timestamp": "...", "value": ...}, ...],
    "seasonal": [{"timestamp": "...", "value": ...}, ...],
    "residual": [{"timestamp": "...", "value": ...}, ...],
    "analysis_metrics": {
      "trend_strength": 0.85,
      "seasonal_strength": 0.72,
      "residual_variance": 123.45
    }
  },
  "algorithm_used": "stl",
  "period_used": 24
}
```

### 趋势检测输出
```json
{
  "detection": {
    "trend_direction": "increasing",
    "sen_slope": 0.0234,
    "p_value": 0.0012,
    "statistical_significance": true,
    "interpretation": "检测到明显的上升趋势，趋势斜率: 0.0234"
  },
  "method_used": "mann_kendall"
}
```

## 文件结构

```
algorithm/trend_analysis/
├── __init__.py          # 模块初始化
├── extractor.py         # 参数提取器
├── processor.py         # 数据处理器
├── config.py            # 算法配置
└── README.md            # 本文档
```

## 依赖模块

本算法整合模块依赖 `forecast_modules/trend_analysis` 中的核心实现：
- `TrendService`: 趋势分析核心服务类

## 注意事项

1. 趋势分解对数据长度有要求，需要至少2个完整周期
2. Mann-Kendall检验对异常值更鲁棒，适合非正态分布数据
3. 线性回归检验假设线性趋势，适合正态分布数据
4. 自动周期检测可能不准确，建议根据业务知识指定周期
