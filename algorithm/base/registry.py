"""
Algorithm Registry

算法注册中心，管理所有算法的提取器和处理器
"""

import logging
from typing import Dict, Optional, List
from algorithm.models import AlgorithmType
from .base_extractor import BaseAlgorithmExtractor
from .base_processor import BaseAlgorithmProcessor

logger = logging.getLogger(__name__)


class AlgorithmRegistry:
    """算法注册中心"""
    
    def __init__(self):
        self._extractors: Dict[str, BaseAlgorithmExtractor] = {}
        self._processors: Dict[str, BaseAlgorithmProcessor] = {}
    
    def register_algorithm(
        self, 
        extractor: BaseAlgorithmExtractor, 
        processor: BaseAlgorithmProcessor
    ) -> None:
        """注册算法（提取器和处理器）"""
        algorithm_name = extractor.algorithm_name
        
        if algorithm_name != processor.algorithm_name:
            raise ValueError(f"提取器和处理器的算法名称不匹配: {algorithm_name} vs {processor.algorithm_name}")
        
        self._extractors[algorithm_name] = extractor
        self._processors[algorithm_name] = processor
        
        logger.info(f"成功注册算法: {algorithm_name}")
    
    def get_extractor(self, algorithm_name: str) -> Optional[BaseAlgorithmExtractor]:
        """获取参数提取器实例"""
        return self._extractors.get(algorithm_name)
    
    def get_processor(self, algorithm_name: str) -> Optional[BaseAlgorithmProcessor]:
        """获取数据处理器实例"""
        return self._processors.get(algorithm_name)
    
    def get_supported_algorithms(self) -> List[str]:
        """获取支持的算法名称列表"""
        return list(self._extractors.keys())
    
    def is_algorithm_supported(self, algorithm_name: str) -> bool:
        """检查算法是否支持"""
        return algorithm_name in self._extractors and algorithm_name in self._processors
    
    def get_extractor_by_type(self, algorithm_type: AlgorithmType) -> Optional[BaseAlgorithmExtractor]:
        """根据算法类型获取提取器"""
        for extractor in self._extractors.values():
            if extractor.algorithm_type == algorithm_type:
                return extractor
        return None
    
    def get_processor_by_type(self, algorithm_type: AlgorithmType) -> Optional[BaseAlgorithmProcessor]:
        """根据算法类型获取处理器"""
        for processor in self._processors.values():
            if processor.algorithm_type == algorithm_type:
                return processor
        return None


# 全局注册中心实例
algorithm_registry = AlgorithmRegistry()


def register_all_algorithms():
    """自动注册所有算法"""
    try:
        # K-Means算法
        from algorithm.kmeans.extractor import KMeansExtractor
        from algorithm.kmeans.processor import KMeansProcessor
        algorithm_registry.register_algorithm(KMeansExtractor(), KMeansProcessor())
        
        logger.info("所有算法注册完成")
        
    except ImportError as e:
        logger.warning(f"部分算法注册失败: {str(e)}")
    except Exception as e:
        logger.error(f"算法注册过程中发生错误: {str(e)}")


def get_algorithm_registry() -> AlgorithmRegistry:
    """获取算法注册中心实例"""
    return algorithm_registry