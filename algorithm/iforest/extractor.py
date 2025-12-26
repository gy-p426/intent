"""
@Author      : Ayaki Shi
@Date        : 2025/12/23 21:00
@Description : 孤立森林算法参数提取器
"""

import logging
from typing import Dict, List, Any, Optional
from algorithm.base.base_extractor import BaseAlgorithmExtractor
from algorithm.models import AlgorithmType, DatabaseColumn

logger = logging.getLogger(__name__)

class IFORESTExtractor(BaseAlgorithmExtractor):

    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.IFOREST

    @property
    def algorithm_name(self) -> str:
        return "iforest"

    async def build_extraction_prompt(
            self,
            question: str,
            database_schema: Optional[List[DatabaseColumn]] = None,
            window_id: str = "default"
    ) -> List[Dict[str, str]]:
        """构建IFOREST特定的参数提取提示词"""

        # 从NL2SQL服务获取候选表信息和关键词
        schema_text, query_db_result = await self._get_candidate_tables_from_nl2sql(question, window_id)

        # 保存查询结果供后续使用
        self._last_query_db_result = query_db_result

        system_prompt = f"""你是使用IFOREST孤立森林算法进行异常分析的专家。根据用户问题和数据库信息，提取IFOREST孤立森林算法所需的参数。

重要：你必须严格按照以下规则输出JSON，确保参数名和列名完全匹配数据库中的实际列名。

IFOREST孤立森林算法异常分析要求：
1. id_column: 必须指定一个ID列，用于标识每个数据点
2. feature_columns: 必须指定至少1个数值型特征列，用于异常分析
3. normalized_query：用于从text-to-sql算法获取数据的自然语言

数据库可用列信息：
{schema_text}
        
严格输出规则：
1. id_column的值必须是数据库中实际存在的列名（如"销售日期"、"sale_date"等）
2. feature_columns的值必须是数据库中实际存在的数值型列名列表
3. 不要创造不存在的列名
4. 列名必须与数据库schema中的column_name完全一致
5. 优先选择有注释说明的列，这样更容易理解业务含义
6. normalized_query中一定写明返回的数据列注释（即id_column+feature_columns），并且标名返回几列数据，否则无法正确解析，如"获取销售日期、销售额，共2列数据"！！！

输出JSON格式（严格遵守）：
{{
  "parameter_mapping": {{
    "id_column": "销售日期",
    "feature_columns": ["销售笔数", "销售额",...],
  }},
  "required_columns": ["所有需要的实际列注释"],
  "normalized_query": "获取A分公司不同销售日期的所有销售笔数、销售额"
}}"""

        user_prompt = f"""用户问题: {question}
        
请严格按照系统提示的规则分析用户需求，输出符合IFOREST孤立森林算法要求的JSON参数。

关键要求：
1. 从数据库schema中选择合适的ID列的列注释作为id_column
2. 从数据库schema中选择合适的数值型列作的列注释为feature_columns
3. 所有列注释必须与数据库中的实际列注释完全匹配
4. normalized_query一定要写明返回哪些列

输出JSON格式的参数提取结果。"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    def get_last_query_db_result(self) -> Dict[str, Any]:
        """获取最后一次query_db的结果，用于后续的SQL生成"""
        return getattr(self, '_last_query_db_result', {})

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

        # 格式化输出，突出显示数值型列
        lines = []
        for table_name, columns in tables.items():
            lines.append(f"表: {table_name}")
            for column in columns:
                # comment = f": {column.column_comment}" if column.column_comment else ""
                # 如果列注释为空，则跳过该行
                if not column.column_comment:
                    continue
                # 标记数值型列
                numeric_types = ['int', 'integer', 'decimal', 'float', 'double', 'numeric']
                is_numeric = any(num_type in column.data_type.lower() for num_type in numeric_types)
                numeric_mark = " [数值型]" if is_numeric else ""
                # 返回结果以列名、数据类型、数据类型标识、列注释
                # lines.append(f"  - {column.column_name} ({column.data_type}){numeric_mark}{comment}")
                # 列注释、数据类型、数据类型标识
                lines.append(f"  - {column.column_comment} ({column.data_type}){numeric_mark}")

        return "\n".join(lines)

    def parse_extraction_response(self, response: str) -> Dict[str, Any]:
        """解析IFOREST特定的LLM响应"""
        try:
            # 基础JSON解析
            result = self._parse_json_response(response)

            # IFOREST特定验证和标准化
            parameter_mapping = result.get('parameter_mapping', {})

            # 确保feature_columns是列表
            if 'feature_columns' in parameter_mapping:
                if isinstance(parameter_mapping['feature_columns'], str):
                    parameter_mapping['feature_columns'] = [parameter_mapping['feature_columns']]

            result['parameter_mapping'] = parameter_mapping
            return result

        except Exception as e:
            logger.error(f"IFOREST参数解析失败: {str(e)}")
            raise ValueError(f"IFOREST参数解析失败: {str(e)}")

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证IFOREST参数"""
        validated = {}

        # 验证ID列
        id_column = parameters.get('id_column')
        if not id_column:
            raise ValueError("IFOREST密度聚类需要指定ID列")
        validated['id_column'] = str(id_column)

        # 验证特征列
        feature_columns = parameters.get('feature_columns', [])
        if not feature_columns:
            raise ValueError("IFOREST孤立森林算法至少需要1个特征列")
        if not isinstance(feature_columns, list):
            feature_columns = [feature_columns]
        validated['feature_columns'] = feature_columns
        if len(feature_columns) > 50:
            raise ValueError(f"IFOREST孤立森林算法最多支持50个特征列，当前传入了{len(feature_columns)}个")
        validated['feature_columns'] = feature_columns

        return validated