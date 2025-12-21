"""
Parameter Extractor Implementation

Implements the IParameterExtractor interface to extract algorithm parameters
from user queries using LLM-based natural language processing.
"""

import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from algorithm.interfaces import IParameterExtractor, IAlgorithmConfigManager
from algorithm.models import (
    AlgorithmType, AlgorithmParameters, AlgorithmConfig, 
    DatabaseColumn, AlgorithmField
)
from llm.llm_client import LLMClient

logger = logging.getLogger(__name__)


class ParameterExtractor(IParameterExtractor):
    """
    参数提取器实现
    
    使用LLM从用户查询中提取算法特定参数，并将参数映射到数据库列。
    """
    
    def __init__(self, llm_client: LLMClient, config_manager: IAlgorithmConfigManager):
        """
        初始化参数提取器
        
        Args:
            llm_client: LLM客户端
            config_manager: 算法配置管理器
        """
        self.llm_client = llm_client
        self.config_manager = config_manager
        logger.info("ParameterExtractor initialized")
    
    async def extract_parameters(
        self, 
        question: str, 
        algorithm_type: AlgorithmType,
        database_schema: List[DatabaseColumn]
    ) -> AlgorithmParameters:
        """
        从用户查询中提取算法参数
        
        Args:
            question: 用户自然语言查询
            algorithm_type: 算法类型
            database_schema: 数据库模式信息
            
        Returns:
            AlgorithmParameters: 提取的算法参数
            
        Raises:
            ValueError: 参数提取失败时抛出
        """
        try:
            logger.info(f"开始提取算法参数，算法类型: {algorithm_type.value}, 问题: {question}")
            
            # 获取算法配置
            algorithm_config = self.config_manager.get_algorithm_config(algorithm_type)
            if not algorithm_config:
                raise ValueError(f"未找到算法类型 {algorithm_type.value} 的配置")
            
            # 构建参数提取提示词
            messages = self._build_extraction_prompt(
                question, algorithm_config, database_schema
            )
            
            # 调用LLM进行参数提取
            response = await self.llm_client.chat_completion(messages)

            logger.debug(f"LLM响应: {response}")
            
            # 解析LLM响应
            extraction_result = self._parse_extraction_response(response)
            
            # 验证和设置默认值
            validated_params = self._validate_and_set_defaults(
                extraction_result, algorithm_config
            )
            
            # 生成规范化查询语句（优先使用LLM提供的，否则基于参数生成）
            llm_normalized_query = extraction_result.get('normalized_query')
            if llm_normalized_query and llm_normalized_query != "未提供查询描述":
                # 使用LLM提供的查询，但仍需要验证和格式化
                parameter_json_mapping = self._create_parameter_json_mapping(
                    validated_params, algorithm_config, database_schema
                )
                normalized_query = self._validate_and_format_query(
                    llm_normalized_query, parameter_json_mapping, algorithm_config
                )
            else:
                # 基于算法参数和数据库列信息生成规范化查询
                normalized_query = self._generate_normalized_query(
                    question, algorithm_config, validated_params, database_schema
                )
            
            # 创建算法参数对象
            algorithm_parameters = AlgorithmParameters(
                algorithm_type=algorithm_type,
                normalized_query=normalized_query,
                parameter_mapping=validated_params,
                required_columns=extraction_result.get('required_columns', []),
                sql_queries=extraction_result.get('sql_queries', {})
            )
            
            logger.info(f"参数提取完成，提取到 {len(validated_params)} 个参数")
            return algorithm_parameters
            
        except Exception as e:
            logger.error(f"参数提取失败: {str(e)}", exc_info=True)
            raise ValueError(f"参数提取失败: {str(e)}")
    
    def _build_extraction_prompt(
        self, 
        question: str, 
        algorithm_config: AlgorithmConfig,
        database_schema: List[DatabaseColumn]
    ) -> List[Dict[str, str]]:
        """
        构建参数提取的LLM提示模板
        
        Args:
            question: 用户问题
            algorithm_config: 算法配置
            database_schema: 数据库模式信息
            
        Returns:
            List[Dict[str, str]]: LLM消息列表
        """
        # 格式化数据库模式信息
        schema_text = self._format_database_schema(database_schema)
        
        # 格式化算法字段要求
        fields_text = self._format_algorithm_fields(algorithm_config)
        
        # 系统提示词
        system_prompt = f"""你是一个智能参数提取专家。根据用户问题、算法配置和数据库信息，提取算法所需的参数并映射到数据库列。

算法信息：
- 算法类型: {algorithm_config.name}
- 算法描述: {algorithm_config.description}
- 数据格式: {algorithm_config.data_format}

算法字段要求：
{fields_text}

数据库信息：
{schema_text}

提取规则：
1. 仔细分析用户问题，识别算法所需的参数
2. 将参数映射到最合适的数据库列
3. 为必需参数提供值，为可选参数提供默认值或null
4. 生成用于算法输入的数据检索的规范化sql查询语句
5. 输出JSON格式，包含以下字段：
   - parameter_mapping: 参数名到值的映射
   - required_columns: 所需的数据库列名列表
   - sql_queries: 生成的SQL查询（如果需要多个查询）
   - normalized_query: 规范化的查询描述

输出示例：
{{
  "parameter_mapping": {{
    "id_column": "user_id",
    "feature_columns": ["age", "income", "purchase_amount"],
    "k_value": null
  }},
  "required_columns": ["user_id", "age", "income", "purchase_amount"],
  "sql_queries": {{
    "main_query": "SELECT user_id, age, income, purchase_amount FROM users WHERE active = 1"
  }},
  "normalized_query": "获取活跃用户的id、年龄、收入和购买金额数据"
}}"""
        
        # 用户提示词
        user_prompt = f"""用户问题: {question}

请分析用户问题，提取算法所需的参数，并将参数映射到合适的数据库列。输出JSON格式的结果。"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        logger.debug(f"构建参数提取提示词: system={len(system_prompt)} chars, user={len(user_prompt)} chars")
        
        return messages
    
    def _format_database_schema(self, database_schema: List[DatabaseColumn]) -> str:
        """
        格式化数据库模式信息为文本，只使用列注释和数据类型
        
        Args:
            database_schema: 数据库列信息列表
            
        Returns:
            str: 格式化的模式信息
        """
        if not database_schema:
            return "（无可用数据库模式信息）"
        
        # 按表名分组
        tables = {}
        for column in database_schema:
            # 只处理有列注释的列
            if column.column_comment and column.column_comment.strip():
                table_name = column.table_name
                if table_name not in tables:
                    tables[table_name] = []
                tables[table_name].append(column)
        
        if not tables:
            return "（无可用的有注释的数据库列信息）"
        
        # 格式化输出，只使用列注释和数据类型
        lines = []
        for table_name, columns in tables.items():
            lines.append(f"表: {table_name}")
            for column in columns:
                # 只显示列名、数据类型和列注释
                lines.append(f"  - {column.column_name} ({column.data_type}): {column.column_comment}")
        
        return "\n".join(lines)
    
    def _format_algorithm_fields(self, algorithm_config: AlgorithmConfig) -> str:
        """
        格式化算法字段要求为文本
        
        Args:
            algorithm_config: 算法配置
            
        Returns:
            str: 格式化的字段要求
        """
        lines = []
        
        if algorithm_config.required_fields:
            lines.append("必需参数:")
            for field in algorithm_config.required_fields:
                options_text = f", 可选值: {field.options}" if field.options else ""
                lines.append(f"  - {field.field} ({field.type}): {field.description}{options_text}")
        
        if algorithm_config.optional_fields:
            lines.append("可选参数:")
            for field in algorithm_config.optional_fields:
                default_text = f", 默认值: {field.default}" if field.default is not None else ""
                options_text = f", 可选值: {field.options}" if field.options else ""
                lines.append(f"  - {field.field} ({field.type}): {field.description}{default_text}{options_text}")
        
        return "\n".join(lines)
    
    def _parse_extraction_response(self, response: str) -> Dict[str, Any]:
        """
        解析LLM参数提取响应
        
        Args:
            response: LLM响应文本
            
        Returns:
            Dict[str, Any]: 解析后的参数信息
            
        Raises:
            ValueError: 响应解析失败
        """
        try:
            logger.debug(f"解析参数提取响应: {response[:200]}...")
            
            # 清理响应文本
            response = response.strip()
            
            # 处理可能的markdown代码块格式
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                if end > start:
                    response = response[start:end].strip()
            elif "```" in response:
                start = response.find("```") + 3
                end = response.find("```", start)
                if end > start:
                    response = response[start:end].strip()
            
            # 尝试查找JSON对象
            start_idx = response.find('{')
            end_idx = response.rfind('}')
            
            if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
                raise ValueError(f"响应中未找到有效的JSON对象: {response}")
            
            json_str = response[start_idx:end_idx + 1]
            
            # 解析JSON
            result = json.loads(json_str)
            
            # 验证必需字段
            required_keys = ['parameter_mapping', 'required_columns', 'normalized_query']
            for key in required_keys:
                if key not in result:
                    logger.warning(f"响应中缺少字段: {key}")
                    if key == 'parameter_mapping':
                        result[key] = {}
                    elif key == 'required_columns':
                        result[key] = []
                    elif key == 'normalized_query':
                        result[key] = "未提供查询描述"
            
            logger.debug(f"成功解析参数提取结果: {len(result.get('parameter_mapping', {}))} 个参数")
            
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}, 响应内容: {response}")
            raise ValueError(f"LLM响应格式错误，无法解析JSON: {str(e)}")
        
        except Exception as e:
            logger.error(f"响应解析失败: {str(e)}, 响应内容: {response}")
            raise ValueError(f"参数提取响应解析失败: {str(e)}")
    
    def _validate_and_set_defaults(
        self, 
        extraction_result: Dict[str, Any], 
        algorithm_config: AlgorithmConfig
    ) -> Dict[str, Any]:
        """
        验证参数并设置默认值
        
        Args:
            extraction_result: 提取的参数结果
            algorithm_config: 算法配置
            
        Returns:
            Dict[str, Any]: 验证后的参数映射
            
        Raises:
            ValueError: 参数验证失败
        """
        parameter_mapping = extraction_result.get('parameter_mapping', {})
        validated_params = {}
        
        # 验证必需参数
        for field in algorithm_config.required_fields:
            field_name = field.field
            
            # data_rows 是特殊字段，会在后续步骤中从SQL结果填充
            if field_name == "data_rows":
                validated_params[field_name] = parameter_mapping.get(field_name, [])
                continue
            
            # data_sets 也是特殊字段，用于分类算法的训练数据
            if field_name == "data_sets":
                validated_params[field_name] = parameter_mapping.get(field_name, [])
                continue
            
            if field_name not in parameter_mapping or parameter_mapping[field_name] is None:
                raise ValueError(f"缺少必需参数: {field_name} ({field.description})")
            
            value = parameter_mapping[field_name]
            validated_value = self._validate_field_value(field, value)
            validated_params[field_name] = validated_value
        
        # 处理可选参数
        for field in algorithm_config.optional_fields:
            field_name = field.field
            if field_name in parameter_mapping and parameter_mapping[field_name] is not None:
                value = parameter_mapping[field_name]
                validated_value = self._validate_field_value(field, value)
                validated_params[field_name] = validated_value
            else:
                # 设置默认值
                validated_params[field_name] = field.default
        
        logger.debug(f"参数验证完成，验证了 {len(validated_params)} 个参数")
        
        return validated_params
    
    def _validate_field_value(self, field: AlgorithmField, value: Any) -> Any:
        """
        验证字段值
        
        Args:
            field: 字段定义
            value: 字段值
            
        Returns:
            Any: 验证后的值
            
        Raises:
            ValueError: 值验证失败
        """
        # 类型验证
        if field.type == "string" and not isinstance(value, str):
            if value is not None:
                value = str(value)
        elif field.type == "integer" and not isinstance(value, int):
            if isinstance(value, str) and value.isdigit():
                value = int(value)
            elif value is not None:
                raise ValueError(f"字段 {field.field} 需要整数类型，得到: {type(value)}")
        elif field.type == "float" and not isinstance(value, (int, float)):
            if isinstance(value, str):
                try:
                    value = float(value)
                except ValueError:
                    raise ValueError(f"字段 {field.field} 需要浮点数类型，得到: {value}")
            elif value is not None:
                raise ValueError(f"字段 {field.field} 需要浮点数类型，得到: {type(value)}")
        elif field.type == "array" and not isinstance(value, list):
            if isinstance(value, str):
                # 尝试解析字符串为列表
                try:
                    value = json.loads(value)
                    if not isinstance(value, list):
                        raise ValueError()
                except:
                    # 按逗号分割字符串
                    value = [item.strip() for item in value.split(',') if item.strip()]
            elif value is not None:
                raise ValueError(f"字段 {field.field} 需要数组类型，得到: {type(value)}")
        
        # 选项验证
        if field.options and value is not None and value not in field.options:
            raise ValueError(f"字段 {field.field} 的值 {value} 不在允许的选项中: {field.options}")
        
        return value
    
    def _generate_normalized_query(
        self,
        question: str,
        algorithm_config: AlgorithmConfig,
        parameters: Dict[str, Any],
        database_schema: List[DatabaseColumn]
    ) -> str:
        """
        生成规范化查询语句
        
        基于算法参数和数据库列信息生成查询描述，实现查询语句的格式化和验证
        
        Args:
            question: 原始用户问题
            algorithm_config: 算法配置
            parameters: 提取的参数
            database_schema: 数据库模式
            
        Returns:
            str: 规范化查询语句
        """
        try:
            logger.info(f"开始生成规范化查询语句，算法类型: {algorithm_config.name}")
            
            # 创建算法参数到JSON结构的映射
            parameter_json_mapping = self._create_parameter_json_mapping(
                parameters, algorithm_config, database_schema
            )
            
            # 基于算法类型和参数生成规范化查询
            normalized_query = self._build_normalized_query_description(
                question, algorithm_config, parameter_json_mapping, database_schema
            )
            
            # 验证和格式化查询语句
            validated_query = self._validate_and_format_query(
                normalized_query, parameter_json_mapping, algorithm_config
            )
            
            logger.info(f"成功生成规范化查询: {validated_query}")
            return validated_query
            
        except Exception as e:
            logger.error(f"生成规范化查询失败: {str(e)}", exc_info=True)
            return f"获取数据用于{algorithm_config.name}"
    
    def _create_parameter_json_mapping(
        self,
        parameters: Dict[str, Any],
        algorithm_config: AlgorithmConfig,
        database_schema: List[DatabaseColumn]
    ) -> Dict[str, Any]:
        """
        创建算法参数到JSON结构的映射逻辑
        
        Args:
            parameters: 提取的参数
            algorithm_config: 算法配置
            database_schema: 数据库模式
            
        Returns:
            Dict[str, Any]: 参数JSON映射结构
        """
        try:
            logger.debug("创建算法参数到JSON结构的映射")
            
            # 基础映射结构
            json_mapping = {
                "algorithm_info": {
                    "type": algorithm_config.name,
                    "data_format": algorithm_config.data_format,
                    "api_endpoint": algorithm_config.api_endpoint
                },
                "data_requirements": {},
                "query_components": {},
                "validation_rules": {}
            }
            
            # 提取数据需求
            data_requirements = self._extract_data_requirements(parameters, algorithm_config)
            json_mapping["data_requirements"] = data_requirements
            
            # 构建查询组件
            query_components = self._build_query_components(
                parameters, algorithm_config, database_schema
            )
            json_mapping["query_components"] = query_components
            
            # 设置验证规则
            validation_rules = self._create_validation_rules(parameters, algorithm_config)
            json_mapping["validation_rules"] = validation_rules
            
            logger.debug(f"参数JSON映射创建完成: {len(json_mapping)} 个主要组件")
            return json_mapping
            
        except Exception as e:
            logger.error(f"创建参数JSON映射失败: {str(e)}")
            return {"error": str(e)}
    
    def _extract_data_requirements(
        self,
        parameters: Dict[str, Any],
        algorithm_config: AlgorithmConfig
    ) -> Dict[str, Any]:
        """
        提取数据需求信息
        
        Args:
            parameters: 算法参数
            algorithm_config: 算法配置
            
        Returns:
            Dict[str, Any]: 数据需求信息
        """
        requirements = {
            "required_columns": [],
            "optional_columns": [],
            "data_types": {},
            "constraints": []
        }
        
        # 提取必需列
        id_column = parameters.get('id_column')
        if id_column:
            requirements["required_columns"].append(id_column)
            requirements["data_types"][id_column] = "identifier"
        
        feature_columns = parameters.get('feature_columns', [])
        if feature_columns:
            requirements["required_columns"].extend(feature_columns)
            for col in feature_columns:
                requirements["data_types"][col] = "numeric"
        
        target_column = parameters.get('target_column')
        if target_column:
            requirements["required_columns"].append(target_column)
            requirements["data_types"][target_column] = "categorical"
        
        # 提取可选列
        time_column = parameters.get('time_column')
        if time_column:
            requirements["optional_columns"].append(time_column)
            requirements["data_types"][time_column] = "datetime"
        
        # 添加约束条件
        if algorithm_config.data_format == "time_series":
            requirements["constraints"].append("数据需按时间列排序")
        
        if parameters.get('k_value'):
            requirements["constraints"].append(f"聚类数量: {parameters['k_value']}")
        
        return requirements
    
    def _build_query_components(
        self,
        parameters: Dict[str, Any],
        algorithm_config: AlgorithmConfig,
        database_schema: List[DatabaseColumn]
    ) -> Dict[str, Any]:
        """
        构建查询组件
        
        Args:
            parameters: 算法参数
            algorithm_config: 算法配置
            database_schema: 数据库模式
            
        Returns:
            Dict[str, Any]: 查询组件信息
        """
        components = {
            "select_clause": [],
            "from_clause": [],
            "where_clause": [],
            "group_by_clause": [],
            "order_by_clause": []
        }
        
        # 构建SELECT子句
        select_columns = []
        if parameters.get('id_column'):
            select_columns.append(parameters['id_column'])
        
        feature_columns = parameters.get('feature_columns', [])
        select_columns.extend(feature_columns)
        
        if parameters.get('target_column'):
            select_columns.append(parameters['target_column'])
        
        if parameters.get('time_column'):
            select_columns.append(parameters['time_column'])
        
        components["select_clause"] = select_columns
        
        # 推断表名
        table_names = self._infer_table_names(select_columns, database_schema)
        components["from_clause"] = list(table_names)
        
        # 构建WHERE子句（基于数据类型和约束）
        where_conditions = self._build_where_conditions(parameters, database_schema)
        components["where_clause"] = where_conditions
        
        # 构建ORDER BY子句
        if algorithm_config.data_format == "time_series" and parameters.get('time_column'):
            components["order_by_clause"] = [f"{parameters['time_column']} ASC"]
        
        # 构建GROUP BY子句
        if algorithm_config.data_format == "tabular" and parameters.get('id_column'):
            # 对于某些算法可能需要按ID分组
            if algorithm_config.name in ["用户画像", "关联分析"]:
                components["group_by_clause"] = [parameters['id_column']]
        
        return components
    
    def _create_validation_rules(
        self,
        parameters: Dict[str, Any],
        algorithm_config: AlgorithmConfig
    ) -> Dict[str, Any]:
        """
        创建验证规则
        
        Args:
            parameters: 算法参数
            algorithm_config: 算法配置
            
        Returns:
            Dict[str, Any]: 验证规则
        """
        rules = {
            "required_fields": [],
            "data_quality": [],
            "business_logic": []
        }
        
        # 必需字段验证
        for field in algorithm_config.required_fields:
            if field.field in parameters:
                rules["required_fields"].append({
                    "field": field.field,
                    "type": field.type,
                    "value": parameters[field.field]
                })
        
        # 数据质量验证
        if parameters.get('feature_columns'):
            rules["data_quality"].append("特征列不能包含过多空值")
            rules["data_quality"].append("数值型特征需要进行异常值检测")
        
        if parameters.get('target_column'):
            rules["data_quality"].append("目标列的类别分布需要相对均衡")
        
        # 业务逻辑验证
        if algorithm_config.name == "聚类分析 (K-Means)":
            rules["business_logic"].append("聚类特征应该是数值型")
            if parameters.get('k_value'):
                rules["business_logic"].append(f"K值({parameters['k_value']})应该小于数据行数")
        
        elif algorithm_config.name == "智能分类预测 (Auto-Routing)":
            rules["business_logic"].append("训练数据和预测数据的特征列必须一致")
            rules["business_logic"].append("目标列的类别数量应该合理(2-20个)")
        
        return rules
    
    def _build_normalized_query_description(
        self,
        question: str,
        algorithm_config: AlgorithmConfig,
        parameter_json_mapping: Dict[str, Any],
        database_schema: List[DatabaseColumn]
    ) -> str:
        """
        构建规范化查询描述
        
        Args:
            question: 原始问题
            algorithm_config: 算法配置
            parameter_json_mapping: 参数JSON映射
            database_schema: 数据库模式
            
        Returns:
            str: 规范化查询描述
        """
        try:
            algorithm_name = algorithm_config.name
            data_requirements = parameter_json_mapping.get("data_requirements", {})
            query_components = parameter_json_mapping.get("query_components", {})
            
            # 基础查询描述
            base_description = f"执行{algorithm_name}分析"
            
            # 添加数据来源信息
            tables = query_components.get("from_clause", [])
            if tables:
                table_text = "、".join(tables)
                base_description += f"，数据来源：{table_text}表"
            
            # 添加特征信息
            required_columns = data_requirements.get("required_columns", [])
            if required_columns:
                # 按类型分组列名
                id_cols = [col for col, dtype in data_requirements.get("data_types", {}).items() 
                          if dtype == "identifier"]
                feature_cols = [col for col, dtype in data_requirements.get("data_types", {}).items() 
                               if dtype == "numeric"]
                target_cols = [col for col, dtype in data_requirements.get("data_types", {}).items() 
                              if dtype == "categorical"]
                time_cols = [col for col, dtype in data_requirements.get("data_types", {}).items() 
                            if dtype == "datetime"]
                
                feature_parts = []
                if id_cols:
                    feature_parts.append(f"标识列({', '.join(id_cols)})")
                if feature_cols:
                    feature_parts.append(f"特征列({', '.join(feature_cols)})")
                if target_cols:
                    feature_parts.append(f"目标列({', '.join(target_cols)})")
                if time_cols:
                    feature_parts.append(f"时间列({', '.join(time_cols)})")
                
                if feature_parts:
                    base_description += f"，包含{', '.join(feature_parts)}"
            
            # 添加筛选条件信息
            where_conditions = query_components.get("where_clause", [])
            if where_conditions:
                base_description += f"，筛选条件：{', '.join(where_conditions)}"
            
            # 添加排序信息
            order_by = query_components.get("order_by_clause", [])
            if order_by:
                base_description += f"，按{', '.join(order_by)}排序"
            
            # 添加约束信息
            constraints = data_requirements.get("constraints", [])
            if constraints:
                base_description += f"，约束条件：{', '.join(constraints)}"
            
            return base_description
            
        except Exception as e:
            logger.error(f"构建规范化查询描述失败: {str(e)}")
            return f"执行{algorithm_config.name}分析"
    
    def _validate_and_format_query(
        self,
        normalized_query: str,
        parameter_json_mapping: Dict[str, Any],
        algorithm_config: AlgorithmConfig
    ) -> str:
        """
        验证和格式化查询语句
        
        Args:
            normalized_query: 原始规范化查询
            parameter_json_mapping: 参数JSON映射
            algorithm_config: 算法配置
            
        Returns:
            str: 验证和格式化后的查询语句
        """
        try:
            # 基础格式化
            formatted_query = normalized_query.strip()
            
            # 验证查询完整性
            validation_errors = []
            
            # 检查必需组件
            data_requirements = parameter_json_mapping.get("data_requirements", {})
            required_columns = data_requirements.get("required_columns", [])
            
            if not required_columns:
                validation_errors.append("缺少必需的数据列信息")
            
            # 检查算法特定要求
            if algorithm_config.name == "聚类分析 (K-Means)":
                # 检查是否有特征列信息（通过参数映射或查询描述）
                feature_columns = parameter_json_mapping.get("data_requirements", {}).get("required_columns", [])
                has_features = any(col for col in feature_columns if col != parameter_json_mapping.get("data_requirements", {}).get("data_types", {}).get(col) != "identifier")
                if not has_features and "特征列" not in formatted_query:
                    validation_errors.append("聚类分析需要明确的特征列")
            
            elif algorithm_config.name == "智能分类预测 (Auto-Routing)":
                # 检查是否有目标列信息
                data_types = parameter_json_mapping.get("data_requirements", {}).get("data_types", {})
                has_target = any(dtype == "categorical" for dtype in data_types.values())
                if not has_target and "目标列" not in formatted_query:
                    validation_errors.append("分类预测需要明确的目标列")
            
            # 如果有验证错误，添加到查询描述中
            if validation_errors:
                formatted_query += f"（注意：{', '.join(validation_errors)}）"
            
            # 确保查询以句号结尾
            if not formatted_query.endswith(('。', '.', '！', '!')):
                formatted_query += "。"
            
            logger.debug(f"查询验证完成，错误数量: {len(validation_errors)}")
            return formatted_query
            
        except Exception as e:
            logger.error(f"验证和格式化查询失败: {str(e)}")
            return normalized_query
    
    def _infer_table_names(
        self,
        column_names: List[str],
        database_schema: List[DatabaseColumn]
    ) -> set:
        """
        根据列名推断表名
        
        Args:
            column_names: 列名列表
            database_schema: 数据库模式
            
        Returns:
            set: 推断的表名集合
        """
        table_names = set()
        
        for column_name in column_names:
            for schema_column in database_schema:
                if schema_column.column_name == column_name:
                    table_names.add(schema_column.table_name)
        
        return table_names
    
    def _build_where_conditions(
        self,
        parameters: Dict[str, Any],
        database_schema: List[DatabaseColumn]
    ) -> List[str]:
        """
        构建WHERE条件
        
        Args:
            parameters: 算法参数
            database_schema: 数据库模式
            
        Returns:
            List[str]: WHERE条件列表
        """
        conditions = []
        
        # 基于数据类型添加常见的筛选条件
        for column_name in parameters.get('feature_columns', []):
            for schema_column in database_schema:
                if schema_column.column_name == column_name:
                    if 'int' in schema_column.data_type.lower() or 'decimal' in schema_column.data_type.lower():
                        conditions.append(f"{column_name} IS NOT NULL")
                    break
        
        # 添加业务逻辑条件
        if parameters.get('target_column'):
            conditions.append(f"{parameters['target_column']} IS NOT NULL")
        
        return conditions