# forecast_service/core/auto_univariate_forecast/router.py
"""自动单变量预测路由"""
from fastapi import APIRouter, HTTPException
import time

from .schemas import ForecastRequest, ForecastResponse
from .core.predictor import AutoUnivariatePredictor

router = APIRouter(prefix="/forecast", tags=["时序预测"], responses={404: {"description": "未找到"}})
_predictor = None


def get_predictor():
    global _predictor
    if _predictor is None:
        _predictor = AutoUnivariatePredictor()
    return _predictor


@router.post("/univariate", response_model=ForecastResponse)
async def auto_univariate_forecast(request: ForecastRequest):
    """自动单变量预测"""
    try:
        start_time = time.time()
        predictor = get_predictor()
        result = predictor.forecast(request.dict())
        result['processing_time'] = time.time() - start_time

        if not result.get('success'):
            raise HTTPException(status_code=400, detail=result.get('message', '预测失败'))
        return ForecastResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, detail=f"服务错误: {str(e)}")


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "auto_univariate_forecast", "timestamp": time.time()}
