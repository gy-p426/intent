"""
Multi Analysis Algorithm Module

统一多算法分析模块，支持周期性分析、环比分析、同比分析、定基比分析
"""

from .extractor import MultiAnalysisExtractor
from .processor import MultiAnalysisProcessor
from .config import MULTI_ANALYSIS_CONFIG

__all__ = [
    'MultiAnalysisExtractor',
    'MultiAnalysisProcessor', 
    'MULTI_ANALYSIS_CONFIG'
]
