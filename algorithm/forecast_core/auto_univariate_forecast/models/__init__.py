# forecast_modules/auto_univariate_forecast/models/__init__.py
"""预测模型实现"""
from .arima_model import ARIMAModel
from .prophet_model import ProphetModel

__all__ = ["ARIMAModel", "ProphetModel"]
