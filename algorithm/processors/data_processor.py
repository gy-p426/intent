"""
Data Processor Implementation

Processes and transforms data between different formats,
particularly converting SQL results to algorithm-compatible input formats.
Includes comprehensive data validation and type conversion capabilities.
"""

import logging
import json
import math
from datetime import datetime, date
from decimal import Decimal
from typing import List, Dict, Any, Union, Optional, Set
from algorithm.models import (
    AlgorithmConfig, AlgorithmParameters, AlgorithmExecutionRequest, AlgorithmField, AlgorithmType
)
from algorithm.interfaces import IDataProcessor


logger = logging.getLogger(__name__)


class DataProcessor(IDataProcessor):
    """数据处理器实现"""
    
    def __init__(self):
        """初始化数据处理器"""
        self.supported_data_types = {
            'string', 'integer', 'float', 'boolean', 'array', 'object', 'datetime'
        }
        self.numeric_types = {'integer', 'float', 'number'}
        self.conversion_stats = {
            'total_conversions': 0,
            'successful_conversions': 0,
            'failed_conversions': 0,
            'type_conversions': {}
        }
        
        # 初始化算法注册中心
        from algorithm.base.registry import algorithm_registry, register_all_algorithms
        register_all_algorithms()
        self.algorithm_registry = algorithm_registry
    
    async def convert_sql_result_to_algorithm_input(
        self,
        sql_result: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """
        将SQL结果转换为算法输入格式
        
        Args:
            sql_result: SQL查询结果
            algorithm_config: 算法配置
            parameters: 算法参数
            
        Returns:
            AlgorithmExecutionRequest: 算法执行请求
            
        Raises:
            ValueError: 数据转换失败时抛出
        """
        logger.info(f"转换SQL结果为{algorithm_config.name}算法输入格式")
        
        try:
            self.conversion_stats['total_conversions'] += 1
            
            # 验证输入数据
            if not sql_result:
                raise ValueError("SQL查询结果为空")
            
            # 尝试使用算法特定处理器
            algorithm_processor = self.algorithm_registry.get_processor_by_type(parameters.algorithm_type)
            if algorithm_processor:
                logger.info(f"使用算法特定处理器: {algorithm_processor.algorithm_name}")
                result = await algorithm_processor.convert_sql_result_to_algorithm_input(
                    sql_result, algorithm_config, parameters
                )
            else:
                logger.info("使用通用处理器")
                result = await self._convert_with_generic_processor(
                    sql_result, algorithm_config, parameters
                )
            
            self.conversion_stats['successful_conversions'] += 1
            logger.info(f"成功转换{len(sql_result)}行数据为{algorithm_config.name}算法输入")
            
            return result
                
        except Exception as e:
            self.conversion_stats['failed_conversions'] += 1
            logger.error(f"SQL结果转换失败: {str(e)}")
            raise ValueError(f"数据转换失败: {str(e)}")
    
    async def _convert_with_generic_processor(
        self,
        sql_result: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """使用通用处理器转换数据"""
        # 数据预处理和清洗
        cleaned_data = await self._clean_and_preprocess_data(sql_result)
        
        # 根据算法类型进行不同的转换
        if "聚类" in algorithm_config.name or parameters.algorithm_type.value == "cluster":
            result = await self._convert_for_clustering(
                cleaned_data, algorithm_config, parameters
            )
        elif "分类" in algorithm_config.name or parameters.algorithm_type.value == "classify":
            result = await self._convert_for_classification(
                cleaned_data, algorithm_config, parameters
            )
        else:
            # 通用转换
            result = await self._convert_generic(
                cleaned_data, algorithm_config, parameters
            )
        
        # 执行数据类型转换和格式化
        formatted_result = await self._format_algorithm_input(result, algorithm_config)
        
        return formatted_result
    
    async def _clean_and_preprocess_data(
        self, 
        sql_result: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        清洗和预处理SQL结果数据
        
        Args:
            sql_result: 原始SQL结果
            
        Returns:
            List[Dict[str, Any]]: 清洗后的数据
        """
        logger.debug(f"开始清洗和预处理{len(sql_result)}行数据")
        
        cleaned_data = []
        
        for row_idx, row in enumerate(sql_result):
            try:
                cleaned_row = {}
                
                for column, value in row.items():
                    # 处理None值
                    if value is None:
                        cleaned_row[column] = None
                        continue
                    
                    # 处理不同数据类型
                    cleaned_value = await self._clean_column_value(column, value)
                    cleaned_row[column] = cleaned_value
                
                cleaned_data.append(cleaned_row)
                
            except Exception as e:
                logger.warning(f"清洗第{row_idx + 1}行数据时出错: {str(e)}")
                # 跳过有问题的行，但记录警告
                continue
        
        logger.debug(f"数据清洗完成，保留{len(cleaned_data)}行有效数据")
        return cleaned_data
    
    async def _clean_column_value(self, column: str, value: Any) -> Any:
        """
        清洗单个列值
        
        Args:
            column: 列名
            value: 原始值
            
        Returns:
            Any: 清洗后的值
        """
        try:
            # 处理字符串类型
            if isinstance(value, str):
                # 去除前后空格
                value = value.strip()
                
                # 处理空字符串
                if value == '':
                    return None
                
                # 尝试转换数字字符串
                if value.replace('.', '').replace('-', '').isdigit():
                    try:
                        if '.' in value:
                            return float(value)
                        else:
                            return int(value)
                    except ValueError:
                        pass
                
                return value
            
            # 处理Decimal类型
            elif isinstance(value, Decimal):
                return float(value)
            
            # 处理日期时间类型
            elif isinstance(value, (datetime, date)):
                return value.isoformat()
            
            # 处理布尔类型
            elif isinstance(value, bool):
                return value
            
            # 处理数字类型
            elif isinstance(value, (int, float)):
                # 检查是否为NaN或无穷大
                if isinstance(value, float):
                    if math.isnan(value) or math.isinf(value):
                        return None
                return value
            
            # 其他类型转换为字符串
            else:
                return str(value)
                
        except Exception as e:
            logger.warning(f"清洗列{column}的值{value}时出错: {str(e)}")
            return value
    
    async def _format_algorithm_input(
        self,
        request: AlgorithmExecutionRequest,
        algorithm_config: AlgorithmConfig
    ) -> AlgorithmExecutionRequest:
        """
        格式化算法输入数据，确保数据类型符合算法要求
        
        Args:
            request: 原始算法执行请求
            algorithm_config: 算法配置
            
        Returns:
            AlgorithmExecutionRequest: 格式化后的请求
        """
        logger.debug(f"格式化{algorithm_config.name}算法输入数据")
        
        try:
            # 格式化数据行
            formatted_data_rows = await self._format_data_rows(
                request.data_rows, algorithm_config, request.config
            )
            
            # 格式化训练数据集（如果存在）
            formatted_data_sets = None
            if request.data_sets:
                formatted_data_sets = await self._format_data_rows(
                    request.data_sets, algorithm_config, request.config
                )
            
            # 格式化配置参数
            formatted_config = await self._format_config_parameters(
                request.config, algorithm_config
            )
            
            return AlgorithmExecutionRequest(
                data_rows=formatted_data_rows,
                data_sets=formatted_data_sets,
                config=formatted_config
            )
            
        except Exception as e:
            logger.error(f"格式化算法输入数据失败: {str(e)}")
            raise ValueError(f"数据格式化失败: {str(e)}")
    
    async def _format_data_rows(
        self,
        data_rows: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        格式化数据行，确保数据类型正确
        
        Args:
            data_rows: 原始数据行
            algorithm_config: 算法配置
            config: 算法参数配置
            
        Returns:
            List[Dict[str, Any]]: 格式化后的数据行
        """
        if not data_rows:
            return data_rows
        
        formatted_rows = []
        
        # 获取列类型信息
        column_types = await self._infer_column_types(data_rows, config)
        
        for row in data_rows:
            formatted_row = {}
            
            for column, value in row.items():
                if value is None:
                    formatted_row[column] = None
                    continue
                
                # 根据列类型进行格式化
                column_type = column_types.get(column, 'string')
                formatted_value = await self._convert_value_to_type(
                    value, column_type, column
                )
                formatted_row[column] = formatted_value
            
            formatted_rows.append(formatted_row)
        
        return formatted_rows
    
    async def _infer_column_types(
        self,
        data_rows: List[Dict[str, Any]],
        config: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        推断列的数据类型
        
        Args:
            data_rows: 数据行
            config: 算法配置
            
        Returns:
            Dict[str, str]: 列名到类型的映射
        """
        column_types = {}
        
        if not data_rows:
            return column_types
        
        # 获取特征列和其他重要列
        feature_columns = config.get("feature_columns", [])
        id_column = config.get("id_column")
        target_column = config.get("target_column")
        categorical_columns = config.get("categorical_columns", [])
        
        # 分析每一列的数据类型
        for column in data_rows[0].keys():
            # 收集该列的非空值样本
            samples = []
            for row in data_rows[:min(100, len(data_rows))]:  # 最多分析100行
                value = row.get(column)
                if value is not None:
                    samples.append(value)
            
            if not samples:
                column_types[column] = 'string'
                continue
            
            # 根据列的用途和数据特征推断类型
            if column == id_column:
                column_types[column] = 'string'  # ID通常作为字符串处理
            elif column in categorical_columns:
                column_types[column] = 'string'  # 分类列作为字符串
            elif column in feature_columns:
                # 特征列优先推断为数值类型
                inferred_type = self._infer_numeric_type(samples)
                column_types[column] = inferred_type
            else:
                # 其他列根据数据内容推断
                column_types[column] = self._infer_general_type(samples)
        
        logger.debug(f"推断的列类型: {column_types}")
        return column_types
    
    def _infer_numeric_type(self, samples: List[Any]) -> str:
        """
        推断数值类型
        
        Args:
            samples: 数据样本
            
        Returns:
            str: 推断的类型
        """
        numeric_count = 0
        has_float = False
        
        for sample in samples:
            try:
                if isinstance(sample, (int, float)):
                    numeric_count += 1
                    if isinstance(sample, float) or '.' in str(sample):
                        has_float = True
                elif isinstance(sample, str):
                    float(sample)  # 尝试转换为浮点数
                    numeric_count += 1
                    if '.' in sample:
                        has_float = True
            except (ValueError, TypeError):
                continue
        
        # 如果大部分样本都是数值类型
        if numeric_count / len(samples) > 0.8:
            return 'float' if has_float else 'integer'
        else:
            return 'string'
    
    def _infer_general_type(self, samples: List[Any]) -> str:
        """
        推断一般数据类型
        
        Args:
            samples: 数据样本
            
        Returns:
            str: 推断的类型
        """
        type_counts = {}
        
        for sample in samples:
            if isinstance(sample, bool):
                sample_type = 'boolean'
            elif isinstance(sample, int):
                sample_type = 'integer'
            elif isinstance(sample, float):
                sample_type = 'float'
            elif isinstance(sample, str):
                # 尝试推断字符串的实际类型
                if sample.lower() in ['true', 'false', '1', '0']:
                    sample_type = 'boolean'
                elif sample.replace('.', '').replace('-', '').isdigit():
                    sample_type = 'float' if '.' in sample else 'integer'
                else:
                    sample_type = 'string'
            else:
                sample_type = 'string'
            
            type_counts[sample_type] = type_counts.get(sample_type, 0) + 1
        
        # 返回最常见的类型
        return max(type_counts, key=type_counts.get) if type_counts else 'string'
    
    async def _convert_value_to_type(
        self, 
        value: Any, 
        target_type: str, 
        column_name: str
    ) -> Any:
        """
        将值转换为目标类型
        
        Args:
            value: 原始值
            target_type: 目标类型
            column_name: 列名（用于日志）
            
        Returns:
            Any: 转换后的值
        """
        if value is None:
            return None
        
        try:
            # 记录类型转换统计
            conversion_key = f"{type(value).__name__}_to_{target_type}"
            self.conversion_stats['type_conversions'][conversion_key] = \
                self.conversion_stats['type_conversions'].get(conversion_key, 0) + 1
            
            if target_type == 'string':
                return str(value)
            
            elif target_type == 'integer':
                if isinstance(value, str):
                    # 处理字符串转整数
                    value = value.strip()
                    if value == '':
                        return None
                    # 先转换为浮点数再转整数，处理"3.0"这样的情况
                    return int(float(value))
                elif isinstance(value, float):
                    return int(value)
                elif isinstance(value, bool):
                    return int(value)
                else:
                    return int(value)
            
            elif target_type == 'float':
                if isinstance(value, str):
                    value = value.strip()
                    if value == '':
                        return None
                    return float(value)
                elif isinstance(value, bool):
                    return float(value)
                else:
                    return float(value)
            
            elif target_type == 'boolean':
                if isinstance(value, str):
                    value = value.strip().lower()
                    if value in ['true', '1', 'yes', 'y']:
                        return True
                    elif value in ['false', '0', 'no', 'n']:
                        return False
                    else:
                        return bool(value)
                else:
                    return bool(value)
            
            elif target_type == 'array':
                if isinstance(value, str):
                    # 尝试解析JSON数组
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, list):
                            return parsed
                    except json.JSONDecodeError:
                        # 尝试按逗号分割
                        return [item.strip() for item in value.split(',')]
                elif isinstance(value, list):
                    return value
                else:
                    return [value]
            
            else:
                # 默认转换为字符串
                return str(value)
                
        except Exception as e:
            logger.warning(f"转换列{column_name}的值{value}到类型{target_type}失败: {str(e)}")
            # 转换失败时返回原值
            return value
    
    async def _format_config_parameters(
        self,
        config: Dict[str, Any],
        algorithm_config: AlgorithmConfig
    ) -> Dict[str, Any]:
        """
        格式化配置参数，确保参数类型正确
        
        Args:
            config: 原始配置
            algorithm_config: 算法配置
            
        Returns:
            Dict[str, Any]: 格式化后的配置
        """
        formatted_config = {}
        
        # 处理必需字段
        for field in algorithm_config.required_fields:
            field_name = field.field
            if field_name in config:
                formatted_value = await self._format_config_field(
                    config[field_name], field
                )
                formatted_config[field_name] = formatted_value
            else:
                logger.warning(f"缺少必需配置字段: {field_name}")
        
        # 处理可选字段
        for field in algorithm_config.optional_fields:
            field_name = field.field
            if field_name in config:
                formatted_value = await self._format_config_field(
                    config[field_name], field
                )
                formatted_config[field_name] = formatted_value
            elif field.default is not None:
                formatted_config[field_name] = field.default
        
        # 保留其他配置项
        for key, value in config.items():
            if key not in formatted_config:
                formatted_config[key] = value
        
        return formatted_config
    
    async def _format_config_field(
        self, 
        value: Any, 
        field: AlgorithmField
    ) -> Any:
        """
        格式化单个配置字段
        
        Args:
            value: 字段值
            field: 字段定义
            
        Returns:
            Any: 格式化后的值
        """
        if value is None:
            return field.default
        
        try:
            return await self._convert_value_to_type(
                value, field.type, field.field
            )
        except Exception as e:
            logger.warning(f"格式化配置字段{field.field}失败: {str(e)}")
            return value
    
    async def _convert_for_clustering(
        self,
        sql_result: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """
        为聚类算法转换数据
        
        Args:
            sql_result: SQL查询结果
            algorithm_config: 算法配置
            parameters: 算法参数
            
        Returns:
            AlgorithmExecutionRequest: 聚类算法执行请求
        """
        try:
            # 提取参数映射中的配置
            param_mapping = parameters.parameter_mapping
            
            # 确定ID列和特征列
            id_column = param_mapping.get("id_column", "id")
            feature_columns = param_mapping.get("feature_columns", [])
            
            # 如果没有指定特征列，自动推断
            if not feature_columns and sql_result:
                sample_row = sql_result[0]
                feature_columns = [
                    col for col in sample_row.keys() 
                    if col != id_column and isinstance(sample_row[col], (int, float))
                ]
            
            # 构建算法配置
            config = {
                "id_column": id_column,
                "feature_columns": feature_columns,
                "k_value": param_mapping.get("k_value")
            }
            
            return AlgorithmExecutionRequest(
                data_rows=sql_result,
                config=config
            )
            
        except Exception as e:
            logger.error(f"聚类数据转换失败: {str(e)}")
            raise
    
    async def _convert_for_classification(
        self,
        sql_result: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """
        为分类算法转换数据
        
        Args:
            sql_result: SQL查询结果
            algorithm_config: 算法配置
            parameters: 算法参数
            
        Returns:
            AlgorithmExecutionRequest: 分类算法执行请求
        """
        try:
            # 提取参数映射中的配置
            param_mapping = parameters.parameter_mapping
            
            # 确定各种列
            id_column = param_mapping.get("id_column", "id")
            feature_columns = param_mapping.get("feature_columns", [])
            target_column = param_mapping.get("target_column", "target")
            categorical_columns = param_mapping.get("categorical_columns", [])
            
            # 如果没有指定特征列，自动推断
            if not feature_columns and sql_result:
                sample_row = sql_result[0]
                feature_columns = [
                    col for col in sample_row.keys() 
                    if col not in [id_column, target_column]
                ]
            
            # 分离训练数据和预测数据
            # 这里假设SQL结果包含了所有数据，需要根据是否有target值来分离
            train_data = []
            predict_data = []
            
            for row in sql_result:
                if target_column in row and row[target_column] is not None:
                    train_data.append(row)
                else:
                    predict_data.append(row)
            
            # 构建算法配置
            config = {
                "id_column": id_column,
                "feature_columns": feature_columns,
                "target_column": target_column,
                "categorical_columns": categorical_columns,
                "algorithm": param_mapping.get("algorithm")
            }
            
            return AlgorithmExecutionRequest(
                data_rows=predict_data if predict_data else sql_result,
                data_sets=train_data if train_data else None,
                config=config
            )
            
        except Exception as e:
            logger.error(f"分类数据转换失败: {str(e)}")
            raise
    
    async def _convert_generic(
        self,
        sql_result: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """
        通用数据转换
        
        Args:
            sql_result: SQL查询结果
            algorithm_config: 算法配置
            parameters: 算法参数
            
        Returns:
            AlgorithmExecutionRequest: 通用算法执行请求
        """
        try:
            # 基础配置
            config = dict(parameters.parameter_mapping)
            
            return AlgorithmExecutionRequest(
                data_rows=sql_result,
                config=config
            )
            
        except Exception as e:
            logger.error(f"通用数据转换失败: {str(e)}")
            raise
    
    async def validate_algorithm_input(
        self,
        request: AlgorithmExecutionRequest,
        algorithm_config: AlgorithmConfig
    ) -> bool:
        """
        验证算法输入数据
        
        Args:
            request: 算法执行请求
            algorithm_config: 算法配置
            
        Returns:
            bool: 数据是否有效
        """
        logger.debug(f"验证{algorithm_config.name}算法输入数据")
        
        try:
            # 尝试使用算法特定处理器验证
            # 从算法配置推断算法类型
            algorithm_type = self._infer_algorithm_type_from_config(algorithm_config)
            if algorithm_type:
                algorithm_processor = self.algorithm_registry.get_processor_by_type(algorithm_type)
                if algorithm_processor:
                    logger.info(f"使用算法特定验证器: {algorithm_processor.algorithm_name}")
                    return await algorithm_processor.validate_algorithm_input(request, algorithm_config)
            
            # 回退到通用验证
            logger.info("使用通用验证器")
            return await self._validate_with_generic_validator(request, algorithm_config)
            
        except Exception as e:
            logger.error(f"验证算法输入数据失败: {str(e)}")
            return False
    
    def _infer_algorithm_type_from_config(self, algorithm_config: AlgorithmConfig) -> Optional[AlgorithmType]:
        """从算法配置推断算法类型"""
        try:
            algorithm_name_lower = algorithm_config.name.lower()
            
            # 优先匹配更具体的算法类型，避免关键词冲突
            # 异常检测算法统一映射到ANOMALY类型
            if "异常" in algorithm_config.name or "anomaly" in algorithm_name_lower:
                return AlgorithmType.ANOMALY
            # 注释掉具体异常检测算法的特殊处理，统一使用ANOMALY
            # elif "dbscan" in algorithm_name_lower or "密度聚类" in algorithm_config.name:
            #     return AlgorithmType.DBSCAN
            # elif "iforest" in algorithm_name_lower or "孤立森林" in algorithm_config.name or "isolation forest" in algorithm_name_lower:
            #     return AlgorithmType.IFOREST
            elif "聚类" in algorithm_config.name or "cluster" in algorithm_name_lower:
                return AlgorithmType.CLUSTER
            elif ("分类" in algorithm_config.name or
                  "classif" in algorithm_name_lower or
                  "xgboost" in algorithm_name_lower or
                  "tabnet" in algorithm_name_lower):
                return AlgorithmType.CLASSIFY
            elif "预测" in algorithm_config.name or "forecast" in algorithm_name_lower or "predict" in algorithm_name_lower:
                return AlgorithmType.PREDICT
            elif "关联" in algorithm_config.name or "associate" in algorithm_name_lower:
                return AlgorithmType.ASSOCIATE
            elif "相似" in algorithm_config.name or "similarity" in algorithm_name_lower:
                return AlgorithmType.SIMILARITY
            elif "趋势" in algorithm_config.name or "trend" in algorithm_name_lower:
                return AlgorithmType.TREND
            else:
                return None
        except Exception as e:
            logger.warning(f"推断算法类型失败: {str(e)}")
            return None
    
    async def _validate_with_generic_validator(
        self,
        request: AlgorithmExecutionRequest,
        algorithm_config: AlgorithmConfig
    ) -> bool:
        """使用通用验证器验证数据"""
        # 基础验证
        if not request.data_rows:
            logger.error("数据行为空")
            return False
        
        if not request.config:
            logger.error("算法配置为空")
            return False
        
        # 验证必需字段
        if not await self._validate_required_fields(request, algorithm_config):
            return False
        
        # 验证数据行结构
        if not await self._validate_data_rows_structure(request.data_rows, request.config):
            return False
        
        # 验证数据质量
        if not await self._validate_data_quality(request.data_rows, request.config):
            return False
        
        # 验证数据类型
        if not await self._validate_data_types(request, algorithm_config):
            return False
        
        # 算法特定验证
        if "聚类" in algorithm_config.name or "cluster" in algorithm_config.name.lower():
            return await self._validate_clustering_input(request, algorithm_config)
        elif "分类" in algorithm_config.name or "classif" in algorithm_config.name.lower():
            return await self._validate_classification_input(request, algorithm_config)
        
        return True
    
    async def _validate_required_fields(
        self,
        request: AlgorithmExecutionRequest,
        algorithm_config: AlgorithmConfig
    ) -> bool:
        """
        验证必需字段
        
        Args:
            request: 算法执行请求
            algorithm_config: 算法配置
            
        Returns:
            bool: 必需字段是否有效
        """
        if not algorithm_config.required_fields:
            return True
        
        for field in algorithm_config.required_fields:
            field_name = field.field
            
            # 特殊处理data_rows字段，它在request对象中而不是config中
            if field_name == "data_rows":
                if not request.data_rows:
                    logger.error("数据行为空")
                    return False
                continue
            
            # 特殊处理data_sets字段
            if field_name == "data_sets":
                # data_sets是可选的，在某些情况下可能为空
                continue
            
            # 检查配置中是否包含必需字段
            if field_name not in request.config:
                logger.error(f"缺少必需字段: {field_name}")
                return False
            
            # 检查字段值是否有效
            field_value = request.config[field_name]
            if field_value is None and field.default is None:
                logger.error(f"必需字段值为空: {field_name}")
                return False
            
            # 验证字段类型
            if not await self._validate_field_type(field_value, field):
                logger.error(f"字段{field_name}类型不匹配，期望{field.type}")
                return False
            
            # 验证字段选项
            if field.options and field_value not in field.options:
                logger.error(f"字段{field_name}的值{field_value}不在允许的选项中: {field.options}")
                return False
        
        return True
    
    async def _validate_field_type(self, value: Any, field: AlgorithmField) -> bool:
        """
        验证字段类型
        
        Args:
            value: 字段值
            field: 字段定义
            
        Returns:
            bool: 类型是否匹配
        """
        if value is None:
            return True
        
        try:
            field_type = field.type.lower()
            
            if field_type == 'string':
                return isinstance(value, str)
            elif field_type in ['integer', 'int']:
                return isinstance(value, int) or (isinstance(value, str) and value.isdigit())
            elif field_type in ['float', 'number']:
                return isinstance(value, (int, float)) or (isinstance(value, str) and self._is_numeric(value))
            elif field_type == 'boolean':
                return isinstance(value, bool) or (isinstance(value, str) and value.lower() in ['true', 'false'])
            elif field_type == 'array':
                return isinstance(value, list)
            elif field_type == 'object':
                return isinstance(value, dict)
            else:
                # 未知类型，默认通过
                return True
                
        except Exception as e:
            logger.warning(f"验证字段类型时出错: {str(e)}")
            return False
    
    def _is_numeric(self, value: str) -> bool:
        """
        检查字符串是否为数值
        
        Args:
            value: 字符串值
            
        Returns:
            bool: 是否为数值
        """
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    
    async def _validate_data_quality(
        self,
        data_rows: List[Dict[str, Any]],
        config: Dict[str, Any]
    ) -> bool:
        """
        验证数据质量
        
        Args:
            data_rows: 数据行
            config: 算法配置
            
        Returns:
            bool: 数据质量是否合格
        """
        if not data_rows:
            return False
        
        # 获取关键列
        feature_columns = config.get("feature_columns", [])
        id_column = config.get("id_column")
        
        # 检查数据完整性
        null_counts = {}
        for column in feature_columns:
            null_count = sum(1 for row in data_rows if row.get(column) is None)
            null_counts[column] = null_count
            
            # 如果某个特征列的空值超过50%，发出警告
            null_ratio = null_count / len(data_rows)
            if null_ratio > 0.5:
                logger.warning(f"特征列{column}的空值比例过高: {null_ratio:.2%}")
        
        # 检查ID唯一性（如果有ID列）
        if id_column:
            ids = [row.get(id_column) for row in data_rows if row.get(id_column) is not None]
            if len(ids) != len(set(ids)):
                logger.warning(f"ID列{id_column}存在重复值")
        
        # 检查数据行的一致性
        if not await self._validate_data_consistency(data_rows):
            return False
        
        return True
    
    async def _validate_data_consistency(
        self,
        data_rows: List[Dict[str, Any]]
    ) -> bool:
        """
        验证数据一致性
        
        Args:
            data_rows: 数据行
            
        Returns:
            bool: 数据是否一致
        """
        if not data_rows:
            return True
        
        # 检查所有行是否有相同的列
        first_row_columns = set(data_rows[0].keys())
        
        for idx, row in enumerate(data_rows[1:], start=1):
            row_columns = set(row.keys())
            if row_columns != first_row_columns:
                missing_columns = first_row_columns - row_columns
                extra_columns = row_columns - first_row_columns
                
                if missing_columns:
                    logger.warning(f"第{idx + 1}行缺少列: {missing_columns}")
                if extra_columns:
                    logger.warning(f"第{idx + 1}行有额外的列: {extra_columns}")
        
        return True
    
    async def _validate_data_types(
        self,
        request: AlgorithmExecutionRequest,
        algorithm_config: AlgorithmConfig
    ) -> bool:
        """
        验证数据类型
        
        Args:
            request: 算法执行请求
            algorithm_config: 算法配置
            
        Returns:
            bool: 数据类型是否正确
        """
        config = request.config
        feature_columns = config.get("feature_columns", [])
        
        if not feature_columns:
            return True
        
        # 检查特征列的数据类型
        for column in feature_columns:
            # 收集该列的非空值
            values = [
                row.get(column) for row in request.data_rows 
                if row.get(column) is not None
            ]
            
            if not values:
                logger.warning(f"特征列{column}没有非空值")
                continue
            
            # 检查是否为数值类型
            numeric_count = sum(1 for v in values if isinstance(v, (int, float)))
            numeric_ratio = numeric_count / len(values)
            
            if numeric_ratio < 0.8:
                logger.warning(f"特征列{column}的数值类型比例较低: {numeric_ratio:.2%}")
        
        return True
    
    async def _validate_data_rows_structure(
        self, 
        data_rows: List[Dict[str, Any]], 
        config: Dict[str, Any]
    ) -> bool:
        """
        验证数据行结构
        
        Args:
            data_rows: 数据行
            config: 算法配置
            
        Returns:
            bool: 结构是否有效
        """
        try:
            if not data_rows:
                return False
            
            # 检查第一行的结构
            sample_row = data_rows[0]
            
            # 验证ID列
            id_column = config.get("id_column")
            if id_column and id_column not in sample_row:
                logger.error(f"数据行中缺少ID列: {id_column}")
                return False
            
            # 验证特征列
            feature_columns = config.get("feature_columns", [])
            for col in feature_columns:
                if col not in sample_row:
                    logger.error(f"数据行中缺少特征列: {col}")
                    return False
            
            # 验证目标列（如果存在）
            target_column = config.get("target_column")
            if target_column:
                # 检查是否有任何行包含目标列
                has_target = any(target_column in row for row in data_rows)
                if not has_target:
                    logger.warning(f"数据行中没有目标列: {target_column}")
            
            return True
            
        except Exception as e:
            logger.error(f"验证数据行结构失败: {str(e)}")
            return False
    
    async def _validate_clustering_input(
        self, 
        request: AlgorithmExecutionRequest, 
        algorithm_config: AlgorithmConfig
    ) -> bool:
        """
        验证聚类算法输入
        
        Args:
            request: 算法执行请求
            algorithm_config: 算法配置
            
        Returns:
            bool: 输入是否有效
        """
        try:
            config = request.config
            
            # 验证特征列数量
            feature_columns = config.get("feature_columns", [])
            if len(feature_columns) < 1:
                logger.error("聚类算法至少需要1个特征列")
                return False
            
            # 验证数据行数量
            if len(request.data_rows) < 2:
                logger.error("聚类算法至少需要2行数据")
                return False
            
            # 验证K值
            k_value = config.get("k_value")
            if k_value is not None:
                if not isinstance(k_value, int) or k_value < 1:
                    logger.error("K值必须是正整数")
                    return False
                
                if k_value > len(request.data_rows):
                    logger.error("K值不能大于数据行数")
                    return False
            
            # 验证特征列的数值性
            if not await self._validate_numeric_features(request.data_rows, feature_columns):
                logger.error("聚类算法的特征列必须包含数值数据")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"验证聚类算法输入失败: {str(e)}")
            return False
    
    async def _validate_classification_input(
        self, 
        request: AlgorithmExecutionRequest, 
        algorithm_config: AlgorithmConfig
    ) -> bool:
        """
        验证分类算法输入
        
        Args:
            request: 算法执行请求
            algorithm_config: 算法配置
            
        Returns:
            bool: 输入是否有效
        """
        try:
            config = request.config
            
            # 验证特征列
            feature_columns = config.get("feature_columns", [])
            if len(feature_columns) < 1:
                logger.error("分类算法至少需要1个特征列")
                return False
            
            # 验证目标列
            target_column = config.get("target_column")
            if not target_column:
                logger.error("分类算法需要指定目标列")
                return False
            
            # 如果有训练数据，验证训练数据
            if request.data_sets:
                if len(request.data_sets) < 2:
                    logger.error("分类算法训练数据至少需要2行")
                    return False
                
                # 验证训练数据包含目标列
                sample_train_row = request.data_sets[0]
                if target_column not in sample_train_row:
                    logger.error(f"训练数据中缺少目标列: {target_column}")
                    return False
                
                # 验证目标列的类别数量
                target_values = [
                    row.get(target_column) for row in request.data_sets 
                    if row.get(target_column) is not None
                ]
                unique_targets = set(target_values)
                
                if len(unique_targets) < 2:
                    logger.error("分类算法的目标列至少需要2个不同的类别")
                    return False
                
                if len(unique_targets) > 100:
                    logger.warning(f"目标列有{len(unique_targets)}个类别，可能过多")
            
            return True
            
        except Exception as e:
            logger.error(f"验证分类算法输入失败: {str(e)}")
            return False
    
    async def _validate_numeric_features(
        self,
        data_rows: List[Dict[str, Any]],
        feature_columns: List[str]
    ) -> bool:
        """
        验证特征列是否为数值类型
        
        Args:
            data_rows: 数据行
            feature_columns: 特征列名列表
            
        Returns:
            bool: 特征列是否都是数值类型
        """
        for column in feature_columns:
            numeric_count = 0
            total_count = 0
            
            for row in data_rows:
                value = row.get(column)
                if value is not None:
                    total_count += 1
                    if isinstance(value, (int, float)):
                        numeric_count += 1
                    elif isinstance(value, str) and self._is_numeric(value):
                        numeric_count += 1
            
            if total_count == 0:
                logger.error(f"特征列{column}没有有效数据")
                return False
            
            numeric_ratio = numeric_count / total_count
            if numeric_ratio < 0.8:
                logger.error(f"特征列{column}的数值比例过低: {numeric_ratio:.2%}")
                return False
        
        return True
    
    def get_conversion_stats(self) -> Dict[str, Any]:
        """
        获取数据转换统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "total_conversions": self.conversion_stats['total_conversions'],
            "successful_conversions": self.conversion_stats['successful_conversions'],
            "failed_conversions": self.conversion_stats['failed_conversions'],
            "success_rate": (
                self.conversion_stats['successful_conversions'] / 
                max(1, self.conversion_stats['total_conversions'])
            ),
            "type_conversions": dict(self.conversion_stats['type_conversions'])
        }
    
    def reset_conversion_stats(self) -> None:
        """重置转换统计信息"""
        self.conversion_stats = {
            'total_conversions': 0,
            'successful_conversions': 0,
            'failed_conversions': 0,
            'type_conversions': {}
        }
    
    async def validate_data_format_compatibility(
        self,
        data_rows: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig
    ) -> Dict[str, Any]:
        """
        验证数据格式与算法的兼容性
        
        Args:
            data_rows: 数据行
            algorithm_config: 算法配置
            
        Returns:
            Dict[str, Any]: 兼容性检查结果
        """
        result = {
            "compatible": True,
            "issues": [],
            "warnings": [],
            "recommendations": []
        }
        
        try:
            if not data_rows:
                result["compatible"] = False
                result["issues"].append("数据为空")
                return result
            
            data_format = algorithm_config.data_format.lower()
            
            # 检查数据格式兼容性
            if data_format == "tabular":
                # 表格数据格式检查
                if not isinstance(data_rows[0], dict):
                    result["compatible"] = False
                    result["issues"].append("表格数据格式要求每行��字典结构")
            
            elif data_format == "time_series":
                # 时间序列数据格式检查
                time_columns = [
                    col for col in data_rows[0].keys() 
                    if 'time' in col.lower() or 'date' in col.lower()
                ]
                if not time_columns:
                    result["warnings"].append("时间序列数据建议包含时间列")
            
            elif data_format == "transactional":
                # 事务数据格式检查
                required_cols = ['transaction_id', 'item_id']
                missing_cols = [
                    col for col in required_cols 
                    if col not in data_rows[0]
                ]
                if missing_cols:
                    result["warnings"].append(f"事务数据建议包含列: {missing_cols}")
            
            # 检查数据量
            row_count = len(data_rows)
            if row_count < 10:
                result["warnings"].append(f"数据量较少({row_count}行)，可能影响算法效果")
            elif row_count > 100000:
                result["warnings"].append(f"数据量较大({row_count}行)，建议考虑采样或分批处理")
            
            # 检查列数量
            col_count = len(data_rows[0])
            if col_count > 1000:
                result["warnings"].append(f"列数较多({col_count}列)，建议进行特征选择")
            
            return result
            
        except Exception as e:
            result["compatible"] = False
            result["issues"].append(f"兼容性检查失败: {str(e)}")
            return result