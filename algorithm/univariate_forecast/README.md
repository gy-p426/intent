# 单变量时间序列预测算法

## 算法简介

单变量时间序列预测算法基于历史时间序列数据预测未来值，支持自动模型选择，可根据数据特征自动选择最优的预测模型。

## 支持的算法

| 算法 | 说明 | 适用场景 |
|------|------|----------|
| ARIMA | 自回归积分滑动平均模型 | 平稳或可差分平稳的时间序列，数据量较小 |
| Prophet | Facebook开发的时间序列预测模型 | 有明显季节性和趋势的数据，节假日效应 |

## 参数说明

### 必需参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| timestamp_column | string | 时间戳列名，用于标识时间序列的时间点 |
| value_column | string | 数值列名，作为预测的目标变量 |

### 可选参数

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| forecast_horizon | integer | 24 | 预测步数，范围 1-365 |
| model_type | string | auto | 预测模型类型：`auto`（自动选择）、`arima`、`prophet` |
| include_confidence | boolean | true | 是否包含置信区间 |
| confidence_level | float | 0.95 | 置信区间水平，范围 0.5-0.99 |

## 数据要求

1. 至少需要 **10个** 数据点
2. 数值数据比例应大于 **80%**
3. 需要包含时间列和数值列
4. 时间序列应按时间顺序排列
5. 建议预测步数不超过历史数据长度的 **1/3**

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

详细的返回参数说明请参考 [算法返回参数规范文档](../API_RESPONSE_SPEC.md)。

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

| 条件 | 选择模型 |
|------|----------|
| 数据点少于50个 | ARIMA |
| 数据有明显季节性 | Prophet |
| 数据有明显趋势 | Prophet |
| 其他情况 | ARIMA |

## 文件结构

```
algorithm/univariate_forecast/
├── __init__.py          # 模块初始化，导出主要类
├── config.py            # 算法配置定义
├── extractor.py         # 参数提取器（UnivariateForecastExtractor）
├── processor.py         # 数据处理器（UnivariateForecastProcessor）
└── README.md            # 本文档
```

## 核心组件

### UnivariateForecastExtractor (extractor.py)
参数提取器，负责从用户自然语言查询中提取单变量预测所需的参数。

### UnivariateForecastProcessor (processor.py)
数据处理器，负责：
1. 将SQL查询结果转换为预测所需格式
2. 数据清洗和预处理
3. 验证算法输入
4. 调用核心预测模块执行预测

## 依赖模块

本算法整合模块依赖 `algorithm/forecast_core/auto_univariate_forecast` 中的核心实现：
- `AutoUnivariatePredictor`: 自动单变量预测器
- `ARIMAModel`: ARIMA模型实现
- `ProphetModel`: Prophet模型实现

## 注意事项

1. Prophet模型首次运行可能需要编译Stan模型，耗时较长
2. ARIMA模型对数据平稳性有要求，会自动进行差分处理
3. 预测步数过大可能导致预测精度下降
4. 建议预测步数不超过历史数据长度的1/3
5. 数据中的缺失值会自动进行线性插值处理

## 测试

运行测试用例：
```bash
# 运行单变量预测专项测试
python -m pytest tests/algorithm/test_univariate_forecast.py -v

# 运行所有预测算法集成测试
python -m pytest tests/test_forecast_integration.py -k "univariate" -v
```

## 开发指南

### 修改提示词
在 `extractor.py` 的 `build_extraction_prompt` 方法中修改系统提示词和用户提示词。

### 修改数据处理逻辑
在 `processor.py` 中修改数据转换和验证逻辑。

### 添加新的预测模型
1. 在 `config.py` 中添加新模型的配置
2. 在 `processor.py` 的 `execute_univariate_forecast` 方法中添加新模型的调用逻辑
3. 更新本文档
