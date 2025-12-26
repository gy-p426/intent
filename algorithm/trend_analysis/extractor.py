"""
Trend Analysis Algorithm Parameter Extractor

趋势分析算法参数提取器
"""

import logging
from typing import Dict, List, Any, Optional
from algorithm.base.base_extractor import BaseAlgorithmExtractor
from algorithm.models import AlgorithmType, DatabaseColumn

logger = logging.getLogger(__name__)


class TrendAnalysisExtractor(BaseAlgorithmExtractor):
    """趋势分析算法参数提取器"""
    
    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.TREND
    
    @property
    def algorithm_name(self) -> str:
        return "trend_analysis"
    
    async def build_extraction_prompt(
        self, 
        question: str, 
        database_schema: Optional[List[DatabaseColumn]] = None,
        window_id: str = "default"
    ) -> List[Dict[str, str]]:
        """构建趋势分析特定的参数提取提示词"""
        
        # 从NL2SQL服务获取候选表信息和关键词
        schema_text, query_db_result = await self._get_candidate_tables_from_nl2sql(question, window_id)
        
        # 保存查询结果供后续使用
        self._last_query_db_result = query_db_result
        
        system_prompt = f"""你是时间序列趋势分析专家。根据用户问题和数据库信息，提取趋势分析所需的参数。

重要：你必须严格按照以下规则输出JSON，确保参数名和列名完全匹配SQL查询返回的实际字段名。

趋势分析要求：
1. timestamp_column: 必须指定一个时间列，用于标识时间序列的时间点
2. value_column: 必须指定一个数值列，用于趋势分析的目标数值
3. analysis_type: 分析类型，"decomposition"（趋势分解）或"detection"（趋势检测）
4. period: 可选，季节周期长度（如24表示小时数据的日周期，7表示日数据的周周期）
5. decomposition_model: 可选，分解模型类型，"additive"或"multiplicative"
6. algorithm: 可选，分解算法，"auto"、"stl"或"classical"
7. detection_method: 可选，趋势检测方法，"auto"、"mann_kendall"或"linear_regression"
8. confidence_level: 可选，置信水平，默认0.95

数据库可用列信息：
{schema_text}

特别注意：
- 如果用户问题涉及"出车"、"派车"、"调度"等，时间列通常是"日期"，数值列通常是"出车次数"
- 如果用户问题涉及销售、订单等，时间列可能是"日期"、"时间"，数值列可能是"销售额"、"订单数"等
- 字段名可能是中文，请使用SQL查询实际返回的字段名，不要翻译成英文

严格输出规则：
1. timestamp_column的值必须是SQL查询实际返回的时间字段名（可能是中文）
2. value_column的值必须是SQL查询实际返回的数值字段名（可能是中文）
3. 不要创造不存在的列名，不要将中文字段名翻译成英文
4. 列名必须与SQL查询结果中的字段名完全一致
5. 优先选择有注释说明的列
6. normalized_query中一定写明返回的数据列（时间列+数值列），并标名返回几列数据

输出JSON格式（严格遵守）：
{{
  "parameter_mapping": {{
    "timestamp_column": "日期",
    "value_column": "出车次数",
    "analysis_type": "decomposition",
    "period": null,
    "decomposition_model": "additive",
    "algorithm": "auto",
    "detection_method": "auto",
    "confidence_level": 0.95
  }},
  "required_columns": ["日期", "出车次数"],
  "normalized_query": "获取出车数据的日期和出车次数用于趋势分析，返回2列数据"
}}"""
        
        user_prompt = f"""用户问题: {question}

请严格按照系统提示的规则分析用户需求，输出符合趋势分析要求的JSON参数。

关键要求：
1. 从SQL查询结果中选择合适的时间字段作为timestamp_column（如"日期"）
2. 从SQL查询结果中选择合适的数值字段作为value_column（如"出车次数"）
3. 根据用户问题判断是需要"趋势分解"还是"趋势检测"
4. 如果用户提到周期（如日周期、周周期），设置period值
5. normalized_query一定要写明返回哪些列
6. 字段名使用中文，与SQL查询返回的字段名保持一致

特别提醒：
- 对于出车、派车相关问题，时间字段通常是"日期"，数值字段通常是"出车次数"
- 不要将中文字段名翻译成英文（如不要用dispatch_date代替"日期"）

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
        """解析趋势分析特定的LLM响应"""
        try:
            # 基础JSON解析
            result = self._parse_json_response(response)
            
            # 趋势分析特定验证和标准化
            parameter_mapping = result.get('parameter_mapping', {})
            
            # 处理analysis_type
            analysis_type = parameter_mapping.get('analysis_type', 'decomposition')
            if analysis_type not in ['decomposition', 'detection']:
                parameter_mapping['analysis_type'] = 'decomposition'
            
            # 处理period
            period = parameter_mapping.get('period')
            if period is not None:
                if isinstance(period, str):
                    if period.isdigit():
                        parameter_mapping['period'] = int(period)
                    elif period.lower() in ['null', 'none', '']:
                        parameter_mapping['period'] = None
                elif isinstance(period, (int, float)):
                    parameter_mapping['period'] = int(period)
            
            # 处理decomposition_model
            decomposition_model = parameter_mapping.get('decomposition_model', 'additive')
            if decomposition_model not in ['additive', 'multiplicative']:
                parameter_mapping['decomposition_model'] = 'additive'
            
            # 处理algorithm
            algorithm = parameter_mapping.get('algorithm', 'auto')
            if algorithm not in ['auto', 'stl', 'classical']:
                parameter_mapping['algorithm'] = 'auto'
            
            # 处理detection_method
            detection_method = parameter_mapping.get('detection_method', 'auto')
            if detection_method not in ['auto', 'mann_kendall', 'linear_regression']:
                parameter_mapping['detection_method'] = 'auto'
            
            # 处理confidence_level
            confidence_level = parameter_mapping.get('confidence_level', 0.95)
            if isinstance(confidence_level, str):
                try:
                    confidence_level = float(confidence_level)
                except ValueError:
                    confidence_level = 0.95
            if not (0.5 <= confidence_level <= 0.99):
                confidence_level = 0.95
            parameter_mapping['confidence_level'] = confidence_level
            
            result['parameter_mapping'] = parameter_mapping
            return result
            
        except Exception as e:
            logger.error(f"趋势分析参数解析失败: {str(e)}")
            raise ValueError(f"趋势分析参数解析失败: {str(e)}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证趋势分析参数"""
        validated = {}
        
        # 验证时间列
        timestamp_column = parameters.get('timestamp_column')
        if not timestamp_column:
            raise ValueError("趋势分析需要指定时间列")
        validated['timestamp_column'] = str(timestamp_column)
        
        # 验证数值列
        value_column = parameters.get('value_column')
        if not value_column:
            raise ValueError("趋势分析需要指定数值列")
        validated['value_column'] = str(value_column)
        
        # 验证分析类型
        analysis_type = parameters.get('analysis_type', 'decomposition')
        if analysis_type not in ['decomposition', 'detection']:
            analysis_type = 'decomposition'
        validated['analysis_type'] = analysis_type
        
        # 验证周期
        period = parameters.get('period')
        if period is not None:
            if not isinstance(period, int) or period < 2:
                raise ValueError("周期必须是大于等于2的整数")
            validated['period'] = period
        else:
            validated['period'] = None
        
        # 验证分解模型
        decomposition_model = parameters.get('decomposition_model', 'additive')
        if decomposition_model not in ['additive', 'multiplicative']:
            decomposition_model = 'additive'
        validated['decomposition_model'] = decomposition_model
        
        # 验证算法
        algorithm = parameters.get('algorithm', 'auto')
        if algorithm not in ['auto', 'stl', 'classical']:
            algorithm = 'auto'
        validated['algorithm'] = algorithm
        
        # 验证检测方法
        detection_method = parameters.get('detection_method', 'auto')
        if detection_method not in ['auto', 'mann_kendall', 'linear_regression']:
            detection_method = 'auto'
        validated['detection_method'] = detection_method
        
        # 验证置信水平
        confidence_level = parameters.get('confidence_level', 0.95)
        if not (0.5 <= confidence_level <= 0.99):
            confidence_level = 0.95
        validated['confidence_level'] = confidence_level
        
        return validated
