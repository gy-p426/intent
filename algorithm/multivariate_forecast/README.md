# 多变量预测算法整合模块

## 概述

本模块将 `forecast_modules/multivariate_forecast` 中的多变量时间序列预测功能整合到算法服务框架中。

## 模块结构

```
algorithm/multivariate_forecast/
├── __init__.py          # 模块初始化，导出主要类
├── config.py            # 算法配置定义
├── extractor.py         # 参数提取器
├── processor.py         # 数据处理器
└── README.md            # 本文档
```

## 核心组件

### MultivariateForecastExtractor (extractor.py)

参数提取器，负责从用户自然语言查询中提取多变量预测所需的参数：

- `timestamp_column`: 时间列名
- `target_column`: 预测目标列名
- `feature_columns`: 特征列列表（可选）
- `forecast_horizon`: 预测步数（默认14）
- `algorithm`: 预测算法（lightgbm/xgboost/random_forest/linear_regression）
- `model_name`: 模型名称（可选，用于保存和复用）

### MultivariateForecastProcessor (processor.py)

数据处理器，负责：

1. 将SQL查询结果转换为算法输入格式
2. 数据清洗和预处理
3. 验证算法输入
4. 调用核心预测模块执行预测

## 支持的算法

| 算法 | 说明 | 适用场景 |
|------|------|----------|
| lightgbm | LightGBM梯度提升 | 数据量大、特征多 |
| xgboost | XGBoost梯度提升 | 数据量大、特征多 |
| random_forest | 随机森林 | 需要可解释性 |
| linear_regression | 线性回归 | 数据量小、快速训练 |

## 使用示例

### 自然语言查询示例

```
"使用lightgbm预测未来14天的销售额，基于温度、湿度等特征"
"预测下周的用户活跃度，使用随机森林算法"
"基于历史数据预测未来30天的能耗"
```

### 参数提取结果示例

```json
{
  "parameter_mapping": {
    "timestamp_column": "record_time",
    "target_column": "sales_amount",
    "feature_columns": ["temperature", "humidity", "promotion_flag"],
    "forecast_horizon": 14,
    "algorithm": "lightgbm",
    "model_name": "sales_predictor"
  },
  "required_columns": ["record_time", "sales_amount", "temperature", "humidity", "promotion_flag"],
  "normalized_query": "获取销售额及相关特征的历史数据用于多变量预测"
}
```

## 数据要求

1. 必须包含时间列（datetime类型）
2. 必须包含目标列（数值类型）
3. 特征列应为数值类型
4. 建议至少10条以上的历史数据
5. 数据应按时间排序

## 预测结果格式

```json
{
  "success": true,
  "results": {
    "timestamps": ["2024-01-15 00:00", "2024-01-16 00:00", ...],
    "forecast": [123.45, 126.78, ...],
    "horizon": 14
  },
  "model_used": "lightgbm",
  "model_id": "mv_abc12345",
  "metrics": {
    "rmse": 5.23,
    "mae": 3.45,
    "r2": 0.89
  }
}
```

## 依赖模块

- `forecast_modules.multivariate_forecast.core.predictor`: 核心预测实现
- `algorithm.base.base_extractor`: 基础提取器
- `algorithm.base.base_processor`: 基础处理器

## 注意事项

1. 首次使用需要训练模型，后续可通过 `model_id` 或 `model_name` 复用已训练模型
2. 预测步数建议不超过365天
3. 特征列如果不指定，将自动选择除时间列和目标列外的所有数值列
