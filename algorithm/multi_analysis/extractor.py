"""
Multi Analysis Algorithm Parameter Extractor

统一多算法分析参数提取器
"""

import logging
from datetime import datetime
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
        
        # 获取当前日期信息，用于时间表达解析
        current_date = datetime.now()
        current_year = current_date.year
        current_month = current_date.month
        current_day = current_date.day
        # 计算当前季度
        current_quarter = (current_month - 1) // 3 + 1
        # 计算当前周数
        current_week = current_date.isocalendar()[1]
        
        system_prompt = f"""你是时间序列综合分析专家。根据用户问题和数据库信息，提取统一多算法分析所需的参数。

重要：你必须严格按照以下规则输出JSON，确保参数名和列名完全匹配SQL查询返回的实际字段名。

【当前日期上下文】
当前日期: {current_year}年{current_month}月{current_day}日
当前年份: {current_year}年
当前月份: {current_month}月
当前季度: Q{current_quarter}
当前周数: 第{current_week}周

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
7. time_range_info: 时间范围信息（新增字段，详见下方说明）

数据库可用列信息：
{schema_text}

分析类型选择规则：
- 用户提到"周期"、"规律"、"周期性" → 包含 periodicity
- 用户提到"环比"、"上月"、"上周"、"与上期对比" → 包含 period_over_period
- 用户提到"同比"、"去年"、"同期"、"与去年对比" → 包含 year_over_year
- 用户提到"定基"、"基期"、"以...为基准" → 包含 base_period_index
- 用户提到"综合分析"、"全面分析" → 设置 include_all: true

【时间范围扩展规则（重要！）】
根据分析类型，必须自动扩展查询时间范围，以获取完整的对比数据：

1. 环比分析 (period_over_period) 时间扩展规则：
   - 用户指定"8月" → 查询范围扩展为"7月+8月"（包含上一个月）
   - 用户指定"本周" → 查询范围扩展为"上周+本周"（包含上一周）
   - 用户指定"Q2" → 查询范围扩展为"Q1+Q2"（包含上一季度）
   - 用户指定"2025年" → 查询范围扩展为"2024年+2025年"（包含上一年）
   - 用户指定"8月15日" → 查询范围扩展为"8月14日+8月15日"（包含前一天）
   - 跨年处理：1月环比需要查询去年12月和今年1月

2. 同比分析 (year_over_year) 时间扩展规则：
   - 用户指定"2025年8月" → 查询范围扩展为"2024年8月+2025年8月"（包含去年同月）
   - 用户指定"今年Q2" → 查询范围扩展为"去年Q2+今年Q2"（包含去年同季度）
   - 用户指定"本周" → 查询范围扩展为"去年同周+本周"（包含去年同周）
   - 用户指定"2025年" → 查询范围扩展为"2024年+2025年"（包含前一年）

3. 定基比分析 (base_period_index) 时间扩展规则：
   - 用户指定基期"2020年"，目标"2025年" → 查询范围为"2020年至2025年"（连续）
   - 用户指定基期"1月"，目标"8月" → 查询范围为"1月至8月"（连续）
   - 未指定基期时 → 使用数据中最早的周期作为默认基期

4. 周期性分析 (periodicity) 数据量要求：
   - 确保查询范围至少包含8个数据点
   - 如果用户指定范围不足8个数据点，自动向前扩展时间范围
   - 例如：月度数据至少需要8个月，日度数据至少需要8天

【时间表达解析规则】
相对时间表达映射（基于当前日期 {current_year}年{current_month}月{current_day}日）：
| 表达方式 | 解析结果 |
|---------|---------|
| 本月、这个月、当月 | {current_year}年{current_month}月 |
| 上月、上个月 | {current_year - 1 if current_month == 1 else current_year}年{12 if current_month == 1 else current_month - 1}月 |
| 本周、这周 | {current_year}年第{current_week}周 |
| 上周、上个周 | {current_year}年第{current_week - 1 if current_week > 1 else 52}周 |
| 今年、本年 | {current_year}年 |
| 去年、上一年 | {current_year - 1}年 |
| 本季度、这个季度 | {current_year}年Q{current_quarter} |
| 上季度、上个季度 | {current_year - 1 if current_quarter == 1 else current_year}年Q{4 if current_quarter == 1 else current_quarter - 1} |

绝对时间表达映射：
| 表达方式 | 解析结果 |
|---------|---------|
| 2025年8月、2025-08 | year=2025, month=8 |
| 8月、8月份 | year={current_year}, month=8 |
| 2025年 | year=2025 |
| Q1、第一季度、一季度 | quarter=1 |
| 2025年Q2 | year=2025, quarter=2 |

严格输出规则：
1. timestamp_column的值必须是SQL查询实际返回的时间字段名（可能是中文）
2. value_column的值必须是SQL查询实际返回的数值字段名（可能是中文）
3. 不要创造不存在的列名，不要将中文字段名翻译成英文
4. 列名必须与SQL查询结果中的字段名完全一致
5. 优先选择有注释说明的列
6. normalized_query中一定写明返回的数据列注释（即timestamp_column+value_column），并且标名返回几列数据，否则无法正确解析，如"获取2025年7月至8月的日期、销售额，返回日期、销售额共2列数据"！！！
7. required_columns中一定写明列注释，一定与normalized_query的使用的名称相同
8. normalized_query必须包含扩展后的完整时间范围描述（如"2025年7月至8月"而非仅"8月"）

【time_range_info 字段说明】
time_range_info 是新增的必填字段，用于记录时间范围扩展信息，结构如下：

{{
  "analysis_type": "period_over_period",  // 分析类型
  "period_type": "month",                  // 周期类型: hour/day/week/month/quarter/year
  "target_period": {{"year": 2025, "month": 8}},  // 目标周期
  "comparison_period": {{"year": 2025, "month": 7}},  // 对比周期（环比为上一周期，同比为去年同期）
  "expanded_range": {{
    "start": "2025-07-01",  // 扩展后时间范围起始
    "end": "2025-08-31"     // 扩展后时间范围结束
  }}
}}

不同分析类型的 time_range_info 字段：
- 环比分析: 包含 current_period（当前周期）和 previous_period（上一周期）
- 同比分析: 包含 current_period（当前周期）和 same_period_last_year（去年同期）
- 定基比分析: 包含 base_period（基期）和 target_periods（目标周期列表）
- 周期性分析: 包含 expanded_range（扩展后的时间范围）

输出JSON格式（严格遵守）：
{{
  "parameter_mapping": {{
    "timestamp_column": "日期",
    "value_column": "销售额",
    "analysis_types": ["period_over_period"],
    "include_all": false,
    "period_type": "month",
    "base_period": null,
    "base_value": 100,
    "simplified": false,
    "time_range_info": {{
      "analysis_type": "period_over_period",
      "period_type": "month",
      "current_period": {{"year": 2025, "month": 8}},
      "previous_period": {{"year": 2025, "month": 7}},
      "expanded_range": {{
        "start": "2025-07-01",
        "end": "2025-08-31"
      }}
    }}
  }},
  "required_columns": ["日期", "销售额"],
  "normalized_query": "获取2025年7月至8月的销售数据的日期、销售额，返回日期、销售额共2列数据"
}}

【更多输出示例】

示例1 - 同比分析（2025年8月与去年同期对比）：
{{
  "parameter_mapping": {{
    "timestamp_column": "日期",
    "value_column": "出车次数",
    "analysis_types": ["year_over_year"],
    "include_all": false,
    "period_type": "month",
    "base_period": null,
    "base_value": 100,
    "simplified": false,
    "time_range_info": {{
      "analysis_type": "year_over_year",
      "period_type": "month",
      "current_period": {{"year": 2025, "month": 8}},
      "same_period_last_year": {{"year": 2024, "month": 8}},
      "expanded_range": {{
        "start": "2024-08-01",
        "end": "2025-08-31"
      }}
    }}
  }},
  "required_columns": ["日期", "出车次数"],
  "normalized_query": "获取2024年8月和2025年8月的出车数据的日期、出车次数，返回日期、出车次数共2列数据"
}}

示例2 - 定基比分析（以2020年为基期）：
{{
  "parameter_mapping": {{
    "timestamp_column": "日期",
    "value_column": "销售额",
    "analysis_types": ["base_period_index"],
    "include_all": false,
    "period_type": "year",
    "base_period": "2020",
    "base_value": 100,
    "simplified": false,
    "time_range_info": {{
      "analysis_type": "base_period_index",
      "period_type": "year",
      "base_period": {{"year": 2020}},
      "target_periods": [{{"year": 2021}}, {{"year": 2022}}, {{"year": 2023}}, {{"year": 2024}}, {{"year": 2025}}],
      "expanded_range": {{
        "start": "2020-01-01",
        "end": "2025-12-31"
      }}
    }}
  }},
  "required_columns": ["日期", "销售额"],
  "normalized_query": "获取2020年至2025年的销售数据的日期、销售额，返回日期、销售额共2列数据"
}}

示例3 - 周期性分析（确保足够数据点）：
{{
  "parameter_mapping": {{
    "timestamp_column": "日期",
    "value_column": "出车次数",
    "analysis_types": ["periodicity"],
    "include_all": false,
    "period_type": "month",
    "base_period": null,
    "base_value": 100,
    "simplified": false,
    "time_range_info": {{
      "analysis_type": "periodicity",
      "period_type": "month",
      "min_data_points": 8,
      "expanded_range": {{
        "start": "2025-01-01",
        "end": "2025-08-31"
      }}
    }}
  }},
  "required_columns": ["日期", "出车次数"],
  "normalized_query": "获取2025年1月至8月的出车数据的日期、出车次数，返回日期、出车次数共2列数据"
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

【时间范围扩展要求（重要！）】
7. 根据分析类型自动扩展时间范围：
   - 环比分析：扩展包含上一周期的数据
   - 同比分析：扩展包含去年同期的数据
   - 定基比分析：扩展包含基期到目标期的完整数据
   - 周期性分析：确保至少8个数据点
8. normalized_query必须包含扩展后的完整时间范围（如"2025年7月至8月"）
9. 必须填写time_range_info字段，包含：
   - analysis_type: 分析类型
   - period_type: 周期类型
   - 对应的周期字段（current_period/previous_period/same_period_last_year/base_period/target_periods）
   - expanded_range: 扩展后的时间范围（start和end）

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
            
            # 处理time_range_info（新增）
            time_range_info = parameter_mapping.get('time_range_info')
            if time_range_info is not None:
                parameter_mapping['time_range_info'] = self._parse_time_range_info(time_range_info)
            else:
                # 如果缺失time_range_info，根据其他参数生成默认值
                parameter_mapping['time_range_info'] = self._generate_default_time_range_info(parameter_mapping)
            
            result['parameter_mapping'] = parameter_mapping
            return result
            
        except Exception as e:
            logger.error(f"统一多算法分析参数解析失败: {str(e)}")
            raise ValueError(f"统一多算法分析参数解析失败: {str(e)}")
    
    def _parse_time_range_info(self, time_range_info: Dict[str, Any]) -> Dict[str, Any]:
        """解析和标准化time_range_info字段
        
        Args:
            time_range_info: LLM返回的时间范围信息
            
        Returns:
            标准化后的time_range_info字典
        """
        if not isinstance(time_range_info, dict):
            logger.warning(f"time_range_info不是字典类型: {type(time_range_info)}")
            return {}
        
        parsed = {}
        
        # 解析analysis_type
        analysis_type = time_range_info.get('analysis_type')
        valid_analysis_types = ['periodicity', 'period_over_period', 'year_over_year', 'base_period_index']
        if analysis_type and analysis_type in valid_analysis_types:
            parsed['analysis_type'] = analysis_type
        
        # 解析period_type
        period_type = time_range_info.get('period_type')
        valid_period_types = ['hour', 'day', 'week', 'month', 'quarter', 'year']
        if period_type and period_type in valid_period_types:
            parsed['period_type'] = period_type
        
        # 解析expanded_range（必需字段）
        expanded_range = time_range_info.get('expanded_range')
        if expanded_range and isinstance(expanded_range, dict):
            parsed_range = {}
            if 'start' in expanded_range:
                parsed_range['start'] = str(expanded_range['start'])
            if 'end' in expanded_range:
                parsed_range['end'] = str(expanded_range['end'])
            if parsed_range:
                parsed['expanded_range'] = parsed_range
        
        # 根据分析类型解析特定字段
        analysis_type = parsed.get('analysis_type')
        
        if analysis_type == 'period_over_period':
            # 环比分析：解析current_period和previous_period
            current_period = time_range_info.get('current_period')
            if current_period and isinstance(current_period, dict):
                parsed['current_period'] = self._parse_period_dict(current_period)
            
            previous_period = time_range_info.get('previous_period')
            if previous_period and isinstance(previous_period, dict):
                parsed['previous_period'] = self._parse_period_dict(previous_period)
                
        elif analysis_type == 'year_over_year':
            # 同比分析：解析current_period和same_period_last_year
            current_period = time_range_info.get('current_period')
            if current_period and isinstance(current_period, dict):
                parsed['current_period'] = self._parse_period_dict(current_period)
            
            same_period_last_year = time_range_info.get('same_period_last_year')
            if same_period_last_year and isinstance(same_period_last_year, dict):
                parsed['same_period_last_year'] = self._parse_period_dict(same_period_last_year)
                
        elif analysis_type == 'base_period_index':
            # 定基比分析：解析base_period和target_periods
            base_period = time_range_info.get('base_period')
            if base_period and isinstance(base_period, dict):
                parsed['base_period'] = self._parse_period_dict(base_period)
            
            target_periods = time_range_info.get('target_periods')
            if target_periods and isinstance(target_periods, list):
                parsed['target_periods'] = [
                    self._parse_period_dict(p) for p in target_periods 
                    if isinstance(p, dict)
                ]
                
        elif analysis_type == 'periodicity':
            # 周期性分析：解析min_data_points
            min_data_points = time_range_info.get('min_data_points')
            if min_data_points is not None:
                try:
                    parsed['min_data_points'] = int(min_data_points)
                except (ValueError, TypeError):
                    parsed['min_data_points'] = 8  # 默认最少8个数据点
        
        # 兼容旧字段名：target_period和comparison_period
        if 'target_period' in time_range_info and 'current_period' not in parsed:
            target_period = time_range_info.get('target_period')
            if target_period and isinstance(target_period, dict):
                parsed['current_period'] = self._parse_period_dict(target_period)
        
        if 'comparison_period' in time_range_info:
            comparison_period = time_range_info.get('comparison_period')
            if comparison_period and isinstance(comparison_period, dict):
                # 根据分析类型决定存储到哪个字段
                if analysis_type == 'period_over_period' and 'previous_period' not in parsed:
                    parsed['previous_period'] = self._parse_period_dict(comparison_period)
                elif analysis_type == 'year_over_year' and 'same_period_last_year' not in parsed:
                    parsed['same_period_last_year'] = self._parse_period_dict(comparison_period)
        
        return parsed
    
    def _parse_period_dict(self, period: Dict[str, Any]) -> Dict[str, int]:
        """解析周期字典，将值转换为整数
        
        Args:
            period: 周期字典，如 {"year": 2025, "month": 8}
            
        Returns:
            标准化后的周期字典，所有值为整数
        """
        parsed = {}
        valid_keys = ['year', 'month', 'day', 'week', 'quarter', 'hour']
        
        for key in valid_keys:
            if key in period:
                try:
                    parsed[key] = int(period[key])
                except (ValueError, TypeError):
                    logger.warning(f"无法将周期字段 {key}={period[key]} 转换为整数")
        
        return parsed
    
    def _generate_default_time_range_info(self, parameter_mapping: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """当time_range_info缺失时，根据其他参数生成默认值
        
        Args:
            parameter_mapping: 参数映射字典
            
        Returns:
            默认的time_range_info字典，如果无法生成则返回None
        """
        analysis_types = parameter_mapping.get('analysis_types')
        period_type = parameter_mapping.get('period_type')
        
        # 如果没有分析类型，无法生成默认值
        if not analysis_types:
            return None
        
        # 取第一个分析类型作为主要类型
        primary_analysis_type = analysis_types[0] if isinstance(analysis_types, list) else analysis_types
        
        default_info = {
            'analysis_type': primary_analysis_type,
            'period_type': period_type or 'month'  # 默认月度
        }
        
        # 注意：由于缺少具体时间信息，expanded_range无法自动生成
        # 这种情况下，后续的SQL生成将依赖normalized_query中的时间描述
        logger.info(f"time_range_info缺失，生成默认值: {default_info}")
        
        return default_info
    
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
        
        # 验证time_range_info（新增）
        time_range_info = parameters.get('time_range_info')
        if time_range_info is not None:
            validated['time_range_info'] = self._validate_time_range_info(
                time_range_info, 
                validated.get('analysis_types'),
                validated.get('period_type')
            )
        else:
            validated['time_range_info'] = None
        
        return validated
    
    def _validate_time_range_info(
        self, 
        time_range_info: Dict[str, Any],
        analysis_types: Optional[List[str]] = None,
        period_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """验证time_range_info字段的完整性和一致性
        
        Args:
            time_range_info: 时间范围信息字典
            analysis_types: 分析类型列表（用于一致性验证）
            period_type: 周期类型（用于一致性验证）
            
        Returns:
            验证后的time_range_info字典
            
        Raises:
            ValueError: 当验证失败时
        """
        if not isinstance(time_range_info, dict):
            raise ValueError("time_range_info必须是字典类型")
        
        validated = {}
        
        # 验证analysis_type
        analysis_type = time_range_info.get('analysis_type')
        valid_analysis_types = ['periodicity', 'period_over_period', 'year_over_year', 'base_period_index']
        if analysis_type:
            if analysis_type not in valid_analysis_types:
                logger.warning(f"无效的analysis_type: {analysis_type}，将被忽略")
            else:
                validated['analysis_type'] = analysis_type
                
                # 验证与analysis_types的一致性，不一致时自动修正
                if analysis_types and analysis_type not in analysis_types:
                    logger.warning(
                        f"time_range_info.analysis_type ({analysis_type}) "
                        f"与analysis_types ({analysis_types}) 不一致，自动修正为 {analysis_types[0]}"
                    )
                    validated['analysis_type'] = analysis_types[0]
        elif analysis_types:
            # 如果 time_range_info 中没有 analysis_type，使用外层的第一个
            validated['analysis_type'] = analysis_types[0]
        
        # 验证period_type
        info_period_type = time_range_info.get('period_type')
        valid_period_types = ['hour', 'day', 'week', 'month', 'quarter', 'year']
        if info_period_type:
            if info_period_type not in valid_period_types:
                logger.warning(f"无效的period_type: {info_period_type}，将被忽略")
            else:
                validated['period_type'] = info_period_type
                
                # 验证与外层period_type的一致性，不一致时自动修正
                if period_type and info_period_type != period_type:
                    logger.warning(
                        f"time_range_info.period_type ({info_period_type}) "
                        f"与外层period_type ({period_type}) 不一致，自动修正为 {period_type}"
                    )
                    validated['period_type'] = period_type
        elif period_type:
            # 如果 time_range_info 中没有 period_type，使用外层的
            validated['period_type'] = period_type
        
        # 验证expanded_range
        expanded_range = time_range_info.get('expanded_range')
        if expanded_range:
            validated['expanded_range'] = self._validate_expanded_range(expanded_range)
        
        # 根据分析类型验证特定字段
        analysis_type = validated.get('analysis_type')
        
        if analysis_type == 'period_over_period':
            # 环比分析：验证current_period和previous_period
            current_period = time_range_info.get('current_period')
            if current_period:
                validated['current_period'] = self._validate_period_fields(current_period, 'current_period')
            
            previous_period = time_range_info.get('previous_period')
            if previous_period:
                validated['previous_period'] = self._validate_period_fields(previous_period, 'previous_period')
                
        elif analysis_type == 'year_over_year':
            # 同比分析：验证current_period和same_period_last_year
            current_period = time_range_info.get('current_period')
            if current_period:
                validated['current_period'] = self._validate_period_fields(current_period, 'current_period')
            
            same_period_last_year = time_range_info.get('same_period_last_year')
            if same_period_last_year:
                validated['same_period_last_year'] = self._validate_period_fields(
                    same_period_last_year, 'same_period_last_year'
                )
                
        elif analysis_type == 'base_period_index':
            # 定基比分析：验证base_period和target_periods
            base_period = time_range_info.get('base_period')
            if base_period:
                validated['base_period'] = self._validate_period_fields(base_period, 'base_period')
            
            target_periods = time_range_info.get('target_periods')
            if target_periods and isinstance(target_periods, list):
                validated['target_periods'] = [
                    self._validate_period_fields(p, f'target_periods[{i}]')
                    for i, p in enumerate(target_periods)
                    if isinstance(p, dict)
                ]
                
        elif analysis_type == 'periodicity':
            # 周期性分析：验证min_data_points
            min_data_points = time_range_info.get('min_data_points')
            if min_data_points is not None:
                try:
                    min_points = int(min_data_points)
                    if min_points < 1:
                        min_points = 8
                    validated['min_data_points'] = min_points
                except (ValueError, TypeError):
                    validated['min_data_points'] = 8
        
        return validated
    
    def _validate_expanded_range(self, expanded_range: Dict[str, Any]) -> Dict[str, str]:
        """验证expanded_range字段格式
        
        Args:
            expanded_range: 扩展时间范围字典
            
        Returns:
            验证后的expanded_range字典
            
        Raises:
            ValueError: 当格式无效时
        """
        if not isinstance(expanded_range, dict):
            raise ValueError("expanded_range必须是字典类型")
        
        validated = {}
        
        # 验证start字段
        start = expanded_range.get('start')
        if start:
            start_str = str(start)
            # 简单验证日期格式（YYYY-MM-DD 或 YYYY-MM 或 YYYY）
            if not self._is_valid_date_format(start_str):
                logger.warning(f"expanded_range.start格式可能不正确: {start_str}")
            validated['start'] = start_str
        
        # 验证end字段
        end = expanded_range.get('end')
        if end:
            end_str = str(end)
            if not self._is_valid_date_format(end_str):
                logger.warning(f"expanded_range.end格式可能不正确: {end_str}")
            validated['end'] = end_str
        
        return validated
    
    def _is_valid_date_format(self, date_str: str) -> bool:
        """检查日期字符串格式是否有效
        
        支持的格式：
        - YYYY-MM-DD (如 2025-08-15)
        - YYYY-MM (如 2025-08)
        - YYYY (如 2025)
        
        Args:
            date_str: 日期字符串
            
        Returns:
            是否为有效格式
        """
        import re
        
        # YYYY-MM-DD
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            return True
        # YYYY-MM
        if re.match(r'^\d{4}-\d{2}$', date_str):
            return True
        # YYYY
        if re.match(r'^\d{4}$', date_str):
            return True
        
        return False
    
    def _validate_period_fields(self, period: Dict[str, Any], field_name: str) -> Dict[str, int]:
        """验证周期字段
        
        Args:
            period: 周期字典
            field_name: 字段名称（用于错误信息）
            
        Returns:
            验证后的周期字典
            
        Raises:
            ValueError: 当验证失败时
        """
        if not isinstance(period, dict):
            raise ValueError(f"{field_name}必须是字典类型")
        
        validated = {}
        valid_keys = ['year', 'month', 'day', 'week', 'quarter', 'hour']
        
        for key in valid_keys:
            if key in period:
                try:
                    value = int(period[key])
                    
                    # 范围验证
                    if key == 'year' and (value < 1900 or value > 2100):
                        logger.warning(f"{field_name}.{key}={value} 超出合理范围")
                    elif key == 'month' and (value < 1 or value > 12):
                        raise ValueError(f"{field_name}.{key}={value} 必须在1-12之间")
                    elif key == 'day' and (value < 1 or value > 31):
                        raise ValueError(f"{field_name}.{key}={value} 必须在1-31之间")
                    elif key == 'week' and (value < 1 or value > 53):
                        raise ValueError(f"{field_name}.{key}={value} 必须在1-53之间")
                    elif key == 'quarter' and (value < 1 or value > 4):
                        raise ValueError(f"{field_name}.{key}={value} 必须在1-4之间")
                    elif key == 'hour' and (value < 0 or value > 23):
                        raise ValueError(f"{field_name}.{key}={value} 必须在0-23之间")
                    
                    validated[key] = value
                    
                except (ValueError, TypeError) as e:
                    if "必须在" in str(e):
                        raise
                    logger.warning(f"无法将{field_name}.{key}={period[key]}转换为整数")
        
        return validated
