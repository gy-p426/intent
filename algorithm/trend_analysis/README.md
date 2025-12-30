# 趋势分析算法

## 算法简介

趋势分析算法用于分析时间序列数据的趋势特征，包括两种主要功能：

1. **趋势分解（Decomposition）**：将时间序列分解为趋势、季节性和残差三个组成部分
2. **趋势检测（Detection）**：检测时间序列是否存在显著的上升或下降趋势

## 架构说明

本模块通过 `AlgorithmExecutor` 调用远程 `forecast_service` 微服务执行趋势分析。

```
主项目                              远程服务
┌─────────────────────┐            ┌─────────────────────┐
│ TrendAnalysisProcessor │  HTTP   │   forecast_service   │
│   └─ AlgorithmExecutor ├────────►│   (192.168.x.x:8100) │
└─────────────────────┘            └─────────────────────┘
```

**配置远程服务地址**：在 `.env` 文件中设置：
```
FORECAST_SERVICE_URL=http://192.168.5.106:8100
```

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

详细的返回参数说明请参考 [趋势分析与预测接口文档](../趋势分析与预测接口文档.md)。

### 🆕 大模型智能分析

系统集成了大模型（LLM）自动分析功能，会将算法原始结果转换为用户友好的自然语言分析报告。

**响应结构**：
```json
{
  "readable_result": {
    "llm_analysis": "根据分析结果，您的数据呈现明显的上升趋势，平均每周增长约3%...",
    "technical_details": {
      "summary": "算法执行完成",
      "status": "success",
      "metrics": {
        "trend_direction": "increasing",
        "slope": 0.0234,
        "r_squared": 0.85
      }
    },
    "analysis_source": "llm_enhanced"
  }
}
```

**analysis_source 取值**：
- `llm_enhanced`: 大模型增强分析
- `fallback`: 降级处理（模板生成）

### 趋势分解输出
```json
{
  "是否成功": true,
  "分解结果": {
    "趋势成分": [{"时间点": "2024-01-01", "值": 1200}, ...],
    "季节成分": [{"时间点": "2024-01-01", "值": 34.56}, ...],
    "残差成分": [{"时间点": "2024-01-01", "值": 0.0}, ...]
  },
  "分析类型": "decomposition",
  "使用算法": "stl",
  "使用周期": 7,
  "数据点数": 100,
  "通俗摘要": {
    "标题": "📊 时间序列趋势分解分析",
    "关键发现": ["数据呈现明显的上升趋势", "存在周期为7的季节性波动"],
    "详细解释": "通过STL分解算法，将您的数据分解为趋势、季节性和残差三个部分...",
    "建议": ["关注趋势变化", "考虑季节性因素进行规划"]
  }
}
```

### 趋势检测输出
```json
{
  "是否成功": true,
  "检测结果": {
    "趋势方向": "increasing",
    "斜率": 0.0234,
    "p值": 0.0012,
    "统计显著": true
  },
  "分析类型": "detection",
  "使用方法": "mann_kendall",
  "数据点数": 100,
  "通俗摘要": {
    "标题": "📈 趋势检测分析结果",
    "关键发现": ["数据存在显著上升趋势", "统计检验结果高度可信"],
    "详细解释": "使用Mann-Kendall检验方法分析，p值为0.0012，远小于0.05...",
    "建议": ["趋势明显，可据此进行预测", "建议持续监控趋势变化"]
  }
}
```

## 文件结构

```
algorithm/trend_analysis/
├── __init__.py          # 模块初始化，导出主要类
├── config.py            # 算法配置定义（TREND_ANALYSIS_CONFIG, TREND_ANALYSIS_RESPONSE）
├── extractor.py         # 参数提取器（TrendAnalysisExtractor）
├── processor.py         # 数据处理器（TrendAnalysisProcessor）
└── README.md            # 本文档
```

## 相关文档

- [趋势分析与预测接口文档](../趋势分析与预测接口文档.md) - 完整的返回参数说明和前端集成指南
- [算法接入指南](../../算法接入改.md) - 新算法接入说明

## 核心组件

### TrendAnalysisExtractor (extractor.py)
参数提取器，负责从用户自然语言查询中提取趋势分析所需的参数。

### TrendAnalysisProcessor (processor.py)
数据处理器，负责：
1. 将SQL查询结果转换为时间序列格式
2. 数据清洗和预处理
3. 验证算法输入
4. 通过 `AlgorithmExecutor` 调用远程 `forecast_service` 执行分析

## 远程服务依赖

本模块通过 HTTP 调用远程 `forecast_service` 微服务：

- **服务地址配置**：`infrastructure/config.py` 中的 `forecast_service_url`
- **API 端点**：
  - 趋势分解：`POST /api/v1/trend/decomposition`
  - 趋势检测：`POST /api/v1/trend/detection`
- **执行器**：`algorithm/executor/algorithm_executor.py` 中的 `execute_trend_analysis()`

## 注意事项

1. 趋势分解对数据长度有要求，需要至少2个完整周期
2. Mann-Kendall检验对异常值更鲁棒，适合非正态分布数据
3. 线性回归检验假设线性趋势，适合正态分布数据
4. 自动周期检测可能不准确，建议根据业务知识指定周期
5. 乘法模型要求数据全为正值
6. **确保远程 `forecast_service` 服务已启动**

## 测试

运行测试用例：
```bash
# 运行趋势分析结构测试
python -m pytest tests/algorithm/test_trend_analysis.py -v
```

## 开发指南

### 修改提示词
在 `extractor.py` 的 `build_extraction_prompt` 方法中修改系统提示词和用户提示词。

### 修改数据处理逻辑
在 `processor.py` 中修改数据转换和验证逻辑。

### 修改远程调用逻辑
在 `algorithm/executor/algorithm_executor.py` 的 `execute_trend_analysis()` 方法中修改。
