"""
Univariate Forecast Algorithm Configuration

单变量预测算法配置信息
"""

UNIVARIATE_FORECAST_CONFIG = {
    "name": "单变量时间序列预测",
    "description": "基于历史时间序列数据进行未来值预测，支持ARIMA和Prophet算法自动选择",
    "algorithm_type": "predict",
    "data_format": "time_series",
    "required_parameters": [
        {
            "name": "timestamp_column",
            "type": "string",
            "description": "时间戳列名，用于标识时间序列的时间点"
        },
        {
            "name": "value_column",
            "type": "string",
            "description": "数值列名，用于预测的目标数值"
        }
    ],
    "optional_parameters": [
        {
            "name": "forecast_horizon",
            "type": "integer",
            "description": "预测步数，即预测未来多少个时间点",
            "default": 24,
            "min_value": 1,
            "max_value": 365
        },
        {
            "name": "model_type",
            "type": "string",
            "description": "预测模型类型：auto（自动选择）、arima、prophet",
            "default": "auto",
            "options": ["auto", "arima", "prophet"]
        },
        {
            "name": "include_confidence",
            "type": "boolean",
            "description": "是否包含置信区间",
            "default": True
        },
        {
            "name": "confidence_level",
            "type": "float",
            "description": "置信区间水平",
            "default": 0.95,
            "min_value": 0.5,
            "max_value": 0.99
        }
    ],
    "data_requirements": {
        "min_rows": 10,
        "min_features": 1,
        "numeric_features_required": True,
        "time_column_required": True
    },
    "examples": [
        "预测未来24小时的销售额",
        "预测下周的用户访问量",
        "预测未来30天的库存需求",
        "预测明天的温度变化",
        "预测下个月的收入"
    ],
    "preprocessing_options": {
        "handle_missing": True,
        "interpolate_method": "linear",
        "remove_outliers": False,
        "normalize_data": False
    }
}

# ============================================================================
# 单变量预测算法响应参数说明
# ============================================================================
#
# 响应类型说明：
# 单变量预测算法根据执行结果返回不同的响应结构，共有2种可能的响应：
#
# ┌─────────────────────────────────────────────────────────────────────────┐
# │ 响应类型          │ 触发条件                                            │
# ├─────────────────────────────────────────────────────────────────────────┤
# │ success_response  │ 预测执行成功                                        │
# │                   │ success = true                                      │
# ├─────────────────────────────────────────────────────────────────────────┤
# │ error_response    │ 预测执行失败，可能原因：                             │
# │                   │ - 数据点不足 (< 10个)                               │
# │                   │ - 数据格式错误                                       │
# │                   │ - 模型训练失败                                       │
# │                   │ success = false                                     │
# └─────────────────────────────────────────────────────────────────────────┘
#
# 模型自动选择逻辑 (model_type = "auto"):
# - 数据点 < 50 → 选择 ARIMA (小数据量更稳定)
# - 数据有明显季节性 → 选择 Prophet (更好处理季节性)
# - 数据有明显趋势 → 选择 Prophet (更好处理趋势变化)
# - 其他情况 → 选择 ARIMA
#
# 置信区间说明:
# - 当 include_confidence = true 时，返回 confidence_lower 和 confidence_upper
# - 当 include_confidence = false 时，不返回置信区间字段
#
# ============================================================================

UNIVARIATE_FORECAST_RESPONSE = {
    # ========================================================================
    # 响应1: 成功响应
    # 触发条件: 预测执行成功
    # ========================================================================
    "success_response": {
        "success": "boolean - 固定为 true",
        "results": {
            "forecast": ["float - 预测值数组，长度等于forecast_horizon"],
            "timestamps": ["string - 预测时间点数组，格式: 'YYYY-MM-DD HH:MM'"],
            "confidence_lower": ["float - 置信区间下界数组 (当include_confidence=true时返回)"],
            "confidence_upper": ["float - 置信区间上界数组 (当include_confidence=true时返回)"],
            "training_data_points": "integer - 训练数据点数",
            "forecast_horizon": "integer - 预测步数",
            "training_date_range": {
                "start": "string - 训练数据起始时间，格式: 'YYYY-MM-DD HH:MM:SS'",
                "end": "string - 训练数据结束时间，格式: 'YYYY-MM-DD HH:MM:SS'"
            }
        },
        "model_used": "string - 使用的模型: 'prophet' 或 'arima'",
        "data_analysis": {
            "data_points": "integer - 数据点总数",
            "mean": "float - 数据均值",
            "std": "float - 数据标准差",
            "min": "float - 数据最小值",
            "max": "float - 数据最大值",
            "has_seasonality": "boolean - 是否存在季节性",
            "trend_direction": "string - 趋势方向: increasing/decreasing/stable",
            "missing_ratio": "float - 缺失值比例 (0-1)"
        },
        "forecast_horizon": "integer - 预测步数"
    },
    
    # ========================================================================
    # 响应2: 失败响应
    # 触发条件: 预测执行失败
    # 常见错误:
    #   - "数据点不足，至少需要10个数据点"
    #   - "数据格式错误: timestamp列无法解析"
    #   - "模型训练失败: ..."
    # ========================================================================
    "error_response": {
        "success": "boolean - 固定为 false",
        "message": "string - 错误描述信息",
        "model_used": "string - 尝试使用的模型 (可能为null)",
        "error_details": {
            "error": "string - 详细错误信息",
            "traceback": "string - 错误堆栈信息（调试模式）"
        }
    }
}
