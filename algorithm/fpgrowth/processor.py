"""
@Author      : Surface
@Date        : 2025/12/24
@Description : FP-Growth关联分析数据处理器
"""

import logging
from typing import Dict, List, Any, Set
from collections import defaultdict
from algorithm.base.base_processor import BaseAlgorithmProcessor
from algorithm.models import (
    AlgorithmExecutionRequest, AlgorithmConfig, 
    AlgorithmParameters, AlgorithmType
)

logger = logging.getLogger(__name__)


class FPGrowthProcessor(BaseAlgorithmProcessor):
    """FP-Growth关联分析数据处理器"""
    
    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.ASSOCIATION
    
    @property
    def algorithm_name(self) -> str:
        return "fpgrowth"
    
    async def convert_sql_result_to_algorithm_input(
        self,
        sql_result: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """将SQL结果转换为FP-Growth算法输入格式"""
        try:
            logger.info(f"开始转换SQL结果为FP-Growth算法输入，数据行数: {len(sql_result)}")
            
            if not sql_result:
                raise ValueError("SQL查询结果为空")
            
            # 获取参数映射
            param_mapping = parameters.parameter_mapping
            group_id_col = param_mapping.get('group_id_column')
            element_col = param_mapping.get('element_column')
            
            # 简单数据填充
            filled_data = await self._simple_data_fill(sql_result, param_mapping)
            
            # FP-Growth特定的数据清洗和转换
            groups = await self._convert_to_groups(
                filled_data, group_id_col, element_col
            )
            
            logger.info(f"转换完成 - 分组数: {len(groups)}, 示例: {list(groups.items())[:3]}")
            
            # 构建FP-Growth算法配置
            config = {
                "groups": groups,  # {group_id: [element1, element2, ...]}
                "min_support": param_mapping.get('min_support', 0.01),
                "min_confidence": param_mapping.get('min_confidence', 0.5),
                "max_length": param_mapping.get('max_length'),
                "metric": param_mapping.get('metric', 'confidence'),
                "min_lift": param_mapping.get('min_lift', 1.0),
                "preprocessing": {
                    "remove_duplicates": True,
                    "case_sensitive": False,
                    "min_group_length": 1
                }
            }
            
            # 保留元数据
            metadata = {
                "group_id_column": group_id_col,
                "element_column": element_col,
                "total_groups": len(groups),
                "total_records": len(filled_data)
            }
            
            logger.info(f"FP-Growth数据转换完成")
            
            return AlgorithmExecutionRequest(
                data_rows=[],  # FP-Growth使用config中的groups
                config=config,
                metadata=metadata
            )
            
        except Exception as e:
            logger.error(f"FP-Growth数据转换失败: {str(e)}")
            raise ValueError(f"FP-Growth数据转换失败: {str(e)}")
    
    async def _convert_to_groups(
        self,
        filled_data: List[Dict[str, Any]],
        group_id_col: str,
        element_col: str
    ) -> Dict[str, List[str]]:
        """将数据转换为分组格式"""
        groups = defaultdict(list)
        
        for row in filled_data:
            # 获取分组ID
            group_id = row.get(group_id_col)
            if group_id is None:
                logger.warning(f"行缺少分组ID列{group_id_col}，跳过")
                continue
            
            # 转换为字符串作为键
            group_id = str(group_id)
            
            # 获取元素
            element = row.get(element_col)
            if element is None or element == '':
                logger.warning(f"分组{group_id}的元素列{element_col}为空，跳过")
                continue
            
            # 转换为字符串并处理大小写
            element = str(element).strip()
            if not element:
                continue
            
            # 可选：转换为小写（根据配置）
            element_lower = element.lower()
            
            # 添加到分组中（去重）
            if element_lower not in [e.lower() for e in groups[group_id]]:
                groups[group_id].append(element)
        
        # 移除空分组
        groups = {
            gid: elements for gid, elements in groups.items() 
            if len(elements) > 0
        }
        
        logger.info(f"转换完成，共{len(groups)}个分组")
        
        # 统计信息
        total_elements = sum(len(elements) for elements in groups.values())
        unique_elements = len(set(elem for elements in groups.values() for elem in elements))
        avg_length = total_elements / len(groups) if groups else 0
        
        logger.info(
            f"分组统计 - 总分组数: {len(groups)}, "
            f"唯一元素数: {unique_elements}, "
            f"平均分组长度: {avg_length:.2f}"
        )
        
        return dict(groups)
    
    async def validate_algorithm_input(
        self,
        request: AlgorithmExecutionRequest,
        algorithm_config: AlgorithmConfig
    ) -> bool:
        """验证FP-Growth算法输入"""
        try:
            config = request.config
            
            # 验证groups
            groups = config.get('groups')
            if not groups:
                logger.error("缺少groups数据")
                return False
            
            if not isinstance(groups, dict):
                logger.error("groups必须是字典格式")
                return False
            
            # 验证分组数量
            if len(groups) < 10:
                logger.error(f"分组数量不足({len(groups)})，至少需要10个分组")
                return False
            
            # 验证唯一元素数
            all_elements = set()
            for elements in groups.values():
                if not isinstance(elements, list):
                    logger.error("每个分组必须是列表格式")
                    return False
                all_elements.update(elements)
            
            if len(all_elements) < 2:
                logger.error(f"唯一元素数不足({len(all_elements)})，至少需要2个不同的元素")
                return False
            
            # 验证min_support
            min_support = config.get('min_support', 0.01)
            if not isinstance(min_support, (int, float)) or not (0 < min_support <= 1):
                logger.error(f"min_support无效: {min_support}")
                return False
            
            # 验证min_confidence
            min_confidence = config.get('min_confidence', 0.5)
            if not isinstance(min_confidence, (int, float)) or not (0 < min_confidence <= 1):
                logger.error(f"min_confidence无效: {min_confidence}")
                return False
            
            # 验证max_length
            max_length = config.get('max_length')
            if max_length is not None:
                if not isinstance(max_length, int) or max_length < 1:
                    logger.error(f"max_length无效: {max_length}")
                    return False
            
            # 验证metric
            metric = config.get('metric', 'confidence')
            if metric not in ['confidence', 'lift', 'leverage', 'conviction']:
                logger.error(f"不支持的metric: {metric}")
                return False
            
            logger.info(
                f"FP-Growth算法输入验证通过 - "
                f"分组数: {len(groups)}, "
                f"唯一元素数: {len(all_elements)}, "
                f"min_support: {min_support}, "
                f"min_confidence: {min_confidence}"
            )
            return True
            
        except Exception as e:
            logger.error(f"FP-Growth输入验证失败: {str(e)}")
            return False
