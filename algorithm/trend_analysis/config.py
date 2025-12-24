"""
Trend Analysis Algorithm Configuration

趋势分析算法配置信息
"""

TREND_ANALYSIS_CONFIG = {
    "name": "趋势分析",
    "description": "时间序列趋势分解和趋势检测分析，支持STL分解、经典分解、Mann-Kendall检验和线性回归检验",
    "algorithm_type": "trend",
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
            "description": "数值列名，用于趋势分析的目标数值"
        }
    ],
    "optional_parameters": [
        {
            "name": "analysis_type",
            "type": "string",
            "description": "分析类型：decomposition（趋势分解）或 detection（趋势检测）",
            "default": "decomposition",
            "options": ["decomposition", "detection"]
        },
        {
            "name": "period",
            "type": "integer",
            "description": "季节周期长度，如24（小时数据的日周期）、7（日数据的周周期）",
            "default": None,
            "min_value": 2
        },
        {
            "name": "decomposition_model",
            "type": "string",
            "description": "分解模型类型：additive（加法模型）或 multiplicative（乘法模型）",
            "default": "additive",
            "options": ["additive", "multiplicative"]
        },
        {
            "name": "algorithm",
            "type": "string",
            "description": "分解算法：auto（自动选择）、stl（STL分解）、classical（经典分解）",
            "default": "auto",
            "options": ["auto", "stl", "classical"]
        },
        {
            "name": "detection_method",
            "type": "string",
            "description": "趋势检测方法：auto（自动选择）、mann_kendall、linear_regression",
            "default": "auto",
            "options": ["auto", "mann_kendall", "linear_regression"]
        },
        {
            "name": "confidence_level",
            "type": "float",
            "description": "置信水平，用于趋势检测的统计显著性判断",
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
        "分析销售数据的趋势变化",
        "对温度数据进行趋势分解",
        "检测用户活跃度是否有上升趋势",
        "分析股票价格的长期趋势",
        "对流量数据进行季节性分解"
    ],
    "preprocessing_options": {
        "handle_missing": True,
        "interpolate_method": "linear",
        "remove_outliers": False
    }
}
