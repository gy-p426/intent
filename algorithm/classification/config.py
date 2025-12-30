"""
Classification Algorithm Configuration

分类预测算法配置信息
"""

CLASSIFICATION_CONFIG = {
    "name": "分类预测分析",
    "description": "基于历史数据训练模型，预测目标列的类别（支持XGBoost和TabNet）",
    "algorithm_type": "classify",
    "data_format": "tabular",
    "required_parameters": [
        {
            "name": "id_column",
            "type": "string",
            "description": "数据点的唯一标识列"
        },
        {
            "name": "target_column",
            "type": "string",
            "description": "想要预测的目标列（标签列）"
        },
        {
            "name": "feature_columns",
            "type": "array",
            "description": "用于训练和预测的特征列列表"
        }
    ],
    "optional_parameters": [
        {
            "name": "algorithm",
            "type": "string",
            "description": "指定算法类型 (xgboost/tabnet)，不填则自动选择",
            "default": None,
            "options": ["xgboost", "tabnet"]
        },
        {
            "name": "categorical_columns",
            "type": "array",
            "description": "明确指定哪些特征是类别型（非数值）",
            "default": []
        }
    ],
    "data_requirements": {
        "min_rows": 10,
        "min_features": 1,
        "label_required": True  # 必须有训练数据
    },
    "examples": [
        "根据年龄和收入预测客户流失",
        "预测贷款是否违约",
        "对用户信用等级进行分类"
    ],
    "preprocessing_options": {
        "handle_missing": True,
        "impute_strategy": "mean",
        "encode_categorical": True
    }
}

# 响应结果结构定义 (涵盖同步和异步两种情况)
CLASSIFICATION_RESULT = {
    "status": {
        "type": "string",
        "description": "执行状态"
    },
    "mode": {
        "type": "string",
        "description": "执行模式 (sync/async)"
    },
    "algorithm_used": {
        "type": "string",
        "description": "实际使用的算法 (xgboost/tabnet)"
    },
    "message": {
        "type": "string",
        "description": "提示信息"
    },
    # 异步模式字段
    "task_id": {
        "type": "string",
        "description": "异步任务ID (仅在 mode=async 时存在)"
    },
    # 同步模式后的结果字段(异步任务需要使用task接口查询)
    "result": {
        "type": "array",
        "description": "预测结果列表",
        "item_type": "object",
        "properties": {
            "uid": {
                "type": "string",
                "description": "数据点唯一标识"
            },
            "predicted_label": {
                "type": "string",
                "description": "预测的类别"
            },
            "probability": {
                "type": "float",
                "description": "预测置信度/概率"
            },
            "top_risk_factor": {
                "type": "string",
                "description": "主要影响因子 (Top Risk Factor)"
            }
        }
    }
}