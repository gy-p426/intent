"""
@Author      : Ayaki Shi
@Date        : 2025/12/23 21:00
@Description : 孤立森林算法实现
"""

from .config import IFOREST_CONFIG
from .extractor import IFORESTExtractor
from .processor import IFORESTProcessor

__all__ = [
    'IFOREST_CONFIG',
    'IFORESTExtractor',
    'IFORESTProcessor'
]