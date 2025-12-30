# forecast_service/core/trend_analysis/core/trend_service.py
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

# 导入字段映射工具
from forecast_service.core.field_mapper import FieldMapper

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
        """分析数据特征，返回中文字段名"""
        characteristics = {}
        try:
            characteristics['数据点数'] = len(series)
            characteristics['均值'] = float(series.mean())
            characteristics['标准差'] = float(series.std())
            characteristics['最小值'] = float(series.min())
            characteristics['最大值'] = float(series.max())

            Q1 = series.quantile(0.25)
            Q3 = series.quantile(0.75)
            IQR = Q3 - Q1
            outliers = series[(series < (Q1 - 1.5 * IQR)) | (series > (Q3 + 1.5 * IQR))]
            characteristics['异常值数量'] = len(outliers)
            characteristics['异常值比例'] = len(outliers) / len(series)

            if len(series) <= 5000:
                try:
                    _, p_value = stats.shapiro(series.dropna())
                    characteristics['是否正态分布'] = p_value > 0.05
                except Exception:
                    characteristics['是否正态分布'] = False

            if len(series) > 24:
                autocorr = series.autocorr(lag=24) if len(series) > 24 else 0
                characteristics['是否有季节性'] = abs(autocorr) > 0.3

            return characteristics
        except Exception as e:
            logger.error(f"数据特征分析失败: {e}")
            return {}

    def decompose_trend_stl(self, series: pd.Series, period: int, robust: bool = True) -> Dict[str, Any]:
        """使用STL方法进行趋势分解，返回中文字段名"""
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
                "趋势分量": self._format_series(trend_component),
                "季节性分量": self._format_series(seasonal_component),
                "残差分量": self._format_series(residual_component),
                "分析指标": {
                    "趋势强度": float(trend_strength),
                    "季节性强度": float(seasonal_strength),
                    "残差方差": float(residual_component.var()),
                    "算法": "STL",
                    "使用周期": period
                }
            }
            logger.info(f"STL分解完成，季节性强度: {seasonal_strength:.3f}")
            return result
        except Exception as e:
            logger.error(f"STL分解失败: {e}")
            raise


    def decompose_trend_classical(self, series: pd.Series, period: int, model: str = "additive") -> Dict[str, Any]:
        """使用经典方法进行趋势分解，返回中文字段名"""
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
                "趋势分量": self._format_series(trend_component),
                "季节性分量": self._format_series(seasonal_component),
                "残差分量": self._format_series(residual_component),
                "分析指标": {
                    "趋势强度": float(trend_strength),
                    "季节性强度": float(seasonal_strength),
                    "残差方差": float(residual_component.var()),
                    "算法": "Classical",
                    "模型类型": model,
                    "使用周期": period
                }
            }
            logger.info(f"经典分解完成，季节性强度: {seasonal_strength:.3f}")
            return result
        except Exception as e:
            logger.error(f"经典分解失败: {e}")
            raise

    def detect_trend_mann_kendall(self, series: pd.Series, alpha: float = 0.05) -> Dict[str, Any]:
        """Mann-Kendall趋势检验，返回中文字段名"""
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
                "趋势方向": trend_direction,
                "Sen斜率": float(sen_slope),
                "p值": float(p_value),
                "Z统计量": float(z),
                "S统计量": int(s),
                "统计显著性": bool(significant),
                "置信水平": 1 - alpha,
                "检测方法": "Mann-Kendall",
                "样本量": n,
                "结果解释": self._interpret_trend_result(trend_direction, significant, sen_slope)
            }
            logger.info(f"Mann-Kendall检验完成: {trend_direction}, p={p_value:.4f}")
            return result
        except Exception as e:
            logger.error(f"Mann-Kendall检验失败: {e}")
            raise

    def detect_trend_linear_regression(self, series: pd.Series, confidence_level: float = 0.95) -> Dict[str, Any]:
        """线性回归趋势检验，返回中文字段名"""
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
                "趋势方向": str(trend_direction),
                "斜率": float(slope),
                "截距": float(intercept),
                "p值": float(p_value),
                "R平方值": float(r_squared),
                "标准误差": float(std_err),
                "置信区间": [float(slope_ci[0]), float(slope_ci[1])],
                "统计显著性": bool(significant),
                "置信水平": confidence_level,
                "检测方法": "Linear Regression",
                "样本量": n,
                "结果解释": self._interpret_trend_result(trend_direction, significant, slope)
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
        """格式化时间序列数据，使用中文字段名"""
        if series is None:
            return []
        result = []
        for timestamp, value in series.items():
            if pd.notna(value):
                result.append({
                    "时间戳": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                    "数值": float(value)
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

    def generate_readable_summary(self, results: Dict[str, Any], analysis_type: str) -> Dict[str, Any]:
        """
        生成通俗易懂的分析结果摘要，使用中文字段名
        
        Args:
            results: 原始分析结果
            analysis_type: 分析类型 (decomposition/detection)
            
        Returns:
            包含通俗解释的摘要字典（中文字段名）
        """
        summary = {
            "标题": "",
            "关键发现": [],
            "详细解释": "",
            "建议": []
        }
        
        if analysis_type == "decomposition":
            summary = self._generate_decomposition_summary(results)
        elif analysis_type == "detection":
            summary = self._generate_detection_summary(results)
        
        return summary
    
    def _generate_decomposition_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """生成趋势分解的通俗摘要，使用中文字段名"""
        summary = {
            "标题": "📊 趋势分解分析结果",
            "关键发现": [],
            "详细解释": "",
            "建议": []
        }
        
        # 适配中文字段名
        metrics = results.get("分析指标", results.get("analysis_metrics", {}))
        trend_strength = metrics.get("趋势强度", metrics.get("trend_strength", 0))
        seasonal_strength = metrics.get("季节性强度", metrics.get("seasonal_strength", 0))
        algorithm = metrics.get("算法", metrics.get("algorithm", "未知"))
        period = metrics.get("使用周期", metrics.get("period_used", 0))
        
        # 趋势强度解读
        if trend_strength >= 0.8:
            trend_desc = "非常明显"
            trend_finding = f"📈 数据存在非常明显的长期趋势（强度：{trend_strength:.0%}），说明数据整体呈现持续的变化方向"
        elif trend_strength >= 0.5:
            trend_desc = "较为明显"
            trend_finding = f"📈 数据存在较为明显的趋势（强度：{trend_strength:.0%}），整体有一定的变化方向"
        elif trend_strength >= 0.3:
            trend_desc = "轻微"
            trend_finding = f"📈 数据存在轻微的趋势（强度：{trend_strength:.0%}），变化方向不太明显"
        else:
            trend_desc = "不明显"
            trend_finding = f"📈 数据趋势不明显（强度：{trend_strength:.0%}），整体较为平稳"
        
        summary["关键发现"].append(trend_finding)
        
        # 季节性强度解读
        if seasonal_strength >= 0.7:
            seasonal_desc = "非常明显"
            seasonal_finding = f"🔄 数据存在非常明显的周期性规律（强度：{seasonal_strength:.0%}），每{period}个时间单位会重复类似的模式"
        elif seasonal_strength >= 0.4:
            seasonal_desc = "较为明显"
            seasonal_finding = f"🔄 数据存在较为明显的周期性（强度：{seasonal_strength:.0%}），周期约为{period}个时间单位"
        elif seasonal_strength >= 0.2:
            seasonal_desc = "轻微"
            seasonal_finding = f"🔄 数据存在轻微的周期性（强度：{seasonal_strength:.0%}），周期约为{period}个时间单位"
        else:
            seasonal_desc = "不明显"
            seasonal_finding = f"🔄 数据周期性不明显（强度：{seasonal_strength:.0%}），没有发现明显的重复规律"
        
        summary["关键发现"].append(seasonal_finding)
        
        # 生成通俗解释
        summary["详细解释"] = (
            f"我们将您的数据分解成了三个部分：\n\n"
            f"1️⃣ **趋势成分**：反映数据的长期走向，您的数据趋势{trend_desc}\n"
            f"2️⃣ **季节性成分**：反映数据的周期性波动，您的数据周期性{seasonal_desc}\n"
            f"3️⃣ **残差成分**：去除趋势和周期后的随机波动\n\n"
            f"使用的分析方法：{algorithm}分解算法"
        )
        
        # 生成建议
        if trend_strength >= 0.5:
            summary["建议"].append("💡 趋势明显，建议关注长期变化方向，可能需要调整策略以适应趋势")
        if seasonal_strength >= 0.4:
            summary["建议"].append(f"💡 周期性明显（周期约{period}个单位），建议在业务规划中考虑这种周期性波动")
        if trend_strength < 0.3 and seasonal_strength < 0.2:
            summary["建议"].append("💡 数据较为平稳，没有明显的趋势或周期性，可能受随机因素影响较大")
        
        return summary
    
    def _generate_detection_summary(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """生成趋势检测的通俗摘要，使用中文字段名"""
        summary = {
            "标题": "🔍 趋势检测分析结果",
            "关键发现": [],
            "详细解释": "",
            "建议": []
        }
        
        # 适配中文字段名
        direction = results.get("趋势方向", results.get("trend_direction", "unknown"))
        significant = results.get("统计显著性", results.get("statistical_significance", False))
        p_value = results.get("p值", results.get("p_value", 1.0))
        confidence = results.get("置信水平", results.get("confidence_level", 0.95))
        method = results.get("检测方法", results.get("method", "未知"))
        
        # 方向映射
        direction_map = {
            "increasing": ("上升", "📈", "增长"),
            "decreasing": ("下降", "📉", "下降"),
            "no trend": ("无明显变化", "➡️", "稳定")
        }
        
        dir_cn, emoji, action = direction_map.get(direction, ("未知", "❓", "变化"))
        
        # 显著性解读
        if significant:
            confidence_pct = confidence * 100
            certainty = "非常确定" if p_value < 0.01 else ("比较确定" if p_value < 0.05 else "有一定把握")
            main_finding = f"{emoji} 检测到数据呈现**{dir_cn}趋势**，我们{certainty}这个结论是可靠的（置信度：{confidence_pct:.0f}%）"
        else:
            main_finding = f"➡️ 未检测到明显的趋势变化，数据整体较为**平稳**"
        
        summary["关键发现"].append(main_finding)
        
        # 添加斜率解读（如果有）- 适配中文字段名
        slope = results.get("斜率", results.get("slope")) or results.get("Sen斜率", results.get("sen_slope"))
        if slope is not None and significant:
            slope_abs = abs(slope)
            if slope_abs < 0.1:
                speed = "缓慢"
            elif slope_abs < 1:
                speed = "平稳"
            elif slope_abs < 5:
                speed = "较快"
            else:
                speed = "快速"
            
            slope_finding = f"📊 {action}速度：{speed}（每个时间单位平均变化 {slope:.4f}）"
            summary["关键发现"].append(slope_finding)
        
        # R²解读（线性回归特有）- 适配中文字段名
        r_squared = results.get("R平方值", results.get("r_squared"))
        if r_squared is not None:
            if r_squared >= 0.8:
                fit_desc = "非常好"
            elif r_squared >= 0.5:
                fit_desc = "较好"
            elif r_squared >= 0.3:
                fit_desc = "一般"
            else:
                fit_desc = "较弱"
            
            r2_finding = f"📐 趋势拟合程度：{fit_desc}（R² = {r_squared:.2%}），表示趋势能解释{r_squared:.0%}的数据变化"
            summary["关键发现"].append(r2_finding)
        
        # 生成通俗解释
        if significant:
            if direction == "increasing":
                summary["详细解释"] = (
                    f"分析结果表明，您的数据整体呈现**上升趋势**。\n\n"
                    f"这意味着随着时间推移，数值在持续增长。"
                    f"我们使用{method}方法进行检验，结果在统计学上是显著的（p值={p_value:.4f}），"
                    f"说明这个上升趋势不太可能是偶然波动造成的。"
                )
            elif direction == "decreasing":
                summary["详细解释"] = (
                    f"分析结果表明，您的数据整体呈现**下降趋势**。\n\n"
                    f"这意味着随着时间推移，数值在持续减少。"
                    f"我们使用{method}方法进行检验，结果在统计学上是显著的（p值={p_value:.4f}），"
                    f"说明这个下降趋势不太可能是偶然波动造成的。"
                )
            else:
                summary["详细解释"] = (
                    f"分析结果表明，您的数据**没有明显的趋势变化**。\n\n"
                    f"数据整体保持相对稳定，没有持续上升或下降的迹象。"
                )
        else:
            summary["详细解释"] = (
                f"分析结果表明，**未能检测到统计显著的趋势**。\n\n"
                f"这可能意味着：\n"
                f"• 数据确实没有明显的趋势，整体较为平稳\n"
                f"• 数据波动较大，趋势被噪声掩盖\n"
                f"• 数据量可能不足以得出确定性结论\n\n"
                f"使用的检验方法：{method}"
            )
        
        # 生成建议
        if significant:
            if direction == "increasing":
                summary["建议"].append("💡 数据呈上升趋势，建议关注增长的可持续性，并分析增长原因")
                summary["建议"].append("💡 可以考虑利用这一趋势进行预测和规划")
            elif direction == "decreasing":
                summary["建议"].append("💡 数据呈下降趋势，建议分析下降原因，评估是否需要采取措施")
                summary["建议"].append("💡 关注下降速度，判断是否会影响业务目标")
        else:
            summary["建议"].append("💡 数据较为平稳，可以继续监测，观察是否会出现新的趋势")
            summary["建议"].append("💡 如果期望看到变化，可能需要采取主动措施来推动")
        
        return summary
    
    def _interpret_p_value(self, p_value: float) -> str:
        """解释p值的含义"""
        if p_value < 0.001:
            return "极其显著（p < 0.001），结论非常可靠"
        elif p_value < 0.01:
            return "非常显著（p < 0.01），结论很可靠"
        elif p_value < 0.05:
            return "显著（p < 0.05），结论较为可靠"
        elif p_value < 0.1:
            return "边缘显著（p < 0.1），结论有一定参考价值"
        else:
            return "不显著（p ≥ 0.1），无法得出确定性结论"
