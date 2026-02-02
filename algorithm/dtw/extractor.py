"""
@Author      : Surface
@Date        : 2025/12/24 20:54 
@Description : DTW算法参数提取器
"""

import logging
from typing import Dict, List, Any, Optional
from algorithm.base.base_extractor import BaseAlgorithmExtractor
from algorithm.models import AlgorithmType, DatabaseColumn

logger = logging.getLogger(__name__)


class DTWExtractor(BaseAlgorithmExtractor):
    """DTW相似度分析参数提取器"""
    
    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.SIMILARITY
    
    @property
    def algorithm_name(self) -> str:
        return "dtw"
    
    async def build_extraction_prompt(
        self, 
        question: str, 
        database_schema: Optional[List[DatabaseColumn]] = None,
        window_id: str = "default",
        user_id: Optional[int] = None,
        schema_text: str = "",
        query_db_result: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """构建DTW算法参数提取提示词"""
        
        # 使用传入的候选表信息（由parameter_extractor统一获取）
        if not schema_text:
            schema_text = "（无可用数据库模式信息）"
        if query_db_result is None:
            query_db_result = {}
        
        system_prompt = f"""你是DTW(动态时间规整)相似度分析专家。根据用户问题和数据库信息,提取DTW算法所需的参数。

重要:DTW算法用于比较表格中两列数值序列的相似度。

数据格式说明,
表格必须包含两列数值列,
1. 序列1的数值列（必需）
2. 序列2的数值列（必需）

提取参数说明,
1. time_series1: 数值列1的列注释(必需),数据将从该列提取
2. time_series2: 数值列2的列注释(必需),数据将从该列提取
3. window_size (可选): Sakoe-Chiba带约束窗口大小(正整数或null)
4. distance_metric (可选): euclidean/manhattan/cosine(默认euclidean)
5. normalize (可选): true/false(默认true)
6. step_pattern (可选): symmetric1/symmetric2/asymmetric(默认symmetric2)

数据库可用列信息,
{schema_text}

严格输出规则,
1. 所有列注释必须是数据库中实际存在的列注释
2. time_series1和time_series2必须是数值型列(标记为[数值型]的列)
3. time_series1和time_series2不能是同一列
4. required_columns中必须包含time_series1和time_series2的列注释，一定与normalized_query的使用的名称相同，如"required_columns": ["日期", "销售额"],"normalized_query": "获取XX年xx月到xx年月期间的历史销售数据的日期、销售额，返回日期、销售额共2列数据"
5. normalized_query中必须写明返回的数据列注释（即time_series1+time_series2）,并且必须标明"返回XX、XX共2列数据"否则无法正确解析，如"获取日期、销售额，返回日期、销售额共2列数据"！！！

常见应用场景识别,
- "温度和湿度" → time_series1=温度, time_series2=湿度
- "实际值和预测值" → time_series1=实际值, time_series2=预测值
- "设备A和设备B" → time_series1=设备A, time_series2=设备B
- "销量和库存" → time_series1=销量, time_series2=库存

输出JSON格式(严格遵守),
{{
  "parameter_mapping": {{
    "time_series1": "数据库中的数值列注释1",
    "time_series2": "数据库中的数值列注释2",
    "window_size": 正整数或null,
    "distance_metric": "euclidean"或"manhattan"或"cosine"或null,
    "normalize": true或false或null,
    "step_pattern": "symmetric2"或"symmetric1"或"asymmetric"或null
  }},
  "required_columns": ["time_series1的值", "time_series2的值"],
  "normalized_query": "获取日期、销售额，返回日期、销售额共2列数据"
}}"""
        
        user_prompt = f"""用户问题: {question}

请严格按照系统提示的规则分析用户需求,输出符合DTW相似度分析要求的JSON参数。

关键要求,
1. 识别用户想要比较的两列数值(如温度vs湿度、实际vs预测)
2. 确保time_series1和time_series2是不同的数值列
3. 根据问题决定是否需要窗口约束和归一化
4. 所有列名必须是数据库中实际存在的列名
5. normalized_query必须包含"返回XX、XX共2列数据"的说明

输出JSON格式的参数提取结果。"""
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def parse_extraction_response(self, response: str) -> Dict[str, Any]:
        """解析DTW算法的LLM响应"""
        try:
            # 基础JSON解析
            result = self._parse_json_response(response)
            
            parameter_mapping = result.get('parameter_mapping', {})
            
            # 处理window_size参数
            if 'window_size' in parameter_mapping:
                window_size = parameter_mapping['window_size']
                if window_size in [None, 'null', '']:
                    parameter_mapping['window_size'] = None
                elif isinstance(window_size, str):
                    if window_size.isdigit():
                        parameter_mapping['window_size'] = int(window_size)
                    else:
                        parameter_mapping['window_size'] = None
            
            # 处理distance_metric参数
            if 'distance_metric' in parameter_mapping:
                metric = parameter_mapping['distance_metric']
                if metric in [None, 'null', '']:
                    parameter_mapping['distance_metric'] = 'euclidean'
                elif metric not in ['euclidean', 'manhattan', 'cosine']:
                    logger.warning(f"不支持的距离度量: {metric},使用默认值euclidean")
                    parameter_mapping['distance_metric'] = 'euclidean'
            else:
                parameter_mapping['distance_metric'] = 'euclidean'
            
            # 处理normalize参数
            if 'normalize' in parameter_mapping:
                normalize = parameter_mapping['normalize']
                if normalize in [None, 'null', '']:
                    parameter_mapping['normalize'] = True
                elif isinstance(normalize, str):
                    parameter_mapping['normalize'] = normalize.lower() == 'true'
            else:
                parameter_mapping['normalize'] = True
            
            # 处理step_pattern参数
            if 'step_pattern' in parameter_mapping:
                pattern = parameter_mapping['step_pattern']
                if pattern in [None, 'null', '']:
                    parameter_mapping['step_pattern'] = 'symmetric2'
                elif pattern not in ['symmetric1', 'symmetric2', 'asymmetric']:
                    logger.warning(f"不支持的步进模式: {pattern},使用默认值symmetric2")
                    parameter_mapping['step_pattern'] = 'symmetric2'
            else:
                parameter_mapping['step_pattern'] = 'symmetric2'
            
            result['parameter_mapping'] = parameter_mapping
            return result
            
        except Exception as e:
            logger.error(f"DTW参数解析失败: {str(e)}")
            raise ValueError(f"DTW参数解析失败: {str(e)}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证DTW算法参数"""
        validated = {}
        
        # 验证time_series1
        time_series1 = parameters.get('time_series1')
        if not time_series1:
            raise ValueError("DTW算法需要指定time_series1(数值列1)")  
        validated['time_series1'] = str(time_series1)

        # 验证time_series2
        time_series2 = parameters.get('time_series2')
        if not time_series2:
            raise ValueError("DTW算法需要指定time_series2(数值列2)")  
        validated['time_series2'] = str(time_series2)
        
        # 确保两个数值列不同
        if time_series1 == time_series2:
            raise ValueError("time_series1和time_series2不能是同一列")
        
        # 验证window_size
        window_size = parameters.get('window_size')
        if window_size is not None:
            if not isinstance(window_size, int) or window_size < 1:
                raise ValueError("window_size必须是正整数")
            validated['window_size'] = window_size
        else:
            validated['window_size'] = None
        
        # 验证distance_metric
        distance_metric = parameters.get('distance_metric', 'euclidean')
        if distance_metric not in ['euclidean', 'manhattan', 'cosine']:
            raise ValueError(f"不支持的distance_metric: {distance_metric}")
        validated['distance_metric'] = distance_metric
        
        # 验证normalize
        normalize = parameters.get('normalize', True)
        validated['normalize'] = bool(normalize)
        
        # 验证step_pattern
        step_pattern = parameters.get('step_pattern', 'symmetric2')
        if step_pattern not in ['symmetric1', 'symmetric2', 'asymmetric']:
            raise ValueError(f"不支持的step_pattern: {step_pattern}")
        validated['step_pattern'] = step_pattern
        
        return validated
    
    def get_last_query_db_result(self) -> Dict[str, Any]:
        """获取最后一次query_db的结果,用于后续的SQL生成"""
        return getattr(self, '_last_query_db_result', {})
