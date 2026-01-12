"""
Multi Analysis Algorithm Configuration

统一多算法分析配置信息
"""

MULTI_ANALYSIS_CONFIG = {
    "name": "统一多算法分析",
    "description": "统一多算法分析接口，支持一次调用执行多种分析：周期性分析、环比分析、同比分析、定基比分析",
    "algorithm_type": "multi_analysis",
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
            "description": "数值列名，用于分析的目标数值"
        }
    ],
    "optional_parameters": [
        {
            "name": "analysis_types",
            "type": "array",
            "description": "要执行的分析类型列表：periodicity(周期性)、period_over_period(环比)、year_over_year(同比)、base_period_index(定基比)",
            "default": None,
            "options": ["periodicity", "period_over_period", "year_over_year", "base_period_index"]
        },
        {
            "name": "include_all",
            "type": "boolean",
            "description": "是否执行所有分析（当analysis_types为空时生效）",
            "default": True
        },
        {
            "name": "candidate_periods",
            "type": "array",
            "description": "周期性分析：候选周期列表",
            "default": None
        },
        {
            "name": "period_type",
            "type": "string",
            "description": "环比/同比分析：周期类型（hour/day/week/month/quarter/year）",
            "default": None
        },
        {
            "name": "base_period",
            "type": "string",
            "description": "定基比分析：基期标识，如 '2020'",
            "default": None
        },
        {
            "name": "base_value",
            "type": "float",
            "description": "定基比分析：基期指数值",
            "default": 100
        },
        {
            "name": "simplified",
            "type": "boolean",
            "description": "是否返回简化结果（仅包含解释和关键指标）",
            "default": False
        }
    ],
    "data_requirements": {
        "min_rows": 2,
        "min_features": 1,
        "numeric_features_required": True,
        "time_column_required": True
    },
    "examples": [
        "分析销售数据的周期性规律",
        "对比本月和上月的销售额变化",
        "分析今年与去年同期的业绩对比",
        "以2020年为基期计算各年度指数",
        "综合分析销售数据的周期性、环比和同比变化",
        "分析出车数据的周期性和环比变化"
    ],
    "preprocessing_options": {
        "handle_missing": True,
        "interpolate_method": "linear"
    }
}

# 响应参数说明 - 统一输出格式（v5.0）
MULTI_ANALYSIS_RESPONSE = {
    "unified_format": {
        "description": "统一多算法分析返回综合分析结果",
        "structure": {
            "解释": "string - 综合分析结论摘要",
            "分析结果": "object - 各分析类型的详细结果",
            "执行的分析": "array - 实际执行的分析类型列表",
            "成功数量": "integer - 成功执行的分析数量",
            "失败数量": "integer - 失败的分析数量",
            "数据点数": "integer - 输入数据点数量",
            "执行耗时": "object - 各分析的执行耗时（毫秒）",
            "总耗时": "float - 总执行耗时（毫秒）"
        }
    },
    "single_analysis_result": {
        "分析类型": "string - 分析类型标识",
        "分析名称": "string - 分析类型中文名称",
        "成功": "boolean - 分析是否成功",
        "解释": "string - 面向用户的通俗分析结论（可选）",
        "算法结果": "object - 算法特定的详细数据（可选）",
        "错误信息": "string - 失败时的错误信息（可选）"
    }
}
