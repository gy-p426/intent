"""
算法识别专用LLM模块
专门用于算法类型识别的增强LLM模块
"""
import json
import logging
from typing import List, Dict, Optional
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


class AlgorithmLLMModule:
    """
    算法识别专用LLM模块
    专门优化算法类型识别的提示词和响应解析
    """
    
    def __init__(self, llm_client: LLMClient):
        """
        初始化算法LLM模块
        
        Args:
            llm_client: LLM API客户端
        """
        self.client = llm_client
        logger.info("AlgorithmLLMModule initialized")
    
    async def identify_algorithm_type(
        self, 
        question: str, 
        candidates: List[Dict[str, any]]
    ) -> Optional[str]:
        """
        识别算法类型
        
        Args:
            question: 用户问题
            candidates: 候选算法类型列表，每个候选包含intent、text、score字段
        
        Returns:
            Optional[str]: 识别出的算法类型名称，如果无法识别则返回None
        
        Raises:
            Exception: LLM调用或响应解析失败
        """
        try:
            logger.debug(f"开始算法类型识别，问题: {question}, 候选数量: {len(candidates)}")
            
            # 构建算法识别专用提示词
            messages = self._build_algorithm_prompt(question, candidates)
            
            # 调用LLM API
            response = await self.client.chat_completion(messages)
            
            # 解析响应
            algorithm_type = self._parse_algorithm_response(response)
            
            if algorithm_type:
                logger.info(f"算法类型识别完成: {algorithm_type}")
            else:
                logger.warning("未能识别出有效的算法类型")
            
            return algorithm_type
            
        except Exception as e:
            logger.error(f"算法类型识别失败: {str(e)}", exc_info=True)
            raise
    
    def _build_algorithm_prompt(
        self, 
        question: str, 
        candidates: List[Dict[str, any]]
    ) -> List[Dict[str, str]]:
        """
        构建算法识别专用提示词
        
        Args:
            question: 用户问题
            candidates: 候选算法类型列表
        
        Returns:
            List[Dict[str, str]]: 消息列表，包含system和user角色的消息
        """
        # 算法识别专用系统提示词
        system_prompt = """你是一个智能算法识别专家。根据用户问题和候选算法类型列表，判断用户需求对应哪一个算法类型。

算法类型说明：
- cluster: 聚类分析，将数据按相似性分组，关键词：分群、聚类、分组、归类、K-means
- classify: 分类预测，预测数据的类别标签，关键词：分类、预测、判断、识别、分级
- predict: 预测分析，预测未来趋势或数值，关键词：预测、预估、预报、预见
- anomaly: 异常检测，发现数据中的异常点，关键词：异常、离群、检测、发现
- associate: 关联分析，发现数据项之间的关联规则，关键词：关联、关系、规则、购物篮
- compare: 对比分析，比较不同组别或时期的差异，关键词：对比、比较、差异、A/B测试
- similarity: 相似度分析，计算实体间相似程度，关键词：相似、相似度、匹配、相近
- trend: 趋势分析，分析时间序列的趋势变化，关键词：趋势、变化、走势、季节性
- profile: 用户画像，构建实体特征画像，关键词：画像、档案、特征、360度视图
- causality: 因果分析，分析变量间因果关系，关键词：原因、因果、根因、影响因素
- alert: 预警系统，基于阈值的监控预警，关键词：预警、报警、监控、阈值
- recommend: 推荐系统，提供个性化推荐，关键词：推荐、建议、优化、个性化

识别规则：
1. 仔细分析用户问题的核心需求和关键动词
2. 从候选算法类型中选择最匹配的一个
3. 优先考虑问题中的动作词汇和业务场景
4. 只能选择一个算法类型
5. 直接输出算法类型名称，不需要JSON格式

识别示例：
问题："将用户按信用等级分类" → 输出：classify
问题："将客户按购买偏好分组" → 输出：cluster
问题："预测下个月销售额" → 输出：predict
问题："检测交易中的异常" → 输出：anomaly
问题："分析商品关联关系" → 输出：associate
问题："对比两个季度业绩" → 输出：compare
"""
        
        # 格式化候选算法类型列表
        candidates_text = self._format_algorithm_candidates(candidates)
        
        # 用户提示词
        user_prompt = f"""用户问题: {question}

候选算法类型:
{candidates_text}

请分析用户问题的核心需求，选择最匹配的算法类型名称。直接输出算法类型名称即可。"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        logger.debug(f"构建算法识别提示词: system={len(system_prompt)} chars, user={len(user_prompt)} chars")
        
        return messages
    
    def _format_algorithm_candidates(self, candidates: List[Dict[str, any]]) -> str:
        """
        格式化候选算法类型列表为文本
        
        Args:
            candidates: 候选算法类型列表
        
        Returns:
            str: 格式化后的文本
        """
        if not candidates:
            return "（无候选算法类型）"
        
        # 按算法类型分组候选示例
        algorithm_groups = {}
        for candidate in candidates:
            algorithm_type = candidate.get('intent', 'unknown')
            text = candidate.get('text', '')
            score = candidate.get('score', 0.0)
            
            if algorithm_type not in algorithm_groups:
                algorithm_groups[algorithm_type] = []
            
            algorithm_groups[algorithm_type].append({
                'text': text,
                'score': score
            })
        
        # 格式化输出
        lines = []
        for idx, (algorithm_type, examples) in enumerate(algorithm_groups.items(), 1):
            # 取每个算法类型的前3个示例
            top_examples = sorted(examples, key=lambda x: x['score'], reverse=True)[:3]
            example_texts = [f"  - {ex['text']} (相似度: {ex['score']:.3f})" 
                           for ex in top_examples]
            
            lines.append(f"{idx}. 算法类型: {algorithm_type}")
            lines.extend(example_texts)
        
        return "\n".join(lines)
    
    def _parse_algorithm_response(self, response: str) -> Optional[str]:
        """
        解析算法识别响应，提取算法类型名称
        
        Args:
            response: 大模型返回的响应文本
        
        Returns:
            Optional[str]: 算法类型名称，如果解析失败则返回None
        """
        try:
            logger.debug(f"解析算法识别响应: {response[:200]}...")
            
            # 清理响应文本
            response = response.strip()
            
            # 定义有效的算法类型
            valid_algorithms = {
                'cluster', 'classify', 'predict', 'anomaly', 'associate', 
                'compare', 'similarity', 'trend', 'profile', 'causality', 
                'alert', 'recommend'
            }
            
            # 尝试直接匹配算法类型名称
            response_lower = response.lower()
            for algorithm in valid_algorithms:
                if algorithm in response_lower:
                    logger.debug(f"成功识别算法类型: {algorithm}")
                    return algorithm
            
            # 尝试从JSON格式中提取
            if '[' in response and ']' in response:
                try:
                    start_idx = response.find('[')
                    end_idx = response.rfind(']')
                    json_str = response[start_idx:end_idx + 1]
                    algorithms = json.loads(json_str)
                    
                    if algorithms and len(algorithms) > 0:
                        algorithm = str(algorithms[0]).strip().lower()
                        if algorithm in valid_algorithms:
                            logger.debug(f"从JSON中识别算法类型: {algorithm}")
                            return algorithm
                except json.JSONDecodeError:
                    pass
            
            # 尝试从响应中提取第一个有效的算法类型词汇
            words = response.lower().split()
            for word in words:
                clean_word = word.strip('.,!?;:"()[]{}')
                if clean_word in valid_algorithms:
                    logger.debug(f"从词汇中识别算法类型: {clean_word}")
                    return clean_word
            
            logger.warning(f"无法从响应中识别有效的算法类型: {response}")
            return None
            
        except Exception as e:
            logger.error(f"算法响应解析失败: {str(e)}, 响应内容: {response}")
            return None