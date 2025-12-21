"""
Base Algorithm Processor

算法特定数据处理器基类
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Any
from algorithm.models import AlgorithmExecutionRequest, AlgorithmConfig, AlgorithmParameters, AlgorithmType

logger = logging.getLogger(__name__)


class BaseAlgorithmProcessor(ABC):
    """算法特定数据处理器基类"""
    
    @property
    @abstractmethod
    def algorithm_type(self) -> AlgorithmType:
        """返回支持的算法类型"""
        pass
    
    @property
    @abstractmethod
    def algorithm_name(self) -> str:
        """返回算法名称，用于注册"""
        pass
    
    @abstractmethod
    async def convert_sql_result_to_algorithm_input(
        self,
        sql_result: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """将SQL结果转换为算法输入格式"""
        pass
    
    @abstractmethod
    async def validate_algorithm_input(
        self,
        request: AlgorithmExecutionRequest,
        algorithm_config: AlgorithmConfig
    ) -> bool:
        """验证算法输入数据"""
        pass
    
    async def _simple_data_fill(
        self,
        sql_result: List[Dict[str, Any]],
        parameter_mapping: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """简单的数据填充方法"""
        filled_data = []
        
        for row in sql_result:
            filled_row = {}
            
            # 直接按照参数映射中指定的列名填充数据
            for param_name, column_names in parameter_mapping.items():
                if param_name == 'id_column':
                    if column_names in row:
                        filled_row[column_names] = row[column_names]
                elif param_name == 'feature_columns' and isinstance(column_names, list):
                    for col_name in column_names:
                        if col_name in row:
                            filled_row[col_name] = row[col_name]
                elif param_name == 'target_column':
                    if column_names in row:
                        filled_row[column_names] = row[column_names]
                elif param_name == 'time_column':
                    if column_names in row:
                        filled_row[column_names] = row[column_names]
            
            filled_data.append(filled_row)
        
        return filled_data