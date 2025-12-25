# forecast_modules/auto_univariate_forecast/models/prophet_model.py
import pandas as pd
import numpy as np
from prophet import Prophet
import logging

logging.getLogger('prophet').setLevel(logging.WARNING)
logging.getLogger('cmdstanpy').setLevel(logging.WARNING)


class ProphetModel:
    """Prophet模型预测器"""

    def __init__(self, params: dict = None):
        self.params = params or {}
        self.model = None
        self.is_fitted = False

    def _prepare_data(self, df: pd.DataFrame):
        """准备Prophet所需的数据格式"""
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("DataFrame索引必须是DatetimeIndex")

        prophet_df = df.reset_index()
        if 'timestamp' in prophet_df.columns:
            prophet_df = prophet_df.rename(columns={'timestamp': 'ds'})
        elif prophet_df.columns[0] == 'index':
            prophet_df = prophet_df.rename(columns={'index': 'ds'})

        if 'value' in prophet_df.columns:
            prophet_df = prophet_df.rename(columns={'value': 'y'})
        elif len(prophet_df.columns) > 1:
            prophet_df = prophet_df.rename(columns={prophet_df.columns[1]: 'y'})

        prophet_df = prophet_df[['ds', 'y']].copy()
        prophet_df['ds'] = pd.to_datetime(prophet_df['ds'])
        prophet_df['y'] = pd.to_numeric(prophet_df['y'], errors='coerce')
        prophet_df = prophet_df.dropna()

        if len(prophet_df) < 10:
            raise ValueError("有效数据点太少，无法训练Prophet模型")
        return prophet_df

    def fit(self, df: pd.DataFrame):
        """训练Prophet模型"""
        try:
            prophet_df = self._prepare_data(df)
            self.model = Prophet(
                seasonality_mode=self.params.get('seasonality_mode', 'additive'),
                changepoint_prior_scale=self.params.get('changepoint_prior_scale', 0.05),
                holidays_prior_scale=self.params.get('holidays_prior_scale', 10.0),
                daily_seasonality=self.params.get('daily_seasonality', False),
                weekly_seasonality=self.params.get('weekly_seasonality', True),
                yearly_seasonality=self.params.get('yearly_seasonality', False),
                uncertainty_samples=self.params.get('uncertainty_samples', False)
            )
            self.model.fit(prophet_df)
            self.is_fitted = True
            return self
        except Exception as e:
            raise RuntimeError(f"Prophet模型训练失败: {str(e)}")

    def predict(self, horizon: int, freq: str = 'H') -> dict:
        """进行预测"""
        if not self.is_fitted or self.model is None:
            raise ValueError("模型未训练，请先调用fit方法")

        try:
            future = self.model.make_future_dataframe(periods=horizon, freq=freq, include_history=False)
            forecast_df = self.model.predict(future)

            result = {
                'forecast': [float(x) for x in forecast_df['yhat'].tolist()],
                'forecast_dates': [str(date) for date in forecast_df['ds'].dt.strftime('%Y-%m-%d %H:%M:%S').tolist()],
                'model_type': 'Prophet'
            }

            if 'yhat_lower' in forecast_df.columns and 'yhat_upper' in forecast_df.columns:
                result['confidence_interval'] = {
                    'lower': [float(x) for x in forecast_df['yhat_lower'].tolist()],
                    'upper': [float(x) for x in forecast_df['yhat_upper'].tolist()]
                }
            if 'trend' in forecast_df.columns:
                result['trend'] = [float(x) for x in forecast_df['trend'].tolist()]
            return result
        except Exception as e:
            raise RuntimeError(f"Prophet预测失败: {str(e)}")
