"""
@Author      : Ayaki Shi
@Date        : 2025/12/23 16:42 
@Description : DBSCAN聚类算法数据处理器
"""

import logging
from typing import Dict, List, Any
from algorithm.base.base_processor import BaseAlgorithmProcessor
from algorithm.models import (
    AlgorithmExecutionRequest, AlgorithmConfig,
    AlgorithmParameters, AlgorithmType
)

logger = logging.getLogger(__name__)

class DBSCANProcessor(BaseAlgorithmProcessor):

    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.ANOMALY

    @property
    def algorithm_name(self) -> str:
        return "dbscan"

    async def convert_sql_result_to_algorithm_input(
            self,
            sql_result: List[Dict[str, Any]],
            algorithm_config: AlgorithmConfig,
            parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """将SQL结果转换为DBSCAN算法输入格式"""
        try:
            logger.info(f"开始转换SQL结果为DBSCAN算法输入，数据行数: {len(sql_result)}")

            if not sql_result:
                raise ValueError("SQL查询结果为空")

            # 获取参数映射
            param_mapping = parameters.parameter_mapping

            # 简单数据填充 - 直接按照LLM指定的列名填充
            filled_data = await self._simple_data_fill(sql_result, param_mapping)

            # 基础数据清洗
            cleaned_data = await self._clean_numeric_data(filled_data, param_mapping)

            # 构建算法配置
            config = {
                "id_column": param_mapping.get('id_column'),
                "feature_columns": param_mapping.get('feature_columns', []),
                "preprocessing": {
                    "handle_missing": True,
                    "normalize_features": True
                }
            }

            logger.info(f"DBSCAN数据转换完成，配置: {config}")

            return AlgorithmExecutionRequest(
                data_rows=cleaned_data,
                config=config
            )

        except Exception as e:
            logger.error(f"DBSCAN数据转换失败: {str(e)}")
            raise ValueError(f"DBSCAN数据转换失败: {str(e)}")

    async def _clean_numeric_data(
            self,
            filled_data: List[Dict[str, Any]],
            param_mapping: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """DBSCAN清洗数值数据"""
        cleaned_data = []
        feature_columns = param_mapping.get('feature_columns', [])

        for row in filled_data:
            cleaned_row = row.copy()

            # 清洗特征列的数值数据
            for col in feature_columns:
                if col in cleaned_row:
                    value = cleaned_row[col]
                    if value is not None:
                        try:
                            # 转换为浮点数
                            if isinstance(value, str):
                                cleaned_row[col] = float(value.strip())
                            else:
                                cleaned_row[col] = float(value)
                        except (ValueError, TypeError):
                            logger.warning(f"无法转换列{col}的值{value}为数值，设为None")
                            cleaned_row[col] = None

            cleaned_data.append(cleaned_row)

        logger.debug(f"数值数据清洗完成，处理了{len(cleaned_data)}行数据")
        return cleaned_data

    async def validate_algorithm_input(
            self,
            request: AlgorithmExecutionRequest,
            algorithm_config: AlgorithmConfig
    ) -> bool:
        """验证DBSCAN算法输入"""
        try:
            config = request.config
            data_rows = request.data_rows

            # 基础验证
            if not data_rows:
                logger.error("数据行为空")
                return False

            # 验证ID列
            id_column = config.get('id_column')
            if not id_column:
                logger.error("缺少ID列配置")
                return False

            if id_column not in data_rows[0]:
                logger.error(f"数据中缺少ID列: {id_column}")
                return False

            # 验证特征列
            feature_columns = config.get('feature_columns', [])
            if len(feature_columns) < 1:
                logger.error("至少需要1个特征列")
                return False
            if len(feature_columns) > 10:
                logger.error("最多10个特征列")
                return False

            for col in feature_columns:
                if col not in data_rows[0]:
                    logger.error(f"数据中缺少特征列: {col}")
                    return False

            # 验证数据质量
            if not await self._validate_data_quality(data_rows, feature_columns):
                return False

            logger.info("DBSCAN算法输入验证通过")
            return True

        except Exception as e:
            logger.error(f"DBSCAN算法输入验证失败: {str(e)}")
            return False

    async def _validate_data_quality(
            self, 
            data_rows: List[Dict[str, Any]], 
            feature_columns: List[str]
    ) -> bool:
        """验证数据质量"""
        for col in feature_columns:
            # 检查数值型数据比例
            numeric_count = 0
            total_count = 0
            
            for row in data_rows:
                value = row.get(col)
                if value is not None:
                    total_count += 1
                    if isinstance(value, (int, float)):
                        numeric_count += 1
            
            if total_count == 0:
                logger.error(f"特征列{col}没有有效数据")
                return False
            
            numeric_ratio = numeric_count / total_count
            if numeric_ratio < 0.7:
                logger.error(f"特征列{col}的数值比例过低: {numeric_ratio:.2%}")
                return False
        
        return True