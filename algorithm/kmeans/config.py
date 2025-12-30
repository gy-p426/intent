"""
K-Means Algorithm Configuration

K-Means算法配置信息
"""

KMEANS_CONFIG = {
    "name": "K-Means聚类分析",
    "description": "基于距离的聚类算法，将数据点分成K个簇",
    "algorithm_type": "cluster",
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
    "optional_parameters": [
        {
            "name": "k_value",
            "type": "integer",
            "description": "聚类数量，如果不指定则自动确定",
            "default": None,
            "min_value": 2
        }
    ],
    "data_requirements": {
        "min_rows": 2,
        "min_features": 1,
        "numeric_features_required": True
    },
    "examples": [
        "对员工绩效数据进行聚类分析",
        "将客户按消费行为分成3类",
        "对产品销售数据进行聚类"
    ],
    "preprocessing_options": {
        "handle_missing": True,
        "normalize_features": True,
        "remove_outliers": False
    }
}

# 响应结果结构定义
KMEANS_RESULT = {
    "status": {
        "type": "string",
        "description": "执行状态 (success/error)"
    },
    "k_used": {
        "type": "integer",
        "description": "实际使用的聚类簇数"
    },
    "results": {
        "type": "array",
        "description": "聚类结果列表",
        "item_type": "object",
        "properties": {
            "uid": {
                "type": "string",
                "description": "数据点唯一标识ID"
            },
            "cluster_id": {
                "type": "integer",
                "description": "所属簇的ID (从0开始)"
            }
        }
    }
}