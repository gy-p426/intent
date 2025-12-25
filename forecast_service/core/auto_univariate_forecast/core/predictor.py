# forecast_service/core/auto_univariate_forecast/core/predictor.py
import pandas as pd
import numpy as np
import traceback
import json

from .data_processor import DataProcessor
from .model_selector import ModelSelector
from ..models.arima_model import ARIMAModel
from ..models.prophet_model import ProphetModel


class AutoUnivariatePredictor:
    """自动单变量预测执行器"""

    def __init__(self):
        self.data_processor = None
        self.model_selector = ModelSelector()
        self.model = None
        self.model_name = None

    def forecast(self, request_data: dict) -> dict:
        """执行自动预测"""
        try:
            df = self._parse_request_data(request_data)
            self.data_processor = DataProcessor(df)
            analysis_results = self.data_processor.analyze()

            config = request_data.get('config', {})
            forecast_horizon = config.get('forecast_horizon', 24)

            self.model_name = self.model_selector.select_model(analysis_results, forecast_horizon)
            model_params = self.model_selector.get_model_params(self.model_name, analysis_results)
            forecast_result = self._train_and_predict(self.model_name, df, model_params, forecast_horizon)
            cleaned_analysis = self._clean_data_for_serialization(analysis_results)

            result = {
                'success': True,
                'results': forecast_result,
                'model_used': self.model_name,
                'data_analysis': cleaned_analysis,
                'forecast_horizon': forecast_horizon
            }
            self._validate_serializable(result)
            return result
        except Exception as e:
            return {
                'success': False,
                'message': f"预测失败: {str(e)}",
                'model_used': self.model_name,
                'error_details': {'error': str(e), 'traceback': traceback.format_exc()}
            }

    def _parse_request_data(self, request_data: dict) -> pd.DataFrame:
        data = request_data['data']
        df = pd.DataFrame({'timestamp': data['timestamp'], 'value': data['value']})
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        df = df.sort_index()
        if df.index.duplicated().any():
            df = df.groupby(df.index).mean()
        return df

    def _train_and_predict(self, model_name: str, df: pd.DataFrame, params: dict, horizon: int) -> dict:
        try:
            if model_name == 'prophet':
                model = ProphetModel(params)
                model.fit(df)
                result = model.predict(horizon)
            elif model_name == 'arima':
                model = ARIMAModel(params)
                model.fit(df['value'])
                result = model.predict(horizon)
            else:
                raise ValueError(f"不支持的模型类型: {model_name}")

            result = self._clean_data_for_serialization(result)
            result['training_data_points'] = int(len(df))
            result['forecast_horizon'] = int(horizon)
            result['training_date_range'] = {
                'start': str(df.index.min().strftime('%Y-%m-%d %H:%M:%S')),
                'end': str(df.index.max().strftime('%Y-%m-%d %H:%M:%S'))
            }
            return result
        except Exception as e:
            raise RuntimeError(f"模型训练和预测失败: {str(e)}")

    def _clean_data_for_serialization(self, data):
        if isinstance(data, dict):
            return {key: self._clean_data_for_serialization(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._clean_data_for_serialization(item) for item in data]
        elif isinstance(data, tuple):
            return tuple(self._clean_data_for_serialization(item) for item in data)
        elif isinstance(data, np.bool_):
            return bool(data)
        elif isinstance(data, np.integer):
            return int(data)
        elif isinstance(data, np.floating):
            return None if np.isnan(data) or np.isinf(data) else float(data)
        elif isinstance(data, np.ndarray):
            return self._clean_data_for_serialization(data.tolist())
        elif isinstance(data, pd.Timestamp):
            return str(data)
        elif isinstance(data, (str, int, float, bool, type(None))):
            return data
        else:
            try:
                return str(data)
            except:
                return None

    def _validate_serializable(self, data):
        try:
            json.dumps(data)
            return True
        except (TypeError, ValueError) as e:
            raise ValueError(f"数据无法序列化为JSON: {str(e)}")
