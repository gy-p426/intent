# 单变量时间序列预测算法

## 算法简介

单变量时间序列预测算法基于历史时间序列数据预测未来值，支持自动模型选择，可根据数据特征自动选择最优的预测模型。

## 架构说明

本模块通过 `AlgorithmExecutor` 调用远程 `forecast_service` 微服务执行预测。

```
主项目                                  远程服务
┌───────────────────────────┐          ┌─────────────────────┐
│ UnivariateForecastProcessor │  HTTP   │   forecast_service   │
│   └─ AlgorithmExecutor      ├────────►│   (192.168.x.x:8100) │
└───────────────────────────┘          └─────────────────────┘
```

**配置远程服务地址**：在 `.env` 文件中设置：
```
FORECAST_SERVICE_URL=http://192.168.5.106:8100
```

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

## 输出结果

详细的返回参数说明请参考 [趋势分析与预测接口文档](../趋势分析与预测接口文档.md)。

### 🆕 大模型智能分析

系统集成了大模型（LLM）自动分析功能，会将算法原始结果转换为用户友好的自然语言分析报告。

**响应结构**：
```json
{
  "readable_result": {
    "llm_analysis": "预测分析完成，基于168条历史数据，使用Prophet模型预测了未来24小时的数据。预测结果显示整体呈上升趋势，建议关注...",
    "technical_details": {
      "summary": "算法执行完成",
      "status": "success",
      "metrics": {
        "model_used": "prophet",
        "forecast_periods": 24
      }
    },
    "analysis_source": "llm_enhanced"
  }
}
```

**analysis_source 取值**：
- `llm_enhanced`: 大模型增强分析
- `fallback`: 降级处理（模板生成）

### 预测结果输出（v5.0 统一格式）

```json
{
  "解释": "【单变量预测分析结果】\n\n📌 关键发现：\n1. 系统自动选择了 Prophet（适合有季节性的数据）模型进行预测\n2. 预测了未来 24 个时间点的数据\n3. 预测期内整体呈上升趋势，变化幅度约 5.2%\n4. 数据存在周期性规律，预测已考虑这一特征\n\n💡 分析说明：\n我们使用 Prophet 对您的数据进行了分析和预测...\n\n📋 建议：\n• 预测值仅供参考，建议结合实际业务情况进行决策\n• 数据有周期性，建议关注周期性波动对业务的影响",
  "算法结果": {
    "是否成功": true,
    "预测结果": {
      "预测值": [110.5, 112.3, 115.0, ...],
      "时间点": ["2024-01-01 00:00", "2024-01-01 01:00", ...],
      "置信下限": [105.2, 107.1, 109.5, ...],
      "置信上限": [115.8, 117.5, 120.5, ...],
      "训练数据点数": 168,
      "预测步数": 24
    },
    "使用模型": "prophet",
    "数据分析": {
      "数据点数": 168,
      "均值": 108.5,
      "标准差": 12.3,
      "是否有季节性": true,
      "趋势方向": "increasing"
    },
    "预测步数": 24
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
├── config.py            # 算法配置定义（UNIVARIATE_FORECAST_CONFIG, UNIVARIATE_FORECAST_RESPONSE）
├── extractor.py         # 参数提取器（UnivariateForecastExtractor）
├── processor.py         # 数据处理器（UnivariateForecastProcessor）
└── README.md            # 本文档
```

## 相关文档

- [趋势分析与预测接口文档](../趋势分析与预测接口文档.md) - 完整的返回参数说明和前端集成指南
- [算法接入指南](../../算法接入改.md) - 新算法接入说明

## 核心组件

### UnivariateForecastExtractor (extractor.py)
参数提取器，负责从用户自然语言查询中提取单变量预测所需的参数。

### UnivariateForecastProcessor (processor.py)
数据处理器，负责：
1. 将SQL查询结果转换为预测所需格式
2. 数据清洗和预处理
3. 验证算法输入
4. 通过 `AlgorithmExecutor` 调用远程 `forecast_service` 执行预测

## 远程服务依赖

本模块通过 HTTP 调用远程 `forecast_service` 微服务：

- **服务地址配置**：`infrastructure/config.py` 中的 `forecast_service_url`
- **API 端点**：`POST /api/v1/forecast/univariate`
- **执行器**：`algorithm/executor/algorithm_executor.py` 中的 `execute_univariate_forecast()`

## 注意事项

1. Prophet模型首次运行可能需要编译Stan模型，耗时较长
2. ARIMA模型对数据平稳性有要求，会自动进行差分处理
3. 预测步数过大可能导致预测精度下降
4. 建议预测步数不超过历史数据长度的1/3
5. 数据中的缺失值会自动进行线性插值处理
6. **确保远程 `forecast_service` 服务已启动**

## 测试

运行测试用例：
```bash
# 运行单变量预测结构测试
python -m pytest tests/algorithm/test_univariate_forecast.py -v
```

## 开发指南

### 修改提示词
在 `extractor.py` 的 `build_extraction_prompt` 方法中修改系统提示词和用户提示词。

### 修改数据处理逻辑
在 `processor.py` 中修改数据转换和验证逻辑。

### 修改远程调用逻辑
在 `algorithm/executor/algorithm_executor.py` 的 `execute_univariate_forecast()` 方法中修改。
