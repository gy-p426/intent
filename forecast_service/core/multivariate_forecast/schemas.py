# forecast_service/core/multivariate_forecast/schemas.py
"""多变量预测模块的 Pydantic 数据模型"""
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime


class MultivariateForecastConfig(BaseModel):
    """预测配置"""
    model_config = ConfigDict(protected_namespaces=())
    
    target_column: str = Field(default="target", description="目标列名")
    feature_columns: Optional[List[str]] = Field(default=None, description="特征列名列表")
    algorithm: str = Field(default="lightgbm", description="算法: lightgbm, xgboost, random_forest, linear_regression")
    forecast_horizon: int = Field(default=14, description="预测步数")
    model_name: Optional[str] = Field(default=None, description="模型名称")
    model_description: Optional[str] = Field(default=None, description="模型描述")
    use_model_id: Optional[str] = Field(default=None, description="重用指定ID的模型")
    use_model_name: Optional[str] = Field(default=None, description="重用指定名称的模型")
    use_model_version: Optional[int] = Field(default=None, description="指定版本")


class MultivariateForecastRequest(BaseModel):
    """多变量预测请求"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {"timestamp": "2024-01-01 00:00", "target": 1000, "price": 99, "promotion": 1},
                    {"timestamp": "2024-01-01 01:00", "target": 1050, "price": 95, "promotion": 1}
                ],
                "config": {"target_column": "target", "algorithm": "random_forest", "forecast_horizon": 14}
            }
        }
    )

    task_type: str = Field(default="forecast", description="任务类型")
    data_type: str = Field(default="multivariate", description="数据类型")
    data: List[Dict[str, Any]] = Field(..., description="多变量时序数据")
    config: Optional[Dict[str, Any]] = Field(default=None, description="配置参数")

    @field_validator('data')
    @classmethod
    def validate_data(cls, data):
        if len(data) < 10:
            raise ValueError("数据点太少，至少需要10个数据点")
        if not all('timestamp' in d for d in data):
            raise ValueError("每个数据点必须包含 timestamp 字段")
        return data


class MultivariateForecastResponse(BaseModel):
    """多变量预测响应"""
    model_config = ConfigDict(protected_namespaces=())
    
    success: bool
    message: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
    model_used: Optional[str] = None
    model_id: Optional[str] = None
    model_name: Optional[str] = None
    model_version: Optional[int] = None
    reused_model: Optional[bool] = False
    data_analysis: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, float]] = None
    processing_time: Optional[float] = None


class ModelInfo(BaseModel):
    """模型信息"""
    model_config = ConfigDict(protected_namespaces=())
    
    model_id: str
    model_name: Optional[str] = None
    version: Optional[int] = None
    algorithm: str
    target_column: str
    feature_columns: List[str]
    description: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    metrics: Optional[Dict[str, float]] = None
