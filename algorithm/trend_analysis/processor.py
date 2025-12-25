"""
Trend Analysis Algorithm Data Processor

趋势分析算法数据处理器
"""

import logging
from typing import Dict, List, Any
from algorithm.base.base_processor import BaseAlgorithmProcessor
from algorithm.models import (
    AlgorithmExecutionRequest, AlgorithmConfig, 
    AlgorithmParameters, AlgorithmType
)

logger = logging.getLogger(__name__)


class TrendAnalysisProcessor(BaseAlgorithmProcessor):
    """趋势分析算法数据处理器"""
    
    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.TREND
    
    @property
    def algorithm_name(self) -> str:
        return "trend_analysis"
    
    async def convert_sql_result_to_algorithm_input(
        self,
        sql_result: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """将SQL结果转换为趋势分析算法输入格式"""
        try:
            logger.info(f"开始转换SQL结果为趋势分析算法输入，数据行数: {len(sql_result)}")
            
            if not sql_result:
                raise ValueError("SQL查询结果为空")
            
            # 获取参数映射
            param_mapping = parameters.parameter_mapping
            timestamp_column = param_mapping.get('timestamp_column')
            value_column = param_mapping.get('value_column')
            
            # 转换数据格式为趋势分析所需格式
            converted_data = await self._convert_to_time_series_format(
                sql_result, timestamp_column, value_column
            )
            
            # 构建算法配置
            config = {
                "timestamp_column": timestamp_column,
                "value_column": value_column,
                "analysis_type": param_mapping.get('analysis_type', 'decomposition'),
                "period": param_mapping.get('period'),
                "decomposition_model": param_mapping.get('decomposition_model', 'additive'),
                "algorithm": param_mapping.get('algorithm', 'auto'),
                "detection_method": param_mapping.get('detection_method', 'auto'),
                "confidence_level": param_mapping.get('confidence_level', 0.95),
                "preprocessing": {
                    "handle_missing": True,
                    "interpolate_method": "linear"
                }
            }
            
            logger.info(f"趋势分析数据转换完成，配置: {config}")
            
            return AlgorithmExecutionRequest(
                data_rows=converted_data,
                config=config
            )
            
        except Exception as e:
            logger.error(f"趋势分析数据转换失败: {str(e)}")
            raise ValueError(f"趋势分析数据转换失败: {str(e)}")
    
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
        """验证趋势分析算法输入"""
        try:
            config = request.config
            data_rows = request.data_rows
            
            # 基础验证
            if not data_rows:
                logger.error("数据行为空")
                return False
            
            # 验证数据点数量
            if len(data_rows) < 10:
                logger.error(f"数据点太少，至少需要10个数据点，当前: {len(data_rows)}")
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
            
            # 验证周期参数
            period = config.get('period')
            analysis_type = config.get('analysis_type', 'decomposition')
            
            if analysis_type == 'decomposition' and period is not None:
                if len(data_rows) < 2 * period:
                    logger.error(f"趋势分解需要至少2个完整周期的数据，当前数据点: {len(data_rows)}，周期: {period}")
                    return False
            
            logger.info("趋势分析算法输入验证通过")
            return True
            
        except Exception as e:
            logger.error(f"趋势分析输入验证失败: {str(e)}")
            return False
    
    async def _validate_data_quality(self, data_rows: List[Dict[str, Any]]) -> bool:
        """验证数据质量"""
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
        
        numeric_ratio = numeric_count / total_count
        if numeric_ratio < 0.8:
            logger.error(f"数值数据比例过低: {numeric_ratio:.2%}")
            return False
        
        return True
    
    async def execute_trend_analysis(
        self,
        request: AlgorithmExecutionRequest
    ) -> Dict[str, Any]:
        """
        执行趋势分析（调用远程 forecast_service）
        
        Args:
            request: 算法执行请求
            
        Returns:
            趋势分析结果字典
        """
        try:
            from algorithm.executor.algorithm_executor import AlgorithmExecutor
            
            logger.info("执行趋势分析（远程服务）")
            
            # 使用 AlgorithmExecutor 调用远程 forecast_service
            executor = AlgorithmExecutor()
            try:
                response = await executor.execute_trend_analysis(request)
                
                if response.status == "success":
                    logger.info("趋势分析执行成功")
                    return response.result
                else:
                    raise ValueError(f"趋势分析执行失败: {response.message}")
            finally:
                await executor.close()
            
        except Exception as e:
            logger.error(f"趋势分析执行失败: {str(e)}")
            raise
