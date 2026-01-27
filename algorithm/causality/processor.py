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
        验证清洗后的数据质量，自动过滤不符合要求的列
        
        Args:
            cleaned_data: 清洗后的数据
            param_mapping: 参数映射
            
        Raises:
            ValueError: 数据验证失败（所有列都不符合要求时）
        """
        # 获取所有列
        dependent_var = param_mapping.get('dependent_variable')
        independent_vars = param_mapping.get('independent_variables', [])
        all_columns = [dependent_var] + (independent_vars if isinstance(independent_vars, list) else [])

        valid_columns = []
        excluded_columns = []
        exclusion_reasons = {}

        # 验证每列的有效数据点数量和变异性
        for col in all_columns:
            valid_count = sum(1 for row in cleaned_data if row.get(col) is not None)
            
            # 数据点不足，自动排除
            if valid_count < 2:
                logger.warning(
                    f"列'{col}'只有{valid_count}个有效数据点（需要至少2个），将自动排除"
                )
                excluded_columns.append(col)
                exclusion_reasons[col] = f"数据点不足（{valid_count}<2）"
                continue
            
            # 检查数据变异性（所有值都相同的列自动排除）
            valid_values = [row.get(col) for row in cleaned_data if row.get(col) is not None]
            if len(set(valid_values)) == 1:
                logger.warning(
                    f"列'{col}'的所有值都相同（值为{valid_values[0]}），将自动排除"
                )
                excluded_columns.append(col)
                exclusion_reasons[col] = f"常量列（值={valid_values[0]}）"
                continue
            
            # 通过验证
            valid_columns.append(col)

        # 验证过滤后至少有2列有效数据（1个因变量 + 1个自变量）
        if len(valid_columns) < 2:
            error_msg = (
                f"过滤后只剩{len(valid_columns)}列有效数据，"
                f"因果分析至少需要2列（1个因变量 + 1个自变量）。\n"
                f"被排除的列及原因:\n"
            )
            for col in excluded_columns:
                error_msg += f"  - {col}: {exclusion_reasons.get(col, '未知原因')}\n"
            logger.error(error_msg)
            raise ValueError(error_msg)

        # 更新参数映射，移除被排除的列
        if excluded_columns:
            logger.info(
                f"因果分析将使用{len(valid_columns)}列数据，"
                f"自动排除了{len(excluded_columns)}列: {excluded_columns}"
            )
            
            # 检查因变量是否被排除
            if dependent_var in excluded_columns:
                error_msg = (
                    f"因变量'{dependent_var}'不符合要求，无法进行因果分析。\n"
                    f"原因: {exclusion_reasons.get(dependent_var, '未知原因')}\n"
                    f"因变量必须有至少2个不同的有效数据点。"
                )
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            # 更新自变量列表（移除被排除的列）
            if isinstance(independent_vars, list):
                new_independent_vars = [
                    var for var in independent_vars if var not in excluded_columns
                ]
                param_mapping['independent_variables'] = new_independent_vars
                
                # 验证至少还有1个自变量
                if len(new_independent_vars) < 1:
                    error_msg = (
                        f"所有自变量都被排除，无法进行因果分析。\n"
                        f"被排除的自变量及原因:\n"
                    )
                    for var in independent_vars:
                        if var in excluded_columns:
                            error_msg += f"  - {var}: {exclusion_reasons.get(var, '未知原因')}\n"
                    logger.error(error_msg)
                    raise ValueError(error_msg)
            
            # 保存排除列信息供后续使用
            param_mapping['excluded_columns'] = excluded_columns
            param_mapping['exclusion_reasons'] = exclusion_reasons
        
        logger.info(
            f"数据验证通过 - 有效列: {len(valid_columns)}, "
            f"排除列: {len(excluded_columns)}"
        )


    async def _build_algorithm_config(
            self,
            cleaned_data: List[Dict[str, Any]],
            param_mapping: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建符合算法服务要求的请求格式（新格式：因变量和自变量分开）"""
        # 获取所有列名（已过滤常量列）
        dependent_var = param_mapping.get('dependent_variable')
        independent_vars = param_mapping.get('independent_variables', [])
        excluded_columns = param_mapping.get('excluded_columns', [])
        
        # 验证因变量存在
        if not dependent_var:
            raise ValueError("因变量不能为空")
        
        # 验证自变量列表
        if not independent_vars or not isinstance(independent_vars, list):
            raise ValueError("自变量列表不能为空")

        config = {
            "dependent_variable": dependent_var,  # 因变量
            "independent_variables": independent_vars,  # 自变量列表
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
        """验证因果分析算法输入，自动过滤不符合要求的列"""
        try:
            config = request.config
            data_rows = request.data_rows

            # 基础验证：数据行不为空
            if not data_rows:
                logger.error("验证失败：数据行为空，无法执行因果分析")
                return False

            # 验证因变量
            dependent_var = config.get('dependent_variable')
            if not dependent_var:
                logger.error("验证失败：缺少因变量（dependent_variable）")
                return False

            # 验证自变量
            independent_vars = config.get('independent_variables', [])
            if not independent_vars or not isinstance(independent_vars, list):
                logger.error("验证失败：缺少自变量（independent_variables）或格式不正确")
                return False

            # 验证所有列（因变量 + 自变量）
            all_columns = [dependent_var] + independent_vars
            valid_columns = []
            excluded_columns = []
            exclusion_reasons = {}

            # 验证每列，自动过滤不符合要求的列
            for col in all_columns:
                # 检查列是否存在
                if col not in data_rows[0]:
                    logger.warning(f"列'{col}'在数据中不存在，将自动排除")
                    excluded_columns.append(col)
                    exclusion_reasons[col] = "列不存在"
                    continue

                # 统计有效数据点
                valid_count = sum(1 for row in data_rows if row.get(col) is not None)
                if valid_count < 2:
                    logger.warning(
                        f"列'{col}'只有{valid_count}个有效数据点（需要至少2个），将自动排除"
                    )
                    excluded_columns.append(col)
                    exclusion_reasons[col] = f"数据点不足（{valid_count}<2）"
                    continue

                # 检查数据质量
                if not await self._check_column_quality(data_rows, col):
                    logger.warning(f"列'{col}'数据质量不符合要求，将自动排除")
                    excluded_columns.append(col)
                    exclusion_reasons[col] = "数据质量不符合要求"
                    continue

                # 通过验证
                valid_columns.append(col)

            # 验证过滤后至少有2列（1个因变量 + 1个自变量）
            if len(valid_columns) < 2:
                error_msg = (
                    f"过滤后只剩{len(valid_columns)}列有效数据，"
                    f"因果分析至少需要2列（1个因变量 + 1个自变量）。\n"
                    f"被排除的列及原因:\n"
                )
                for col in excluded_columns:
                    error_msg += f"  - {col}: {exclusion_reasons.get(col, '未知原因')}\n"
                logger.error(error_msg)
                return False

            # 更新配置，移除被排除的列
            if excluded_columns:
                logger.info(
                    f"自动过滤了{len(excluded_columns)}列，"
                    f"保留{len(valid_columns)}列用于因果分析"
                )
                
                # 检查因变量是否被排除
                if dependent_var in excluded_columns:
                    error_msg = (
                        f"因变量'{dependent_var}'不符合要求，无法进行因果分析。\n"
                        f"原因: {exclusion_reasons.get(dependent_var, '未知原因')}\n"
                        f"因变量必须有至少2个不同的有效数据点。"
                    )
                    logger.error(error_msg)
                    return False
                
                # 更新自变量列表（移除被排除的列）
                new_independent_vars = [
                    var for var in independent_vars if var not in excluded_columns
                ]
                config['independent_variables'] = new_independent_vars
                
                # 验证至少还有1个自变量
                if len(new_independent_vars) < 1:
                    error_msg = (
                        f"所有自变量都被排除，无法进行因果分析。\n"
                        f"被排除的自变量及原因:\n"
                    )
                    for var in independent_vars:
                        if var in excluded_columns:
                            error_msg += f"  - {var}: {exclusion_reasons.get(var, '未知原因')}\n"
                    logger.error(error_msg)
                    return False
                
                # 保存排除信息
                config['excluded_columns'] = excluded_columns
                config['exclusion_reasons'] = exclusion_reasons

            logger.info(
                f"因果分析算法输入验证通过 - 因变量: {config.get('dependent_variable')}, "
                f"自变量数: {len(config.get('independent_variables', []))}"
            )
            return True

        except Exception as e:
            logger.error(f"因果分析算法输入验证过程中发生异常: {str(e)}")
            return False

    async def _check_column_quality(
            self,
            data_rows: List[Dict[str, Any]],
            col: str
    ) -> bool:
        """检查单列的数据质量"""
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
            return False

        numeric_ratio = numeric_count / total_count
        
        # 数值比例至少70%
        if numeric_ratio < 0.7:
            logger.warning(
                f"列'{col}'的数值比例过低（{numeric_ratio:.1%}），"
                f"需要至少70%的数据为数值类型"
            )
            return False

        return True


        return True
