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
        "description": "聚类结果列表（严格有序：第1个字段为cluster_id，第2个字段为动态标识ID，后续为特征）",
        "item_type": "object",
        "properties": {
            "cluster_id": {
                "type": "integer",
                "description": "所属簇的ID (从0开始)，固定为结果对象的第1个字段"
            },
            # 使用通用的键名描述，实际键名是动态的
            "identity_column": {
                "type": "string",
                "description": "数据点的唯一标识（如'成员编号'、'book_id'等），固定为结果对象的第2个字段"
            },
            "features": {
                "type": "object",
                "description": "其他原始特征数据"
            }
        }
    },
    # 大模型分析指南
    "readable_summary_description": {
        "purpose": "解释聚类结果，分析不同群体的特征差异",
        "fields": {
            "标题": "分析结果标题",
            "群体特征": "每个聚类簇的显著特征描述",
            "总结": "整体聚类效果总结"
        },
        "example": {
            "标题": "👥 用户群体分层分析",
            "群体特征": [
                "**第1类 (核心群)**：包含用户 'A1001' 等，特征是活跃度极高。",
                "**第2类 (边缘群)**：包含用户 'B2023' 等，特征是仅在周末活跃。"
            ],
            "总结": "数据被清晰地划分为具有不同行为模式的群体。"
        }
    }
}