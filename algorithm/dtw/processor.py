"""
@Author      : Surface
@Date        : 2025/12/24 21:07
@Description : DTW算法数据处理器
"""

import logging
from typing import Dict, List, Any
from algorithm.base.base_processor import BaseAlgorithmProcessor
from algorithm.models import (
    AlgorithmExecutionRequest, AlgorithmConfig, 
    AlgorithmParameters, AlgorithmType
)

logger = logging.getLogger(__name__)


class DTWProcessor(BaseAlgorithmProcessor):
    """DTW相似度分析数据处理器"""
    
    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.SIMILARITY
    
    @property
    def algorithm_name(self) -> str:
        return "dtw"
    
    async def convert_sql_result_to_algorithm_input(
        self,
        sql_result: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """将SQL结果转换为DTW算法输入格式"""
        try:
            logger.info(f"开始转换SQL结果为DTW算法输入,数据行数: {len(sql_result)}")
            
            if not sql_result:
                raise ValueError("SQL查询结果为空")
            
            # 获取参数映射
            param_mapping = parameters.parameter_mapping
            time_column = param_mapping.get('time_column')
            series1_column = param_mapping.get('time_series1')  
            series2_column = param_mapping.get('time_series2')  
            
            # 简单数据填充
            filled_data = await self._simple_data_fill(sql_result, param_mapping)
            
            # DTW特定的数据清洗和排序
            cleaned_data = await self._clean_and_sort_dtw_data(
                filled_data, time_column, series1_column, series2_column
            )
            
            # 提取两个数值序列数组
            series1_values, series2_values = self._extract_sequences(
                cleaned_data, 
                series1_column, 
                series2_column,
                normalize=param_mapping.get('normalize', True)  # 传递用户参数
            )
            
            logger.info(f"提取序列完成 - time_series1长度: {len(series1_values)}, time_series2长度: {len(series2_values)}")
            
            is_normalized = param_mapping.get('normalize', True)
            # 构建DTW算法配置
            config = {
                "time_series1": series1_values,   
                "time_series2": series2_values,  
                "window_size": param_mapping.get('window_size'),
                "distance_metric": param_mapping.get('distance_metric', 'euclidean'),
                "already_normalized": is_normalized,  # 标记数据是否已归一化
                "step_pattern": param_mapping.get('step_pattern', 'symmetric2')
            }
            
            # 保留元数据用于可视化
            metadata = {
                "original_data": cleaned_data,
                "time_column": time_column,
                "series1_column": series1_column,  
                "series2_column": series2_column   
            }
            
            logger.info(f"DTW数据转换完成")
            
            return AlgorithmExecutionRequest(
                data_rows=[],  
                config=config,
                metadata=metadata
            )

            
        except Exception as e:
            logger.error(f"DTW数据转换失败: {str(e)}")
            raise ValueError(f"DTW数据转换失败: {str(e)}")
    
    async def _clean_and_sort_dtw_data(
        self,
        filled_data: List[Dict[str, Any]],
        time_column: str,
        time_series1: str,
        time_series2: str
    ) -> List[Dict[str, Any]]:
        """清洗并排序DTW数据"""
        cleaned_data = []
        
        for row in filled_data:
            # 验证必需字段存在
            if time_column not in row or row[time_column] is None:
                logger.warning(f"行缺少时间列{time_column},跳过")
                continue
            
            if time_series1 not in row or row[time_series1] is None:
                logger.warning(f"行缺少time_series1列{time_series1},跳过")
                continue
            
            if time_series2 not in row or row[time_series2] is None:
                logger.warning(f"行缺少time_series2列{time_series2},跳过")
                continue
            
            cleaned_row = {}
            
            # 保留时间列
            cleaned_row[time_column] = row[time_column]
            
            # 清洗series1数值
            try:
                value1 = row[time_series1]
                if isinstance(value1, str):
                    cleaned_row[time_series1] = float(value1.strip())
                else:
                    cleaned_row[time_series1] = float(value1)
            except (ValueError, TypeError) as e:
                logger.warning(f"无法转换{time_series1}的值{value1}为数值: {e},跳过此行")
                continue
            
            # 清洗series2数值
            try:
                value2 = row[time_series2]
                if isinstance(value2, str):
                    cleaned_row[time_series2] = float(value2.strip())
                else:
                    cleaned_row[time_series2] = float(value2)
            except (ValueError, TypeError) as e:
                logger.warning(f"无法转换{time_series2}的值{value2}为数值: {e},跳过此行")
                continue
            
            cleaned_data.append(cleaned_row)
        
        # 按时间列排序
        try:
            cleaned_data.sort(key=lambda x: x[time_column])
            logger.info(f"数据已按{time_column}排序")
        except Exception as e:
            logger.warning(f"无法按时间列排序: {e},使用原始顺序")
        
        logger.info(f"DTW数据清洗完成,有效数据行数: {len(cleaned_data)}")
        return cleaned_data
    
    def _extract_sequences(
        self,
        cleaned_data: List[Dict[str, Any]],
        series1_column: str,  # ← 改名
        series2_column: str,  # ← 改名
        normalize: bool = True
    ) -> tuple[List[float], List[float]]:
        """从清洗后的数据中提取两个数值序列"""
        series1_values = [row[series1_column] for row in cleaned_data]
        series2_values = [row[series2_column] for row in cleaned_data]

        # 根据参数决定是否归一化
        if normalize:
            logger.info(f"对序列进行归一化处理")
            series1_values = self._normalize_sequence(series1_values)
            series2_values = self._normalize_sequence(series2_values)
        else:
            logger.info(f"跳过归一化，使用原始数值")
            
        return series1_values, series2_values
        
    def _normalize_sequence(self, sequence: List[float]) -> List[float]:
        if not sequence:
            logger.warning("序列为空，无法归一化")
            return sequence       
        min_val = min(sequence)
        max_val = max(sequence)        
        # 如果所有值相同，返回全0.5
        if max_val == min_val:
            logger.warning(f"序列所有值相同({min_val})，归一化为0.5")
            return [0.5] * len(sequence)        
        # 归一化到[0, 1]
        normalized = [(x - min_val) / (max_val - min_val) for x in sequence]
        logger.debug(f"归一化完成: 原始范围[{min_val}, {max_val}] -> [0, 1]")

        return normalized
    
    async def validate_algorithm_input(
        self,
        request: AlgorithmExecutionRequest,
        algorithm_config: AlgorithmConfig
    ) -> bool:
        """验证DTW算法输入"""
        try:
            config = request.config
            
            # 验证time_series1
            time_series1 = config.get('time_series1')
            if not time_series1:
                logger.error("缺少time_series1")
                return False
            
            if not isinstance(time_series1, list):
                logger.error("time_series1必须是数组")
                return False
            
            if len(time_series1) < 2:
                logger.error(f"time_series1长度不足({len(time_series1)}),至少需要2个数据点")
                return False
            
            # 验证time_series2
            time_series2 = config.get('time_series2')
            if not time_series2:
                logger.error("缺少time_series2")
                return False
            
            if not isinstance(time_series2, list):
                logger.error("time_series2必须是数组")
                return False
            
            if len(time_series2) < 2:
                logger.error(f"time_series2长度不足({len(time_series2)}),至少需要2个数据点")
                return False
            
            # 验证序列数据类型
            if not all(isinstance(x, (int, float)) for x in time_series1):
                logger.error("time_series1包含非数值元素")
                return False
            
            if not all(isinstance(x, (int, float)) for x in time_series2):
                logger.error("time_series2包含非数值元素")
                return False
            
            # 验证window_size（如果设置）
            window_size = config.get('window_size')
            if window_size is not None:
                max_length = max(len(time_series1), len(time_series2))
                if window_size >= max_length:
                    logger.error(f"window_size({window_size})不能大于等于序列最大长度({max_length})")
                    return False
            
            # 验证distance_metric
            distance_metric = config.get('distance_metric', 'euclidean')
            if distance_metric not in ['euclidean', 'manhattan', 'cosine']:
                logger.error(f"不支持的distance_metric: {distance_metric}")
                return False
            
            # 验证step_pattern
            step_pattern = config.get('step_pattern', 'symmetric2')
            if step_pattern not in ['symmetric1', 'symmetric2', 'asymmetric']:
                logger.error(f"不支持的step_pattern: {step_pattern}")
                return False
            
            logger.info(
                f"DTW算法输入验证通过 - series1: {len(time_series1)}点, "
                f"series2: {len(time_series2)}点"
            )
            return True
            
        except Exception as e:
            logger.error(f"DTW输入验证失败: {str(e)}")
            return False
