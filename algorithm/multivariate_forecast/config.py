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

# 响应参数说明
MULTIVARIATE_FORECAST_RESPONSE = {
    # 新模型训练预测响应
    "train_and_predict_response": {
        "success": "boolean - 固定为 true",
        "results": {
            "timestamps": ["string - 预测时间点数组"],
            "forecast": ["float - 预测值数组"],
            "horizon": "integer - 预测步数"
        },
        "model_used": "string - lightgbm/xgboost/random_forest/linear_regression",
        "model_id": "string - 模型唯一标识符",
        "model_name": "string - 用户指定的模型名称",
        "data_analysis": {
            "data_points": "integer",
            "target_stats": {
                "mean": "float",
                "std": "float",
                "min": "float",
                "max": "float"
            },
            "feature_count": "integer",
            "missing_values": "integer"
        },
        "metrics": {
            "rmse": "float - 均方根误差",
            "mae": "float - 平均绝对误差",
            "r2": "float - R²决定系数"
        },
        "reused_model": "boolean - 固定为 false"
    },
    
    # 复用已有模型预测响应
    "reuse_model_response": {
        "success": "boolean - 固定为 true",
        "results": {
            "timestamps": ["string"],
            "forecast": ["float"],
            "horizon": "integer"
        },
        "model_used": "string",
        "model_id": "string",
        "model_name": "string",
        "model_version": "integer - 模型版本号",
        "reused_model": "boolean - 固定为 true"
    },
    
    # 失败响应
    "error_response": {
        "success": "boolean - 固定为 false",
        "message": "string - 错误描述信息"
    }
}
