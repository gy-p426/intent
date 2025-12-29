# forecast_service/api/routes/univariate.py
"""
单变量预测API路由
实现 /api/v1/forecast/univariate 端点
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
from core.auto_univariate_forecast.core import AutoUnivariatePredictor

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/forecast", tags=["单变量预测"])

# 初始化预测器
predictor = AutoUnivariatePredictor()


# ============ 请求/响应模型 ============

class UnivariateForecastRequest(BaseModel):
    """单变量预测请求"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": {
                    "timestamp": ["2024-01-01 00:00", "2024-01-01 01:00", "2024-01-01 02:00"],
                    "value": [100, 105, 110]
                },
                "config": {
                    "forecast_horizon": 24,
                    "include_confidence": True
                }
            }
        }
    )
    
    data: Dict[str, Any] = Field(..., description="时序数据，包含timestamp和value列表")
    config: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {"forecast_horizon": 24, "include_confidence": True},
        description="配置参数"
    )
    
    @field_validator('data')
    @classmethod
    def validate_data_structure(cls, data):
        if 'timestamp' not in data or 'value' not in data:
            raise ValueError("数据必须包含'timestamp'和'value'字段")
        if len(data['timestamp']) != len(data['value']):
            raise ValueError("timestamp和value长度必须一致")
        if len(data['timestamp']) < 10:
            raise ValueError("数据点太少，至少需要10个数据点")
        return data


class UnivariateForecastResponse(BaseModel):
    """单变量预测响应"""
    success: bool = Field(..., description="请求是否成功")
    message: Optional[str] = Field(default=None, description="响应消息")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="响应时间戳")
    model_used: Optional[str] = Field(default=None, description="使用的模型")
    predictions: Optional[List[Dict[str, Any]]] = Field(default=None, description="预测结果")
    metrics: Optional[Dict[str, float]] = Field(default=None, description="模型指标")
    processing_time: Optional[float] = Field(default=None, description="处理时间(秒)")
    results: Optional[Dict[str, Any]] = Field(default=None, description="完整结果")
    data_analysis: Optional[Dict[str, Any]] = Field(default=None, description="数据分析结果")


# ============ API端点 ============

@router.post(
    "/univariate",
    response_model=UnivariateForecastResponse,
    summary="单变量时序预测",
    description="对单变量时间序列数据进行自动预测，自动选择最佳模型"
)
async def univariate_forecast(request: UnivariateForecastRequest) -> UnivariateForecastResponse:
    """
    单变量预测端点
    
    - **data**: 时序数据，包含timestamp和value两个列表
    - **config**: 配置参数
        - forecast_horizon: 预测步数（默认24）
        - include_confidence: 是否包含置信区间
    """
    try:
        logger.info("收到单变量预测请求")
        start_time = time.time()
        
        # 构造请求数据
        request_data = {
            'data': request.data,
            'config': request.config or {"forecast_horizon": 24, "include_confidence": True}
        }
        
        # 执行预测
        result = predictor.forecast(request_data)
        
        processing_time = time.time() - start_time
        
        if result.get('success'):
            # 格式化预测结果
            predictions = None
            if 'results' in result and result['results']:
                forecast_data = result['results']
                if 'forecast' in forecast_data:
                    predictions = []
                    forecast_values = forecast_data.get('forecast', [])
                    timestamps = forecast_data.get('timestamps', [])
                    lower_bounds = forecast_data.get('lower_bound', [])
                    upper_bounds = forecast_data.get('upper_bound', [])
                    
                    for i, value in enumerate(forecast_values):
                        pred_item = {
                            'timestamp': timestamps[i] if i < len(timestamps) else None,
                            'value': value
                        }
                        if i < len(lower_bounds):
                            pred_item['lower_bound'] = lower_bounds[i]
                        if i < len(upper_bounds):
                            pred_item['upper_bound'] = upper_bounds[i]
                        predictions.append(pred_item)
            
            return UnivariateForecastResponse(
                success=True,
                message="预测完成",
                timestamp=datetime.utcnow().isoformat(),
                model_used=result.get('model_used'),
                predictions=predictions,
                metrics=result.get('results', {}).get('metrics'),
                processing_time=round(processing_time, 3),
                results=result.get('results'),
                data_analysis=result.get('data_analysis')
            )
        else:
            return UnivariateForecastResponse(
                success=False,
                message=result.get('message', '预测失败'),
                timestamp=datetime.utcnow().isoformat(),
                model_used=result.get('model_used'),
                processing_time=round(processing_time, 3)
            )
            
    except ValueError as e:
        logger.warning(f"单变量预测参数错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"单变量预测失败: {e}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")
