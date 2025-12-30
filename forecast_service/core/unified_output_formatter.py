# forecast_service/core/unified_output_formatter.py
"""
统一输出格式化器

将各算法的原始返回结果转换为统一的两字段格式：
- 解释：面向用户的通俗分析结论（中文）
- 算法结果：算法特定的详细数据
"""
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class UnifiedOutputFormatter:
    """统一输出格式化器"""
    
    def format_trend_decomposition(self, raw_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化趋势分解结果
        
        Args:
            raw_result: 原始趋势分解结果，包含以下字段：
                - 数据特征: 数据统计信息
                - 分解结果: 趋势、季节性、残差分量
                - 通俗摘要: 可读性摘要
                - 分析类型: "decomposition"
                - 使用算法: 算法名称
                - 使用周期: 季节周期
                
        Returns:
            统一格式的输出：{"解释": str, "算法结果": dict}
        """
        try:
            # 提取通俗摘要并生成解释文本
            readable_summary = raw_result.get('通俗摘要', {})
            explanation = self._merge_summary_to_explanation(readable_summary)
            
            # 构建算法结果
            algorithm_result = {
                "分析类型": raw_result.get('分析类型', 'decomposition'),
                "数据特征": raw_result.get('数据特征', {}),
                "分解结果": raw_result.get('分解结果', {}),
                "使用算法": raw_result.get('使用算法', ''),
                "使用周期": raw_result.get('使用周期', 0),
                "数据点数": raw_result.get('数据特征', {}).get('数据点数', 0)
            }
            
            return {
                "解释": explanation,
                "算法结果": algorithm_result
            }
        except Exception as e:
            logger.error(f"格式化趋势分解结果失败: {e}")
            return self._format_error_response(str(e))
    
    def format_trend_detection(self, raw_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化趋势检测结果
        
        Args:
            raw_result: 原始趋势检测结果，包含以下字段：
                - 数据特征: 数据统计信息
                - 检测结果: 趋势方向、斜率、p值等
                - 通俗摘要: 可读性摘要
                - 分析类型: "detection"
                - 使用方法: 检测方法名称
                
        Returns:
            统一格式的输出：{"解释": str, "算法结果": dict}
        """
        try:
            # 提取通俗摘要并生成解释文本
            readable_summary = raw_result.get('通俗摘要', {})
            explanation = self._merge_summary_to_explanation(readable_summary)
            
            # 构建算法结果
            algorithm_result = {
                "分析类型": raw_result.get('分析类型', 'detection'),
                "数据特征": raw_result.get('数据特征', {}),
                "检测结果": raw_result.get('检测结果', {}),
                "使用方法": raw_result.get('使用方法', ''),
                "数据点数": raw_result.get('数据特征', {}).get('数据点数', 0)
            }
            
            return {
                "解释": explanation,
                "算法结果": algorithm_result
            }
        except Exception as e:
            logger.error(f"格式化趋势检测结果失败: {e}")
            return self._format_error_response(str(e))
    
    def format_univariate_forecast(self, raw_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化单变量预测结果
        
        Args:
            raw_result: 原始单变量预测结果，包含以下字段：
                - 是否成功: bool
                - 预测结果: 预测值、时间点、置信区间等（内含通俗摘要）
                - 使用模型: 模型名称
                - 数据分析: 数据特征统计
                - 预测步数: 预测的时间点数量
                
        Returns:
            统一格式的输出：{"解释": str, "算法结果": dict}
        """
        try:
            # 检查是否成功
            if not raw_result.get('是否成功', False):
                error_msg = raw_result.get('消息', '预测失败')
                return self._format_error_response(error_msg)
            
            # 从预测结果中提取通俗摘要
            forecast_result = raw_result.get('预测结果', {})
            readable_summary = forecast_result.get('通俗摘要', {})
            explanation = self._merge_summary_to_explanation(readable_summary)
            
            # 构建算法结果（移除通俗摘要，避免重复）
            clean_forecast_result = {k: v for k, v in forecast_result.items() if k != '通俗摘要'}
            
            algorithm_result = {
                "是否成功": True,
                "预测结果": clean_forecast_result,
                "使用模型": raw_result.get('使用模型', ''),
                "数据分析": raw_result.get('数据分析', {}),
                "预测步数": raw_result.get('预测步数', 0)
            }
            
            return {
                "解释": explanation,
                "算法结果": algorithm_result
            }
        except Exception as e:
            logger.error(f"格式化单变量预测结果失败: {e}")
            return self._format_error_response(str(e))
    
    def format_multivariate_forecast(self, raw_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        格式化多变量预测结果
        
        Args:
            raw_result: 原始多变量预测结果，包含以下字段：
                - 是否成功: bool
                - 预测结果: 预测值、时间点、预测期数等（内含通俗摘要）
                - 使用模型: 模型名称
                - 模型ID: 模型标识
                - 评估指标: RMSE、MAE、R²
                - 数据分析: 数据特征统计
                - 是否复用模型: bool
                
        Returns:
            统一格式的输出：{"解释": str, "算法结果": dict}
        """
        try:
            # 检查是否成功
            if not raw_result.get('是否成功', False):
                error_msg = raw_result.get('消息', '预测失败')
                return self._format_error_response(error_msg)
            
            # 从预测结果中提取通俗摘要
            forecast_result = raw_result.get('预测结果', {})
            readable_summary = forecast_result.get('通俗摘要', {})
            explanation = self._merge_summary_to_explanation(readable_summary)
            
            # 构建算法结果（移除通俗摘要，避免重复）
            clean_forecast_result = {k: v for k, v in forecast_result.items() if k != '通俗摘要'}
            
            algorithm_result = {
                "是否成功": True,
                "预测结果": clean_forecast_result,
                "使用模型": raw_result.get('使用模型', ''),
                "模型ID": raw_result.get('模型ID', ''),
                "模型名称": raw_result.get('模型名称', ''),
                "数据分析": raw_result.get('数据分析', {}),
                "评估指标": raw_result.get('评估指标', {}),
                "是否复用模型": raw_result.get('是否复用模型', False)
            }
            
            return {
                "解释": explanation,
                "算法结果": algorithm_result
            }
        except Exception as e:
            logger.error(f"格式化多变量预测结果失败: {e}")
            return self._format_error_response(str(e))

    def _generate_explanation(self, analysis_type: str, key_data: Dict[str, Any]) -> str:
        """
        根据分析类型和关键数据生成通俗解释文本
        
        Args:
            analysis_type: 分析类型 (decomposition/detection/univariate/multivariate)
            key_data: 关键数据字典
            
        Returns:
            通俗易懂的解释文本
        """
        try:
            if analysis_type == "decomposition":
                return self._generate_decomposition_explanation(key_data)
            elif analysis_type == "detection":
                return self._generate_detection_explanation(key_data)
            elif analysis_type == "univariate":
                return self._generate_univariate_explanation(key_data)
            elif analysis_type == "multivariate":
                return self._generate_multivariate_explanation(key_data)
            else:
                return "分析已完成，请查看详细数据。"
        except Exception as e:
            logger.warning(f"生成解释文本失败: {e}")
            return "分析已完成，请查看详细数据。"
    
    def _merge_summary_to_explanation(self, summary: Dict[str, Any]) -> str:
        """
        将通俗摘要合并为单一的解释文本
        
        Args:
            summary: 通俗摘要字典，包含：
                - 标题: 分析结果标题
                - 关键发现: 关键发现列表
                - 详细解释: 详细解释文本
                - 建议: 建议列表
                
        Returns:
            合并后的解释文本（150-400字）
        """
        if not summary:
            return "分析已完成，请查看详细数据。"
        
        parts = []
        
        # 添加标题
        title = summary.get('标题', '')
        if title:
            # 移除 emoji 后的标题作为开头
            clean_title = title.replace('📊', '').replace('🔍', '').replace('🔮', '').replace('🎯', '').strip()
            parts.append(f"【{clean_title}】")
        
        # 添加关键发现
        key_findings = summary.get('关键发现', [])
        if key_findings:
            parts.append("\n\n📌 关键发现：")
            for i, finding in enumerate(key_findings[:4], 1):  # 最多4条
                # 清理 emoji 前缀，保持简洁
                clean_finding = self._clean_emoji_prefix(finding)
                parts.append(f"\n{i}. {clean_finding}")
        
        # 添加详细解释（精简版）
        explanation = summary.get('详细解释', '')
        if explanation:
            # 截取前200字符，避免过长
            short_explanation = explanation[:200]
            if len(explanation) > 200:
                short_explanation += "..."
            parts.append(f"\n\n💡 分析说明：\n{short_explanation}")
        
        # 添加建议
        recommendations = summary.get('建议', [])
        if recommendations:
            parts.append("\n\n📋 建议：")
            for rec in recommendations[:2]:  # 最多2条建议
                clean_rec = self._clean_emoji_prefix(rec)
                parts.append(f"\n• {clean_rec}")
        
        result = ''.join(parts)
        
        # 确保结果不为空
        if not result.strip():
            return "分析已完成，请查看详细数据。"
        
        return result
    
    def _clean_emoji_prefix(self, text: str) -> str:
        """清理文本开头的 emoji"""
        if not text:
            return text
        # 常见的 emoji 前缀
        emoji_prefixes = ['📈', '📉', '➡️', '🔄', '📊', '📐', '🤖', '📅', '⭐', '💡', '❓']
        result = text.strip()
        for emoji in emoji_prefixes:
            if result.startswith(emoji):
                result = result[len(emoji):].strip()
        return result
    
    def _generate_decomposition_explanation(self, key_data: Dict[str, Any]) -> str:
        """生成趋势分解的解释文本"""
        trend_strength = key_data.get('trend_strength', 0)
        seasonal_strength = key_data.get('seasonal_strength', 0)
        algorithm = key_data.get('algorithm', '未知')
        period = key_data.get('period', 0)
        
        # 趋势强度描述
        if trend_strength >= 0.8:
            trend_desc = "非常明显的长期趋势"
        elif trend_strength >= 0.5:
            trend_desc = "较为明显的趋势"
        elif trend_strength >= 0.3:
            trend_desc = "轻微的趋势"
        else:
            trend_desc = "趋势不明显"
        
        # 季节性强度描述
        if seasonal_strength >= 0.7:
            seasonal_desc = f"非常明显的周期性规律（周期约{period}个时间单位）"
        elif seasonal_strength >= 0.4:
            seasonal_desc = f"较为明显的周期性（周期约{period}个时间单位）"
        elif seasonal_strength >= 0.2:
            seasonal_desc = f"轻微的周期性（周期约{period}个时间单位）"
        else:
            seasonal_desc = "周期性不明显"
        
        return (
            f"【趋势分解分析结果】\n\n"
            f"使用{algorithm}算法对数据进行了分解分析。\n\n"
            f"📌 关键发现：\n"
            f"1. 数据存在{trend_desc}（强度：{trend_strength:.0%}）\n"
            f"2. 数据存在{seasonal_desc}（强度：{seasonal_strength:.0%}）\n\n"
            f"💡 数据已被分解为趋势、季节性和残差三个成分，可用于进一步分析。"
        )
    
    def _generate_detection_explanation(self, key_data: Dict[str, Any]) -> str:
        """生成趋势检测的解释文本"""
        direction = key_data.get('direction', 'unknown')
        significant = key_data.get('significant', False)
        p_value = key_data.get('p_value', 1.0)
        method = key_data.get('method', '未知')
        
        direction_map = {
            'increasing': '上升',
            'decreasing': '下降',
            'no trend': '无明显变化'
        }
        direction_cn = direction_map.get(direction, '未知')
        
        if significant:
            certainty = "非常确定" if p_value < 0.01 else ("比较确定" if p_value < 0.05 else "有一定把握")
            return (
                f"【趋势检测分析结果】\n\n"
                f"使用{method}方法进行趋势检验。\n\n"
                f"📌 关键发现：\n"
                f"检测到数据呈现{direction_cn}趋势，我们{certainty}这个结论是可靠的。\n\n"
                f"💡 建议关注趋势变化，并分析可能的原因。"
            )
        else:
            return (
                f"【趋势检测分析结果】\n\n"
                f"使用{method}方法进行趋势检验。\n\n"
                f"📌 关键发现：\n"
                f"未检测到统计显著的趋势变化，数据整体较为平稳。\n\n"
                f"💡 可以继续监测，观察是否会出现新的趋势。"
            )
    
    def _generate_univariate_explanation(self, key_data: Dict[str, Any]) -> str:
        """生成单变量预测的解释文本"""
        model = key_data.get('model', '自动选择')
        horizon = key_data.get('horizon', 0)
        trend = key_data.get('trend', 'stable')
        
        trend_map = {'up': '上升', 'down': '下降', 'stable': '平稳'}
        trend_cn = trend_map.get(trend, '平稳')
        
        return (
            f"【单变量预测分析结果】\n\n"
            f"使用{model}模型进行预测。\n\n"
            f"📌 关键发现：\n"
            f"1. 预测了未来{horizon}个时间点的数据\n"
            f"2. 预测期内整体呈{trend_cn}趋势\n\n"
            f"💡 预测值仅供参考，建议结合实际业务情况进行决策。"
        )
    
    def _generate_multivariate_explanation(self, key_data: Dict[str, Any]) -> str:
        """生成多变量预测的解释文本"""
        model = key_data.get('model', '未知')
        r2 = key_data.get('r2', 0)
        feature_count = key_data.get('feature_count', 0)
        horizon = key_data.get('horizon', 0)
        
        if r2 >= 0.9:
            accuracy_desc = "非常高"
        elif r2 >= 0.7:
            accuracy_desc = "较高"
        elif r2 >= 0.5:
            accuracy_desc = "中等"
        else:
            accuracy_desc = "一般"
        
        return (
            f"【多变量预测分析结果】\n\n"
            f"使用{model}模型，综合{feature_count}个特征变量进行预测。\n\n"
            f"📌 关键发现：\n"
            f"1. 预测了未来{horizon}个时间点的数据\n"
            f"2. 模型准确度{accuracy_desc}（R² = {r2:.1%}）\n\n"
            f"💡 预测值会随时间推移而累积误差，建议定期更新模型。"
        )
    
    def _format_error_response(self, error_message: str) -> Dict[str, Any]:
        """
        格式化错误响应
        
        Args:
            error_message: 错误信息
            
        Returns:
            统一格式的错误响应
        """
        return {
            "解释": f"分析过程中遇到问题：{error_message}。请检查输入数据或稍后重试。",
            "算法结果": {
                "是否成功": False,
                "错误信息": error_message,
                "错误类型": "处理错误"
            }
        }


# 创建全局实例，方便导入使用
unified_formatter = UnifiedOutputFormatter()
