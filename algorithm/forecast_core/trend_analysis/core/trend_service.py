# forecast_modules/trend_analysis/core/trend_service.py
"""
趋势分析核心服务

提供趋势分解和趋势检测功能
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
import warnings
from scipy import stats
from statsmodels.tsa.seasonal import seasonal_decompose, STL
import logging

logger = logging.getLogger(__name__)
warnings.filterwarnings('ignore')


class TrendService:
    """趋势分析服务"""

    def __init__(self):
        pass

    def prepare_data(self, data_points: List[Dict[str, Any]]) -> pd.Series:
        """准备时间序列数据"""
        try:
            df = pd.DataFrame(data_points)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df.set_index('timestamp', inplace=True)
            df.sort_index(inplace=True)
            series = pd.to_numeric(df['value'], errors='coerce')
            
            missing_ratio = series.isnull().sum() / len(series)
            if missing_ratio > 0.1:
                logger.warning(f"数据缺失率较高: {missing_ratio:.2%}")
                series = series.interpolate(method='linear')
            return series
        except Exception as e:
            logger.error(f"数据准备失败: {e}")
            raise ValueError(f"数据格式错误: {e}")

    def analyze_data_characteristics(self, series: pd.Series) -> Dict[str, Any]:
        """分析数据特征"""
        characteristics = {}
        try:
            characteristics['data_points'] = len(series)
            characteristics['mean'] = float(series.mean())
            characteristics['std'] = float(series.std())
            characteristics['min'] = float(series.min())
            characteristics['max'] = float(series.max())

            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)
            IQR = Q3 - Q1
            outliers = series[(series < (Q1 - 1.5 * IQR)) | (series > (Q3 + 1.5 * IQR))]
            characteristics['outlier_count'] = len(outliers)
            characteristics['outlier_ratio'] = len(outliers) / len(series)

            if len(series) <= 5000:
                try:
                    _, p_value = stats.shapiro(series.dropna())
                    characteristics['is_normal'] = p_value > 0.05
                except Exception:
                    characteristics['is_normal'] = False

            if len(series) > 24:
                autocorr = series.autocorr(lag=24) if len(series) > 24 else 0
                characteristics['has_seasonality'] = abs(autocorr) > 0.3

            return characteristics
        except Exception as e:
            logger.error(f"数据特征分析失败: {e}")
            return {}

    def decompose_trend_stl(self, series: pd.Series, period: int, robust: bool = True) -> Dict[str, Any]:
        """使用STL方法进行趋势分解"""
        try:
            logger.info(f"开始STL分解，周期: {period}, 数据长度: {len(series)}")
            if len(series) < 2 * period:
                raise ValueError(f"STL分解需要至少2个完整周期的数据")

            stl_result = STL(series, period=period, robust=robust, seasonal=13).fit()
            
            trend_component = stl_result.trend
            seasonal_component = stl_result.seasonal
            residual_component = stl_result.resid

            seasonal_strength = self._calculate_seasonal_strength(seasonal_component, residual_component)
            trend_strength = self._calculate_trend_strength(trend_component, residual_component)

            result = {
                "trend": self._format_series(trend_component),
                "seasonal": self._format_series(seasonal_component),
                "residual": self._format_series(residual_component),
                "analysis_metrics": {
                    "trend_strength": float(trend_strength),
                    "seasonal_strength": float(seasonal_strength),
                    "residual_variance": float(residual_component.var()),
                    "algorithm": "STL",
                    "period_used": period
                }
            }
            logger.info(f"STL分解完成，季节性强度: {seasonal_strength:.3f}")
            return result
        except Exception as e:
            logger.error(f"STL分解失败: {e}")
            raise

    def decompose_trend_classical(self, series: pd.Series, period: int, model: str = "additive") -> Dict[str, Any]:
        """使用经典方法进行趋势分解"""
        try:
            logger.info(f"开始经典分解，周期: {period}, 模型: {model}")
            if len(series) < 2 * period:
                raise ValueError(f"经典分解需要至少2个完整周期的数据")

            decomposition = seasonal_decompose(series, model=model, period=period, extrapolate_trend='freq')
            
            trend_component = decomposition.trend
            seasonal_component = decomposition.seasonal
            residual_component = decomposition.resid

            seasonal_strength = self._calculate_seasonal_strength(seasonal_component, residual_component)
            trend_strength = self._calculate_trend_strength(trend_component, residual_component)

            result = {
                "trend": self._format_series(trend_component),
                "seasonal": self._format_series(seasonal_component),
                "residual": self._format_series(residual_component),
                "analysis_metrics": {
                    "trend_strength": float(trend_strength),
                    "seasonal_strength": float(seasonal_strength),
                    "residual_variance": float(residual_component.var()),
                    "algorithm": "Classical",
                    "model_type": model,
                    "period_used": period
                }
            }
            logger.info(f"经典分解完成，季节性强度: {seasonal_strength:.3f}")
            return result
        except Exception as e:
            logger.error(f"经典分解失败: {e}")
            raise

    def detect_trend_mann_kendall(self, series: pd.Series, alpha: float = 0.05) -> Dict[str, Any]:
        """Mann-Kendall趋势检验"""
        try:
            logger.info(f"开始Mann-Kendall趋势检验，数据长度: {len(series)}")
            clean_series = series.dropna()
            n = len(clean_series)

            if n < 8:
                raise ValueError(f"Mann-Kendall检验需要至少8个数据点，当前: {n}")

            s = 0
            for i in range(n - 1):
                for j in range(i + 1, n):
                    s += np.sign(clean_series.iloc[j] - clean_series.iloc[i])

            var_s = n * (n - 1) * (2 * n + 5) / 18.0

            if s > 0:
                z = (s - 1) / np.sqrt(var_s)
            elif s < 0:
                z = (s + 1) / np.sqrt(var_s)
            else:
                z = 0

            p_value = 2 * (1 - stats.norm.cdf(abs(z)))

            slopes = []
            for i in range(n - 1):
                for j in range(i + 1, n):
                    slope = (clean_series.iloc[j] - clean_series.iloc[i]) / (j - i)
                    if not np.isnan(slope):
                        slopes.append(slope)
            sen_slope = np.median(slopes) if slopes else 0

            if s > 0:
                trend_direction = "increasing"
            elif s < 0:
                trend_direction = "decreasing"
            else:
                trend_direction = "no trend"

            significant = p_value < alpha

            result = {
                "trend_direction": trend_direction,
                "sen_slope": float(sen_slope),
                "p_value": float(p_value),
                "z_statistic": float(z),
                "s_statistic": int(s),
                "statistical_significance": bool(significant),
                "confidence_level": 1 - alpha,
                "method": "Mann-Kendall",
                "sample_size": n,
                "interpretation": self._interpret_trend_result(trend_direction, significant, sen_slope)
            }
            logger.info(f"Mann-Kendall检验完成: {trend_direction}, p={p_value:.4f}")
            return result
        except Exception as e:
            logger.error(f"Mann-Kendall检验失败: {e}")
            raise

    def detect_trend_linear_regression(self, series: pd.Series, confidence_level: float = 0.95) -> Dict[str, Any]:
        """线性回归趋势检验"""
        try:
            logger.info(f"开始线性回归趋势检验，数据长度: {len(series)}")
            clean_series = series.dropna()
            n = len(clean_series)

            if n < 10:
                raise ValueError(f"线性回归趋势检验需要至少10个数据点，当前: {n}")

            x = np.arange(n)
            y = clean_series.values
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)

            alpha = 1 - confidence_level
            t_critical = stats.t.ppf(1 - alpha / 2, df=n - 2)
            slope_ci = (slope - t_critical * std_err, slope + t_critical * std_err)
            r_squared = r_value ** 2

            if slope > 0:
                trend_direction = "increasing"
            elif slope < 0:
                trend_direction = "decreasing"
            else:
                trend_direction = "no trend"

            significant = p_value < alpha

            result = {
                "trend_direction": str(trend_direction),
                "slope": float(slope),
                "intercept": float(intercept),
                "p_value": float(p_value),
                "r_squared": float(r_squared),
                "std_error": float(std_err),
                "confidence_interval": [float(slope_ci[0]), float(slope_ci[1])],
                "statistical_significance": bool(significant),
                "confidence_level": confidence_level,
                "method": "Linear Regression",
                "sample_size": n,
                "interpretation": self._interpret_trend_result(trend_direction, significant, slope)
            }
            logger.info(f"线性回归检验完成: {trend_direction}, slope={slope:.4f}, p={p_value:.4f}")
            return result
        except Exception as e:
            logger.error(f"线性回归检验失败: {e}")
            raise

    def auto_select_trend_method(self, series: pd.Series) -> str:
        """自动选择趋势检测方法"""
        characteristics = self.analyze_data_characteristics(series)
        if characteristics.get('outlier_ratio', 0) > 0.1:
            return "mann_kendall"
        elif characteristics.get('is_normal', False):
            return "linear_regression"
        elif len(series) < 30:
            return "mann_kendall"
        else:
            return "mann_kendall"

    def auto_select_decomposition_algorithm(self, series: pd.Series, period: int) -> str:
        """自动选择趋势分解算法"""
        characteristics = self.analyze_data_characteristics(series)
        if characteristics.get('outlier_ratio', 0) > 0.05:
            return "stl"
        elif len(series) > 1000:
            return "stl"
        else:
            return "classical"

    def detect_seasonal_period(self, series: pd.Series) -> int:
        """自动检测季节周期"""
        try:
            if len(series) < 50:
                return 24
            max_lag = min(100, len(series) // 2)
            autocorr = []
            for lag in range(1, max_lag + 1):
                corr = series.autocorr(lag=lag)
                if not np.isnan(corr):
                    autocorr.append((lag, corr))
            if autocorr:
                best_lag = max(autocorr, key=lambda x: abs(x[1]))[0]
                common_periods = [24, 12, 7, 30, 365]
                for period in common_periods:
                    if abs(best_lag - period) <= 2:
                        return period
                return best_lag
            return 24
        except Exception as e:
            logger.warning(f"季节周期检测失败: {e}")
            return 24

    def _calculate_seasonal_strength(self, seasonal: pd.Series, residual: pd.Series) -> float:
        try:
            combined_var = (seasonal + residual).var()
            if combined_var == 0:
                return 0.0
            strength = 1 - (residual.var() / combined_var)
            return max(0.0, min(1.0, strength))
        except:
            return 0.0

    def _calculate_trend_strength(self, trend: pd.Series, residual: pd.Series) -> float:
        try:
            combined_var = (trend + residual).var()
            if combined_var == 0:
                return 0.0
            strength = 1 - (residual.var() / combined_var)
            return max(0.0, min(1.0, strength))
        except:
            return 0.0

    def _format_series(self, series: pd.Series) -> List[Dict[str, Any]]:
        if series is None:
            return []
        result = []
        for timestamp, value in series.items():
            if pd.notna(value):
                result.append({
                    "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                    "value": float(value)
                })
        return result

    def _interpret_trend_result(self, direction: str, significant: bool, slope: float) -> str:
        if not significant:
            return "未检测到统计显著的趋势变化"
        direction_map = {"increasing": "上升", "decreasing": "下降", "no trend": "无趋势"}
        direction_cn = direction_map.get(direction, direction)
        if direction == "no trend":
            return "数据基本保持稳定，无明显趋势"
        slope_abs = abs(slope)
        if slope_abs < 0.1:
            magnitude = "微弱"
        elif slope_abs < 1:
            magnitude = "平缓"
        elif slope_abs < 5:
            magnitude = "明显"
        else:
            magnitude = "强烈"
        return f"检测到{magnitude}的{direction_cn}趋势，趋势斜率: {slope:.4f}"
