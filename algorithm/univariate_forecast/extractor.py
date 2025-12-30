"""
Univariate Forecast Algorithm Parameter Extractor

单变量预测算法参数提取器
"""

import logging
from typing import Dict, List, Any, Optional
from algorithm.base.base_extractor import BaseAlgorithmExtractor
from algorithm.models import AlgorithmType, DatabaseColumn

logger = logging.getLogger(__name__)


class UnivariateForecastExtractor(BaseAlgorithmExtractor):
    """单变量预测算法参数提取器"""
    
    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.PREDICT
    
    @property
    def algorithm_name(self) -> str:
        return "univariate_forecast"
    
    async def build_extraction_prompt(
        self, 
        question: str, 
        database_schema: Optional[List[DatabaseColumn]] = None,
        window_id: str = "default"
    ) -> List[Dict[str, str]]:
        """构建单变量预测特定的参数提取提示词"""
        
        # 从NL2SQL服务获取候选表信息和关键词
        schema_text, query_db_result = await self._get_candidate_tables_from_nl2sql(question, window_id)
        
        # 保存查询结果供后续使用
        self._last_query_db_result = query_db_result
        
        system_prompt = f"""你是时间序列预测专家。根据用户问题和数据库信息，提取单变量预测所需的参数。

重要：你必须严格按照以下规则输出JSON，确保参数名和列名完全匹配数据库中的实际列名。

单变量预测要求：
1. timestamp_column: 必须指定一个时间列，用于标识时间序列的时间点
2. value_column: 必须指定一个数值列，作为预测的目标变量
3. forecast_horizon: 预测步数，即预测未来多少个时间点（根据用户需求判断）
4. model_type: 可选，预测模型类型，"auto"（自动选择）、"arima"或"prophet"
5. include_confidence: 可选，是否包含置信区间，默认true
6. confidence_level: 可选，置信区间水平，默认0.95

数据库可用列信息：
{schema_text}

预测步数判断规则：
- "未来24小时" → forecast_horizon: 24
- "下周" → forecast_horizon: 7（如果是日数据）或168（如果是小时数据）
- "未来30天" → forecast_horizon: 30
- "明天" → forecast_horizon: 1（如果是日数据）或24（如果是小时数据）
- 如果用户没有明确指定，默认使用24

严格输出规则：
1. timestamp_column的值必须是数据库中实际存在的时间类型列名
2. value_column的值必须是数据库中实际存在的数值型列名
3. 不要创造不存在的列名
4. 列名必须与数据库schema中的column_name完全一致
5. 优先选择有注释说明的列
6. normalized_query中一定写明返回的数据列注释（即timestamp_column+value_column），并且标名返回几列数据，否则无法正确解析，如"获取日期、销售额，共2列数据"！！！

输出JSON格式（严格遵守）：
{{
  "parameter_mapping": {{
    "timestamp_column": "日期",
    "value_column": "销售额",
    "forecast_horizon": 24,
    "model_type": "auto",
    "include_confidence": true,
    "confidence_level": 0.95
  }},
  "required_columns": ["日期", "销售额"],
  "normalized_query": "获取历史销售数据的日期、销售额，共2列数据"
}}"""
        
        user_prompt = f"""用户问题: {question}

请严格按照系统提示的规则分析用户需求，输出符合单变量预测要求的JSON参数。

关键要求：
1. 从数据库schema中选择合适的时间列作为timestamp_column
2. 从数据库schema中选择合适的数值列作为value_column
3. 根据用户问题判断预测步数forecast_horizon
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
        """解析单变量预测特定的LLM响应"""
        try:
            # 基础JSON解析
            result = self._parse_json_response(response)
            
            # 单变量预测特定验证和标准化
            parameter_mapping = result.get('parameter_mapping', {})
            
            # 处理forecast_horizon
            forecast_horizon = parameter_mapping.get('forecast_horizon', 24)
            if isinstance(forecast_horizon, str):
                if forecast_horizon.isdigit():
                    forecast_horizon = int(forecast_horizon)
                else:
                    forecast_horizon = 24
            elif isinstance(forecast_horizon, float):
                forecast_horizon = int(forecast_horizon)
            if forecast_horizon < 1:
                forecast_horizon = 24
            if forecast_horizon > 365:
                forecast_horizon = 365
            parameter_mapping['forecast_horizon'] = forecast_horizon
            
            # 处理model_type
            model_type = parameter_mapping.get('model_type', 'auto')
            if model_type not in ['auto', 'arima', 'prophet']:
                model_type = 'auto'
            parameter_mapping['model_type'] = model_type
            
            # 处理include_confidence
            include_confidence = parameter_mapping.get('include_confidence', True)
            if isinstance(include_confidence, str):
                include_confidence = include_confidence.lower() in ['true', '1', 'yes']
            parameter_mapping['include_confidence'] = bool(include_confidence)
            
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
            logger.error(f"单变量预测参数解析失败: {str(e)}")
            raise ValueError(f"单变量预测参数解析失败: {str(e)}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证单变量预测参数"""
        validated = {}
        
        # 验证时间列
        timestamp_column = parameters.get('timestamp_column')
        if not timestamp_column:
            raise ValueError("单变量预测需要指定时间列")
        validated['timestamp_column'] = str(timestamp_column)
        
        # 验证数值列
        value_column = parameters.get('value_column')
        if not value_column:
            raise ValueError("单变量预测需要指定数值列")
        validated['value_column'] = str(value_column)
        
        # 验证预测步数
        forecast_horizon = parameters.get('forecast_horizon', 24)
        if not isinstance(forecast_horizon, int) or forecast_horizon < 1:
            forecast_horizon = 24
        if forecast_horizon > 365:
            forecast_horizon = 365
        validated['forecast_horizon'] = forecast_horizon
        
        # 验证模型类型
        model_type = parameters.get('model_type', 'auto')
        if model_type not in ['auto', 'arima', 'prophet']:
            model_type = 'auto'
        validated['model_type'] = model_type
        
        # 验证置信区间选项
        validated['include_confidence'] = bool(parameters.get('include_confidence', True))
        
        # 验证置信水平
        confidence_level = parameters.get('confidence_level', 0.95)
        if not (0.5 <= confidence_level <= 0.99):
            confidence_level = 0.95
        validated['confidence_level'] = confidence_level
        
        return validated
