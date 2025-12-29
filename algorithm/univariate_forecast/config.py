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

# 响应参数说明
UNIVARIATE_FORECAST_RESPONSE = {
    # 成功响应
    "success_response": {
        "success": "boolean - 固定为 true",
        "results": {
            "forecast": ["float - 预测值数组"],
            "timestamps": ["string - 预测时间点数组"],
            "confidence_lower": ["float - 置信区间下界数组"],
            "confidence_upper": ["float - 置信区间上界数组"],
            "training_data_points": "integer - 训练数据点数",
            "forecast_horizon": "integer - 预测步数",
            "training_date_range": {
                "start": "string - 训练数据起始时间",
                "end": "string - 训练数据结束时间"
            }
        },
        "model_used": "string - 使用的模型: 'prophet' 或 'arima'",
        "data_analysis": {
            "data_points": "integer",
            "mean": "float",
            "std": "float",
            "min": "float",
            "max": "float",
            "has_seasonality": "boolean",
            "trend_direction": "string - increasing/decreasing/stable",
            "missing_ratio": "float"
        },
        "forecast_horizon": "integer - 预测步数"
    },
    
    # 失败响应
    "error_response": {
        "success": "boolean - 固定为 false",
        "message": "string - 错误描述信息",
        "model_used": "string - 尝试使用的模型 (可能为null)",
        "error_details": {
            "error": "string - 详细错误信息"
        }
    }
}
