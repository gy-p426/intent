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
        "readable_summary": {
            "title": "string - 分析结果标题（如：📊 趋势分解分析结果）",
            "key_findings": "array[string] - 关键发现列表，用通俗语言描述趋势和季节性强度",
            "explanation": "string - 详细的通俗解释，说明分解结果的含义",
            "recommendations": "array[string] - 基于分析结果的建议"
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
        "readable_summary": {
            "title": "string - 分析结果标题（如：🔍 趋势检测分析结果）",
            "key_findings": "array[string] - 关键发现列表，用通俗语言描述趋势方向和可信度",
            "explanation": "string - 详细的通俗解释，说明检测结果的含义",
            "recommendations": "array[string] - 基于分析结果的建议"
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
        "readable_summary": {
            "title": "string - 分析结果标题（如：🔍 趋势检测分析结果）",
            "key_findings": "array[string] - 关键发现列表，用通俗语言描述趋势方向、速度和拟合程度",
            "explanation": "string - 详细的通俗解释，说明检测结果的含义",
            "recommendations": "array[string] - 基于分析结果的建议"
        },
        "analysis_type": "string - 固定为 'detection'",
        "method_used": "string - 固定为 'linear_regression'",
        "data_points": "integer"
    },
    
    # readable_summary 字段说明
    "readable_summary_description": {
        "purpose": "为非专业用户提供通俗易懂的分析结果解读",
        "fields": {
            "title": "带有emoji的分析结果标题，直观展示分析类型",
            "key_findings": "关键发现列表，每条发现都用通俗语言描述，避免专业术语",
            "explanation": "详细解释分析结果的含义，帮助用户理解数据背后的故事",
            "recommendations": "基于分析结果给出的实用建议，帮助用户采取行动"
        },
        "example_decomposition": {
            "title": "📊 趋势分解分析结果",
            "key_findings": [
                "📈 数据存在较为明显的趋势（强度：65%），整体有一定的变化方向",
                "🔄 数据存在非常明显的周期性规律（强度：78%），每24个时间单位会重复类似的模式"
            ],
            "explanation": "我们将您的数据分解成了三个部分：1️⃣ 趋势成分：反映数据的长期走向...",
            "recommendations": [
                "💡 趋势明显，建议关注长期变化方向，可能需要调整策略以适应趋势",
                "💡 周期性明显（周期约24个单位），建议在业务规划中考虑这种周期性波动"
            ]
        },
        "example_detection": {
            "title": "🔍 趋势检测分析结果",
            "key_findings": [
                "📈 检测到数据呈现**上升趋势**，我们比较确定这个结论是可靠的（置信度：95%）",
                "📊 增长速度：平稳（每个时间单位平均变化 0.5234）"
            ],
            "explanation": "分析结果表明，您的数据整体呈现**上升趋势**...",
            "recommendations": [
                "💡 数据呈上升趋势，建议关注增长的可持续性，并分析增长原因",
                "💡 可以考虑利用这一趋势进行预测和规划"
            ]
        }
    }
}
