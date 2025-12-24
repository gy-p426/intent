"""
@Author      : Ayaki Shi
@Date        : 2025/12/23 15:51
@Description : DBSCAN算法配置信息
"""

DBSCAN_CONFIG = {
    "name": "DBSCAN密度聚类-异常分析",
    "description": "密度聚类算法是一种基于数据点的局部密度分布，将密度相连的连续区域划分为同一聚类，同时能自然识别出任意形状聚类和孤立噪声点的无监督学习算法。",
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
            "description": "用于聚类计算的数值型特征列"
        }
    ],
    "optional_parameters": [],
    "data_requirements": {
        "min_features": 1,
        "max_features": 10,
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