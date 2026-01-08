"""
Association Analysis Data Processor

关联分析数据处理器
"""

import logging
from typing import Dict, List, Any
from algorithm.base.base_processor import BaseAlgorithmProcessor
from algorithm.models import (
    AlgorithmExecutionRequest, AlgorithmConfig, 
    AlgorithmParameters, AlgorithmType
)

logger = logging.getLogger(__name__)


class AssociationProcessor(BaseAlgorithmProcessor):
    """关联分析数据处理器"""
    
    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.ASSOCIATE
    
    @property
    def algorithm_name(self) -> str:
        return "association"
    
    async def convert_sql_result_to_algorithm_input(
        self,
        sql_result: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """将SQL结果转换为关联分析输入格式"""
        try:
            logger.info(f"开始转换SQL结果为多元关联分析输入，数据行数: {len(sql_result)}")
            
            if not sql_result:
                raise ValueError("SQL查询结果为空")
            
            # 获取参数映射
            param_mapping = parameters.parameter_mapping
            
            # 获取列名列表和分析模式
            columns = param_mapping.get('columns')
            analysis_mode = param_mapping.get('analysis_mode')
            
            # 向后兼容：如果没有columns但有column1/column2，则使用旧格式
            if not columns:
                column1 = param_mapping.get('column1')
                column2 = param_mapping.get('column2')
                if column1 and column2:
                    columns = [column1, column2]
                    analysis_mode = 'bivariate'
                    logger.info("检测到旧格式参数，自动转换为新格式")
                else:
                    raise ValueError("缺少必需的列名参数(columns或column1/column2)")
            
            if not analysis_mode:
                # 根据列数自动推断
                if len(columns) == 2:
                    analysis_mode = 'bivariate'
                elif len(columns) >= 3:
                    analysis_mode = 'pairwise'
                logger.info(f"未指定analysis_mode，根据列数自动推断为: {analysis_mode}")
            
            # 获取SQL结果中的实际列名
            actual_columns = list(sql_result[0].keys()) if sql_result else []
            logger.info(f"SQL结果中的实际列名: {actual_columns}")
            logger.info(f"参数映射中的列名: {columns}")
            logger.info(f"分析模式: {analysis_mode}")
            
            # 智能匹配列名
            matched_columns = []
            for col_name in columns:
                if col_name in actual_columns:
                    matched_columns.append(col_name)
                else:
                    # 尝试智能匹配
                    logger.warning(f"列名 '{col_name}' 在SQL结果中不存在，尝试智能匹配")
                    matched = False
                    
                    # 简单的匹配策略：查找包含关键词的列名
                    for actual_col in actual_columns:
                        if col_name.lower() in actual_col.lower() or actual_col.lower() in col_name.lower():
                            matched_columns.append(actual_col)
                            logger.info(f"匹配到列名: {col_name} -> {actual_col}")
                            matched = True
                            break
                    
                    if not matched:
                        # 如果没有匹配到，使用位置匹配
                        col_index = columns.index(col_name)
                        if col_index < len(actual_columns):
                            matched_columns.append(actual_columns[col_index])
                            logger.warning(f"使用位置匹配: {col_name} -> {actual_columns[col_index]}")
                        else:
                            raise ValueError(f"无法匹配列名: {col_name}")
            
            # 验证匹配的列数
            if len(matched_columns) != len(columns):
                raise ValueError(f"列名匹配失败: 需要{len(columns)}列，只匹配到{len(matched_columns)}列")
            
            # 提取每列的数据
            data_array = []
            for col_name in matched_columns:
                col_values = []
                for row in sql_result:
                    val = row.get(col_name)
                    col_values.append(val)
                
                data_array.append({
                    "name": col_name,
                    "values": col_values
                })
                
                logger.debug(f"提取列 {col_name}: {len(col_values)} 个数据点")
            
            # 验证所有列的数据长度一致
            lengths = [len(col_data["values"]) for col_data in data_array]
            if len(set(lengths)) > 1:
                raise ValueError(f"各列数据长度不一致: {dict(zip(matched_columns, lengths))}")
            
            if lengths[0] == 0:
                raise ValueError("提取的数据为空")
            
            # 构建算法输入（新格式）
            config = {
                "data": data_array,
                "options": {
                    "analysis_mode": analysis_mode
                }
            }
            
            # 向后兼容：如果是bivariate模式，也保留旧格式
            if analysis_mode == 'bivariate' and len(data_array) == 2:
                config["data_legacy"] = {
                    "column1": data_array[0],
                    "column2": data_array[1]
                }
            
            logger.info(
                f"多元关联分析数据转换完成: "
                f"列数={len(data_array)}, 模式={analysis_mode}, "
                f"数据量={lengths[0]}"
            )
            
            # 这里data_rows可以为空，因为实际数据在config中
            return AlgorithmExecutionRequest(
                data_rows=[],
                config=config
            )
            
        except Exception as e:
            logger.error(f"多元关联分析数据转换失败: {str(e)}")
            raise ValueError(f"多元关联分析数据转换失败: {str(e)}")
    
    async def validate_algorithm_input(
        self,
        request: AlgorithmExecutionRequest,
        algorithm_config: AlgorithmConfig
    ) -> bool:
        """验证多元关联分析输入"""
        try:
            config = request.config
            
            # 验证data字段存在
            data = config.get('data')
            if not data:
                logger.error("配置中缺少data字段")
                return False
            
            # 检查是新格式（数组）还是旧格式（对象）
            if isinstance(data, list):
                # 新格式：data是数组
                logger.info("检测到新格式数据（数组）")
                
                # 验证data数组长度至少为2
                if len(data) < 2:
                    logger.error(f"data数组长度不足: {len(data)}，至少需要2列")
                    return False
                
                # 验证每个列对象的结构
                column_names = []
                column_lengths = []
                
                for i, col_data in enumerate(data):
                    if not isinstance(col_data, dict):
                        logger.error(f"data[{i}]不是字典类型")
                        return False
                    
                    col_name = col_data.get('name')
                    col_values = col_data.get('values')
                    
                    if not col_name:
                        logger.error(f"data[{i}]缺少name字段")
                        return False
                    
                    if not isinstance(col_values, list):
                        logger.error(f"data[{i}]的values不是列表类型")
                        return False
                    
                    column_names.append(col_name)
                    column_lengths.append(len(col_values))
                
                # 验证列名不重复
                if len(column_names) != len(set(column_names)):
                    duplicates = [name for name in column_names if column_names.count(name) > 1]
                    logger.error(f"列名重复: {set(duplicates)}")
                    return False
                
                # 验证所有列的数据长度一致
                if len(set(column_lengths)) > 1:
                    logger.error(f"各列数据长度不一致: {dict(zip(column_names, column_lengths))}")
                    return False
                
                if column_lengths[0] == 0:
                    logger.error("数据为空")
                    return False
                
                # 获取analysis_mode
                options = config.get('options', {})
                analysis_mode = options.get('analysis_mode', 'bivariate')
                
                # 根据analysis_mode验证列数
                if analysis_mode == 'bivariate':
                    if len(data) != 2:
                        logger.error(f"bivariate模式要求恰好2列，当前有{len(data)}列")
                        return False
                elif analysis_mode in ['pairwise', 'multivariate']:
                    if len(data) < 3:
                        logger.error(f"{analysis_mode}模式至少需要3列，当前只有{len(data)}列")
                        return False
                
                # 验证有效数据点（移除None后至少2个数据点）
                # 获取第一列的values作为参考
                first_col_values = data[0]['values']
                valid_count = 0
                
                for i in range(len(first_col_values)):
                    # 检查这一行是否所有列都有值
                    all_valid = True
                    for col_data in data:
                        if i >= len(col_data['values']) or col_data['values'][i] is None:
                            all_valid = False
                            break
                    if all_valid:
                        valid_count += 1
                
                if valid_count < 2:
                    logger.error(f"有效数据点少于2个（当前: {valid_count}）")
                    return False
                
                # 记录缺失值信息
                missing_count = len(first_col_values) - valid_count
                if missing_count > 0:
                    logger.info(f"数据包含{missing_count}个缺失值行，有效数据点: {valid_count}")
                
                logger.info(
                    f"多元关联分析输入验证通过: 列数={len(data)}, 模式={analysis_mode}, "
                    f"数据量={column_lengths[0]}, 有效数据={valid_count}"
                )
                return True
                
            else:
                # 旧格式：data是对象（向后兼容）
                logger.info("检测到旧格式数据（对象），进行兼容性验证")
                
                # 验证column1
                column1 = data.get('column1')
                if not column1:
                    logger.error("配置中缺少column1")
                    return False
                
                column1_name = column1.get('name')
                column1_values = column1.get('values')
                
                if not column1_name:
                    logger.error("column1缺少name字段")
                    return False
                
                if not isinstance(column1_values, list):
                    logger.error("column1的values必须是列表")
                    return False
                
                # 验证column2
                column2 = data.get('column2')
                if not column2:
                    logger.error("配置中缺少column2")
                    return False
                
                column2_name = column2.get('name')
                column2_values = column2.get('values')
                
                if not column2_name:
                    logger.error("column2缺少name字段")
                    return False
                
                if not isinstance(column2_values, list):
                    logger.error("column2的values必须是列表")
                    return False
                
                # 验证两列名称不同
                if column1_name == column2_name:
                    logger.error(f"两列名称相同: {column1_name}")
                    return False
                
                # 验证数据长度
                if len(column1_values) != len(column2_values):
                    logger.error(
                        f"两列数据长度不一致: {column1_name}={len(column1_values)}, "
                        f"{column2_name}={len(column2_values)}"
                    )
                    return False
                
                if len(column1_values) == 0:
                    logger.error("数据为空")
                    return False
                
                # 验证options字段
                options = config.get('options', {})
                if not isinstance(options, dict):
                    logger.error("配置中的options必须是字典类型")
                    return False
                
                # 验证数据质量（移除None后至少2个数据点）
                valid_count = sum(
                    1 for v1, v2 in zip(column1_values, column2_values)
                    if v1 is not None and v2 is not None
                )
                
                if valid_count < 2:
                    logger.error(f"有效数据点少于2个（当前: {valid_count}）")
                    return False
                
                logger.info(
                    f"关联分析输入验证通过（旧格式）: {column1_name} vs {column2_name}, "
                    f"数据量={len(column1_values)}, 有效数据={valid_count}"
                )
                return True
            
        except Exception as e:
            logger.error(f"关联分析输入验证失败: {str(e)}")
            return False
