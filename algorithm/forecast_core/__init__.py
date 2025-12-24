# forecast_modules/__init__.py
"""
时间序列预测模块包

包含三个独立可用的预测模块：
- trend_analysis: 趋势分析（分解和检测）
- auto_univariate_forecast: 自动单变量预测（ARIMA/Prophet）
- multivariate_forecast: 多变量预测（LightGBM/XGBoost/RandomForest/LinearRegression）

使用方式：

1. 作为 FastAPI 路由集成：
    from fastapi import FastAPI
    from forecast_modules.trend_analysis import router as trend_router
    from forecast_modules.auto_univariate_forecast import router as forecast_router
    from forecast_modules.multivariate_forecast import router as multivariate_router
    
    app = FastAPI()
    app.include_router(trend_router, prefix="/api/v1")
    app.include_router(forecast_router, prefix="/api/v2")
    app.include_router(multivariate_router, prefix="/api/v3")

2. 直接调用核心类：
    from forecast_modules.trend_analysis import TrendService
    from forecast_modules.auto_univariate_forecast import AutoUnivariatePredictor
    from forecast_modules.multivariate_forecast import MultivariatePredictor
"""

__version__ = "1.0.0"
__author__ = "Time Series Forecast System"
