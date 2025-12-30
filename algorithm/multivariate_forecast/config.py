"""
Multivariate Forecast Algorithm Configuration

多变量预测算法配置信息
"""

MULTIVARIATE_FORECAST_CONFIG = {
    "name": "多变量时间序列预测",
    "description": "基于多个特征变量进行时间序列预测，支持LightGBM、XGBoost、随机森林和线性回归算法",
    "algorithm_type": "predict",
    "data_format": "multivariate_time_series",
    "required_parameters": [
        {
            "name": "timestamp_column",
            "type": "string",
            "description": "时间戳列名，用于标识时间序列的时间点"
        },
        {
            "name": "target_column",
            "type": "string",
            "description": "目标列名，作为预测的目标变量"
        }
    ],
    "optional_parameters": [
        {
            "name": "feature_columns",
            "type": "array",
            "description": "特征列名列表，用于预测的输入特征，不指定则自动选择所有数值列",
            "default": None
        },
        {
            "name": "forecast_horizon",
            "type": "integer",
            "description": "预测步数，即预测未来多少个时间点",
            "default": 14,
            "min_value": 1,
            "max_value": 365
        },
        {
            "name": "algorithm",
            "type": "string",
            "description": "预测算法：lightgbm、xgboost、random_forest、linear_regression",
            "default": "lightgbm",
            "options": ["lightgbm", "xgboost", "random_forest", "linear_regression"]
        },
        {
            "name": "model_name",
            "type": "string",
            "description": "模型名称，用于保存和复用模型",
            "default": None
        },
        {
            "name": "use_model_id",
            "type": "string",
            "description": "复用已有模型的ID",
            "default": None
        }
    ],
    "data_requirements": {
        "min_rows": 10,
        "min_features": 1,
        "numeric_features_required": True,
        "time_column_required": True
    },
    "examples": [
        "根据价格和促销活动预测销售量",
        "基于天气和节假日预测客流量",
        "使用多个指标预测股票价格",
        "根据历史数据和外部因素预测需求",
        "使用随机森林预测未来14天的收入"
    ],
    "preprocessing_options": {
        "handle_missing": True,
        "create_lag_features": True,
        "create_time_features": True,
        "normalize_features": False
    }
}

# 响应参数说明（字段名已改为中文，与 API 响应保持一致）
MULTIVARIATE_FORECAST_RESPONSE = {
    # 新模型训练预测响应
    "train_and_predict_response": {
        "是否成功": "boolean - 固定为 true",
        "预测结果": {
            "时间点": ["string - 预测时间点数组"],
            "预测值": ["float - 预测值数组"],
            "预测期数": "integer - 预测步数",
            "通俗摘要": {
                "标题": "string - 分析结果标题（如：🎯 多变量预测分析结果）",
                "关键发现": "array[string] - 关键发现列表，用通俗语言描述预测结果和模型准确度",
                "详细解释": "string - 详细的通俗解释，说明预测结果的含义",
                "建议": "array[string] - 基于分析结果的建议"
            }
        },
        "使用模型": "string - lightgbm/xgboost/random_forest/linear_regression",
        "模型ID": "string - 模型唯一标识符",
        "模型名称": "string - 用户指定的模型名称",
        "数据分析": {
            "数据点数": "integer",
            "目标变量统计": {
                "均值": "float",
                "标准差": "float",
                "最小值": "float",
                "最大值": "float"
            },
            "特征数量": "integer",
            "缺失值数量": "integer"
        },
        "评估指标": {
            "均方根误差": "float - 均方根误差",
            "平均绝对误差": "float - 平均绝对误差",
            "决定系数": "float - R²决定系数"
        },
        "是否复用模型": "boolean - 固定为 false"
    },
    
    # 复用已有模型预测响应
    "reuse_model_response": {
        "是否成功": "boolean - 固定为 true",
        "预测结果": {
            "时间点": ["string"],
            "预测值": ["float"],
            "预测期数": "integer"
        },
        "使用模型": "string",
        "模型ID": "string",
        "模型名称": "string",
        "模型版本": "integer - 模型版本号",
        "是否复用模型": "boolean - 固定为 true"
    },
    
    # 失败响应
    "error_response": {
        "是否成功": "boolean - 固定为 false",
        "消息": "string - 错误描述信息"
    },
    
    # 通俗摘要字段说明
    "readable_summary_description": {
        "purpose": "为非专业用户提供通俗易懂的多变量预测结果解读",
        "fields": {
            "标题": "带有emoji的分析结果标题，直观展示分析类型",
            "关键发现": "关键发现列表，包括模型选择、准确度、预测趋势等信息",
            "详细解释": "详细解释预测结果的含义，包括R²值的通俗解读",
            "建议": "基于分析结果给出的实用建议"
        },
        "example": {
            "标题": "🎯 多变量预测分析结果",
            "关键发现": [
                "🤖 使用 **LightGBM（高效梯度提升算法）** 进行预测",
                "📊 综合了 **5** 个特征变量进行分析",
                "📈 模型准确度：**较高** ⭐⭐（R² = 78%）",
                "📐 平均预测误差：约 12.35（RMSE）",
                "📈 预测期内（14个时间点）整体呈 **上升趋势**"
            ],
            "详细解释": "我们使用 **LightGBM** 对您的数据进行了多变量预测分析...",
            "建议": [
                "💡 模型准确度较高，预测结果可作为决策参考",
                "💡 预测值会随时间推移而累积误差，建议定期更新模型"
            ]
        }
    }
}
