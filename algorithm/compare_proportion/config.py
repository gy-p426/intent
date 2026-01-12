"""
@Author      : Ayaki Shi
@Date        : 2025/12/23 15:51
@Description : 比较-占比分析
"""

COMPARE_PROPORTION_CONFIG = {
    "name": "Proportion占比分析",
    "description": "计算数值型特征列的占比、平均值、极值",
    "algorithm_type": "compare_proportion",
    "data_format": "tabular",
    "required_parameters": [
        {
            "name": "id_column",
            "type": "string",
            "description": "用于标识每个数据点的ID列"
        },
        {
            "name": "feature_columns",
            "type": "array",
            "description": "用于比较-占比分析计算的数值型特征列"
        }
    ],
    "optional_parameters": [],
    "data_requirements": {
        "min_features": 1,
        "max_features": 50,
        "min_rows": 1,
        "numeric_features_required": True
    },
    "examples": [
        "对A、B两名员工分析销售的占比贡献情况",
    ],
    "preprocessing_options": {
        "handle_missing": True, # 缺失数据填充0
        "normalize_features": False, # 标准化数据特征
    }
}