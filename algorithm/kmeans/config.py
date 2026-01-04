"""
K-Means Algorithm Configuration

K-Means算法配置信息
"""

KMEANS_CONFIG = {
    "name": "K-Means聚类分析",
    "description": "基于距离的聚类算法，将数据点分成K个簇，并提供可视化坐标与核心特征解释",
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
    "feature_info": {
        "type": "array",
        "description": "参与聚类计算的特征列名称列表",
        "item_type": "string"
    },
    "centroids": {
        "type": "array",
        "description": "聚类中心详情（包含可视化坐标、核心特征及业务均值），可用于绘制雷达图",
        "item_type": "object",
        "properties": {
            "cluster_id": {
                "type": "integer",
                "description": "簇ID"
            },
            "x": {
                "type": "number",
                "description": "聚类中心的可视化2D投影坐标X"
            },
            "y": {
                "type": "number",
                "description": "聚类中心的可视化2D投影坐标Y"
            },
            "top_features": {
                "type": "array",
                "description": "该簇最显著的前3个核心特征，用于解释群体特性",
                "item_type": "object",
                "properties": {
                    "feature": {"type": "string", "description": "特征名称"},
                    "score": {"type": "number", "description": "显著性得分(Z-Score)"},
                    "direction": {"type": "string", "description": "方向 (High/Low)"}
                }
            }
            # 注意：实际响应中还会包含各特征的原始业务均值（如 'amount', 'frequency' 等）
        }
    },
    "results": {
        "type": "array",
        "description": "聚类结果列表（严格有序：字段包含ID、坐标、核心特征及原始数据）",
        "item_type": "object",
        "properties": {
            "cluster_id": {
                "type": "integer",
                "description": "所属簇的ID (从0开始)"
            },
            "identity_column": {
                "type": "string",
                "description": "数据点的唯一标识（如'成员编号'、'book_id'等）"
            },
            "x": {
                "type": "number",
                "description": "数据点的可视化2D投影坐标X"
            },
            "y": {
                "type": "number",
                "description": "数据点的可视化2D投影坐标Y"
            },
            "top_feature": {
                "type": "string",
                "description": "该数据点最显著的特征（导致其被分到该类的主要原因）"
            },
            "top_feature_desc": {
                "type": "string",
                "description": "显著特征的描述（如 'High (2.5)'）"
            },
            "features": {
                "type": "object",
                "description": "其他原始特征数据"
            }
        }
    },
    # 大模型分析指南
    "readable_summary_description": {
        "purpose": "解释聚类结果，结合'centroids'中的'top_features'和业务均值，分析不同群体的核心差异",
        "fields": {
            "标题": "分析结果标题",
            "群体特征": "每个聚类簇的显著特征描述（重点引用 top_features 中的 High/Low 特征）",
            "总结": "整体聚类效果总结及业务建议"
        },
        "example": {
            "标题": "👥 用户群体分层分析",
            "群体特征": [
                "**第1类 (高价值群)**：特征是 **消费金额 High** (均值1.2w) 且 **活跃度 High**。",
                "**第2类 (沉睡群)**：特征是 **最近一次访问 Low** (很久未访)，主要包含流失风险用户。"
            ],
            "总结": "数据被清晰地划分为高价值活跃用户与沉睡用户，建议对第2类群体进行激活营销。"
        }
    }
}