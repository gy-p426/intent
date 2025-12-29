# forecast_service/core/auto_univariate_forecast/models/arima_model.py
import pandas as pd
import numpy as np
from pmdarima import auto_arima
from statsmodels.tsa.arima.model import ARIMA as StatsARIMA
import warnings

warnings.filterwarnings('ignore')


class ARIMAModel:
    """ARIMA模型预测器"""

    def __init__(self, params: dict = None):
        self.params = params or {}
        self.model = None
        self.order = self.params.get('order', (1, 0, 0))
        self.is_fitted = False

    def fit(self, series: pd.Series):
        """训练ARIMA模型"""
        try:
            series = pd.to_numeric(series, errors='coerce').dropna()
            if len(series) < 10:
                raise ValueError("数据点太少，无法训练ARIMA模型")

            if self.params.get('auto_select', True):
                try:
                    self.model = auto_arima(
                        series, start_p=0, start_q=0, max_p=3, max_q=3, d=None,
                        seasonal=False, trace=False, error_action='ignore',
                        suppress_warnings=True, stepwise=True, n_fits=10
                    )
                    if self.model is not None:
                        self.order = self.model.order
                except Exception:
                    self.model = StatsARIMA(series, order=self.order).fit()
            else:
                self.model = StatsARIMA(series, order=self.order).fit()

            self.is_fitted = True
            return self
        except Exception as e:
            raise RuntimeError(f"ARIMA模型训练失败: {str(e)}")

    def predict(self, horizon: int) -> dict:
        """进行预测"""
        if not self.is_fitted or self.model is None:
            raise ValueError("模型未训练，请先调用fit方法")

        try:
            if hasattr(self.model, 'predict_in_sample'):
                forecast, conf_int = self.model.predict(n_periods=horizon, return_conf_int=True, alpha=0.05)
            else:
                forecast_result = self.model.get_forecast(steps=horizon)
                forecast = forecast_result.predicted_mean
                conf_int = forecast_result.conf_int(alpha=0.05)

            forecast_list = [float(x) for x in forecast.tolist()]
            conf_int_list = conf_int.tolist() if hasattr(conf_int, 'tolist') else [[float(l), float(u)] for l, u in conf_int]

            return {
                'forecast': forecast_list,
                'confidence_interval': conf_int_list,
                'model_order': str(self.order),
                'model_type': 'ARIMA'
            }
        except Exception as e:
            raise RuntimeError(f"ARIMA预测失败: {str(e)}")
