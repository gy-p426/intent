# forecast_service/core/auto_univariate_forecast/__init__.py
"""
自动单变量预测模块

根据数据特征自动选择 ARIMA 或 Prophet 算法进行预测。

使用示例:
    from forecast_service.core.auto_univariate_forecast import router
    app.include_router(router, prefix="/api/v1")

    # 或直接使用预测器
    from forecast_service.core.auto_univariate_forecast import AutoUnivariatePredictor
    predictor = AutoUnivariatePredictor()
    result = predictor.forecast(request_data)
"""
from .router import router
from .schemas import ForecastRequest, ForecastResponse
from .core.predictor import AutoUnivariatePredictor

__all__ = ["router", "ForecastRequest", "ForecastResponse", "AutoUnivariatePredictor"]
__version__ = "1.0.0"
