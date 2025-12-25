# 多变量时间序列预测算法

## 算法简介

多变量时间序列预测算法基于多个特征变量进行时间序列预测，通过利用目标变量与多个相关特征之间的关系来提高预测精度。支持多种机器学习算法，适合有多个影响因素的预测场景。

## 架构说明

本模块通过 `AlgorithmExecutor` 调用远程 `forecast_service` 微服务执行预测。

```
主项目                                    远程服务
┌─────────────────────────────┐          ┌─────────────────────┐
│ MultivariateForecastProcessor │  HTTP   │   forecast_service   │
│   └─ AlgorithmExecutor        ├────────►│   (192.168.x.x:8100) │
└─────────────────────────────┘          └─────────────────────┘
```

**配置远程服务地址**：在 `.env` 文件中设置：
```
FORECAST_SERVICE_URL=http://192.168.5.106:8100
```

## 支持的算法

| 算法 | 说明 | 适用场景 |
|------|------|----------|
| LightGBM | 轻量级梯度提升框架 | 数据量大、特征多，训练速度快 |
| XGBoost | 极端梯度提升 | 数据量大、特征多，精度高 |
| Random Forest | 随机森林 | 需要可解释性，防止过拟合 |
| Linear Regression | 线性回归 | 数据量小、快速训练，基准模型 |

## 参数说明

### 必需参数

| 参数名 | 类型 | 说明 |
|--------|------|------|
| timestamp_column | string | 时间戳列名，用于标识时间序列的时间点 |
| target_column | string | 目标列名，作为预测的目标变量 |

### 可选参数

| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| feature_columns | array | 自动选择 | 特征列名列表，不指定则自动选择所有数值列 |
| forecast_horizon | integer | 14 | 预测步数，范围 1-365 |
| algorithm | string | lightgbm | 预测算法：`lightgbm`、`xgboost`、`random_forest`、`linear_regression` |
| model_name | string | null | 模型名称，用于保存和复用模型 |
| use_model_id | string | null | 复用已有模型的ID |

## 数据要求

1. 必须包含时间列（datetime类型）
2. 必须包含目标列（数值类型）
3. 特征列应为数值类型
4. 至少需要 **10条** 以上的历史数据
5. 数据应按时间排序
6. 目标列和特征列的数值比例应大于 **70%**

## 使用示例

### 基于多特征预测销售额
```
用户问题: "使用lightgbm预测未来14天的销售额，基于温度、湿度等特征"
预期输出:
{
  "parameter_mapping": {
    "timestamp_column": "record_time",
    "target_column": "sales_amount",
    "feature_columns": ["temperature", "humidity", "promotion_flag"],
    "forecast_horizon": 14,
    "algorithm": "lightgbm"
  }
}
```

### 使用随机森林预测
```
用户问题: "预测下周的用户活跃度，使用随机森林算法"
预期输出:
{
  "parameter_mapping": {
    "timestamp_column": "date",
    "target_column": "active_users",
    "forecast_horizon": 7,
    "algorithm": "random_forest"
  }
}
```

## 输出结果

详细的返回参数说明请参考 [算法返回参数规范文档](../趋势分析相关算法返回.md)。

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
  },
  "reused_model": false
}
```

## 算法选择建议

| 场景 | 推荐算法 | 原因 |
|------|----------|------|
| 大数据量（>10000行） | LightGBM | 训练速度快，内存占用低 |
| 追求最高精度 | XGBoost | 通常能获得最佳预测效果 |
| 需要可解释性 | Random Forest | 可以获取特征重要性 |
| 快速原型验证 | Linear Regression | 训练最快，作为基准 |
| 特征较少（<10个） | 任意 | 差异不大 |

## 文件结构

```
algorithm/multivariate_forecast/
├── __init__.py          # 模块初始化，导出主要类
├── config.py            # 算法配置定义（MULTIVARIATE_FORECAST_CONFIG, MULTIVARIATE_FORECAST_RESPONSE）
├── extractor.py         # 参数提取器（MultivariateForecastExtractor）
├── processor.py         # 数据处理器（MultivariateForecastProcessor）
└── README.md            # 本文档
```

## 核心组件

### MultivariateForecastExtractor (extractor.py)
参数提取器，负责从用户自然语言查询中提取多变量预测所需的参数：
- 时间列、目标列、特征列的识别
- 预测步数的提取
- 算法类型的识别

### MultivariateForecastProcessor (processor.py)
数据处理器，负责：
1. 将SQL查询结果转换为算法输入格式
2. 时间序列数据清洗和预处理
3. 特征列数值转换
4. 验证算法输入
5. 通过 `AlgorithmExecutor` 调用远程 `forecast_service` 执行预测

## 远程服务依赖

本模块通过 HTTP 调用远程 `forecast_service` 微服务：

- **服务地址配置**：`infrastructure/config.py` 中的 `forecast_service_url`
- **API 端点**：`POST /api/v1/forecast/multivariate`
- **执行器**：`algorithm/executor/algorithm_executor.py` 中的 `execute_multivariate_forecast()`

## 注意事项

1. 首次使用需要训练模型，后续可通过 `model_id` 或 `model_name` 复用已训练模型
2. 预测步数建议不超过365天
3. 特征列如果不指定，将自动选择除时间列和目标列外的所有数值列
4. LightGBM和XGBoost需要安装对应的Python包
5. 特征列中的缺失值会影响预测精度，建议提前处理
6. 数据量越大，机器学习模型的效果越好
7. **确保远程 `forecast_service` 服务已启动**

## 测试

运行测试用例：
```bash
# 运行多变量预测结构测试
python -m pytest tests/algorithm/test_multivariate_forecast.py -v
```

## 开发指南

### 修改提示词
在 `extractor.py` 的 `build_extraction_prompt` 方法中修改系统提示词和用户提示词。

### 修改数据处理逻辑
在 `processor.py` 中修改数据转换和验证逻辑。

### 修改远程调用逻辑
在 `algorithm/executor/algorithm_executor.py` 的 `execute_multivariate_forecast()` 方法中修改。
