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

# 响应参数说明 - 统一输出格式（v5.0）
# 所有单变量预测 API 返回统一的两字段结构：解释 + 算法结果
UNIVARIATE_FORECAST_RESPONSE = {
    # 统一输出格式说明
    "unified_format": {
        "description": "所有单变量预测 API 返回统一的两字段结构",
        "structure": {
            "解释": "string - 面向用户的通俗分析结论（中文，150-400字），包含关键发现和建议",
            "算法结果": "object - 算法特定的详细数据，用于图表展示和技术分析"
        }
    },
    
    # 成功响应
    "success_response": {
        "解释": "string - 通俗易懂的预测分析结论，包含模型选择、预测趋势、关键发现和建议",
        "算法结果": {
            "是否成功": "boolean - 固定为 true",
            "预测结果": {
                "预测值": ["float - 预测值数组"],
                "时间点": ["string - 预测时间点数组"],
                "置信下限": ["float - 置信区间下界数组"],
                "置信上限": ["float - 置信区间上界数组"],
                "训练数据点数": "integer - 训练数据点数",
                "预测步数": "integer - 预测步数",
                "训练数据范围": {
                    "开始时间": "string - 训练数据起始时间",
                    "结束时间": "string - 训练数据结束时间"
                }
            },
            "使用模型": "string - 使用的模型: 'prophet' 或 'arima'",
            "数据分析": {
                "数据点数": "integer",
                "均值": "float",
                "标准差": "float",
                "最小值": "float",
                "最大值": "float",
                "是否有季节性": "boolean",
                "趋势方向": "string - increasing/decreasing/stable",
                "缺失比例": "float"
            },
            "预测步数": "integer - 预测步数"
        }
    },
    
    # 失败响应
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
        "purpose": "为非专业用户提供通俗易懂的预测结果解读",
        "content_structure": {
            "标题": "分析结果标题（如：【单变量预测分析结果】）",
            "关键发现": "2-4条关键发现，用通俗语言描述",
            "分析说明": "简要的分析说明",
            "建议": "1-2条实用建议"
        },
        "length": "150-400字",
        "language": "中文",
        "example": (
            "【单变量预测分析结果】\n\n"
            "📌 关键发现：\n"
            "1. 系统自动选择了 Prophet（适合有季节性的数据）模型进行预测\n"
            "2. 预测了未来 24 个时间点的数据\n"
            "3. 预测期内整体呈上升趋势，变化幅度约 5.2%\n"
            "4. 数据存在周期性规律，预测已考虑这一特征\n\n"
            "💡 分析说明：\n"
            "我们使用 Prophet 对您的数据进行了分析和预测...\n\n"
            "📋 建议：\n"
            "• 预测值仅供参考，建议结合实际业务情况进行决策\n"
            "• 数据有周期性，建议关注周期性波动对业务的影响"
        )
    }
}
