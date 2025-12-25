# forecast_service/core/auto_univariate_forecast/core/data_processor.py
import pandas as pd
import numpy as np
from statsmodels.tsa.stattools import adfuller, acf
import warnings

warnings.filterwarnings('ignore')


class DataProcessor:
    """数据处理与分析类"""

    def __init__(self, df: pd.DataFrame, value_col: str = 'value'):
        self.df = df.copy()
        self.value_col = value_col
        self.analysis_results = {}

    def process_data(self):
        """数据预处理"""
        self.df[self.value_col] = self.df[self.value_col].interpolate(method='linear')
        Q1 = self.df[self.value_col].quantile(0.25)
        Q3 = self.df[self.value_col].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        self.df[self.value_col] = np.clip(self.df[self.value_col], lower_bound, upper_bound)
        return self.df

    def analyze(self):
        """执行全面的数据特征分析"""
        self.process_data()
        self._check_stationarity()
        self._check_seasonality()
        self._check_trend()
        self._calculate_basic_stats()
        self._convert_to_python_types()
        return self.analysis_results

    def _convert_to_python_types(self):
        for key, value in self.analysis_results.items():
            if isinstance(value, np.bool_):
                self.analysis_results[key] = bool(value)
            elif isinstance(value, np.integer):
                self.analysis_results[key] = int(value)
            elif isinstance(value, np.floating):
                self.analysis_results[key] = None if np.isnan(value) or np.isinf(value) else float(value)
            elif isinstance(value, np.ndarray):
                self.analysis_results[key] = value.tolist()

    def _check_stationarity(self):
        try:
            series = self.df[self.value_col].dropna()
            if len(series) < 10:
                self.analysis_results['is_stationary'] = False
                self.analysis_results['adf_pvalue'] = 1.0
                return
            result = adfuller(series, autolag='AIC')
            pvalue = float(result[1])
            self.analysis_results['is_stationary'] = pvalue <= 0.05
            self.analysis_results['adf_pvalue'] = pvalue
        except Exception:
            self.analysis_results['is_stationary'] = False
            self.analysis_results['adf_pvalue'] = 1.0

    def _check_seasonality(self):
        try:
            series = self.df[self.value_col].dropna()
            if len(series) < 50:
                self.analysis_results['seasonal_strength'] = 0.0
                self.analysis_results['has_seasonality'] = False
                return
            nlags = min(100, len(series) // 2)
            autocorr = acf(series, nlags=nlags, fft=True)
            peaks = [(i, autocorr[i]) for i in range(1, len(autocorr) - 1)
                     if autocorr[i] > autocorr[i - 1] and autocorr[i] > autocorr[i + 1]]
            if peaks:
                max_peak = max(peaks, key=lambda x: x[1])
                seasonal_strength = min(float(max_peak[1]) * 2, 1.0)
                self.analysis_results['seasonal_strength'] = seasonal_strength
                self.analysis_results['has_seasonality'] = seasonal_strength > 0.3
            else:
                self.analysis_results['seasonal_strength'] = 0.0
                self.analysis_results['has_seasonality'] = False
        except Exception:
            self.analysis_results['seasonal_strength'] = 0.0
            self.analysis_results['has_seasonality'] = False

    def _check_trend(self):
        try:
            series = self.df[self.value_col].dropna()
            if len(series) < 10:
                self.analysis_results['has_trend'] = False
                return
            x = np.arange(len(series))
            coef = float(np.polyfit(x, series, 1)[0])
            self.analysis_results['has_trend'] = abs(coef) > 0.001
            self.analysis_results['trend_slope'] = coef
        except Exception:
            self.analysis_results['has_trend'] = False

    def _calculate_basic_stats(self):
        series = self.df[self.value_col].dropna()
        self.analysis_results['data_points'] = len(series)
        self.analysis_results['mean'] = float(series.mean()) if not pd.isna(series.mean()) else None
        self.analysis_results['std'] = float(series.std()) if not pd.isna(series.std()) else None
        self.analysis_results['min'] = float(series.min()) if not pd.isna(series.min()) else None
        self.analysis_results['max'] = float(series.max()) if not pd.isna(series.max()) else None
        self.analysis_results['has_holiday_effect'] = False
