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

# 响应参数说明（已修改为符合 {"解释": "", "算法结果": {}} 格式）
CLASSIFICATION_RESPONSE = {
    # 同步预测响应 (XGBoost)
    "sync_response": {
        "是否成功": "boolean - 固定为 true",
        "执行模式": "string - sync",
        "使用算法": "string - xgboost/tabnet",

        # 核心字段 1: 解释 (对应 LLM 分析)
        "解释": {
            "标题": "string - 分析结果标题",
            "关键发现": "array[string] - 关键发现列表",
            "详细解释": "string - 详细解释",
            "建议": "array[string] - 建议列表"
        },

        # 核心字段 2: 算法结果 (对应技术数据)
        "算法结果": {
            "数据点ID": ["string"],
            "预测类别": ["string"],
            "置信度": ["float"],
            "主要影响因子": ["string"]
        },

        "消息": "string - 结果描述或模型下载链接"
    },

    # 异步任务响应 (TabNet)
    "async_response": {
        "是否成功": "boolean - 固定为 true",
        "执行模式": "string - async",
        "使用算法": "string - tabnet",
        "异步任务ID": "string - 用于查询进度的TaskID",
        "消息": "string - 任务创建成功提示"
    },

    # 失败响应
    "error_response": {
        "是否成功": "boolean - 固定为 false",
        "消息": "string - 错误描述信息"
    },

    # 通俗摘要字段说明（映射到 "解释" 字段）
    "readable_summary_description": {
        "purpose": "为非专业用户提供通俗易懂的分类预测结果解读，生成内容将放入'解释'字段",
        "fields": {
            "标题": "带有emoji的分析结果标题，直观展示分析类型",
            "关键发现": "关键发现列表，包括模型选择、预测准确度（置信度）、主要风险特征等信息",
            "详细解释": "详细解释预测结果的含义，说明哪些特征对分类结果影响最大",
            "建议": "基于分类结果给出的实用建议，如针对高风险用户的干预措施"
        },
        "example": {
            "标题": "🔍 客户流失风险预测分析",
            "关键发现": [
                "🤖 使用 **XGBoost（极致梯度提升）** 算法进行预测",
                "📊 分析了 **1,200** 位客户的数据",
                "⚠️ 识别出 **158** 位高风险流失客户（占比 13%）",
                "🎯 平均预测置信度：**92.5%**（模型非常确信）",
                "🔑 主要影响因子：**月均消费金额** 和 **最近一次投诉时间**"
            ],
            "详细解释": "根据您的数据，我们使用 XGBoost 模型对客户流失风险进行了评估。模型发现“月均消费金额”下降是预测流失的最强信号...",
            "建议": [
                "💡 关注高风险客户：针对预测流失概率超过 80% 的客户立即启动挽留活动",
                "💡 优化服务：针对“最近一次投诉时间”较近的客户进行回访"
            ]
        }
    }
}