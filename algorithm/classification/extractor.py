"""
Classification Algorithm Parameter Extractor
分类算法参数提取器
"""

import logging
from typing import Dict, List, Any, Optional
from algorithm.base.base_extractor import BaseAlgorithmExtractor
from algorithm.models import AlgorithmType, DatabaseColumn

logger = logging.getLogger(__name__)


class ClassificationExtractor(BaseAlgorithmExtractor):
    """分类算法参数提取器"""

    @property
    def algorithm_type(self) -> AlgorithmType:
        return AlgorithmType.CLASSIFY

    @property
    def algorithm_name(self) -> str:
        return "classification"

    async def build_extraction_prompt(
            self,
            question: str,
            database_schema: Optional[List[DatabaseColumn]] = None,
            window_id: str = "default"
    ) -> List[Dict[str, str]]:
        """构建分类算法特定的参数提取提示词"""

        # 获取候选表信息（利用基类方法）
        schema_text, query_db_result = await self._get_candidate_tables_from_nl2sql(question, window_id)
        self._last_query_db_result = query_db_result

        system_prompt = f"""你是分类分析算法专家。请根据用户问题和数据库信息，提取分类预测所需的参数。

分类分析核心逻辑：
我们需要利用历史数据（包含特征和目标值）来训练模型，或对新数据进行预测。

请提取以下参数（输出JSON格式）：
1. id_column: 数据行的唯一标识列（如"用户ID"、"id"），必选。
2. target_column: 想要预测的目标列（标签列），必选。例如：预测"客户流失"、"信用等级"。
3. feature_columns: 用于预测的特征列列表，必选。例如：["年龄", "收入", "消费频次"]。
4. algorithm: (可选) 用户指定的算法，仅限 "xgboost" 或 "tabnet"。如果未指定输出 null。
5. normalized_query: 用于查询数据的自然语言描述，必须明确包含上述所有列。

数据库可用列信息：
{schema_text}

严格输出规则：
1. 所有列名必须完全匹配数据库中的实际列注释（中文）。
2. target_column 必须是分类目标（如状态、类别、等级）。
3. normalized_query中一定写明返回的数据列注释（即id_column+target_column+feature_columns），并且标名返回哪几列数据，否则无法正确解析，如"获取客户ID、流失状态、年龄、月使用量，返回客户ID、流失状态、年龄、月使用量共4列数据"！！！
4. 如果用户未指定具体特征，请根据业务逻辑从可用列中智能选择合理的特征列。

输出JSON示例：
{{
  "parameter_mapping": {{
    "id_column": "客户ID",
    "target_column": "流失状态",
    "feature_columns": ["年龄", "月使用量"],
    "algorithm": "xgboost"
  }},
  "normalized_query": "获取客户数据的客户ID、流失状态、年龄、月使用量，返回客户ID、流失状态、年龄、月使用量共4列数据"
}}"""

        user_prompt = f"""用户问题: {question}

请分析需求，提取分类算法参数。"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    def parse_extraction_response(self, response: str) -> Dict[str, Any]:
        """解析分类算法的LLM响应"""
        try:
            result = self._parse_json_response(response)
            param_mapping = result.get('parameter_mapping', {})

            # 1. 规范化 feature_columns
            if 'feature_columns' in param_mapping:
                if isinstance(param_mapping['feature_columns'], str):
                    # 如果LLM只返回了一个字符串，转为列表
                    param_mapping['feature_columns'] = [param_mapping['feature_columns']]

            # 2. 规范化 algorithm
            algo = param_mapping.get('algorithm')
            if isinstance(algo, str):
                algo = algo.lower()
                if algo not in ['xgboost', 'tabnet']:
                    # 如果不是支持的算法，设为None，让后端自动选择
                    algo = None
                param_mapping['algorithm'] = algo
            else:
                param_mapping['algorithm'] = None

            result['parameter_mapping'] = param_mapping
            return result

        except Exception as e:
            logger.error(f"分类算法参数解析失败: {str(e)}")
            raise ValueError(f"参数解析失败: {str(e)}")

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证提取的参数"""
        validated = {}

        # 验证必填项
        if not parameters.get('id_column'):
            raise ValueError("分类分析必须指定ID列 (id_column)")
        validated['id_column'] = str(parameters['id_column'])

        if not parameters.get('target_column'):
            raise ValueError("分类分析必须指定目标列 (target_column)")
        validated['target_column'] = str(parameters['target_column'])

        feats = parameters.get('feature_columns', [])
        if not feats or not isinstance(feats, list) or len(feats) < 1:
            raise ValueError("分类分析至少需要一个特征列 (feature_columns)")
        validated['feature_columns'] = feats

        # 可选项
        validated['algorithm'] = parameters.get('algorithm')

        return validated