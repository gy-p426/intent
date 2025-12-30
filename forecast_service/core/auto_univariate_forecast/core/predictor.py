# forecast_service/core/auto_univariate_forecast/core/predictor.py
import pandas as pd
import numpy as np
import traceback
import json
import logging

from .data_processor import DataProcessor
from .model_selector import ModelSelector
from ..models.arima_model import ARIMAModel
from ..models.prophet_model import ProphetModel

# 导入字段映射工具
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
from core.field_mapper import FieldMapper

logger = logging.getLogger(__name__)


class AutoUnivariatePredictor:
    """自动单变量预测执行器"""

    def __init__(self):
        self.data_processor = None
        self.model_selector = ModelSelector()
        self.model = None
        self.model_name = None

    def forecast(self, request_data: dict) -> dict:
        """执行自动预测，返回中文字段名"""
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
            
            # 转换数据分析结果为中文字段名
            chinese_analysis = self._convert_analysis_to_chinese(cleaned_analysis)
            
            # 生成通俗易懂的摘要（已使用中文字段名）
            readable_summary = self.generate_readable_summary(forecast_result, chinese_analysis)
            forecast_result['通俗摘要'] = readable_summary

            result = {
                '是否成功': True,
                '预测结果': forecast_result,
                '使用模型': self.model_name,
                '数据分析': chinese_analysis,
                '预测步数': forecast_horizon
            }
            self._validate_serializable(result)
            return result
        except Exception as e:
            return {
                '是否成功': False,
                '消息': f"预测失败: {str(e)}",
                '使用模型': self.model_name,
                '错误详情': {'错误信息': str(e), 'traceback': traceback.format_exc()}
            }

    def _parse_request_data(self, request_data: dict) -> pd.DataFrame:
        """解析请求数据，支持多种格式"""
        data = request_data['data']
        
        # 格式1: {"timestamp": [...], "value": [...]}
        if 'timestamp' in data and 'value' in data:
            df = pd.DataFrame({'timestamp': data['timestamp'], 'value': data['value']})
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
        
        # 格式2: {"sample_data": [{"日期": "...", "出车次数": ...}, ...]} 或类似的对象数组
        elif 'sample_data' in data:
            sample_data = data['sample_data']
            df = self._parse_object_array(sample_data)
        
        # 格式3: 直接是对象数组 [{"日期": "...", "出车次数": ...}, ...]
        elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
            df = self._parse_object_array(data)
        
        else:
            raise ValueError("不支持的数据格式，请使用 {'timestamp': [...], 'value': [...]} 或对象数组格式")
        
        df = df.sort_index()
        if df.index.duplicated().any():
            df = df.groupby(df.index).mean()
        return df
    
    def _parse_object_array(self, data_list: list) -> pd.DataFrame:
        """解析对象数组格式的数据"""
        if not data_list:
            raise ValueError("数据列表为空")
        
        # 获取第一个对象的键名
        first_item = data_list[0]
        keys = list(first_item.keys())
        
        # 常见的时间字段名
        time_field_names = ['timestamp', 'time', 'date', 'datetime', '时间', '日期', '时间戳', 'ds']
        # 常见的值字段名
        value_field_names = ['value', 'y', '值', '数值', '出车次数', '销量', '数量', '金额']
        
        # 自动检测时间字段
        time_field = None
        for name in time_field_names:
            if name in keys:
                time_field = name
                break
        
        # 如果没找到，使用第一个字段作为时间字段
        if time_field is None:
            time_field = keys[0]
            logger.info(f"未找到标准时间字段，使用第一个字段 '{time_field}' 作为时间字段")
        
        # 自动检测值字段
        value_field = None
        for name in value_field_names:
            if name in keys:
                value_field = name
                break
        
        # 如果没找到，使用第二个字段（或非时间字段）作为值字段
        if value_field is None:
            for key in keys:
                if key != time_field:
                    value_field = key
                    break
            logger.info(f"未找到标准值字段，使用字段 '{value_field}' 作为值字段")
        
        if value_field is None:
            raise ValueError("无法确定值字段，请确保数据包含数值列")
        
        # 提取数据
        timestamps = [item[time_field] for item in data_list]
        values = [item[value_field] for item in data_list]
        
        logger.info(f"解析数据: 时间字段='{time_field}', 值字段='{value_field}', 数据点数={len(timestamps)}")
        
        df = pd.DataFrame({'timestamp': timestamps, 'value': values})
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df.set_index('timestamp', inplace=True)
        
        return df

    def _train_and_predict(self, model_name: str, df: pd.DataFrame, params: dict, horizon: int) -> dict:
        """训练模型并预测，返回中文字段名"""
        try:
            # 检测数据频率
            freq = self._detect_frequency(df)
            
            if model_name == 'prophet':
                model = ProphetModel(params)
                model.fit(df)
                result = model.predict(horizon, freq=freq)
            elif model_name == 'arima':
                model = ARIMAModel(params)
                model.fit(df['value'])
                result = model.predict(horizon)
                # ARIMA 模型需要手动生成预测时间点
                if 'forecast_dates' not in result or not result.get('forecast_dates'):
                    last_date = df.index.max()
                    forecast_dates = pd.date_range(start=last_date, periods=horizon + 1, freq=freq)[1:]
                    result['forecast_dates'] = [str(date.strftime('%Y-%m-%d %H:%M:%S')) for date in forecast_dates]
            else:
                raise ValueError(f"不支持的模型类型: {model_name}")

            result = self._clean_data_for_serialization(result)
            
            # 转换预测结果字段名为中文
            chinese_result = self._convert_forecast_result_to_chinese(result)
            chinese_result['训练数据点数'] = int(len(df))
            chinese_result['预测步数'] = int(horizon)
            chinese_result['训练数据范围'] = {
                '开始时间': str(df.index.min().strftime('%Y-%m-%d %H:%M:%S')),
                '结束时间': str(df.index.max().strftime('%Y-%m-%d %H:%M:%S'))
            }
            return chinese_result
        except Exception as e:
            raise RuntimeError(f"模型训练和预测失败: {str(e)}")
    
    def _detect_frequency(self, df: pd.DataFrame) -> str:
        """检测时间序列的频率"""
        try:
            if len(df) < 2:
                return 'D'
            
            # 计算时间差
            time_diffs = df.index.to_series().diff().dropna()
            if len(time_diffs) == 0:
                return 'D'
            
            # 获取最常见的时间差
            median_diff = time_diffs.median()
            
            # 根据时间差判断频率
            if median_diff <= pd.Timedelta(minutes=5):
                return 'T'  # 分钟
            elif median_diff <= pd.Timedelta(hours=2):
                return 'H'  # 小时
            elif median_diff <= pd.Timedelta(days=1.5):
                return 'D'  # 天
            elif median_diff <= pd.Timedelta(days=8):
                return 'W'  # 周
            elif median_diff <= pd.Timedelta(days=35):
                return 'M'  # 月
            else:
                return 'D'  # 默认天
        except Exception:
            return 'D'

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
            json.dumps(data, ensure_ascii=False)
            return True
        except (TypeError, ValueError) as e:
            raise ValueError(f"数据无法序列化为JSON: {str(e)}")

    def _convert_forecast_result_to_chinese(self, result: dict) -> dict:
        """
        将预测结果的英文字段名转换为中文
        
        Args:
            result: 原始预测结果（英文字段名）
            
        Returns:
            转换后的预测结果（中文字段名）
        """
        field_mapping = {
            'forecast': '预测值',
            'timestamps': '时间点',
            'forecast_dates': '时间点',
            'lower_bound': '置信下限',
            'upper_bound': '置信上限',
            'lower': '下限',
            'upper': '上限',
            'confidence_lower': '置信下限',
            'confidence_upper': '置信上限',
            'confidence_interval': '置信区间',
            'training_data_points': '训练数据点数',
            'forecast_horizon': '预测步数',
            'training_date_range': '训练数据范围',
            'start': '开始时间',
            'end': '结束时间',
            'metrics': '评估指标',
            'rmse': '均方根误差',
            'mae': '平均绝对误差',
            'r2': '决定系数',
            'model_order': '模型阶数',
            'model_type': '模型类型',
            'trend': '趋势分量',
            'yhat': '预测值',
            'yhat_lower': '置信下限',
            'yhat_upper': '置信上限',
            'ds': '时间点',
        }
        
        return self._convert_dict_keys(result, field_mapping)
    
    def _convert_analysis_to_chinese(self, analysis: dict) -> dict:
        """
        将数据分析结果的英文字段名转换为中文
        
        Args:
            analysis: 原始数据分析结果（英文字段名）
            
        Returns:
            转换后的数据分析结果（中文字段名）
        """
        field_mapping = {
            'data_points': '数据点数',
            'mean': '均值',
            'std': '标准差',
            'min': '最小值',
            'max': '最大值',
            'outlier_count': '异常值数量',
            'outlier_ratio': '异常值比例',
            'is_normal': '是否正态分布',
            'has_seasonality': '是否有季节性',
            'trend_direction': '趋势方向',
            'missing_ratio': '缺失比例',
            'missing_values': '缺失值数量',
        }
        
        return self._convert_dict_keys(analysis, field_mapping)
    
    def _convert_dict_keys(self, data: any, mapping: dict) -> any:
        """
        递归转换字典的键名
        
        Args:
            data: 要转换的数据
            mapping: 字段映射字典
            
        Returns:
            转换后的数据
        """
        if data is None:
            return None
        
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                new_key = mapping.get(key, key)
                result[new_key] = self._convert_dict_keys(value, mapping)
            return result
        elif isinstance(data, list):
            return [self._convert_dict_keys(item, mapping) for item in data]
        else:
            return data

    def generate_readable_summary(self, result: dict, data_analysis: dict) -> dict:
        """
        生成通俗易懂的预测结果摘要，使用中文字段名
        
        Args:
            result: 预测结果（已转换为中文字段名）
            data_analysis: 数据分析结果（已转换为中文字段名）
            
        Returns:
            包含通俗解释的摘要字典（中文字段名）
        """
        summary = {
            "标题": "🔮 单变量预测分析结果",
            "关键发现": [],
            "详细解释": "",
            "建议": []
        }
        
        try:
            model_used = self.model_name or "自动选择"
            # 适配中文字段名
            forecast_horizon = result.get('预测步数', result.get('forecast_horizon', 0))
            forecast_values = result.get('预测值', result.get('forecast', []))
            
            # 模型选择说明
            model_desc = {
                'prophet': 'Prophet（适合有季节性的数据）',
                'arima': 'ARIMA（适合平稳时序数据）'
            }
            model_name_cn = model_desc.get(model_used, model_used)
            
            summary["关键发现"].append(f"🤖 系统自动选择了 **{model_name_cn}** 模型进行预测")
            summary["关键发现"].append(f"📅 预测了未来 **{forecast_horizon}** 个时间点的数据")
            
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
                
                summary["关键发现"].append(
                    f"{trend_emoji} 预测期内整体呈 **{trend_desc}趋势**，"
                    f"变化幅度约 {abs(change_pct):.1f}%"
                )
            
            # 数据特征分析（适配中文字段名）
            if data_analysis:
                has_seasonality = data_analysis.get('是否有季节性', data_analysis.get('has_seasonality', False))
                trend_direction = data_analysis.get('趋势方向', data_analysis.get('trend_direction', 'unknown'))
                
                if has_seasonality:
                    summary["关键发现"].append("🔄 数据存在周期性规律，预测已考虑这一特征")
                
                trend_map = {
                    'increasing': '上升',
                    'decreasing': '下降',
                    'stable': '平稳'
                }
                if trend_direction in trend_map:
                    summary["关键发现"].append(
                        f"📊 历史数据呈 **{trend_map[trend_direction]}** 趋势"
                    )
            
            # 生成通俗解释
            summary["详细解释"] = (
                f"我们使用 **{model_name_cn}** 对您的数据进行了分析和预测。\n\n"
                f"预测结果包含了未来 {forecast_horizon} 个时间点的预估值。"
            )
            
            # 置信区间说明（适配中文字段名）
            lower_bound = result.get('置信下限', result.get('lower_bound'))
            upper_bound = result.get('置信上限', result.get('upper_bound'))
            if lower_bound and upper_bound:
                summary["详细解释"] += (
                    "\n\n预测结果还包含了**置信区间**（预测范围），"
                    "实际值大概率会落在这个范围内。范围越窄，预测越精确。"
                )
            
            # 生成建议
            summary["建议"].append("💡 预测值仅供参考，建议结合实际业务情况进行决策")
            
            if data_analysis and data_analysis.get('是否有季节性', data_analysis.get('has_seasonality')):
                summary["建议"].append("💡 数据有周期性，建议关注周期性波动对业务的影响")
            
            if len(forecast_values) > 7:
                summary["建议"].append("💡 长期预测不确定性较大，建议定期更新预测")
            
        except Exception as e:
            logger.warning(f"生成可读摘要失败: {e}")
            summary["详细解释"] = "预测已完成，请查看详细数据。"
        
        return summary
