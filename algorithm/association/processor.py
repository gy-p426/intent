"""
Association Analysis Data Processor

关联分析数据处理器
"""

import logging
from typing import Dict, List, Any
from algorithm.base.base_processor import BaseAlgorithmProcessor
from algorithm.models import (
    AlgorithmExecutionRequest, AlgorithmConfig, 
    AlgorithmParameters, AlgorithmType
)

logger = logging.getLogger(__name__)


class AssociationProcessor(BaseAlgorithmProcessor):
    """关联分析数据处理器"""
    
    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.STATISTICAL
    
    @property
    def algorithm_name(self) -> str:
        return "association"
    
    async def convert_sql_result_to_algorithm_input(
        self,
        sql_result: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """将SQL结果转换为关联分析输入格式"""
        try:
            logger.info(f"开始转换SQL结果为关联分析输入，数据行数: {len(sql_result)}")
            
            if not sql_result:
                raise ValueError("SQL查询结果为空")
            
            # 获取参数映射
            param_mapping = parameters.parameter_mapping
            column1_name = param_mapping.get('column1')
            column2_name = param_mapping.get('column2')
            significance_level = param_mapping.get('significance_level', 0.05)
            
            if not column1_name or not column2_name:
                raise ValueError("缺少必需的列名参数")
            
            # 提取两列数据
            column1_values = []
            column2_values = []
            
            for row in sql_result:
                val1 = row.get(column1_name)
                val2 = row.get(column2_name)
                
                # 保留None值，后续处理器会清理
                column1_values.append(val1)
                column2_values.append(val2)
            
            # 验证数据长度
            if len(column1_values) != len(column2_values):
                raise ValueError(f"两列数据长度不一致: {len(column1_values)} vs {len(column2_values)}")
            
            if len(column1_values) == 0:
                raise ValueError("提取的数据为空")
            
            # 构建算法输入（按照约定的格式）
            config = {
                "data": {
                    "column1": {
                        "name": column1_name,
                        "values": column1_values
                    },
                    "column2": {
                        "name": column2_name,
                        "values": column2_values
                    }
                },
                "significance_level": significance_level
            }
            
            logger.info(
                f"关联分析数据转换完成: "
                f"{column1_name}({len(column1_values)}) vs {column2_name}({len(column2_values)}), "
                f"α={significance_level}"
            )
            
            # 这里data_rows可以为空，因为实际数据在config中
            return AlgorithmExecutionRequest(
                data_rows=[],
                config=config
            )
            
        except Exception as e:
            logger.error(f"关联分析数据转换失败: {str(e)}")
            raise ValueError(f"关联分析数据转换失败: {str(e)}")
    
    async def validate_algorithm_input(
        self,
        request: AlgorithmExecutionRequest,
        algorithm_config: AlgorithmConfig
    ) -> bool:
        """验证关联分析输入"""
        try:
            config = request.config
            
            # 验证data字段存在
            data = config.get('data')
            if not data:
                logger.error("配置中缺少data字段")
                return False
            
            # 验证column1
            column1 = data.get('column1')
            if not column1:
                logger.error("配置中缺少column1")
                return False
            
            column1_name = column1.get('name')
            column1_values = column1.get('values')
            
            if not column1_name:
                logger.error("column1缺少name字段")
                return False
            
            if not isinstance(column1_values, list):
                logger.error("column1的values必须是列表")
                return False
            
            # 验证column2
            column2 = data.get('column2')
            if not column2:
                logger.error("配置中缺少column2")
                return False
            
            column2_name = column2.get('name')
            column2_values = column2.get('values')
            
            if not column2_name:
                logger.error("column2缺少name字段")
                return False
            
            if not isinstance(column2_values, list):
                logger.error("column2的values必须是列表")
                return False
            
            # 验证两列名称不同
            if column1_name == column2_name:
                logger.error(f"两列名称相同: {column1_name}")
                return False
            
            # 验证数据长度
            if len(column1_values) != len(column2_values):
                logger.error(
                    f"两列数据长度不一致: {column1_name}={len(column1_values)}, "
                    f"{column2_name}={len(column2_values)}"
                )
                return False
            
            if len(column1_values) == 0:
                logger.error("数据为空")
                return False
            
            # 验证显著性水平
            significance_level = config.get('significance_level', 0.05)
            if not isinstance(significance_level, (int, float)):
                logger.error(f"显著性水平必须是数值: {significance_level}")
                return False
            
            if not 0.001 <= significance_level <= 0.5:
                logger.error(f"显著性水平超出范围: {significance_level}")
                return False
            
            # 验证数据质量（移除None后至少2个数据点）
            valid_count = sum(
                1 for v1, v2 in zip(column1_values, column2_values)
                if v1 is not None and v2 is not None
            )
            
            if valid_count < 2:
                logger.error(f"有效数据点少于2个（当前: {valid_count}）")
                return False
            
            logger.info(
                f"关联分析输入验证通过: {column1_name} vs {column2_name}, "
                f"数据量={len(column1_values)}, 有效数据={valid_count}, α={significance_level}"
            )
            return True
            
        except Exception as e:
            logger.error(f"关联分析输入验证失败: {str(e)}")
            return False
