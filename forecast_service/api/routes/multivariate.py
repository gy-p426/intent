# forecast_service/api/routes/multivariate.py
"""
多变量预测API路由
实现 /api/v1/forecast/multivariate 端点
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict, field_validator
import logging
import time
import sys
import os

# 添加父目录到路径以便导入core模块
forecast_service_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, forecast_service_root)

# 导入核心服务
from core.multivariate_forecast.core import MultivariatePredictor

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/forecast", tags=["多变量预测"])

# 初始化预测器
predictor = MultivariatePredictor()


# ============ 请求/响应模型 ============

class MultivariateForecastRequest(BaseModel):
    """多变量预测请求"""
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "data": [
                    {"timestamp": "2024-01-01 00:00", "target": 1000, "price": 99, "promotion": 1},
                    {"timestamp": "2024-01-01 01:00", "target": 1050, "price": 95, "promotion": 1}
                ],
                "config": {
                    "target_column": "target",
                    "algorithm": "random_forest",
                    "forecast_horizon": 14
                }
            }
        }
    )
    
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
    
    success: bool = Field(..., description="请求是否成功")
    message: Optional[str] = Field(default=None, description="响应消息")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="响应时间戳")
    model_id: Optional[str] = Field(default=None, description="模型ID")
    model_name: Optional[str] = Field(default=None, description="模型名称")
    model_used: Optional[str] = Field(default=None, description="使用的算法")
    predictions: Optional[List[Dict[str, Any]]] = Field(default=None, description="预测结果")
    metrics: Optional[Dict[str, float]] = Field(default=None, description="模型指标")
    reused_model: bool = Field(default=False, description="是否复用已有模型")
    processing_time: Optional[float] = Field(default=None, description="处理时间(秒)")
    results: Optional[Dict[str, Any]] = Field(default=None, description="完整结果")
    data_analysis: Optional[Dict[str, Any]] = Field(default=None, description="数据分析结果")


# ============ API端点 ============

@router.post(
    "/multivariate",
    response_model=MultivariateForecastResponse,
    summary="多变量时序预测",
    description="对多变量时间序列数据进行预测，支持多种机器学习算法"
)
async def multivariate_forecast(request: MultivariateForecastRequest) -> MultivariateForecastResponse:
    """
    多变量预测端点
    
    - **data**: 多变量时序数据列表
    - **config**: 配置参数
        - target_column: 目标列名（默认"target"）
        - feature_columns: 特征列名列表（可选，自动推断）
        - algorithm: 算法（lightgbm/xgboost/random_forest/linear_regression）
        - forecast_horizon: 预测步数（默认14）
        - model_name: 模型名称（用于保存和复用）
        - use_model_id: 复用指定ID的模型
        - use_model_name: 复用指定名称的模型
    """
    try:
        logger.info("收到多变量预测请求")
        start_time = time.time()
        
        # 构造请求数据
        request_data = {
            'data': request.data,
            'config': request.config or {}
        }
        
        # 执行预测
        result = predictor.forecast(request_data)
        
        processing_time = time.time() - start_time
        
        if result.get('success'):
            # 格式化预测结果
            predictions = None
            if 'results' in result and result['results']:
                forecast_data = result['results']
                if 'forecast' in forecast_data and 'timestamps' in forecast_data:
                    predictions = [
                        {'timestamp': ts, 'value': val}
                        for ts, val in zip(forecast_data['timestamps'], forecast_data['forecast'])
                    ]
            
            return MultivariateForecastResponse(
                success=True,
                message="预测完成",
                timestamp=datetime.utcnow().isoformat(),
                model_id=result.get('model_id'),
                model_name=result.get('model_name'),
                model_used=result.get('model_used'),
                predictions=predictions,
                metrics=result.get('metrics'),
                reused_model=result.get('reused_model', False),
                processing_time=round(processing_time, 3),
                results=result.get('results'),
                data_analysis=result.get('data_analysis')
            )
        else:
            return MultivariateForecastResponse(
                success=False,
                message=result.get('message', '预测失败'),
                timestamp=datetime.utcnow().isoformat(),
                processing_time=round(processing_time, 3)
            )
            
    except ValueError as e:
        logger.warning(f"多变量预测参数错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"多变量预测失败: {e}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")
