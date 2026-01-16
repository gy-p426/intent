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
        },
        {
            "name": "time_range_info",
            "type": "object",
            "description": "时间范围扩展信息，用于记录LLM自动扩展的查询时间范围",
            "default": None,
            "structure": {
                "analysis_type": {
                    "type": "string",
                    "description": "分析类型：periodicity/period_over_period/year_over_year/base_period_index"
                },
                "period_type": {
                    "type": "string",
                    "description": "周期类型：hour/day/week/month/quarter/year"
                },
                "expanded_range": {
                    "type": "object",
                    "description": "扩展后的时间范围",
                    "properties": {
                        "start": {"type": "string", "description": "起始日期，格式：YYYY-MM-DD 或 YYYY-MM 或 YYYY"},
                        "end": {"type": "string", "description": "结束日期，格式：YYYY-MM-DD 或 YYYY-MM 或 YYYY"}
                    }
                },
                "current_period": {
                    "type": "object",
                    "description": "当前周期（环比/同比分析使用）",
                    "properties": {
                        "year": {"type": "integer"},
                        "month": {"type": "integer", "range": "1-12"},
                        "day": {"type": "integer", "range": "1-31"},
                        "week": {"type": "integer", "range": "1-53"},
                        "quarter": {"type": "integer", "range": "1-4"},
                        "hour": {"type": "integer", "range": "0-23"}
                    }
                },
                "previous_period": {
                    "type": "object",
                    "description": "上一周期（环比分析使用）"
                },
                "same_period_last_year": {
                    "type": "object",
                    "description": "去年同期（同比分析使用）"
                },
                "base_period": {
                    "type": "object",
                    "description": "基期（定基比分析使用）"
                },
                "target_periods": {
                    "type": "array",
                    "description": "目标周期列表（定基比分析使用）"
                },
                "min_data_points": {
                    "type": "integer",
                    "description": "最少数据点数（周期性分析使用）",
                    "default": 8
                }
            },
            "examples": [
                {
                    "description": "环比分析 - 8月与7月对比",
                    "value": {
                        "analysis_type": "period_over_period",
                        "period_type": "month",
                        "current_period": {"year": 2025, "month": 8},
                        "previous_period": {"year": 2025, "month": 7},
                        "expanded_range": {"start": "2025-07-01", "end": "2025-08-31"}
                    }
                },
                {
                    "description": "同比分析 - 2025年8月与2024年8月对比",
                    "value": {
                        "analysis_type": "year_over_year",
                        "period_type": "month",
                        "current_period": {"year": 2025, "month": 8},
                        "same_period_last_year": {"year": 2024, "month": 8},
                        "expanded_range": {"start": "2024-08-01", "end": "2025-08-31"}
                    }
                },
                {
                    "description": "定基比分析 - 以2020年为基期",
                    "value": {
                        "analysis_type": "base_period_index",
                        "period_type": "year",
                        "base_period": {"year": 2020},
                        "target_periods": [{"year": 2021}, {"year": 2022}, {"year": 2023}, {"year": 2024}, {"year": 2025}],
                        "expanded_range": {"start": "2020-01-01", "end": "2025-12-31"}
                    }
                },
                {
                    "description": "周期性分析 - 确保至少8个数据点",
                    "value": {
                        "analysis_type": "periodicity",
                        "period_type": "month",
                        "min_data_points": 8,
                        "expanded_range": {"start": "2025-01-01", "end": "2025-08-31"}
                    }
                }
            ]
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
        "分析出车数据的周期性和环比变化",
        "分析8月销售额的环比变化（自动扩展查询7月和8月数据）",
        "对比2025年Q2与去年同期的业绩（自动扩展查询2024年Q2和2025年Q2数据）",
        "分析本周出车次数与上周的对比",
        "以2020年1月为基期，计算到2025年8月的销售指数"
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
