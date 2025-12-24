"""
Multivariate Forecast Algorithm Data Processor

多变量预测算法数据处理器
"""

import logging
from typing import Dict, List, Any
from algorithm.base.base_processor import BaseAlgorithmProcessor
from algorithm.models import (
    AlgorithmExecutionRequest, AlgorithmConfig, 
    AlgorithmParameters, AlgorithmType
)

logger = logging.getLogger(__name__)


class MultivariateForecastProcessor(BaseAlgorithmProcessor):
    """多变量预测算法数据处理器"""
    
    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.PREDICT
    
    @property
    def algorithm_name(self) -> str:
        return "multivariate_forecast"
    
    async def convert_sql_result_to_algorithm_input(
        self,
        sql_result: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """将SQL结果转换为多变量预测算法输入格式"""
        try:
            logger.info(f"开始转换SQL结果为多变量预测算法输入，数据行数: {len(sql_result)}")
            
            if not sql_result:
                raise ValueError("SQL查询结果为空")
            
            # 获取参数映射
            param_mapping = parameters.parameter_mapping
            
            # 简单数据填充
            filled_data = await self._simple_data_fill(sql_result, param_mapping)
            
            # 数据清洗
            cleaned_data = await self._clean_time_series_data(filled_data, param_mapping)
            
            # 构建算法配置
            config = {
                "timestamp_column": param_mapping.get('timestamp_column'),
                "target_column": param_mapping.get('target_column'),
                "feature_columns": param_mapping.get('feature_columns'),
                "forecast_horizon": param_mapping.get('forecast_horizon', 14),
                "algorithm": param_mapping.get('algorithm', 'lightgbm'),
                "model_name": param_mapping.get('model_name'),
                "preprocessing": {
                    "handle_missing": True,
                    "normalize_features": True
                }
            }
            
            logger.info(f"多变量预测数据转换完成，配置: {config}")
            
            return AlgorithmExecutionRequest(
                data_rows=cleaned_data,
                config=config
            )
            
        except Exception as e:
            logger.error(f"多变量预测数据转换失败: {str(e)}")
            raise ValueError(f"多变量预测数据转换失败: {str(e)}")
    
    async def _clean_time_series_data(
        self, 
        filled_data: List[Dict[str, Any]], 
        param_mapping: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """清洗时间序列数据"""
        cleaned_data = []
        timestamp_column = param_mapping.get('timestamp_column')
        target_column = param_mapping.get('target_column')
        feature_columns = param_mapping.get('feature_columns', []) or []
        
        for row in filled_data:
            cleaned_row = row.copy()
            
            # 处理时间列 - 重命名为标准名称 timestamp
            if timestamp_column and timestamp_column in cleaned_row:
                cleaned_row['timestamp'] = cleaned_row[timestamp_column]
            
            # 清洗目标列的数值数据
            if target_column and target_column in cleaned_row:
                value = cleaned_row[target_column]
                if value is not None:
                    try:
                        if isinstance(value, str):
                            cleaned_row[target_column] = float(value.strip())
                        else:
                            cleaned_row[target_column] = float(value)
                    except (ValueError, TypeError):
                        logger.warning(f"无法转换目标列{target_column}的值{value}为数值，设为None")
                        cleaned_row[target_column] = None
            
            # 清洗特征列的数值数据
            for col in feature_columns:
                if col in cleaned_row:
                    value = cleaned_row[col]
                    if value is not None:
                        try:
                            if isinstance(value, str):
                                cleaned_row[col] = float(value.strip())
                            else:
                                cleaned_row[col] = float(value)
                        except (ValueError, TypeError):
                            logger.warning(f"无法转换特征列{col}的值{value}为数值，设为None")
                            cleaned_row[col] = None
            
            cleaned_data.append(cleaned_row)
        
        logger.debug(f"时间序列数据清洗完成，处理了{len(cleaned_data)}行数据")
        return cleaned_data
    
    async def validate_algorithm_input(
        self,
        request: AlgorithmExecutionRequest,
        algorithm_config: AlgorithmConfig
    ) -> bool:
        """验证多变量预测算法输入"""
        try:
            config = request.config
            data_rows = request.data_rows
            
            # 基础验证
            if not data_rows:
                logger.error("数据行为空")
                return False
            
            # 验证时间列
            timestamp_column = config.get('timestamp_column')
            if not timestamp_column:
                logger.error("缺少时间列配置")
                return False
            
            # 检查数据中是否有时间列（原始列名或标准化后的timestamp）
            first_row = data_rows[0]
            if timestamp_column not in first_row and 'timestamp' not in first_row:
                logger.error(f"数据中缺少时间列: {timestamp_column}")
                return False
            
            # 验证目标列
            target_column = config.get('target_column')
            if not target_column:
                logger.error("缺少目标列配置")
                return False
            
            if target_column not in first_row:
                logger.error(f"数据中缺少目标列: {target_column}")
                return False
            
            # 验证特征列（如果指定）
            feature_columns = config.get('feature_columns')
            if feature_columns:
                for col in feature_columns:
                    if col not in first_row:
                        logger.error(f"数据中缺少特征列: {col}")
                        return False
            
            # 验证数据质量
            if not await self._validate_time_series_quality(data_rows, target_column, feature_columns):
                return False
            
            # 验证预测步数
            forecast_horizon = config.get('forecast_horizon', 14)
            if forecast_horizon < 1 or forecast_horizon > 365:
                logger.error(f"预测步数无效: {forecast_horizon}")
                return False
            
            # 验证算法
            algorithm = config.get('algorithm', 'lightgbm')
            valid_algorithms = ['lightgbm', 'xgboost', 'random_forest', 'linear_regression']
            if algorithm not in valid_algorithms:
                logger.error(f"不支持的算法: {algorithm}")
                return False
            
            logger.info("多变量预测算法输入验证通过")
            return True
            
        except Exception as e:
            logger.error(f"多变量预测输入验证失败: {str(e)}")
            return False
    
    async def _validate_time_series_quality(
        self, 
        data_rows: List[Dict[str, Any]], 
        target_column: str,
        feature_columns: List[str] = None
    ) -> bool:
        """验证时间序列数据质量"""
        # 检查目标列数值比例
        numeric_count = 0
        total_count = 0
        
        for row in data_rows:
            value = row.get(target_column)
            if value is not None:
                total_count += 1
                if isinstance(value, (int, float)):
                    numeric_count += 1
        
        if total_count == 0:
            logger.error(f"目标列{target_column}没有有效数据")
            return False
        
        numeric_ratio = numeric_count / total_count
        if numeric_ratio < 0.7:
            logger.error(f"目标列{target_column}的数值比例过低: {numeric_ratio:.2%}")
            return False
        
        # 检查特征列数值比例
        if feature_columns:
            for col in feature_columns:
                col_numeric_count = 0
                col_total_count = 0
                
                for row in data_rows:
                    value = row.get(col)
                    if value is not None:
                        col_total_count += 1
                        if isinstance(value, (int, float)):
                            col_numeric_count += 1
                
                if col_total_count > 0:
                    col_ratio = col_numeric_count / col_total_count
                    if col_ratio < 0.7:
                        logger.warning(f"特征列{col}的数值比例较低: {col_ratio:.2%}")
        
        # 检查数据量是否足够
        if len(data_rows) < 10:
            logger.error(f"数据量不足，至少需要10条记录，当前: {len(data_rows)}")
            return False
        
        return True
    
    async def execute_multivariate_forecast(
        self,
        request: AlgorithmExecutionRequest
    ) -> Dict[str, Any]:
        """执行多变量预测算法"""
        try:
            from algorithm.forecast_core.multivariate_forecast.core.predictor import MultivariatePredictor
            
            predictor = MultivariatePredictor()
            
            # 构建预测请求
            forecast_request = {
                "data": request.data_rows,
                "config": request.config
            }
            
            # 执行预测
            result = predictor.forecast(forecast_request)
            
            return result
            
        except ImportError as e:
            logger.error(f"导入多变量预测模块失败: {str(e)}")
            raise ValueError(f"多变量预测模块未正确安装: {str(e)}")
        except Exception as e:
            logger.error(f"多变量预测执行失败: {str(e)}")
            raise ValueError(f"多变量预测执行失败: {str(e)}")
