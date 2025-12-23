"""
Template Algorithm Parameter Extractor

新算法参数提取器模板 - 请根据你的算法需求修改
"""

import logging
from typing import Dict, List, Any, Optional
from algorithm.base.base_extractor import BaseAlgorithmExtractor
from algorithm.models import AlgorithmType, DatabaseColumn

logger = logging.getLogger(__name__)


class TemplateExtractor(BaseAlgorithmExtractor):
    """模板算法参数提取器 - 请修改为你的算法名称"""
    
    @property
    def algorithm_type(self) -> AlgorithmType:
        # TODO: 修改为你的算法类型
        return AlgorithmType.CLUSTER  # 示例：聚类算法
    
    @property
    def algorithm_name(self) -> str:
        # TODO: 修改为你的算法名称（用于注册）
        return "template"  # 示例：模板算法
    
    async def build_extraction_prompt(
        self, 
        question: str, 
        database_schema: Optional[List[DatabaseColumn]] = None,
        window_id: str = "default"
    ) -> List[Dict[str, str]]:
        """构建算法特定的参数提取提示词"""
        
        # 从NL2SQL服务获取候选表信息和关键词
        schema_text, query_db_result = await self._get_candidate_tables_from_nl2sql(question, window_id)
        
        # 保存查询结果供后续使用
        self._last_query_db_result = query_db_result
        
        # TODO: 根据你的算法需求设计系统提示词
        system_prompt = f"""你是[算法名称]专家。根据用户问题和数据库信息，提取算法所需的参数。

重要：你必须严格按照以下规则输出JSON，确保参数名和列名完全匹配数据库中的实际列名。

[算法名称]要求：
1. [参数1]: [参数1的描述和要求]
2. [参数2]: [参数2的描述和要求]
3. [参数3]: [参数3的描述和要求]

数据库可用列信息：
{schema_text}

严格输出规则：
1. 所有参数值必须是数据库中实际存在的列名
2. 不要创造不存在的列名
3. 列名必须与数据库schema中的column_name完全一致
4. 优先选择有注释说明的列

输出JSON格式（严格遵守）：
{{
  "parameter_mapping": {{
    "参数1": "数据库中实际的列名",
    "参数2": ["数据库中实际的列名1", "数据库中实际的列名2"],
    "参数3": 参数值或null
  }},
  "required_columns": ["所有需要的实际列名"],
  "normalized_query": "获取数据进行[算法名称]分析"
}}"""
        
        # TODO: 根据你的算法需求设计用户提示词
        user_prompt = f"""用户问题: {question}

请严格按照系统提示的规则分析用户需求，输出符合[算法名称]要求的JSON参数。

关键要求：
1. [具体要求1]
2. [具体要求2]
3. [具体要求3]

输出JSON格式的参数提取结果。"""
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def _format_database_schema(self, database_schema: List[DatabaseColumn]) -> str:
        """格式化数据库模式信息"""
        if not database_schema:
            return "（无可用数据库模式信息）"
        
        # 按表名分组
        tables = {}
        for column in database_schema:
            table_name = column.table_name
            if table_name not in tables:
                tables[table_name] = []
            tables[table_name].append(column)
        
        # 格式化输出
        lines = []
        for table_name, columns in tables.items():
            lines.append(f"表: {table_name}")
            for column in columns:
                comment = f": {column.column_comment}" if column.column_comment else ""
                # TODO: 根据你的算法需求标记特殊列类型
                # 示例：标记数值型列
                numeric_types = ['int', 'integer', 'decimal', 'float', 'double', 'numeric']
                is_numeric = any(num_type in column.data_type.lower() for num_type in numeric_types)
                type_mark = " [数值型]" if is_numeric else ""
                lines.append(f"  - {column.column_name} ({column.data_type}){type_mark}{comment}")
        
        return "\n".join(lines)
    
    def parse_extraction_response(self, response: str) -> Dict[str, Any]:
        """解析算法特定的LLM响应"""
        try:
            # 基础JSON解析
            result = self._parse_json_response(response)
            
            # TODO: 添加算法特定的响应处理逻辑
            parameter_mapping = result.get('parameter_mapping', {})
            
            # 示例：确保某个参数是列表
            # if 'feature_columns' in parameter_mapping:
            #     if isinstance(parameter_mapping['feature_columns'], str):
            #         parameter_mapping['feature_columns'] = [parameter_mapping['feature_columns']]
            
            # 示例：处理数值参数
            # if 'k_value' in parameter_mapping:
            #     k_value = parameter_mapping['k_value']
            #     if isinstance(k_value, str) and k_value.isdigit():
            #         parameter_mapping['k_value'] = int(k_value)
            #     elif k_value in [None, 'null', '']:
            #         parameter_mapping['k_value'] = None
            
            result['parameter_mapping'] = parameter_mapping
            return result
            
        except Exception as e:
            logger.error(f"[算法名称]参数解析失败: {str(e)}")
            raise ValueError(f"[算法名称]参数解析失败: {str(e)}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证算法参数"""
        validated = {}
        
        # TODO: 根据你的算法需求添加参数验证逻辑
        
        # 示例：验证必需参数
        # required_param = parameters.get('required_param')
        # if not required_param:
        #     raise ValueError("[算法名称]需要指定必需参数")
        # validated['required_param'] = str(required_param)
        
        # 示例：验证列表参数
        # list_param = parameters.get('list_param', [])
        # if not list_param:
        #     raise ValueError("[算法名称]至少需要1个列表参数")
        # if not isinstance(list_param, list):
        #     list_param = [list_param]
        # validated['list_param'] = list_param
        
        # 示例：验证数值参数
        # numeric_param = parameters.get('numeric_param')
        # if numeric_param is not None:
        #     if not isinstance(numeric_param, int) or numeric_param < 1:
        #         raise ValueError("数值参数必须是正整数")
        #     validated['numeric_param'] = numeric_param
        # else:
        #     validated['numeric_param'] = None
        
        return validated
    
    def get_last_query_db_result(self) -> Dict[str, Any]:
        """获取最后一次query_db的结果，用于后续的SQL生成"""
        return getattr(self, '_last_query_db_result', {})