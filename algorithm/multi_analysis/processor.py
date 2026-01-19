"""
Multi Analysis Algorithm Data Processor

统一多算法分析数据处理器
"""

import logging
from typing import Dict, List, Any
from algorithm.base.base_processor import BaseAlgorithmProcessor
from algorithm.models import (
    AlgorithmExecutionRequest, AlgorithmConfig, 
    AlgorithmParameters, AlgorithmType
)

logger = logging.getLogger(__name__)


class MultiAnalysisProcessor(BaseAlgorithmProcessor):
    """统一多算法分析数据处理器"""
    
    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.MULTI_ANALYSIS
    
    @property
    def algorithm_name(self) -> str:
        return "multi_analysis"
    
    async def convert_sql_result_to_algorithm_input(
        self,
        sql_result: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """将SQL结果转换为统一多算法分析输入格式"""
        try:
            logger.info(f"开始转换SQL结果为统一多算法分析输入，数据行数: {len(sql_result)}")
            
            if not sql_result:
                raise ValueError("SQL查询结果为空")
            
            # 获取参数映射
            param_mapping = parameters.parameter_mapping
            timestamp_column = param_mapping.get('timestamp_column')
            value_column = param_mapping.get('value_column')
            
            # 添加调试日志
            logger.info(f"期望的时间字段名: {timestamp_column}")
            logger.info(f"期望的数值字段名: {value_column}")
            
            if sql_result:
                actual_fields = list(sql_result[0].keys())
                logger.info(f"SQL返回的实际字段名: {actual_fields}")
                
                # 检查字段名是否匹配
                if timestamp_column not in actual_fields:
                    logger.warning(f"时间字段 '{timestamp_column}' 不在SQL结果中，实际字段: {actual_fields}")
                if value_column not in actual_fields:
                    logger.warning(f"数值字段 '{value_column}' 不在SQL结果中，实际字段: {actual_fields}")
            
            # 转换数据格式为时间序列格式
            converted_data = await self._convert_to_time_series_format(
                sql_result, timestamp_column, value_column
            )
            
            # 构建算法配置
            config = {
                "timestamp_column": timestamp_column,
                "value_column": value_column,
                "analysis_types": param_mapping.get('analysis_types'),
                "include_all": param_mapping.get('include_all', True),
                "candidate_periods": param_mapping.get('candidate_periods'),
                "period_type": param_mapping.get('period_type'),
                "base_period": param_mapping.get('base_period'),
                "base_value": param_mapping.get('base_value', 100),
                "simplified": param_mapping.get('simplified', False),
                "preprocessing": {
                    "handle_missing": True,
                    "interpolate_method": "linear"
                }
            }
            
            logger.info(f"统一多算法分析数据转换完成，配置: {config}")
            
            return AlgorithmExecutionRequest(
                data_rows=converted_data,
                config=config
            )
            
        except Exception as e:
            logger.error(f"统一多算法分析数据转换失败: {str(e)}")
            raise ValueError(f"统一多算法分析数据转换失败: {str(e)}")
    
    async def _convert_to_time_series_format(
        self,
        sql_result: List[Dict[str, Any]],
        timestamp_column: str,
        value_column: str
    ) -> List[Dict[str, Any]]:
        """转换为时间序列格式"""
        converted_data = []
        
        for row in sql_result:
            # 获取时间戳
            timestamp = row.get(timestamp_column)
            if timestamp is None:
                logger.warning(f"数据行缺少时间列 {timestamp_column}，跳过")
                continue
            
            # 获取数值
            value = row.get(value_column)
            if value is None:
                logger.warning(f"数据行缺少数值列 {value_column}，跳过")
                continue
            
            # 转换数值类型
            try:
                if isinstance(value, str):
                    value = float(value.strip())
                else:
                    value = float(value)
            except (ValueError, TypeError):
                logger.warning(f"无法转换值 {value} 为数值，跳过")
                continue
            
            converted_data.append({
                "timestamp": str(timestamp),
                "value": value
            })
        
        logger.debug(f"时间序列数据转换完成，有效数据点: {len(converted_data)}")
        return converted_data
    
    async def validate_algorithm_input(
        self,
        request: AlgorithmExecutionRequest,
        algorithm_config: AlgorithmConfig
    ) -> bool:
        """验证统一多算法分析输入"""
        try:
            config = request.config
            data_rows = request.data_rows
            
            # 基础验证
            if not data_rows:
                logger.error("数据行为空")
                return False
            
            # 验证数据点数量（根据分析类型调整最小要求）
            analysis_types = config.get('analysis_types', [])
            min_required_points = self._get_min_required_points(analysis_types)
            
            if len(data_rows) < min_required_points:
                logger.error(f"数据点太少，当前: {len(data_rows)}，{self._get_analysis_description(analysis_types)}至少需要{min_required_points}个数据点")
                return False
            
            # 验证时间列和数值列
            timestamp_column = config.get('timestamp_column')
            value_column = config.get('value_column')
            
            if not timestamp_column or not value_column:
                logger.error("缺少时间列或数值列配置")
                return False
            
            # 验证数据格式
            for row in data_rows[:5]:  # 检查前5行
                if 'timestamp' not in row or 'value' not in row:
                    logger.error("数据格式错误，缺少timestamp或value字段")
                    return False
            
            # 验证数据质量
            if not await self._validate_data_quality(data_rows):
                return False
            
            logger.info("统一多算法分析输入验证通过")
            return True
            
        except Exception as e:
            logger.error(f"统一多算法分析输入验证失败: {str(e)}")
            return False
    
    def _get_min_required_points(self, analysis_types: List[str]) -> int:
        """根据分析类型获取最小数据点要求"""
        if not analysis_types:
            return 8  # 默认要求
        
        # 不同分析类型的最小数据点要求
        min_points_map = {
            'year_over_year': 2,      # 同比分析：当前期+去年同期，2个数据点即可
            'period_over_period': 2,  # 环比分析：当前期+上一期，2个数据点即可
            'base_period_index': 2,   # 定基比分析：基期+目标期，至少2个数据点
            'periodicity': 8          # 周期性分析：需要足够数据点检测周期
        }
        
        # 取所有分析类型中要求最高的
        max_required = max(min_points_map.get(analysis_type, 8) for analysis_type in analysis_types)
        return max_required
    
    def _get_analysis_description(self, analysis_types: List[str]) -> str:
        """获取分析类型的描述"""
        if not analysis_types:
            return "综合分析"
        
        descriptions = {
            'year_over_year': '同比分析',
            'period_over_period': '环比分析', 
            'base_period_index': '定基比分析',
            'periodicity': '周期性分析'
        }
        
        type_names = [descriptions.get(t, t) for t in analysis_types]
        return '、'.join(type_names)
    
    async def _validate_data_quality(self, data_rows: List[Dict[str, Any]]) -> bool:
        """验证数据质量（增强版）"""
        # 检查数值型数据比例
        numeric_count = 0
        total_count = len(data_rows)
        
        for row in data_rows:
            value = row.get('value')
            if value is not None and isinstance(value, (int, float)):
                numeric_count += 1
        
        if total_count == 0:
            logger.error("没有有效数据")
            return False
        
        # 🚨 紧急修复：检查数据行数是否异常（可能是重复数据问题）
        if total_count > 500:
            logger.error(f"数据行数异常过多({total_count}行)，可能存在重复数据或SQL查询问题")
            return False
        
        # 🚨 紧急修复：检查数据重复问题
        duplicate_check = await self._check_data_duplication(data_rows)
        if not duplicate_check:
            return False
        
        numeric_ratio = numeric_count / total_count
        if numeric_ratio < 0.8:
            logger.error(f"数值数据比例过低: {numeric_ratio:.2%}")
            return False
        
        # 增强验证：检查数据量是否足够进行可靠分析（已在validate_algorithm_input中处理）
        # 这里不再重复检查最小数据点，避免双重验证
        
        # 警告：数据点较少时提醒用户
        if total_count < 30:
            logger.warning(f"数据点较少({total_count}个)，分析结果可能不够可靠，建议收集更多数据")
        
        # 检查数据分布的时间跨度合理性
        try:
            timestamps = []
            for row in data_rows:
                timestamp_str = row.get('timestamp')
                if timestamp_str:
                    # 尝试解析时间戳
                    import pandas as pd
                    timestamps.append(pd.to_datetime(timestamp_str))
            
            if len(timestamps) >= 2:
                time_span = (max(timestamps) - min(timestamps)).days
                
                # 检查时间跨度与数据点数的合理性
                if time_span > 0:
                    points_per_day = total_count / time_span
                    
                    # 如果数据过于稀疏（平均每天少于0.1个数据点），发出警告
                    if points_per_day < 0.1:
                        logger.warning(f"数据过于稀疏，时间跨度{time_span}天但只有{total_count}个数据点，分析结果可能不可靠")
                    
                    # 如果时间跨度太短（少于7天）但要做周期性分析，发出警告
                    if time_span < 7 and total_count < 50:
                        logger.warning(f"时间跨度较短({time_span}天)且数据点较少({total_count}个)，周期性分析结果可能不准确")
        
        except Exception as e:
            logger.warning(f"时间跨度验证失败: {e}")
        
        return True
    
    async def _check_data_duplication(self, data_rows: List[Dict[str, Any]]) -> bool:
        """🚨 紧急修复：检查数据重复问题"""
        if not data_rows:
            return True
        
        # 检查是否所有数据都相同（重复数据问题的典型症状）
        first_row = data_rows[0]
        first_timestamp = first_row.get('timestamp')
        first_value = first_row.get('value')
        
        identical_count = 0
        for row in data_rows:
            if (row.get('timestamp') == first_timestamp and 
                row.get('value') == first_value):
                identical_count += 1
        
        # 如果超过90%的数据都相同，认为是重复数据问题
        if len(data_rows) > 10 and identical_count / len(data_rows) > 0.9:
            logger.error(
                f"检测到严重的数据重复问题：{len(data_rows)}行数据中有{identical_count}行完全相同 "
                f"(timestamp='{first_timestamp}', value={first_value})。"
                f"这通常是SQL查询缺少GROUP BY聚合导致的。"
            )
            return False
        
        # 检查时间戳重复率
        timestamps = [row.get('timestamp') for row in data_rows if row.get('timestamp')]
        unique_timestamps = set(timestamps)
        
        if len(timestamps) > 0:
            duplicate_ratio = 1 - (len(unique_timestamps) / len(timestamps))
            if duplicate_ratio > 0.8:
                logger.error(
                    f"时间戳重复率过高({duplicate_ratio:.1%})，总共{len(timestamps)}个时间戳但只有{len(unique_timestamps)}个唯一值。"
                    f"这可能是SQL查询缺少GROUP BY导致的重复数据。"
                )
                return False
        
        # 如果检测到重复但不严重，进行去重
        if identical_count > len(data_rows) * 0.5:
            logger.warning(f"检测到{identical_count}行重复数据，将进行自动去重")
            # 这里可以添加去重逻辑，但对于严重的重复问题，最好直接报错让用户修复SQL
        
        return True
    
    async def execute_multi_analysis(
        self,
        request: AlgorithmExecutionRequest
    ) -> Dict[str, Any]:
        """
        执行统一多算法分析（调用远程 forecast_service）
        
        Args:
            request: 算法执行请求
            
        Returns:
            统一多算法分析结果字典
        """
        try:
            from algorithm.executor.algorithm_executor import AlgorithmExecutor
            
            logger.info("执行统一多算法分析（远程服务）")
            
            # 使用 AlgorithmExecutor 调用远程 forecast_service
            executor = AlgorithmExecutor()
            try:
                response = await executor.execute_multi_analysis(request)
                
                if response.status == "success":
                    logger.info("统一多算法分析执行成功")
                    return response.result
                else:
                    raise ValueError(f"统一多算法分析执行失败: {response.message}")
            finally:
                await executor.close()
            
        except Exception as e:
            logger.error(f"统一多算法分析执行失败: {str(e)}")
            raise
