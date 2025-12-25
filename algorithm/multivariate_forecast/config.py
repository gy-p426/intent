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

# ============================================================================
# 多变量预测算法响应参数说明
# ============================================================================
#
# 响应类型说明：
# 多变量预测算法根据请求参数和执行结果返回不同的响应结构，共有3种可能的响应：
#
# ┌─────────────────────────────────────────────────────────────────────────┐
# │ 响应类型                  │ 触发条件                                     │
# ├─────────────────────────────────────────────────────────────────────────┤
# │ train_and_predict_response│ 不传 use_model_id 和 use_model_name         │
# │                           │ 训练新模型并预测                             │
# │                           │ reused_model = false                        │
# ├─────────────────────────────────────────────────────────────────────────┤
# │ reuse_model_response      │ 传入 use_model_id 或 use_model_name         │
# │                           │ 复用已有模型进行预测                         │
# │                           │ reused_model = true                         │
# ├─────────────────────────────────────────────────────────────────────────┤
# │ error_response            │ 预测执行失败，可能原因：                      │
# │                           │ - 目标列不存在                               │
# │                           │ - 特征列不存在                               │
# │                           │ - 模型不存在 (复用模型时)                    │
# │                           │ - 数据格式错误                               │
# │                           │ success = false                             │
# └─────────────────────────────────────────────────────────────────────────┘
#
# 模型复用说明:
# - 首次预测会训练新模型，返回 model_id (格式: "mv_xxxxxxxx")
# - 后续可通过 use_model_id 或 use_model_name 复用已训练的模型
# - 复用模型时不返回 data_analysis 和 metrics，但返回 model_version
#
# 算法选择建议:
# - lightgbm: 大数据量(>10000行)，训练速度快
# - xgboost: 追求最高精度
# - random_forest: 需要可解释性，可获取特征重要性
# - linear_regression: 快速原型验证，作为基准模型
#
# ============================================================================

MULTIVARIATE_FORECAST_RESPONSE = {
    # ========================================================================
    # 响应1: 新模型训练预测响应
    # 触发条件: 不传 use_model_id 和 use_model_name (训练新模型)
    # 特点: 包含 data_analysis 和 metrics，reused_model = false
    # ========================================================================
    "train_and_predict_response": {
        "success": "boolean - 固定为 true",
        "results": {
            "timestamps": ["string - 预测时间点数组，格式: 'YYYY-MM-DD HH:MM'"],
            "forecast": ["float - 预测值数组，长度等于forecast_horizon"],
            "horizon": "integer - 预测步数"
        },
        "model_used": "string - 使用的算法: lightgbm/xgboost/random_forest/linear_regression",
        "model_id": "string - 模型唯一标识符，格式: 'mv_xxxxxxxx'",
        "model_name": "string - 用户指定的模型名称 (可选，可能为null)",
        "data_analysis": {
            "data_points": "integer - 数据点总数",
            "target_stats": {
                "mean": "float - 目标变量均值",
                "std": "float - 目标变量标准差",
                "min": "float - 目标变量最小值",
                "max": "float - 目标变量最大值"
            },
            "feature_count": "integer - 特征数量",
            "missing_values": "integer - 缺失值总数"
        },
        "metrics": {
            "rmse": "float - 均方根误差 (Root Mean Square Error)",
            "mae": "float - 平均绝对误差 (Mean Absolute Error)",
            "r2": "float - R²决定系数 (0-1，越接近1越好)"
        },
        "reused_model": "boolean - 固定为 false"
    },
    
    # ========================================================================
    # 响应2: 复用已有模型预测响应
    # 触发条件: 传入 use_model_id 或 use_model_name (复用已有模型)
    # 特点: 包含 model_version，不包含 data_analysis 和 metrics
    #       reused_model = true
    # ========================================================================
    "reuse_model_response": {
        "success": "boolean - 固定为 true",
        "results": {
            "timestamps": ["string - 预测时间点数组，格式: 'YYYY-MM-DD HH:MM'"],
            "forecast": ["float - 预测值数组，长度等于forecast_horizon"],
            "horizon": "integer - 预测步数"
        },
        "model_used": "string - 使用的算法: lightgbm/xgboost/random_forest/linear_regression",
        "model_id": "string - 模型唯一标识符",
        "model_name": "string - 模型名称 (可能为null)",
        "model_version": "integer - 模型版本号",
        "reused_model": "boolean - 固定为 true"
    },
    
    # ========================================================================
    # 响应3: 失败响应
    # 触发条件: 预测执行失败
    # 常见错误:
    #   - "目标列 xxx 不存在"
    #   - "特征列不存在: [xxx, yyy]"
    #   - "模型不存在: mv_xxx" (复用模型时)
    #   - "重用模型时需要提供预测数据"
    # ========================================================================
    "error_response": {
        "success": "boolean - 固定为 false",
        "message": "string - 错误描述信息，常见错误包括: '目标列 xxx 不存在', '特征列不存在: [xxx]', '模型不存在: xxx'"
    }
}
