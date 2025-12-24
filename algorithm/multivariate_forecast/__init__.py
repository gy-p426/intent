"""
Multivariate Forecast Algorithm

多变量时间序列预测算法实现 - 支持LightGBM、XGBoost、RandomForest、LinearRegression
"""

from .extractor import MultivariateForecastExtractor
from .processor import MultivariateForecastProcessor
from .config import MULTIVARIATE_FORECAST_CONFIG

__all__ = [
    'MultivariateForecastExtractor',
    'MultivariateForecastProcessor',
    'MULTIVARIATE_FORECAST_CONFIG'
]
