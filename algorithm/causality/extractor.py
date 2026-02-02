"""
@Author      : Causality Analysis Team
@Date        : 2025/01/15
@Description : 因果分析算法参数提取器
"""

import logging
from typing import Dict, List, Any, Optional
from algorithm.base.base_extractor import BaseAlgorithmExtractor
from algorithm.models import AlgorithmType, DatabaseColumn

logger = logging.getLogger(__name__)


class CausalityExtractor(BaseAlgorithmExtractor):
    """因果分析参数提取器"""

    @property
    def algorithm_type(self) -> AlgorithmType:
        """返回算法类型"""
        return AlgorithmType.CAUSALITY

    @property
    def algorithm_name(self) -> str:
        """返回算法名称"""
        return "causality"

    async def build_extraction_prompt(
            self,
            question: str,
            database_schema: Optional[List[DatabaseColumn]] = None,
            window_id: str = "default",
            user_id: Optional[int] = None,
            schema_text: str = "",
            query_db_result: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, str]]:
        """构建因果分析特定的参数提取提示词"""

        # 使用传入的候选表信息（由parameter_extractor统一获取）
        if not schema_text:
            schema_text = "（无可用数据库模式信息）"
        if query_db_result is None:
            query_db_result = {}

        system_prompt = f"""你是因果分析专家。根据用户问题和数据库信息,提取因果分析所需的参数。

重要:你必须严格按照以下规则输出JSON,确保参数名和列名完全匹配数据库中的实际列名。

因果分析要求:
1. dependent_variable: 必须指定一个因变量(结果变量),即我们想要分析其原因的变量,必须是数据库中实际存在的列注释
2. independent_variables: 自动从数据库中寻找所有可能影响因变量的数值型字段,数量不限
   - 你需要主动分析数据库schema,找出所有可能与因变量相关的数值型字段
   - 不要遗漏任何可能有用的字段，但是也不要创造数据库中不存在的列
   - 必须是数据库中实际存在的数值型列注释列表
3. normalized_query:用于从text-to-sql算法获取数据的自然语言

数据库可用列信息:
{schema_text}
        
严格输出规则:
1. dependent_variable的值必须是数据库中实际存在的列注释，即用户想要分析的结果变量
2. independent_variables的值必须是数据库中实际存在的数值型列注释列表
   - 主动分析并包含所有可能相关的数值型字段
   - 不要只选择用户明确提到的字段,要主动寻找其他潜在影响因素
   - 但是只使用“数据库可用列信息”中的内容，不要创造不存在的列
4. required_columns中一定写明列注释,一定与normalized_query的使用的名称相同
5. normalized_query中一定写明返回的数据列注释(即dependent_variable+independent_variables),并且标明返回几列数据
6. 优先选择有注释说明的列,这样更容易理解业务含义
7. 因变量通常是用户想要分析的目标变量(如销售额、客户流失率等)
8. 自变量要全面覆盖所有可能的影响因素,不要遗漏

输出JSON格式(严格遵守):
{{
  "parameter_mapping": {{
    "dependent_variable": "销售额",
    "independent_variables": ["广告投入", "促销活动", "季节", "价格", "库存", "客户数量", "访问量"]
  }},
  "required_columns": ["销售额", "广告投入", "促销活动", "季节", "价格", "库存", "客户数量", "访问量"],
  "normalized_query": "获取销售数据的销售额、广告投入、促销活动、季节、价格、库存、客户数量、访问量共8列,返回销售额、广告投入、促销活动、季节、价格、库存、客户数量、访问量共8列数据"
}}

格式示例说明:
1. required_columns:必须包含所有列(因变量+自变量),顺序与parameter_mapping一致
    必须与normalized_query中使用的列名完全一致
    示例:["销售额", "广告投入", "促销活动", "季节", "价格", "库存", "客户数量", "访问量"]
   
3. normalized_query格式:必须明确说明返回的列和列数
    格式:"获取[时间范围/条件]的[列1]、[列2]、[列3]...共N列数据,返回[列1]、[列2]、[列3]...共N列数据"
    必须写明所有返回的列名(与required_columns一致)
    必须标明返回的总列数(因变量+自变量的总数)
   
4. 列名一致性:parameter_mapping、required_columns、normalized_query中的列名必须完全一致
    都使用列注释(中文名称),不使用列的英文名称
    三个字段中的列名顺序必须一致

5. 列数计算:总列数 = 1个因变量 + N个自变量  示例:1个因变量 + 7个自变量 = 共8列数据
"""

        user_prompt = f"""用户问题: {question}
        
请严格按照系统提示的规则分析用户需求,输出符合因果分析算法要求的JSON参数。

关键要求:
1. 从数据库schema中识别因变量(用户想要分析的目标变量)
2. 主动从数据库schema中寻找所有可能影响因变量的数值型字段作为自变量
   - 不要只选择用户明确提到的字段
   - 要全面分析“数据库可用列信息”中所有可能相关的数值型字段
   - 但是不要创造“数据库可用列信息”中不存在的列
3. 所有列注释必须与数据库中的实际列注释完全匹配
4. 如果用户指定了某些列，请只使用这些列，不要使用其他列了

输出JSON格式的参数提取结果。"""

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    def parse_extraction_response(self, response: str) -> Dict[str, Any]:
        """解析因果分析特定的LLM响应"""
        try:
            # 基础JSON解析
            result = self._parse_json_response(response)

            # 因果分析特定验证和标准化
            parameter_mapping = result.get('parameter_mapping', {})

            # 确保independent_variables是列表
            if 'independent_variables' in parameter_mapping:
                if isinstance(parameter_mapping['independent_variables'], str):
                    parameter_mapping['independent_variables'] = [parameter_mapping['independent_variables']]

            result['parameter_mapping'] = parameter_mapping
            return result

        except Exception as e:
            logger.error(f"因果分析参数解析失败: {str(e)}")
            raise ValueError(f"因果分析参数解析失败: {str(e)}")

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证因果分析参数"""
        validated = {}

        # 验证因变量
        dependent_variable = parameters.get('dependent_variable')
        if not dependent_variable:
            raise ValueError("因果分析需要指定因变量(dependent_variable)")
        validated['dependent_variable'] = str(dependent_variable)

        # 验证自变量
        independent_variables = parameters.get('independent_variables', [])
        if not independent_variables:
            raise ValueError("因果分析至少需要1个自变量(independent_variables)")
        if not isinstance(independent_variables, list):
            independent_variables = [independent_variables]
        
        # 移除自变量数量限制,允许LLM自由选择
        logger.info(f"因果分析包含 {len(independent_variables)} 个自变量")
        
        validated['independent_variables'] = independent_variables

        return validated

    def get_last_query_db_result(self) -> Dict[str, Any]:
        """获取最后一次query_db的结果,用于后续的SQL生成"""
        return getattr(self, '_last_query_db_result', {})
