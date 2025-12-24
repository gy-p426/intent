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
