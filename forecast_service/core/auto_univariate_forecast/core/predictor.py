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
            
            # 生成通俗易懂的摘要
            readable_summary = self.generate_readable_summary(forecast_result, cleaned_analysis)
            forecast_result['readable_summary'] = readable_summary

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

    def generate_readable_summary(self, result: dict, data_analysis: dict) -> dict:
        """
        生成通俗易懂的预测结果摘要
        
        Args:
            result: 预测结果
            data_analysis: 数据分析结果
            
        Returns:
            包含通俗解释的摘要字典
        """
        summary = {
            "title": "🔮 单变量预测分析结果",
            "key_findings": [],
            "explanation": "",
            "recommendations": []
        }
        
        try:
            model_used = self.model_name or "自动选择"
            forecast_horizon = result.get('forecast_horizon', 0)
            forecast_values = result.get('forecast', [])
            
            # 模型选择说明
            model_desc = {
                'prophet': 'Prophet（适合有季节性的数据）',
                'arima': 'ARIMA（适合平稳时序数据）'
            }
            model_name_cn = model_desc.get(model_used, model_used)
            
            summary["key_findings"].append(f"🤖 系统自动选择了 **{model_name_cn}** 模型进行预测")
            summary["key_findings"].append(f"📅 预测了未来 **{forecast_horizon}** 个时间点的数据")
            
            # 预测趋势分析
            if len(forecast_values) >= 2:
                first_val = forecast_values[0]
                last_val = forecast_values[-1]
                change = last_val - first_val
                change_pct = (change / first_val * 100) if first_val != 0 else 0
                
                if change > 0:
                    trend_emoji = "📈"
                    trend_desc = "上升"
                elif change < 0:
                    trend_emoji = "📉"
                    trend_desc = "下降"
                else:
                    trend_emoji = "➡️"
                    trend_desc = "平稳"
                
                summary["key_findings"].append(
                    f"{trend_emoji} 预测期内整体呈 **{trend_desc}趋势**，"
                    f"变化幅度约 {abs(change_pct):.1f}%"
                )
            
            # 数据特征分析
            if data_analysis:
                has_seasonality = data_analysis.get('has_seasonality', False)
                trend_direction = data_analysis.get('trend_direction', 'unknown')
                
                if has_seasonality:
                    summary["key_findings"].append("🔄 数据存在周期性规律，预测已考虑这一特征")
                
                trend_map = {
                    'increasing': '上升',
                    'decreasing': '下降',
                    'stable': '平稳'
                }
                if trend_direction in trend_map:
                    summary["key_findings"].append(
                        f"📊 历史数据呈 **{trend_map[trend_direction]}** 趋势"
                    )
            
            # 生成通俗解释
            summary["explanation"] = (
                f"我们使用 **{model_name_cn}** 对您的数据进行了分析和预测。\n\n"
                f"预测结果包含了未来 {forecast_horizon} 个时间点的预估值。"
            )
            
            # 置信区间说明
            if result.get('lower_bound') and result.get('upper_bound'):
                summary["explanation"] += (
                    "\n\n预测结果还包含了**置信区间**（预测范围），"
                    "实际值大概率会落在这个范围内。范围越窄，预测越精确。"
                )
            
            # 生成建议
            summary["recommendations"].append("💡 预测值仅供参考，建议结合实际业务情况进行决策")
            
            if data_analysis and data_analysis.get('has_seasonality'):
                summary["recommendations"].append("💡 数据有周期性，建议关注周期性波动对业务的影响")
            
            if len(forecast_values) > 7:
                summary["recommendations"].append("💡 长期预测不确定性较大，建议定期更新预测")
            
        except Exception as e:
            logger.warning(f"生成可读摘要失败: {e}")
            summary["explanation"] = "预测已完成，请查看详细数据。"
        
        return summary
