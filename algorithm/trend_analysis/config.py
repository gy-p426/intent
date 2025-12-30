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

# 响应参数说明 - 统一输出格式（v5.0）
# 所有趋势分析 API 返回统一的两字段结构：解释 + 算法结果
TREND_ANALYSIS_RESPONSE = {
    # 统一输出格式说明
    "unified_format": {
        "description": "所有趋势分析 API 返回统一的两字段结构",
        "structure": {
            "解释": "string - 面向用户的通俗分析结论（中文，150-400字），包含关键发现和建议",
            "算法结果": "object - 算法特定的详细数据，用于图表展示和技术分析"
        }
    },
    
    # 趋势分解统一响应
    "decomposition_response": {
        "解释": "string - 通俗易懂的分解分析结论，包含趋势强度、季节性规律、关键发现和建议",
        "算法结果": {
            "分析类型": "string - 固定为 'decomposition'",
            "数据特征": {
                "数据点数": "integer - 数据点总数",
                "均值": "float - 数据均值",
                "标准差": "float - 数据标准差",
                "最小值": "float - 数据最小值",
                "最大值": "float - 数据最大值",
                "异常值数量": "integer - 异常值数量",
                "异常值比例": "float - 异常值比例 (0-1)",
                "是否正态分布": "boolean - 是否符合正态分布",
                "是否有季节性": "boolean - 是否存在季节性"
            },
            "分解结果": {
                "趋势分量": [{"时间戳": "string", "数值": "float"}],
                "季节性分量": [{"时间戳": "string", "数值": "float"}],
                "残差分量": [{"时间戳": "string", "数值": "float"}],
                "分析指标": {
                    "趋势强度": "float - 趋势强度 (0-1)",
                    "季节性强度": "float - 季节性强度 (0-1)",
                    "残差方差": "float - 残差方差",
                    "算法": "string - 使用的分解算法",
                    "使用周期": "integer - 使用的季节周期"
                }
            },
            "使用算法": "string - 使用的算法 (stl/classical)",
            "使用周期": "integer - 使用的季节周期",
            "数据点数": "integer - 数据点总数"
        }
    },
    
    # 趋势检测统一响应（Mann-Kendall 方法）
    "detection_mann_kendall_response": {
        "解释": "string - 通俗易懂的检测分析结论，包含趋势方向、可信度、关键发现和建议",
        "算法结果": {
            "分析类型": "string - 固定为 'detection'",
            "数据特征": {
                "数据点数": "integer",
                "均值": "float",
                "标准差": "float"
            },
            "检测结果": {
                "趋势方向": "string - increasing/decreasing/no trend",
                "Sen斜率": "float - Sen斜率估计",
                "p值": "float - 统计检验p值",
                "Z统计量": "float - Z统计量",
                "S统计量": "integer - S统计量",
                "统计显著性": "boolean",
                "置信水平": "float",
                "检测方法": "string - 固定为 'Mann-Kendall'",
                "样本量": "integer",
                "结果解释": "string - 结果解释"
            },
            "使用方法": "string - 固定为 'mann_kendall'",
            "数据点数": "integer"
        }
    },
    
    # 趋势检测统一响应（线性回归方法）
    "detection_linear_regression_response": {
        "解释": "string - 通俗易懂的检测分析结论，包含趋势方向、变化速度、拟合程度、关键发现和建议",
        "算法结果": {
            "分析类型": "string - 固定为 'detection'",
            "数据特征": {
                "数据点数": "integer",
                "均值": "float",
                "标准差": "float"
            },
            "检测结果": {
                "趋势方向": "string - increasing/decreasing/no trend",
                "斜率": "float - 回归斜率",
                "截距": "float - 回归截距",
                "p值": "float",
                "R平方值": "float - R²决定系数 (0-1)",
                "标准误差": "float",
                "置信区间": ["float", "float"],
                "统计显著性": "boolean",
                "置信水平": "float",
                "检测方法": "string - 固定为 'Linear Regression'",
                "样本量": "integer",
                "结果解释": "string"
            },
            "使用方法": "string - 固定为 'linear_regression'",
            "数据点数": "integer"
        }
    },
    
    # 错误响应
    "error_response": {
        "解释": "string - 错误说明，如：分析过程中遇到问题：{错误描述}。请检查输入数据或稍后重试。",
        "算法结果": {
            "是否成功": "boolean - 固定为 false",
            "错误信息": "string - 详细错误信息",
            "错误类型": "string - 错误类型"
        }
    },
    
    # 解释字段内容说明
    "explanation_field_description": {
        "purpose": "为非专业用户提供通俗易懂的分析结果解读",
        "content_structure": {
            "标题": "分析结果标题（如：【趋势分解分析结果】）",
            "关键发现": "2-4条关键发现，用通俗语言描述",
            "分析说明": "简要的分析说明",
            "建议": "1-2条实用建议"
        },
        "length": "150-400字",
        "language": "中文",
        "example_decomposition": (
            "【趋势分解分析结果】\n\n"
            "📌 关键发现：\n"
            "1. 数据存在较为明显的趋势（强度：65%），整体有一定的变化方向\n"
            "2. 数据存在非常明显的周期性规律（强度：78%），每24个时间单位会重复类似的模式\n\n"
            "💡 分析说明：\n"
            "我们将您的数据分解成了三个部分：趋势成分、季节性成分和残差成分...\n\n"
            "📋 建议：\n"
            "• 趋势明显，建议关注长期变化方向\n"
            "• 周期性明显，建议在业务规划中考虑这种周期性波动"
        ),
        "example_detection": (
            "【趋势检测分析结果】\n\n"
            "📌 关键发现：\n"
            "1. 检测到数据呈现上升趋势，我们比较确定这个结论是可靠的（置信度：95%）\n"
            "2. 增长速度：平稳（每个时间单位平均变化 0.5234）\n\n"
            "💡 分析说明：\n"
            "使用Mann-Kendall方法进行趋势检验，结果表明数据整体呈现上升趋势...\n\n"
            "📋 建议：\n"
            "• 数据呈上升趋势，建议关注增长的可持续性\n"
            "• 可以考虑利用这一趋势进行预测和规划"
        )
    }
}
