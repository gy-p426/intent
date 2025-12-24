# forecast_modules/auto_univariate_forecast/core/model_selector.py


class ModelSelector:
    """根据数据特征自动选择预测模型"""

    @staticmethod
    def select_model(data_analysis: dict, forecast_horizon: int = 24) -> str:
        """自动选择预测模型"""
        seasonal_strength = data_analysis.get('seasonal_strength', 0)
        has_holiday_effect = data_analysis.get('has_holiday_effect', False)
        is_stationary = data_analysis.get('is_stationary', False)
        data_points = data_analysis.get('data_points', 0)

        if data_points < 50:
            return "arima"
        if seasonal_strength > 0.4 and has_holiday_effect:
            return "prophet"
        elif is_stationary and forecast_horizon <= 50:
            return "arima"
        elif seasonal_strength > 0.3:
            return "prophet"
        else:
            return "arima"

    @staticmethod
    def get_model_params(model_name: str, data_analysis: dict) -> dict:
        """获取选定模型的推荐参数"""
        data_points = data_analysis.get('data_points', 100)

        if model_name == "prophet":
            return {
                'seasonality_mode': 'additive',
                'changepoint_prior_scale': 0.05,
                'holidays_prior_scale': 10.0,
                'daily_seasonality': data_analysis.get('has_seasonality', False),
                'weekly_seasonality': True,
                'yearly_seasonality': data_points > 365,
                'uncertainty_samples': False
            }
        else:
            order = (1, 0, 0) if data_points < 100 else (2, 1, 1)
            return {
                'order': order,
                'seasonal_order': (0, 0, 0, 0),
                'trend': 'c',
                'auto_select': True
            }
