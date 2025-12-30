"""
Classification Algorithm Data Processor
分类算法数据处理器
"""

import logging
from typing import Dict, List, Any
from algorithm.base.base_processor import BaseAlgorithmProcessor
from algorithm.models import (
    AlgorithmExecutionRequest, AlgorithmConfig,
    AlgorithmParameters, AlgorithmType
)

logger = logging.getLogger(__name__)


class ClassificationProcessor(BaseAlgorithmProcessor):
    """分类算法数据处理器"""

    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.CLASSIFY

    @property
    def algorithm_name(self) -> str:
        return "classification"

    async def convert_sql_result_to_algorithm_input(
            self,
            sql_result: List[Dict[str, Any]],
            algorithm_config: AlgorithmConfig,
            parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """
        将SQL结果转换为分类算法输入格式
        """
        try:
            logger.info(f"开始转换SQL结果为分类算法输入，数据行数: {len(sql_result)}")

            if not sql_result:
                raise ValueError("SQL查询结果为空")

            # 1. 获取参数映射
            param_mapping = parameters.parameter_mapping
            id_column = param_mapping.get('id_column')
            target_column = param_mapping.get('target_column')
            feature_columns = param_mapping.get('feature_columns', [])
            algorithm = param_mapping.get('algorithm')

            if not id_column or not target_column:
                raise ValueError("缺少必要的列配置: id_column 或 target_column")

            # 2. 数据清洗与分流
            train_data = []  # data_sets (有标签)
            predict_data = []  # data_rows (所有数据)

            for row in sql_result:
                # 复制行数据以避免修改原始引用
                cleaned_row = row.copy()

                # 清洗特征列（尝试转为数值）
                for col in feature_columns:
                    if col in cleaned_row and cleaned_row[col] is not None:
                        val = cleaned_row[col]
                        try:
                            # 如果是字符串类型的数字，转为float
                            if isinstance(val, str) and val.replace('.', '', 1).isdigit():
                                cleaned_row[col] = float(val)
                            # 已经是数字则保持
                        except (ValueError, TypeError):
                            pass

                            # 添加到预测集（所有数据都做预测）
                predict_data.append(cleaned_row)

                # 检查是否存在目标值，若存在则加入训练集
                target_val = cleaned_row.get(target_column)
                # 注意：这里认为空字符串或None都不算有效标签
                if target_val is not None and str(target_val).strip() != '':
                    train_data.append(cleaned_row)

            logger.info(
                f"数据处理完成: 总数据{len(sql_result)}行 -> 训练集{len(train_data)}行, 预测集{len(predict_data)}行")

            # 3. 构建算法配置 (匹配服务端的 ClassificationConfig)
            config_payload = {
                "id_column": id_column,
                "target_column": target_column,
                "feature_columns": feature_columns,
                "categorical_columns": [],  # 默认列表，算法端会处理
                "algorithm": algorithm  # 传递用户指定的算法
            }

            # 4. 返回请求对象
            return AlgorithmExecutionRequest(
                data_rows=predict_data,
                data_sets=train_data,
                config=config_payload
            )

        except Exception as e:
            logger.error(f"分类数据转换失败: {str(e)}")
            raise ValueError(f"分类数据转换失败: {str(e)}")

    async def validate_algorithm_input(
            self,
            request: AlgorithmExecutionRequest,
            algorithm_config: AlgorithmConfig
    ) -> bool:
        """验证分类算法输入"""
        try:
            config = request.config
            train_data = request.data_sets

            # 验证配置完整性
            required_keys = ['id_column', 'target_column', 'feature_columns']
            for key in required_keys:
                if not config.get(key):
                    logger.error(f"分类配置缺少必要参数: {key}")
                    return False

            # 验证训练数据
            if not train_data or len(train_data) < 2:
                logger.error(f"训练数据不足: {len(train_data) if train_data else 0}行，至少需要2行带标签的数据进行训练")
                return False

            # 验证特征列存在性
            sample_row = train_data[0]
            for feat in config['feature_columns']:
                if feat not in sample_row:
                    logger.error(f"训练数据中缺少特征列: {feat}")
                    return False

            return True

        except Exception as e:
            logger.error(f"分类输入验证异常: {str(e)}")
            return False