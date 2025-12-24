"""
Trend Analysis Algorithm

趋势分析算法实现 - 包括趋势分解和趋势检测
"""

from .extractor import TrendAnalysisExtractor
from .processor import TrendAnalysisProcessor
from .config import TREND_ANALYSIS_CONFIG

__all__ = [
    'TrendAnalysisExtractor',
    'TrendAnalysisProcessor',
    'TREND_ANALYSIS_CONFIG'
]
