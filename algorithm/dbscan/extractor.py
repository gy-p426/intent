"""
@Author      : Ayaki Shi
@Date        : 2025/12/23 16:17 
@Description : 密度聚类算法参数提取器
"""

import logging
from typing import Dict, List, Any, Optional
from algorithm.base.base_extractor import BaseAlgorithmExtractor
from algorithm.models import AlgorithmType, DatabaseColumn

logger = logging.getLogger(__name__)

class DBSCANExtractor(BaseAlgorithmExtractor):

    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.ANOMALY

    @property
    def algorithm_name(self) -> str:
        return "dbscan"  # 保留具体算法名称以便区分

    async def build_extraction_prompt(
            self,
            question: str,
            database_schema: Optional[List[DatabaseColumn]] = None,
            window_id: str = "default",
            user_id: Optional[int] = None,
            schema_text: str = "",
            query_db_result: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """构建DBSCAN特定的参数提取提示词"""

        # 使用传入的候选表信息（由parameter_extractor统一获取）
        if not schema_text:
            schema_text = "（无可用数据库模式信息）"
        if query_db_result is None:
            query_db_result = {}

        system_prompt = f"""你是DBSCAN密度聚类分析专家。根据用户问题和数据库信息，提取聚类分析所需的参数。

重要：你必须严格按照以下规则输出JSON，确保参数名和列名完全匹配数据库中的实际列名。

DBSCAN密度聚类分析要求：
1. id_column: 必须指定一个ID列，用于标识每个数据点
2. feature_columns: 必须指定至少1个数值型特征列，用于聚类计算
3. normalized_query：用于从text-to-sql算法获取数据的自然语言

数据库可用列信息：
{schema_text}
        
严格输出规则：
1. id_column的值必须是数据库中实际存在的列注释
2. feature_columns的值必须是数据库中实际存在的数值型列注释列表
3. 不要创造不存在的列注释
4. required_columns中一定写明列注释，一定与normalized_query的使用的名称相同，如"required_columns": ["日期", "销售额"],"normalized_query": "获取XX年xx月到xx年月期间的历史销售数据的日期、销售额，共2列数据"
5. 优先选择有注释说明的列，这样更容易理解业务含义
6. normalized_query中一定写明返回的数据列注释（即id_column+feature_columns），并且标名返回几列数据，否则无法正确解析，如"获取销售日期、销售额，返回日期、销售额共2列数据"，！！！

输出JSON格式（严格遵守）：
{{
  "parameter_mapping": {{
    "id_column": "销售日期",
    "feature_columns": ["销售笔数", "销售额",...],
  }},
  "required_columns": ["销售日期、销售笔数、销售额"],
  "normalized_query": "获取A分公司不同销售日期的所有销售笔数、销售额，返回销售日期、销售笔数、销售额共3列数据"
}}"""

        user_prompt = f"""用户问题: {question}
        
请严格按照系统提示的规则分析用户需求，输出符合DBSCAN算法要求的JSON参数。

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
        """解析DBSCAN特定的LLM响应"""
        try:
            # 基础JSON解析
            result = self._parse_json_response(response)

            # DBSCAN特定验证和标准化
            parameter_mapping = result.get('parameter_mapping', {})

            # 确保feature_columns是列表
            if 'feature_columns' in parameter_mapping:
                if isinstance(parameter_mapping['feature_columns'], str):
                    parameter_mapping['feature_columns'] = [parameter_mapping['feature_columns']]

            result['parameter_mapping'] = parameter_mapping
            return result

        except Exception as e:
            logger.error(f"DBSCAN参数解析失败: {str(e)}")
            raise ValueError(f"DBSCAN参数解析失败: {str(e)}")

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证DBSCAN参数"""
        validated = {}

        # 验证ID列
        id_column = parameters.get('id_column')
        if not id_column:
            raise ValueError("DBSCAN密度聚类需要指定ID列")
        validated['id_column'] = str(id_column)

        # 验证特征列
        feature_columns = parameters.get('feature_columns', [])
        if not feature_columns:
            raise ValueError("DBSCAN密度聚类至少需要1个特征列")
        if not isinstance(feature_columns, list):
            feature_columns = [feature_columns]
        validated['feature_columns'] = feature_columns
        if len(feature_columns) > 10:
            raise ValueError(f"DBSCAN密度聚类最多支持10个特征列，当前传入了{len(feature_columns)}个")
        validated['feature_columns'] = feature_columns

        return validated