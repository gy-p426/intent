"""
FP-Growth Association Analysis

FP-Growth频繁模式增长关联分析算法
"""

from .extractor import FPGrowthExtractor
from .processor import FPGrowthProcessor
from .config import FPGROWTH_CONFIG

__all__ = [
    'FPGrowthExtractor',
    'FPGrowthProcessor',
    'FPGROWTH_CONFIG'
]
