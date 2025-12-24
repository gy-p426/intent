# forecast_modules/multivariate_forecast/__init__.py
"""
多变量预测模块

使用机器学习算法进行多变量时序预测，支持：
- LightGBM
- XGBoost
- RandomForest
- LinearRegression

使用示例:
    from forecast_modules.multivariate_forecast import router
    app.include_router(router, prefix="/api/v3")

    # 或直接使用预测器
    from forecast_modules.multivariate_forecast import MultivariatePredictor
    predictor = MultivariatePredictor()
    result = predictor.forecast(request_data)
"""
from .router import router
from .schemas import MultivariateForecastRequest, MultivariateForecastResponse
from .core.predictor import MultivariatePredictor
from .core.model_manager import ModelManager

__all__ = ["router", "MultivariateForecastRequest", "MultivariateForecastResponse", 
           "MultivariatePredictor", "ModelManager"]
__version__ = "1.0.0"
