# forecast_modules/auto_univariate_forecast/schemas.py
from pydantic import BaseModel, Field, validator, ConfigDict
from typing import List, Optional, Dict, Any


class ForecastRequest(BaseModel):
    """预测请求数据模型"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": {"timestamp": ["2024-01-01 00:00", "2024-01-01 01:00"], "value": [100, 105]},
                "config": {"forecast_horizon": 24, "include_confidence": True}
            }
        }
    )

    task_type: str = Field(default="forecast", description="任务类型")
    data_type: str = Field(default="univariate", description="数据类型")
    data: Dict[str, List] = Field(..., description="时序数据")
    config: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {"forecast_horizon": 24, "include_confidence": True},
        description="配置参数"
    )

    @validator('data')
    def validate_data_structure(cls, data):
        if 'timestamp' not in data or 'value' not in data:
            raise ValueError("数据必须包含'timestamp'和'value'字段")
        if len(data['timestamp']) != len(data['value']):
            raise ValueError("timestamp和value长度必须一致")
        if len(data['timestamp']) < 10:
            raise ValueError("数据点太少，至少需要10个数据点")
        return data


class ForecastResponse(BaseModel):
    """预测响应数据模型"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "results": {"forecast": [110.5, 112.3, 115.0], "model_type": "ARIMA"},
                "model_used": "arima"
            }
        }
    )

    success: bool = Field(..., description="请求是否成功")
    message: Optional[str] = Field(default=None, description="提示信息")
    results: Optional[Dict[str, Any]] = Field(default=None, description="预测结果")
    model_used: Optional[str] = Field(default=None, description="实际使用的模型")
    data_analysis: Optional[Dict[str, Any]] = Field(default=None, description="数据分析结果")
