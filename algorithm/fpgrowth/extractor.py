"""
@Author      : Surface
@Date        : 2025/12/24
@Description : FP-Growth关联分析参数提取器
"""

import logging
from typing import Dict, List, Any, Optional
from algorithm.base.base_extractor import BaseAlgorithmExtractor
from algorithm.models import AlgorithmType, DatabaseColumn

logger = logging.getLogger(__name__)


class FPGrowthExtractor(BaseAlgorithmExtractor):
    """FP-Growth关联分析参数提取器"""
    
    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.ASSOCIATION
    
    @property
    def algorithm_name(self) -> str:
        return "fpgrowth"
    
    async def build_extraction_prompt(
        self, 
        question: str, 
        database_schema: Optional[List[DatabaseColumn]] = None,
        window_id: str = "default"
    ) -> List[Dict[str, str]]:
        """构建FP-Growth算法参数提取提示词"""
        
        # 从NL2SQL服务获取候选表信息和关键词
        schema_text, query_db_result = await self._get_candidate_tables_from_nl2sql(question, window_id)
        
        # 保存查询结果供后续使用
        self._last_query_db_result = query_db_result
        
        system_prompt = f"""你是FP-Growth频繁模式增长关联分析专家。根据用户问题和数据库信息,提取FP-Growth算法所需的参数。

重要:FP-Growth算法用于发现数据中的频繁模式和关联规则,适用于各种分组-元素关联分析场景。

数据格式说明:
数据通常有两种格式:
1. 宽格式(每行一个分组):group_id, element1, element2, element3, ...
2. 长格式(每行一个分组-元素对):group_id, element(推荐)

提取参数说明:
1. group_id_column (必需): 分组ID列名,用于标识每个分组
2. element_column (必需): 元素列名,表示分组中包含的元素
3. min_support (可选): 最小支持度(0-1之间,默认0.01)
4. min_confidence (可选): 最小置信度(0-1之间,默认0.5)
5. max_length (可选): 频繁元素集最大长度(正整数或null)
6. metric (可选): 规则评估指标(confidence/lift/leverage/conviction,默认confidence)
7. min_lift (可选): 最小提升度(仅metric为lift时使用,默认1.0)

数据库可用列信息:
{schema_text}

严格输出规则:
1. group_id_column和element_column必须是数据库中实际存在的列名
2. group_id_column是标识分组的列(订单、会话、用户、患者等)
3. element_column是分组中包含的元素列(商品、页面、症状、课程等)
4. 支持度和置信度必须在0-1之间
5. 列名必须与数据库schema中的column_name完全一致

常见应用场景识别关键词:

输出JSON格式(严格遵守):
{{
  "parameter_mapping": {{
    "group_id_column": "数据库中的分组ID列名",
    "element_column": "数据库中的元素列名",
    "min_support": 0.01或其他值或null,
    "min_confidence": 0.5或其他值或null,
    "max_length": 正整数或null,
    "metric": "confidence"或"lift"或其他或null,
    "min_lift": 1.0或其他值或null
  }},
  "required_columns": ["分组ID列名", "元素列名"],
  "normalized_query": "使用FP-Growth算法分析[具体场景]中的关联规则"
}}"""
        
        user_prompt = f"""用户问题: {question}

请严格按照系统提示的规则分析用户需求,输出符合FP-Growth关联分析要求的JSON参数。

关键要求:
1. 识别哪一列代表分组ID(订单、会话、用户、患者等标识)
2. 识别哪一列代表元素(商品、页面、课程、症状等)
3. 根据问题判断是否需要调整支持度和置信度阈值
4. 如果问题提到"强关联"或"高置信度",可适当提高min_confidence(如0.7-0.8)
5. 如果问题提到"常见"或"频繁",可适当降低min_support(如0.005-0.01)
6. 如果问题提到"罕见"或"特殊",可进一步降低min_support(如0.001-0.005)
7. 所有列名必须是数据库中实际存在的列

输出JSON格式的参数提取结果。"""
        
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    
    def parse_extraction_response(self, response: str) -> Dict[str, Any]:
        """解析FP-Growth算法的LLM响应"""
        try:
            # 基础JSON解析
            result = self._parse_json_response(response)
            
            parameter_mapping = result.get('parameter_mapping', {})
            
            # 处理min_support参数
            if 'min_support' in parameter_mapping:
                min_support = parameter_mapping['min_support']
                if min_support in [None, 'null', '']:
                    parameter_mapping['min_support'] = 0.01
                else:
                    try:
                        min_support = float(min_support)
                        if not (0 < min_support <= 1):
                            logger.warning(f"min_support超出范围({min_support}),使用默认值0.01")
                            min_support = 0.01
                        parameter_mapping['min_support'] = min_support
                    except (ValueError, TypeError):
                        parameter_mapping['min_support'] = 0.01
            else:
                parameter_mapping['min_support'] = 0.01
            
            # 处理min_confidence参数
            if 'min_confidence' in parameter_mapping:
                min_confidence = parameter_mapping['min_confidence']
                if min_confidence in [None, 'null', '']:
                    parameter_mapping['min_confidence'] = 0.5
                else:
                    try:
                        min_confidence = float(min_confidence)
                        if not (0 < min_confidence <= 1):
                            logger.warning(f"min_confidence超出范围({min_confidence}),使用默认值0.5")
                            min_confidence = 0.5
                        parameter_mapping['min_confidence'] = min_confidence
                    except (ValueError, TypeError):
                        parameter_mapping['min_confidence'] = 0.5
            else:
                parameter_mapping['min_confidence'] = 0.5
            
            # 处理max_length参数
            if 'max_length' in parameter_mapping:
                max_length = parameter_mapping['max_length']
                if max_length in [None, 'null', '']:
                    parameter_mapping['max_length'] = None
                elif isinstance(max_length, str):
                    if max_length.isdigit():
                        parameter_mapping['max_length'] = int(max_length)
                    else:
                        parameter_mapping['max_length'] = None
            else:
                parameter_mapping['max_length'] = None
            
            # 处理metric参数
            if 'metric' in parameter_mapping:
                metric = parameter_mapping['metric']
                if metric in [None, 'null', '']:
                    parameter_mapping['metric'] = 'confidence'
                elif metric not in ['confidence', 'lift', 'leverage', 'conviction']:
                    logger.warning(f"不支持的metric: {metric},使用默认值confidence")
                    parameter_mapping['metric'] = 'confidence'
            else:
                parameter_mapping['metric'] = 'confidence'
            
            # 处理min_lift参数
            if 'min_lift' in parameter_mapping:
                min_lift = parameter_mapping['min_lift']
                if min_lift in [None, 'null', '']:
                    parameter_mapping['min_lift'] = 1.0
                else:
                    try:
                        min_lift = float(min_lift)
                        if min_lift < 0:
                            logger.warning(f"min_lift为负数({min_lift}),使用默认值1.0")
                            min_lift = 1.0
                        parameter_mapping['min_lift'] = min_lift
                    except (ValueError, TypeError):
                        parameter_mapping['min_lift'] = 1.0
            else:
                parameter_mapping['min_lift'] = 1.0
            
            result['parameter_mapping'] = parameter_mapping
            return result
            
        except Exception as e:
            logger.error(f"FP-Growth参数解析失败: {str(e)}")
            raise ValueError(f"FP-Growth参数解析失败: {str(e)}")
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证FP-Growth算法参数"""
        validated = {}
        
        # 验证group_id_column
        group_id_column = parameters.get('group_id_column')
        if not group_id_column:
            raise ValueError("FP-Growth算法需要指定group_id_column(分组ID列)")
        validated['group_id_column'] = str(group_id_column)
        
        # 验证element_column
        element_column = parameters.get('element_column')
        if not element_column:
            raise ValueError("FP-Growth算法需要指定element_column(元素列)")
        validated['element_column'] = str(element_column)
        
        # 确保两列不同
        if group_id_column == element_column:
            raise ValueError("group_id_column和element_column不能是同一列")
        
        # 验证min_support
        min_support = parameters.get('min_support', 0.01)
        if not isinstance(min_support, (int, float)) or not (0 < min_support <= 1):
            raise ValueError("min_support必须在0到1之间")
        validated['min_support'] = float(min_support)
        
        # 验证min_confidence
        min_confidence = parameters.get('min_confidence', 0.5)
        if not isinstance(min_confidence, (int, float)) or not (0 < min_confidence <= 1):
            raise ValueError("min_confidence必须在0到1之间")
        validated['min_confidence'] = float(min_confidence)
        
        # 验证max_length
        max_length = parameters.get('max_length')
        if max_length is not None:
            if not isinstance(max_length, int) or max_length < 1:
                raise ValueError("max_length必须是正整数")
            validated['max_length'] = max_length
        else:
            validated['max_length'] = None
        
        # 验证metric
        metric = parameters.get('metric', 'confidence')
        if metric not in ['confidence', 'lift', 'leverage', 'conviction']:
            raise ValueError(f"不支持的metric: {metric}")
        validated['metric'] = metric
        
        # 验证min_lift
        min_lift = parameters.get('min_lift', 1.0)
        if not isinstance(min_lift, (int, float)) or min_lift < 0:
            raise ValueError("min_lift必须是非负数")
        validated['min_lift'] = float(min_lift)
        
        return validated
    
    def get_last_query_db_result(self) -> Dict[str, Any]:
        """获取最后一次query_db的结果,用于后续的SQL生成"""
        return getattr(self, '_last_query_db_result', {})
