"""
@Author      : Ayaki Shi
@Date        : 2025/12/23 21:00
@Description : 孤立森林算法配置信息
"""

IFOREST_CONFIG = {
    "name": "孤立森林-异常分析",
    "description": "孤立森林通过随机切割特征空间来构建二叉树，异常点因与正常数据差异大，通常能被更快地隔离而被识别。优点是高效，适合高维数据。",
    "algorithm_type": "anomaly",
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
            "description": "用于异常分析的数值型特征列"
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
        "请帮我分析一下A分公司7-9月份销售数据有哪些异常？",
        "请帮我分析一下A传感据器9.12日的数是否有异常？",
    ],
    "preprocessing_options": {
        "handle_missing": True, # 缺失数据填充0
        "normalize_features": True, # 标准化数据特征
    }
}