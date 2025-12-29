"""
Association Analysis Parameter Extractor

关联分析参数提取器
"""

import logging
from typing import Dict, List, Any, Optional
from algorithm.base.base_extractor import BaseAlgorithmExtractor
from algorithm.models import AlgorithmType, DatabaseColumn

logger = logging.getLogger(__name__)


class AssociationExtractor(BaseAlgorithmExtractor):
    """关联分析参数提取器"""
    
    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.STATISTICAL
    
    @property
    def algorithm_name(self) -> str:
        return "association"
    
    async def build_extraction_prompt(
        self, 
        question: str, 
        database_schema: Optional[List[DatabaseColumn]] = None,
        window_id: str = "default"
    ) -> List[Dict[str, str]]:
        """构建关联分析参数提取提示词"""
        
        # 从NL2SQL服务获取候选表信息
        schema_text, query_db_result = await self._get_candidate_tables_from_nl2sql(question, window_id)
        
        # 保存查询结果供后续使用
        self._last_query_db_result = query_db_result
        
        system_prompt = f"""你是关联分析专家。根据用户问题和数据库信息，提取关联分析所需的两列数据。

重要：你必须严格按照以下规则输出JSON，确保列名完全匹配数据库中的实际列名。

关联分析要求：
1. column1: 第一个变量的列名（必需）
2. column2: 第二个变量的列名（必需）
3. significance_level: 显著性水平（可选，默认0.05）

分析方法会自动选择：
- 两个分类变量 → 卡方检验
- 两个数值变量 → 相关性分析（Pearson/Spearman）
- 一个分类 + 一个数值 → 方差分析（ANOVA）

数据库可用列信息：
{schema_text}

严格输出规则：
1. column1 和 column2 必须是数据库中实际存在的列名
2. 列名必须与数据库schema中的column_name完全一致
3. 不要创造不存在的列名
4. 优先选择有注释说明的列

输出JSON格式（严格遵守）：
{{
  "parameter_mapping": {{
    "column1": "数据库中第一列的实际列名",
    "column2": "数据库中第二列的实际列名",
    "significance_level": 0.05
  }},
  "required_columns": ["第一列实际列名", "第二列实际列名"],
  "normalized_query": "分析[列1]与[列2]的关联关系"
}}"""
        
        user_prompt = f"""用户问题: {question}

请严格按照系统提示的规则分析用户需求，输出符合关联分析要求的JSON参数。

关键要求：
1. 识别用户想要分析关联的两个变量
2. 从数据库schema中找到对应的实际列名
3. 确保列名完全匹配数据库中的column_name
4. 如果用户指定了显著性水平（如α=0.01），则设置significance_level

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
                # 标记数值型列和分类型列
                numeric_types = ['int', 'integer', 'decimal', 'float', 'double', 'numeric', 'bigint', 'smallint']
                text_types = ['char', 'varchar', 'text', 'string', 'enum']
                
                if any(num_type in column.data_type.lower() for num_type in numeric_types):
                    type_mark = " [数值型]"
                elif any(text_type in column.data_type.lower() for text_type in text_types):
                    type_mark = " [文本/分类型]"
                else:
                    type_mark = ""
                
                lines.append(f"  - {column.column_name} ({column.data_type}){type_mark}{comment}")
        
        return "\n".join(lines)
    
    def parse_extraction_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应"""
        try:
            # 基础JSON解析
            result = self._parse_json_response(response)
            
            parameter_mapping = result.get('parameter_mapping', {})
            
            # 确保column1和column2是字符串
            if 'column1' in parameter_mapping:
                parameter_mapping['column1'] = str(parameter_mapping['column1'])
            
            if 'column2' in parameter_mapping:
                parameter_mapping['column2'] = str(parameter_mapping['column2'])
            
            # 处理significance_level
            if 'significance_level' in parameter_mapping:
                sig_level = parameter_mapping['significance_level']
                if isinstance(sig_level, str):
                    try:
                        parameter_mapping['significance_level'] = float(sig_level)
                    except ValueError:
                        parameter_mapping['significance_level'] = 0.05
                elif sig_level is None or sig_level == '':
                    parameter_mapping['significance_level'] = 0.05
            else:
                parameter_mapping['significance_level'] = 0.05
            
            result['parameter_mapping'] = parameter_mapping
            return result
            
        except Exception as e:
            logger.error(f"关联分析参数解析失败: {str(e)}")
            raise ValueError(f"关联分析参数解析失败: {str(e)}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证关联分析参数"""
        validated = {}
        
        # 验证column1
        column1 = parameters.get('column1')
        if not column1:
            raise ValueError("关联分析需要指定第一列（column1）")
        validated['column1'] = str(column1)
        
        # 验证column2
        column2 = parameters.get('column2')
        if not column2:
            raise ValueError("关联分析需要指定第二列（column2）")
        validated['column2'] = str(column2)
        
        # 验证两列不能相同
        if validated['column1'] == validated['column2']:
            raise ValueError("两列不能是同一列")
        
        # 验证显著性水平
        sig_level = parameters.get('significance_level', 0.05)
        if sig_level is not None:
            try:
                sig_level = float(sig_level)
                if not 0.001 <= sig_level <= 0.5:
                    raise ValueError("显著性水平必须在0.001到0.5之间")
                validated['significance_level'] = sig_level
            except (ValueError, TypeError):
                raise ValueError("显著性水平必须是有效的浮点数")
        else:
            validated['significance_level'] = 0.05
        
        logger.info(f"关联分析参数验证通过: column1={validated['column1']}, column2={validated['column2']}, α={validated['significance_level']}")
        
        return validated
    
    def get_last_query_db_result(self) -> Dict[str, Any]:
        """获取最后一次query_db的结果"""
        return getattr(self, '_last_query_db_result', {})
