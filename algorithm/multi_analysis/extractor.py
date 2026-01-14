"""
Multi Analysis Algorithm Parameter Extractor

统一多算法分析参数提取器
"""

import logging
from typing import Dict, List, Any, Optional
from algorithm.base.base_extractor import BaseAlgorithmExtractor
from algorithm.models import AlgorithmType, DatabaseColumn

logger = logging.getLogger(__name__)


class MultiAnalysisExtractor(BaseAlgorithmExtractor):
    """统一多算法分析参数提取器"""
    
    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.MULTI_ANALYSIS
    
    @property
    def algorithm_name(self) -> str:
        return "multi_analysis"
    
    async def build_extraction_prompt(
        self, 
        question: str, 
        database_schema: Optional[List[DatabaseColumn]] = None,
        window_id: str = "default"
    ) -> List[Dict[str, str]]:
        """构建统一多算法分析特定的参数提取提示词"""
        
        # 从NL2SQL服务获取候选表信息和关键词
        schema_text, query_db_result = await self._get_candidate_tables_from_nl2sql(question, window_id)
        
        # 保存查询结果供后续使用
        self._last_query_db_result = query_db_result
        
        system_prompt = f"""你是时间序列综合分析专家。根据用户问题和数据库信息，提取统一多算法分析所需的参数。

重要：你必须严格按照以下规则输出JSON，确保参数名和列名完全匹配SQL查询返回的实际字段名。

统一多算法分析支持以下分析类型：
- periodicity: 周期性分析 - 检测数据的周期性规律
- period_over_period: 环比分析 - 与上一周期对比（如本月vs上月）
- year_over_year: 同比分析 - 与去年同期对比（如今年3月vs去年3月）
- base_period_index: 定基比分析 - 以固定基期计算指数

参数说明：
1. timestamp_column: 必须指定一个时间列，用于标识时间序列的时间点
2. value_column: 必须指定一个数值列，用于分析的目标数值
3. analysis_types: 要执行的分析类型列表，根据用户意图选择
4. include_all: 是否执行所有分析（当用户意图不明确时设为true）
5. period_type: 周期类型（hour/day/week/month/quarter/year）
6. base_period: 定基比分析的基期标识（如 "2020"）

数据库可用列信息：
{schema_text}

分析类型选择规则：
- 用户提到"周期"、"规律"、"周期性" → 包含 periodicity
- 用户提到"环比"、"上月"、"上周"、"与上期对比" → 包含 period_over_period
- 用户提到"同比"、"去年"、"同期"、"与去年对比" → 包含 year_over_year
- 用户提到"定基"、"基期"、"以...为基准" → 包含 base_period_index
- 用户提到"综合分析"、"全面分析" → 设置 include_all: true

严格输出规则：
1. timestamp_column的值必须是SQL查询实际返回的时间字段名（可能是中文）
2. value_column的值必须是SQL查询实际返回的数值字段名（可能是中文）
3. 不要创造不存在的列名，不要将中文字段名翻译成英文
4. 列名必须与SQL查询结果中的字段名完全一致
5. 优先选择有注释说明的列
6. normalized_query中一定写明返回的数据列注释（即timestamp_column+value_column），并且标名返回几列数据，否则无法正确解析，如"获取日期、销售额，返回日期、销售额共2列数据"！！！
7. required_columns中一定写明列注释，一定与normalized_query的使用的名称相同

输出JSON格式（严格遵守）：
{{
  "parameter_mapping": {{
    "timestamp_column": "日期",
    "value_column": "销售额",
    "analysis_types": ["periodicity", "period_over_period"],
    "include_all": false,
    "period_type": "month",
    "base_period": null,
    "base_value": 100,
    "simplified": false
  }},
  "required_columns": ["日期", "销售额"],
  "normalized_query": "获取销售数据的日期、销售额，返回日期、销售额共2列数据"
}}"""
        
        user_prompt = f"""用户问题: {question}

请严格按照系统提示的规则分析用户需求，输出符合统一多算法分析要求的JSON参数。

关键要求：
1. 从SQL查询结果中选择合适的时间字段作为timestamp_column
2. 从SQL查询结果中选择合适的数值字段作为value_column
3. 根据用户问题判断需要执行哪些分析类型
4. 如果用户意图不明确，设置include_all为true执行所有分析
5. normalized_query一定要写明返回哪些列，格式为"共X列数据"
6. 字段名使用中文，与SQL查询返回的字段名保持一致

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
        
        # 格式化输出，突出显示时间型和数值型列
        lines = []
        for table_name, columns in tables.items():
            lines.append(f"表: {table_name}")
            for column in columns:
                if not column.column_comment:
                    continue
                # 标记时间型列
                time_types = ['datetime', 'timestamp', 'date', 'time']
                is_time = any(t in column.data_type.lower() for t in time_types)
                # 标记数值型列
                numeric_types = ['int', 'integer', 'decimal', 'float', 'double', 'numeric']
                is_numeric = any(num_type in column.data_type.lower() for num_type in numeric_types)
                
                type_mark = ""
                if is_time:
                    type_mark = " [时间型]"
                elif is_numeric:
                    type_mark = " [数值型]"
                
                lines.append(f"  - {column.column_comment} ({column.data_type}){type_mark}")
        
        return "\n".join(lines)
    
    def parse_extraction_response(self, response: str) -> Dict[str, Any]:
        """解析统一多算法分析特定的LLM响应"""
        try:
            # 基础JSON解析
            result = self._parse_json_response(response)
            
            # 统一多算法分析特定验证和标准化
            parameter_mapping = result.get('parameter_mapping', {})
            
            # 处理analysis_types
            analysis_types = parameter_mapping.get('analysis_types')
            valid_types = ['periodicity', 'period_over_period', 'year_over_year', 'base_period_index']
            if analysis_types is not None:
                if isinstance(analysis_types, str):
                    analysis_types = [analysis_types]
                # 过滤无效类型
                analysis_types = [t for t in analysis_types if t in valid_types]
                parameter_mapping['analysis_types'] = analysis_types if analysis_types else None
            
            # 处理include_all
            include_all = parameter_mapping.get('include_all', True)
            if isinstance(include_all, str):
                include_all = include_all.lower() in ['true', '1', 'yes']
            parameter_mapping['include_all'] = bool(include_all)
            
            # 处理period_type
            period_type = parameter_mapping.get('period_type')
            valid_period_types = ['hour', 'day', 'week', 'month', 'quarter', 'year']
            if period_type and period_type not in valid_period_types:
                parameter_mapping['period_type'] = None
            
            # 处理base_period
            base_period = parameter_mapping.get('base_period')
            if base_period is not None:
                parameter_mapping['base_period'] = str(base_period)
            
            # 处理base_value
            base_value = parameter_mapping.get('base_value', 100)
            if isinstance(base_value, str):
                try:
                    base_value = float(base_value)
                except ValueError:
                    base_value = 100
            parameter_mapping['base_value'] = base_value
            
            # 处理simplified
            simplified = parameter_mapping.get('simplified', False)
            if isinstance(simplified, str):
                simplified = simplified.lower() in ['true', '1', 'yes']
            parameter_mapping['simplified'] = bool(simplified)
            
            result['parameter_mapping'] = parameter_mapping
            return result
            
        except Exception as e:
            logger.error(f"统一多算法分析参数解析失败: {str(e)}")
            raise ValueError(f"统一多算法分析参数解析失败: {str(e)}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证统一多算法分析参数"""
        validated = {}
        
        # 验证时间列
        timestamp_column = parameters.get('timestamp_column')
        if not timestamp_column:
            raise ValueError("统一多算法分析需要指定时间列")
        validated['timestamp_column'] = str(timestamp_column)
        
        # 验证数值列
        value_column = parameters.get('value_column')
        if not value_column:
            raise ValueError("统一多算法分析需要指定数值列")
        validated['value_column'] = str(value_column)
        
        # 验证分析类型
        analysis_types = parameters.get('analysis_types')
        valid_types = ['periodicity', 'period_over_period', 'year_over_year', 'base_period_index']
        if analysis_types is not None:
            if not isinstance(analysis_types, list):
                analysis_types = [analysis_types]
            analysis_types = [t for t in analysis_types if t in valid_types]
            validated['analysis_types'] = analysis_types if analysis_types else None
        else:
            validated['analysis_types'] = None
        
        # 验证include_all
        validated['include_all'] = bool(parameters.get('include_all', True))
        
        # 验证period_type
        period_type = parameters.get('period_type')
        valid_period_types = ['hour', 'day', 'week', 'month', 'quarter', 'year']
        if period_type and period_type in valid_period_types:
            validated['period_type'] = period_type
        else:
            validated['period_type'] = None
        
        # 验证base_period
        base_period = parameters.get('base_period')
        validated['base_period'] = str(base_period) if base_period else None
        
        # 验证base_value
        base_value = parameters.get('base_value', 100)
        if not isinstance(base_value, (int, float)):
            base_value = 100
        validated['base_value'] = float(base_value)
        
        # 验证simplified
        validated['simplified'] = bool(parameters.get('simplified', False))
        
        return validated
