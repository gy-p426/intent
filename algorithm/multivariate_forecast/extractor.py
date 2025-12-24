"""
Multivariate Forecast Algorithm Parameter Extractor

多变量预测算法参数提取器
"""

import logging
from typing import Dict, List, Any, Optional
from algorithm.base.base_extractor import BaseAlgorithmExtractor
from algorithm.models import AlgorithmType, DatabaseColumn

logger = logging.getLogger(__name__)


class MultivariateForecastExtractor(BaseAlgorithmExtractor):
    """多变量预测算法参数提取器"""
    
    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.PREDICT
    
    @property
    def algorithm_name(self) -> str:
        return "multivariate_forecast"
    
    async def build_extraction_prompt(
        self, 
        question: str, 
        database_schema: Optional[List[DatabaseColumn]] = None,
        window_id: str = "default"
    ) -> List[Dict[str, str]]:
        """构建多变量预测特定的参数提取提示词"""
        
        # 从NL2SQL服务获取候选表信息和关键词
        schema_text, query_db_result = await self._get_candidate_tables_from_nl2sql(question, window_id)
        
        # 保存查询结果供后续使用
        self._last_query_db_result = query_db_result
        
        system_prompt = f"""你是多变量时间序列预测专家。根据用户问题和数据库信息，提取多变量预测所需的参数。

重要：你必须严格按照以下规则输出JSON，确保参数名和列名完全匹配数据库中的实际列名。

多变量预测要求：
1. timestamp_column: 必须指定一个时间列，用于标识时间序列的时间点
2. target_column: 必须指定一个数值列，作为预测的目标变量
3. feature_columns: 特征列列表，用于预测的输入特征（可选，不指定则自动选择）
4. forecast_horizon: 预测步数，即预测未来多少个时间点
5. algorithm: 预测算法，"lightgbm"、"xgboost"、"random_forest"或"linear_regression"
6. model_name: 可选，模型名称，用于保存和复用

数据库可用列信息：
{schema_text}

预测步数判断规则：
- "未来14天" → forecast_horizon: 14
- "下周" → forecast_horizon: 7
- "未来30天" → forecast_horizon: 30
- 如果用户没有明确指定，默认使用14

算法选择建议：
- 数据量大、特征多时推荐 lightgbm 或 xgboost
- 需要可解释性时推荐 random_forest
- 数据量小或需要快速训练时推荐 linear_regression
- 如果用户没有指定，默认使用 lightgbm

严格输出规则：
1. timestamp_column的值必须是数据库中实际存在的时间类型列名
2. target_column的值必须是数据库中实际存在的数值型列名
3. feature_columns的值必须是数据库中实际存在的数值型列名列表
4. 不要创造不存在的列名
5. normalized_query中一定写明返回的数据列

输出JSON格式（严格遵守）：
{{
  "parameter_mapping": {{
    "timestamp_column": "时间列名",
    "target_column": "目标列名",
    "feature_columns": ["特征列1", "特征列2", ...],
    "forecast_horizon": 预测步数,
    "algorithm": "lightgbm/xgboost/random_forest/linear_regression",
    "model_name": "模型名称或null"
  }},
  "required_columns": ["时间列名", "目标列名", "特征列1", "特征列2", ...],
  "normalized_query": "获取XXX的历史数据用于多变量预测"
}}"""
        
        user_prompt = f"""用户问题: {question}

请严格按照系统提示的规则分析用户需求，输出符合多变量预测要求的JSON参数。

关键要求：
1. 从数据库schema中选择合适的时间列作为timestamp_column
2. 从数据库schema中选择合适的目标列作为target_column
3. 从数据库schema中选择合适的特征列作为feature_columns
4. 根据用户问题判断预测步数forecast_horizon
5. 根据用户需求选择合适的算法
6. normalized_query一定要写明返回哪些列

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
        """解析多变量预测特定的LLM响应"""
        try:
            # 基础JSON解析
            result = self._parse_json_response(response)
            
            # 多变量预测特定验证和标准化
            parameter_mapping = result.get('parameter_mapping', {})
            
            # 确保feature_columns是列表
            feature_columns = parameter_mapping.get('feature_columns')
            if feature_columns is not None:
                if isinstance(feature_columns, str):
                    parameter_mapping['feature_columns'] = [feature_columns]
                elif not isinstance(feature_columns, list):
                    parameter_mapping['feature_columns'] = None
            
            # 处理forecast_horizon
            forecast_horizon = parameter_mapping.get('forecast_horizon', 14)
            if isinstance(forecast_horizon, str):
                if forecast_horizon.isdigit():
                    forecast_horizon = int(forecast_horizon)
                else:
                    forecast_horizon = 14
            elif isinstance(forecast_horizon, float):
                forecast_horizon = int(forecast_horizon)
            if forecast_horizon < 1:
                forecast_horizon = 14
            if forecast_horizon > 365:
                forecast_horizon = 365
            parameter_mapping['forecast_horizon'] = forecast_horizon
            
            # 处理algorithm
            algorithm = parameter_mapping.get('algorithm', 'lightgbm')
            valid_algorithms = ['lightgbm', 'xgboost', 'random_forest', 'linear_regression']
            if algorithm not in valid_algorithms:
                algorithm = 'lightgbm'
            parameter_mapping['algorithm'] = algorithm
            
            # 处理model_name
            model_name = parameter_mapping.get('model_name')
            if model_name in [None, 'null', '', 'None']:
                parameter_mapping['model_name'] = None
            
            result['parameter_mapping'] = parameter_mapping
            return result
            
        except Exception as e:
            logger.error(f"多变量预测参数解析失败: {str(e)}")
            raise ValueError(f"多变量预测参数解析失败: {str(e)}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证多变量预测参数"""
        validated = {}
        
        # 验证时间列
        timestamp_column = parameters.get('timestamp_column')
        if not timestamp_column:
            raise ValueError("多变量预测需要指定时间列")
        validated['timestamp_column'] = str(timestamp_column)
        
        # 验证目标列
        target_column = parameters.get('target_column')
        if not target_column:
            raise ValueError("多变量预测需要指定目标列")
        validated['target_column'] = str(target_column)
        
        # 验证特征列
        feature_columns = parameters.get('feature_columns')
        if feature_columns is not None:
            if not isinstance(feature_columns, list):
                feature_columns = [feature_columns]
            validated['feature_columns'] = feature_columns
        else:
            validated['feature_columns'] = None
        
        # 验证预测步数
        forecast_horizon = parameters.get('forecast_horizon', 14)
        if not isinstance(forecast_horizon, int) or forecast_horizon < 1:
            forecast_horizon = 14
        if forecast_horizon > 365:
            forecast_horizon = 365
        validated['forecast_horizon'] = forecast_horizon
        
        # 验证算法
        algorithm = parameters.get('algorithm', 'lightgbm')
        valid_algorithms = ['lightgbm', 'xgboost', 'random_forest', 'linear_regression']
        if algorithm not in valid_algorithms:
            algorithm = 'lightgbm'
        validated['algorithm'] = algorithm
        
        # 验证模型名称
        validated['model_name'] = parameters.get('model_name')
        
        return validated
