"""
@Author      : Causality Analysis Module
@Date        : 2025/01/15
@Description : 因果分析算法配置信息
"""

CAUSALITY_CONFIG = {
    "name": "因果分析",
    "description": "因果分析算法使用PC算法和贝叶斯网络来发现变量之间的因果关系，识别哪些因素影响结果。适用于分析销售额的影响因素、找出客户流失的原因、研究价格对需求的影响等场景。",
    "algorithm_type": "causality",
    "data_format": "tabular",
    "required_parameters": [
        {
            "name": "dependent_variable",
            "type": "string",
            "description": "因变量列名，即需要分析的结果变量"
        },
        {
            "name": "independent_variables",
            "type": "array",
            "description": "自变量列名列表，即可能影响结果的因素变量"
        }
    ],
    "optional_parameters": [
        {
            "name": "significance_level",
            "type": "float",
            "description": "显著性水平，用于条件独立性测试，默认0.05",
            "default": 0.05
        }
    ],
    "data_requirements": {
        "min_features": 2,  # 至少需要1个因变量和1个自变量
        "max_features": 20,
        "min_rows": 10,  # 因果分析需要足够的样本
        "numeric_features_required": True
    },
    "examples": [
        "分析销售额的影响因素有哪些？",
        "找出客户流失的原因",
        "研究价格对需求的影响",
        "分析广告投入对销售的因果关系",
        "哪些因素导致了产品质量问题？"
    ],
    "preprocessing_options": {
        "handle_missing": True,  # 缺失数据填充
        "normalize_features": False,  # 因果分析通常不需要标准化
        "convert_to_numeric": True  # 确保所有数据为数值类型
    }
}
