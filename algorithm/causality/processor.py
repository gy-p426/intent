"""
@Author      : Causality Analysis Team
@Date        : 2025/01/15
@Description : 因果分析算法数据处理器
"""

import logging
from typing import Dict, List, Any
from algorithm.base.base_processor import BaseAlgorithmProcessor
from algorithm.models import (
    AlgorithmExecutionRequest, AlgorithmConfig,
    AlgorithmParameters, AlgorithmType
)

logger = logging.getLogger(__name__)


class CausalityProcessor(BaseAlgorithmProcessor):
    """因果分析数据处理器"""

    @property
    def algorithm_type(self) -> AlgorithmType:
        """返回算法类型"""
        return AlgorithmType.CAUSALITY

    @property
    def algorithm_name(self) -> str:
        """返回算法名称"""
        return "causality"

    async def convert_sql_result_to_algorithm_input(
            self,
            sql_result: List[Dict[str, Any]],
            algorithm_config: AlgorithmConfig,
            parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """将SQL结果转换为因果分析算法输入格式"""
        try:
            logger.info(f"开始转换SQL结果为因果分析算法输入，数据行数: {len(sql_result)}")

            # 验证SQL结果不为空
            if not sql_result:
                error_msg = "因果分析需要数据才能执行，但SQL查询结果为空。请检查数据源或调整查询条件。"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # 验证参数映射
            if not parameters or not parameters.parameter_mapping:
                error_msg = "参数映射为空，无法确定因变量和自变量。请确保参数提取步骤正确执行。"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # 获取参数映射
            param_mapping = parameters.parameter_mapping

            # 验证参数映射的完整性
            if 'dependent_variable' not in param_mapping:
                error_msg = "参数映射中缺少因变量（dependent_variable）。因果分析需要至少1个因变量。"
                logger.error(error_msg)
                raise ValueError(error_msg)

            if 'independent_variables' not in param_mapping or not param_mapping['independent_variables']:
                error_msg = "参数映射中缺少自变量（independent_variables）。因果分析需要至少1个自变量。"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # 简单数据填充 - 直接按照LLM指定的列名填充
            filled_data = await self._simple_data_fill(sql_result, param_mapping)

            # 验证填充后的数据
            if not filled_data:
                error_msg = "数据填充后为空。请检查SQL查询结果是否包含所需的列。"
                logger.error(error_msg)
                raise ValueError(error_msg)

            # 数据清洗：转换为数值类型
            cleaned_data = await self._clean_numeric_data(filled_data, param_mapping)

            # 验证清洗后的数据
            await self._validate_cleaned_data(cleaned_data, param_mapping)

            # 构建符合算法服务要求的请求格式
            config = await self._build_algorithm_config(cleaned_data, param_mapping)

            logger.info(f"因果分析数据转换完成，配置: {config}")

            return AlgorithmExecutionRequest(
                data_rows=cleaned_data,
                config=config
            )

        except ValueError as e:
            # 已经是格式化的错误消息，直接抛出
            raise
        except Exception as e:
            logger.error(f"因果分析数据转换失败: {str(e)}")
            error_msg = f"因果分析数据转换过程中发生错误: {str(e)}。请检查数据格式和参数配置。"
            raise ValueError(error_msg)

    async def _simple_data_fill(
            self,
            sql_result: List[Dict[str, Any]],
            parameter_mapping: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """填充因果分析所需的数据列"""
        filled_data = []

        for row in sql_result:
            filled_row = {}

            # 填充因变量
            dependent_var = parameter_mapping.get('dependent_variable')
            if dependent_var and dependent_var in row:
                filled_row[dependent_var] = row[dependent_var]

            # 填充自变量
            independent_vars = parameter_mapping.get('independent_variables', [])
            if isinstance(independent_vars, list):
                for var_name in independent_vars:
                    if var_name in row:
                        filled_row[var_name] = row[var_name]

            filled_data.append(filled_row)

        logger.debug(f"数据填充完成，处理了{len(filled_data)}行数据")
        return filled_data

    async def _clean_numeric_data(
            self,
            filled_data: List[Dict[str, Any]],
            param_mapping: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """清洗数值数据：转换为数值类型"""
        cleaned_data = []

        # 获取所有需要清洗的列
        dependent_var = param_mapping.get('dependent_variable')
        independent_vars = param_mapping.get('independent_variables', [])
        all_columns = [dependent_var] + (independent_vars if isinstance(independent_vars, list) else [])

        # 记录转换失败的情况
        conversion_errors = {}

        for row_idx, row in enumerate(filled_data):
            cleaned_row = row.copy()

            # 清洗每一列的数值数据
            for col in all_columns:
                if col in cleaned_row:
                    value = cleaned_row[col]
                    if value is not None:
                        try:
                            # 转换为浮点数
                            if isinstance(value, str):
                                cleaned_value = value.strip()
                                if cleaned_value == '':
                                    cleaned_row[col] = None
                                else:
                                    cleaned_row[col] = float(cleaned_value)
                            else:
                                cleaned_row[col] = float(value)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"第{row_idx + 1}行，列{col}的值'{value}'无法转换为数值，设为None")
                            cleaned_row[col] = None
                            
                            # 记录转换错误
                            if col not in conversion_errors:
                                conversion_errors[col] = []
                            conversion_errors[col].append((row_idx + 1, value))

            cleaned_data.append(cleaned_row)

        # 如果有大量转换错误，给出警告
        for col, errors in conversion_errors.items():
            if len(errors) > len(filled_data) * 0.3:  # 超过30%的数据转换失败
                error_msg = (
                    f"列'{col}'有{len(errors)}个值（占比{len(errors)/len(filled_data):.1%}）无法转换为数值。"
                    f"因果分析需要数值型数据。请检查数据源或数据类型。"
                    f"示例错误值: {errors[:3]}"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)

        logger.debug(f"数值数据清洗完成，处理了{len(cleaned_data)}行数据")
        return cleaned_data

    async def _validate_cleaned_data(
            self,
            cleaned_data: List[Dict[str, Any]],
            param_mapping: Dict[str, Any]
    ) -> None:
        """
        验证清洗后的数据质量，自动过滤常量列
        
        Args:
            cleaned_data: 清洗后的数据
            param_mapping: 参数映射
            
        Raises:
            ValueError: 数据验证失败
        """
        # 获取所有列
        dependent_var = param_mapping.get('dependent_variable')
        independent_vars = param_mapping.get('independent_variables', [])
        all_columns = [dependent_var] + (independent_vars if isinstance(independent_vars, list) else [])

        valid_columns = []
        excluded_columns = []

        # 验证每列的有效数据点数量和变异性
        for col in all_columns:
            valid_count = sum(1 for row in cleaned_data if row.get(col) is not None)
            
            if valid_count < 2:
                error_msg = (
                    f"列'{col}'只有{valid_count}个有效数据点，因果分析至少需要2个数据点。"
                    f"请检查数据源或增加数据量。"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 检查数据变异性（所有值都相同的列自动排除）
            valid_values = [row.get(col) for row in cleaned_data if row.get(col) is not None]
            if len(set(valid_values)) == 1:
                # 记录警告，不抛出错误
                logger.warning(
                    f"列'{col}'的所有值都相同（值为{valid_values[0]}），将从因果分析中排除。"
                    f"因果分析需要变量有变化才能发现关系。"
                )
                excluded_columns.append(col)
            else:
                valid_columns.append(col)

        # 验证过滤后至少有2列有效数据（1个因变量 + 1个自变量）
        if len(valid_columns) < 2:
            error_msg = (
                f"过滤常量列后，只剩{len(valid_columns)}列有效数据，"
                f"因果分析至少需要2列（1个因变量 + 1个自变量）。"
                f"被排除的常量列: {excluded_columns}"
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        # 更新参数映射，移除被排除的列
        if excluded_columns:
            logger.info(f"因果分析将使用{len(valid_columns)}列数据，排除了{len(excluded_columns)}个常量列: {excluded_columns}")
            
            # 更新因变量（如果被排除则清空）
            if dependent_var in excluded_columns:
                param_mapping['dependent_variable'] = None
            
            # 更新自变量列表（移除被排除的列）
            if isinstance(independent_vars, list):
                param_mapping['independent_variables'] = [
                    var for var in independent_vars if var not in excluded_columns
                ]
            
            # 保存排除列信息供后续使用
            param_mapping['excluded_columns'] = excluded_columns
        
        logger.info("清洗后的数据验证通过")

    async def _build_algorithm_config(
            self,
            cleaned_data: List[Dict[str, Any]],
            param_mapping: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建符合算法服务要求的请求格式"""
        # 获取所有列名（已过滤常量列）
        dependent_var = param_mapping.get('dependent_variable')
        independent_vars = param_mapping.get('independent_variables', [])
        excluded_columns = param_mapping.get('excluded_columns', [])
        
        # 构建列名列表（因变量在第一位，排除None值）
        columns = []
        if dependent_var:
            columns.append(dependent_var)
        if isinstance(independent_vars, list):
            columns.extend(independent_vars)

        config = {
            "columns": columns,
            "options": {
                "analysis_type": "causal"
            }
        }
        
        # 如果有排除的列，添加到配置中
        if excluded_columns:
            config["excluded_columns"] = excluded_columns
            config["excluded_reason"] = "列的所有值相同，无法进行因果分析"

        return config

    async def validate_algorithm_input(
            self,
            request: AlgorithmExecutionRequest,
            algorithm_config: AlgorithmConfig
    ) -> bool:
        """验证因果分析算法输入"""
        try:
            config = request.config
            data_rows = request.data_rows

            # 基础验证：数据行不为空
            if not data_rows:
                logger.error("验证失败：数据行为空，无法执行因果分析")
                return False

            # 验证列配置
            columns = config.get('columns', [])
            if len(columns) < 2:
                logger.error(
                    f"验证失败：因果分析至少需要2列数据（1个因变量 + 1个自变量），"
                    f"当前只有{len(columns)}列。请检查参数提取结果。"
                )
                return False

            # 验证每列至少有2个数据点
            for col in columns:
                if col not in data_rows[0]:
                    logger.error(f"验证失败：数据中缺少列'{col}'。请检查SQL查询结果和列名映射。")
                    return False

                # 统计有效数据点
                valid_count = sum(1 for row in data_rows if row.get(col) is not None)
                if valid_count < 2:
                    logger.error(
                        f"验证失败：列'{col}'只有{valid_count}个有效数据点，"
                        f"因果分析至少需要2个数据点。请增加数据量或检查数据质量。"
                    )
                    return False

            # 验证数据质量
            if not await self._validate_data_quality(data_rows, columns):
                return False

            logger.info("因果分析算法输入验证通过")
            return True

        except Exception as e:
            logger.error(f"因果分析算法输入验证过程中发生异常: {str(e)}")
            return False

    async def _validate_data_quality(
            self,
            data_rows: List[Dict[str, Any]],
            columns: List[str]
    ) -> bool:
        """验证数据质量"""
        for col in columns:
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
                logger.error(f"验证失败：列'{col}'没有有效数据。所有值都是None。")
                return False

            numeric_ratio = numeric_count / total_count
            if numeric_ratio < 0.7:
                logger.error(
                    f"验证失败：列'{col}'的数值比例过低（{numeric_ratio:.1%}），"
                    f"因果分析需要至少70%的数据为数值类型。"
                    f"请检查数据类型转换或数据源。"
                )
                return False

        return True
