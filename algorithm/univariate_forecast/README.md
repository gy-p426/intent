# 单变量时间序列预测算法

## 算法简介

单变量时间序列预测算法基于历史时间序列数据预测未来值，支持自动模型选择，可根据数据特征自动选择最优的预测模型。

## 支持的算法

- **ARIMA**: 自回归积分滑动平均模型，适合平稳或可差分平稳的时间序列
- **Prophet**: Facebook开发的时间序列预测模型，适合有明显季节性和趋势的数据

## 参数说明

### 必需参数

- **timestamp_column**: 时间戳列名，用于标识时间序列的时间点
- **value_column**: 数值列名，作为预测的目标变量

### 可选参数

- **forecast_horizon**: 预测步数，默认24，范围1-365
- **model_type**: 预测模型类型，`auto`（自动选择）、`arima` 或 `prophet`，默认 `auto`
- **include_confidence**: 是否包含置信区间，默认 `true`
- **confidence_level**: 置信区间水平，默认 0.95

## 数据要求

1. 至少需要10个数据点
2. 数值数据比例应大于80%
3. 需要包含时间列和数值列
4. 时间序列应按时间顺序排列

## 使用示例

### 预测未来24小时
```
用户问题: "预测未来24小时的销售额"
预期输出:
{
  "parameter_mapping": {
    "timestamp_column": "时间",
    "value_column": "销售额",
    "forecast_horizon": 24,
    "model_type": "auto",
    "include_confidence": true
  }
}
```

### 预测下周数据
```
用户问题: "预测下周的用户访问量"
预期输出:
{
  "parameter_mapping": {
    "timestamp_column": "日期",
    "value_column": "访问量",
    "forecast_horizon": 7,
    "model_type": "auto",
    "include_confidence": true
  }
}
```

### 使用特定模型
```
用户问题: "使用Prophet模型预测未来30天的温度"
预期输出:
{
  "parameter_mapping": {
    "timestamp_column": "日期",
    "value_column": "温度",
    "forecast_horizon": 30,
    "model_type": "prophet",
    "include_confidence": true
  }
}
```

## 输出结果

```json
{
  "success": true,
  "results": {
    "forecast": [110.5, 112.3, 115.0, ...],
    "timestamps": ["2024-01-01 00:00", "2024-01-01 01:00", ...],
    "confidence_lower": [105.2, 107.1, 109.5, ...],
    "confidence_upper": [115.8, 117.5, 120.5, ...],
    "training_data_points": 168,
    "forecast_horizon": 24
  },
  "model_used": "arima",
  "data_analysis": {
    "data_points": 168,
    "mean": 108.5,
    "std": 12.3,
    "has_seasonality": true,
    "trend_direction": "increasing"
  }
}
```

## 模型选择逻辑

自动模型选择（`model_type: auto`）基于以下规则：
1. 数据点少于50个时，优先使用ARIMA
2. 数据有明显季节性时，优先使用Prophet
3. 数据有明显趋势时，优先使用Prophet
4. 其他情况使用ARIMA

## 文件结构

```
algorithm/univariate_forecast/
├── __init__.py          # 模块初始化
├── extractor.py         # 参数提取器
├── processor.py         # 数据处理器
├── config.py            # 算法配置
└── README.md            # 本文档
```

## 依赖模块

本算法整合模块依赖 `forecast_modules/auto_univariate_forecast` 中的核心实现：
- `AutoUnivariatePredictor`: 自动单变量预测器
- `ARIMAModel`: ARIMA模型实现
- `ProphetModel`: Prophet模型实现

## 注意事项

1. Prophet模型首次运行可能需要编译Stan模型，耗时较长
2. ARIMA模型对数据平稳性有要求，会自动进行差分处理
3. 预测步数过大可能导致预测精度下降
4. 建议预测步数不超过历史数据长度的1/3
