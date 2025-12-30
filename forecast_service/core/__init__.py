# forecast_service/core/__init__.py
"""
预测微服务核心模块

包含:
- trend_analysis: 趋势分析模块
- auto_univariate_forecast: 单变量预测模块
- multivariate_forecast: 多变量预测模块
- unified_output_formatter: 统一输出格式化器
"""

from .unified_output_formatter import UnifiedOutputFormatter, unified_formatter

__all__ = ['UnifiedOutputFormatter', 'unified_formatter']
