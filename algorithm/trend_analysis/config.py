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

# 响应参数说明
TREND_ANALYSIS_RESPONSE = {
    # 趋势分解响应
    "decomposition_response": {
        "data_characteristics": {
            "data_points": "integer - 数据点总数",
            "mean": "float - 数据均值",
            "std": "float - 数据标准差",
            "min": "float - 数据最小值",
            "max": "float - 数据最大值",
            "outlier_count": "integer - 异常值数量",
            "outlier_ratio": "float - 异常值比例 (0-1)",
            "is_normal": "boolean - 是否符合正态分布",
            "has_seasonality": "boolean - 是否存在季节性"
        },
        "decomposition": {
            "trend": [{"timestamp": "string", "value": "float"}],
            "seasonal": [{"timestamp": "string", "value": "float"}],
            "residual": [{"timestamp": "string", "value": "float"}],
            "analysis_metrics": {
                "trend_strength": "float - 趋势强度 (0-1)",
                "seasonal_strength": "float - 季节性强度 (0-1)",
                "residual_variance": "float - 残差方差",
                "algorithm": "string - 使用的分解算法",
                "period_used": "integer - 使用的季节周期"
            }
        },
        "analysis_type": "string - 固定为 'decomposition'",
        "algorithm_used": "string - 使用的算法 (stl/classical)",
        "period_used": "integer - 使用的季节周期",
        "data_points": "integer - 数据点总数"
    },
    
    # 趋势检测响应 - Mann-Kendall方法
    "detection_mann_kendall_response": {
        "data_characteristics": {
            "data_points": "integer",
            "mean": "float",
            "std": "float"
        },
        "detection": {
            "trend_direction": "string - increasing/decreasing/no trend",
            "sen_slope": "float - Sen斜率估计",
            "p_value": "float - 统计检验p值",
            "z_statistic": "float - Z统计量",
            "s_statistic": "integer - S统计量",
            "statistical_significance": "boolean",
            "confidence_level": "float",
            "method": "string - 固定为 'Mann-Kendall'",
            "sample_size": "integer",
            "interpretation": "string - 结果解释"
        },
        "analysis_type": "string - 固定为 'detection'",
        "method_used": "string - 固定为 'mann_kendall'",
        "data_points": "integer"
    },
    
    # 趋势检测响应 - 线性回归方法
    "detection_linear_regression_response": {
        "data_characteristics": {
            "data_points": "integer",
            "mean": "float",
            "std": "float"
        },
        "detection": {
            "trend_direction": "string - increasing/decreasing/no trend",
            "slope": "float - 回归斜率",
            "intercept": "float - 回归截距",
            "p_value": "float",
            "r_squared": "float - R²决定系数 (0-1)",
            "std_error": "float",
            "confidence_interval": ["float", "float"],
            "statistical_significance": "boolean",
            "confidence_level": "float",
            "method": "string - 固定为 'Linear Regression'",
            "sample_size": "integer",
            "interpretation": "string"
        },
        "analysis_type": "string - 固定为 'detection'",
        "method_used": "string - 固定为 'linear_regression'",
        "data_points": "integer"
    }
}
