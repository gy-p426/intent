# forecast_service/core/trend_analysis/schemas.py
"""
趋势分析模块的 Pydantic 数据模型
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Union, Dict, Any
from datetime import datetime


class TimeSeriesPoint(BaseModel):
    """时间序列数据点"""
    timestamp: Union[str, datetime]
    value: float


class TrendDecompositionRequest(BaseModel):
    """趋势分解分析请求"""
    data: List[TimeSeriesPoint]
    period: Optional[int] = Field(default=None, ge=2, description="季节周期长度")
    decomposition_model: str = Field(default="additive", description="分解模型：additive 或 multiplicative")
    algorithm: Optional[str] = Field(default="auto", description="算法：auto/stl/classical")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {"timestamp": "2024-01-01 00:00", "value": 45},
                    {"timestamp": "2024-01-01 01:00", "value": 48}
                ],
                "period": 24,
                "decomposition_model": "additive",
                "algorithm": "auto"
            }
        }
    )


class TrendDetectionRequest(BaseModel):
    """趋势检测请求"""
    data: List[TimeSeriesPoint]
    method: str = Field(default="auto", description="检测方法：auto/mann_kendall/linear_regression")
    confidence_level: float = Field(default=0.95, ge=0.5, le=0.99, description="置信水平")
    include_seasonal_adjustment: bool = Field(default=True, description="是否先去除季节性")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {"timestamp": "2024-01-01", "value": 100},
                    {"timestamp": "2024-01-02", "value": 110}
                ],
                "method": "auto",
                "confidence_level": 0.95
            }
        }
    )


class BaseResponse(BaseModel):
    """基础响应模型"""
    success: bool
    task_id: str
    message: Optional[str] = None
    metadata: Dict[str, Any] = {}


class TrendDecompositionResponse(BaseResponse):
    """趋势分解响应"""
    results: Dict[str, Any]


class TrendDetectionResponse(BaseResponse):
    """趋势检测响应"""
    results: Dict[str, Any]
