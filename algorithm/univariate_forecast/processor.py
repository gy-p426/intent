"""
Univariate Forecast Algorithm Data Processor

单变量预测算法数据处理器
"""

import logging
from typing import Dict, List, Any
from algorithm.base.base_processor import BaseAlgorithmProcessor
from algorithm.models import (
    AlgorithmExecutionRequest, AlgorithmConfig, 
    AlgorithmParameters, AlgorithmType
)

logger = logging.getLogger(__name__)


class UnivariateForecastProcessor(BaseAlgorithmProcessor):
    """单变量预测算法数据处理器"""
    
    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.PREDICT
    
    @property
    def algorithm_name(self) -> str:
        return "univariate_forecast"
    
    async def convert_sql_result_to_algorithm_input(
        self,
        sql_result: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """将SQL结果转换为单变量预测算法输入格式"""
        try:
            logger.info(f"开始转换SQL结果为单变量预测算法输入，数据行数: {len(sql_result)}")
            
            if not sql_result:
                raise ValueError("SQL查询结果为空")
            
            # 获取参数映射
            param_mapping = parameters.parameter_mapping
            timestamp_column = param_mapping.get('timestamp_column')
            value_column = param_mapping.get('value_column')
            
            # 转换数据格式为预测所需格式
            timestamps = []
            values = []
            
            for row in sql_result:
                # 获取时间戳
                timestamp = row.get(timestamp_column)
                if timestamp is None:
                    continue
                
                # 获取数值
                value = row.get(value_column)
                if value is None:
                    continue
                
                # 转换数值类型
                try:
                    if isinstance(value, str):
                        value = float(value.strip())
                    else:
                        value = float(value)
                except (ValueError, TypeError):
                    continue
                
                timestamps.append(str(timestamp))
                values.append(value)
            
            if len(timestamps) < 10:
                raise ValueError(f"有效数据点太少，至少需要10个，当前: {len(timestamps)}")
            
            # 构建预测请求数据格式
            converted_data = [{
                "data": {
                    "timestamp": timestamps,
                    "value": values
                }
            }]
            
            # 构建算法配置
            config = {
                "timestamp_column": timestamp_column,
                "value_column": value_column,
                "forecast_horizon": param_mapping.get('forecast_horizon', 24),
                "model_type": param_mapping.get('model_type', 'auto'),
                "include_confidence": param_mapping.get('include_confidence', True),
                "confidence_level": param_mapping.get('confidence_level', 0.95),
                "preprocessing": {
                    "handle_missing": True,
                    "interpolate_method": "linear"
                }
            }
            
            logger.info(f"单变量预测数据转换完成，有效数据点: {len(timestamps)}，配置: {config}")
            
            return AlgorithmExecutionRequest(
                data_rows=converted_data,
                config=config
            )
            
        except Exception as e:
            logger.error(f"单变量预测数据转换失败: {str(e)}")
            raise ValueError(f"单变量预测数据转换失败: {str(e)}")
    
    async def validate_algorithm_input(
        self,
        request: AlgorithmExecutionRequest,
        algorithm_config: AlgorithmConfig
    ) -> bool:
        """验证单变量预测算法输入"""
        try:
            config = request.config
            data_rows = request.data_rows
            
            # 基础验证
            if not data_rows:
                logger.error("数据行为空")
                return False
            
            # 验证数据格式
            if len(data_rows) != 1 or 'data' not in data_rows[0]:
                logger.error("数据格式错误，应为包含data字段的单元素列表")
                return False
            
            data = data_rows[0]['data']
            if 'timestamp' not in data or 'value' not in data:
                logger.error("数据缺少timestamp或value字段")
                return False
            
            timestamps = data['timestamp']
            values = data['value']
            
            if len(timestamps) != len(values):
                logger.error("timestamp和value长度不一致")
                return False
            
            # 验证数据点数量
            if len(timestamps) < 10:
                logger.error(f"数据点太少，至少需要10个，当前: {len(timestamps)}")
                return False
            
            # 验证数值数据质量
            numeric_count = sum(1 for v in values if isinstance(v, (int, float)))
            if numeric_count / len(values) < 0.8:
                logger.error("数值数据比例过低")
                return False
            
            # 验证预测步数
            forecast_horizon = config.get('forecast_horizon', 24)
            if forecast_horizon < 1 or forecast_horizon > 365:
                logger.error(f"预测步数无效: {forecast_horizon}")
                return False
            
            logger.info("单变量预测算法输入验证通过")
            return True
            
        except Exception as e:
            logger.error(f"单变量预测输入验证失败: {str(e)}")
            return False
    
    async def execute_univariate_forecast(
        self,
        request: AlgorithmExecutionRequest
    ) -> Dict[str, Any]:
        """
        执行单变量预测（调用远程 forecast_service）
        
        Args:
            request: 算法执行请求
            
        Returns:
            单变量预测结果字典
        """
        try:
            from algorithm.executor.algorithm_executor import AlgorithmExecutor
            
            logger.info("执行单变量预测（远程服务）")
            
            # 使用 AlgorithmExecutor 调用远程 forecast_service
            executor = AlgorithmExecutor()
            try:
                response = await executor.execute_univariate_forecast(request)
                
                if response:
                    logger.info(f"单变量预测执行成功，使用模型: {response.result.get('model_used')}")
                    return response.result
                else:
                    logger.warning(f"单变量预测执行失败: {response.message}")
                    return {
                        "success": False,
                        "message": response.message
                    }
            finally:
                await executor.close()
            
        except Exception as e:
            logger.error(f"单变量预测执行失败: {str(e)}")
            raise
