"""
Algorithm Base Module

提供算法开发的基础接口和注册中心
"""

from .base_extractor import BaseAlgorithmExtractor
from .base_processor import BaseAlgorithmProcessor
from .registry import algorithm_registry, register_all_algorithms

__all__ = [
    'BaseAlgorithmExtractor',
    'BaseAlgorithmProcessor', 
    'algorithm_registry',
    'register_all_algorithms'
]