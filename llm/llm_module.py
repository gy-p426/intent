"""
LLM模块
封装提示词构建和响应解析，实现意图分类逻辑
"""
import json
import logging
from typing import List, Dict
from .llm_client import LLMClient

logger = logging.getLogger(__name__)


class LLMModule:
    """
    LLM模块
    负责构建提示词、调用大模型API、解析响应
    """
    
    def __init__(self, llm_client: LLMClient):
        """
        初始化LLM模块
        
        Args:
            llm_client: LLM API客户端
        """
        self.client = llm_client
        logger.info("LLMModule initialized")
    
    async def classify(
        self, 
        question: str, 
        candidates: List[Dict[str, any]]
    ) -> List[str]:
        """
        基于检索结果判断意图
        
        Args:
            question: 用户问题
            candidates: 候选微服务列表，每个候选包含intent、text、score字段
        
        Returns:
            List[str]: 识别出的微服务名称列表
        
        Raises:
            Exception: LLM调用或响应解析失败
        """
        try:
            logger.debug(f"开始意图分类，问题: {question}, 候选数量: {len(candidates)}")
            
            # 构建提示词
            messages = self._build_prompt(question, candidates)
            
            # 调用LLM API
            response = await self.client.chat_completion(messages)
            
            # 解析响应
            intents = self._parse_response(response)
            
            logger.info(f"意图分类完成，识别出 {len(intents)} 个微服务: {intents}")
            
            return intents
            
        except Exception as e:
            logger.error(f"意图分类失败: {str(e)}", exc_info=True)
            raise
    
    def _build_prompt(
        self, 
        question: str, 
        candidates: List[Dict[str, any]]
    ) -> List[Dict[str, str]]:
        """
        构建提示词

        只支持识别单独一个微服务
        
        Args:
            question: 用户问题
            candidates: 候选微服务列表
        
        Returns:
            List[Dict[str, str]]: 消息列表，包含system和user角色的消息
        """
        # 系统提示词
        system_prompt = """你是一个意图识别专家。根据用户问题和候选微服务列表，判断用户需求对应哪一个微服务。

规则：
1. 仔细分析用户问题的核心需求
2. 从候选微服务列表中选择最匹配的微服务
3. 只能选择一个微服务
5. 以JSON数组格式输出。

示例：
 问题：“将用户按信用等级分类”；输出：["classify"]
 """
        # 4. 根据选择的微服务，将用户的问题拆解，拆解为对应每个微服务的问题
        # 问题：“将用户按信用等级分类，再按购买偏好分组”；输出：["classify:将用户按信用等级分类",
        #                                                    "cluster:将分类后的每一组用户按购买偏好分组"]
        # 格式化候选微服务列表
        candidates_text = self._format_candidates(candidates)
        
        # 用户提示词
        user_prompt = f"""用户问题: {question}

候选微服务:
{candidates_text}

请分析用户问题，选择最匹配的微服务名称，以JSON数组格式返回。"""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        logger.debug(f"构建的提示词: system={len(system_prompt)} chars, user={len(user_prompt)} chars")
        
        return messages
    
    def _format_candidates(self, candidates: List[Dict[str, any]]) -> str:
        """
        格式化候选微服务列表为文本
        
        Args:
            candidates: 候选微服务列表
        
        Returns:
            str: 格式化后的文本
        """
        if not candidates:
            return "（无候选微服务）"
        
        # 按相似度分组候选微服务
        intent_groups = {}
        for candidate in candidates:
            intent = candidate.get('intent', 'unknown')
            text = candidate.get('text', '')
            score = candidate.get('score', 0.0)
            
            if intent not in intent_groups:
                intent_groups[intent] = []
            
            intent_groups[intent].append({
                'text': text,
                'score': score
            })
        
        # 格式化输出
        lines = []
        for idx, (intent, examples) in enumerate(intent_groups.items(), 1):
            # 取每个微服务的前3个示例
            top_examples = sorted(examples, key=lambda x: x['score'], reverse=True)[:3]
            example_texts = [f"  - {ex['text']} (相似度: {ex['score']:.3f})" 
                           for ex in top_examples]
            
            lines.append(f"{idx}. 微服务名称: {intent}")
            lines.extend(example_texts)
        
        return "\n".join(lines)
    
    def _parse_response(self, response: str) -> List[str]:
        """
        解析大模型响应，提取微服务名称列表
        
        Args:
            response: 大模型返回的响应文本
        
        Returns:
            List[str]: 微服务名称列表
        
        Raises:
            Exception: 响应格式错误或解析失败
        """
        try:
            logger.debug(f"解析LLM响应: {response[:200]}...")
            
            # 清理响应文本
            response = response.strip()
            
            # 尝试提取JSON数组
            # 处理可能的markdown代码块格式
            if "```json" in response:
                # 提取```json ... ```之间的内容
                start = response.find("```json") + 7
                end = response.find("```", start)
                if end > start:
                    response = response[start:end].strip()
            elif "```" in response:
                # 提取``` ... ```之间的内容
                start = response.find("```") + 3
                end = response.find("```", start)
                if end > start:
                    response = response[start:end].strip()
            
            # 尝试查找JSON数组
            start_idx = response.find('[')
            end_idx = response.rfind(']')
            
            if start_idx == -1 or end_idx == -1 or start_idx >= end_idx:
                raise ValueError(f"响应中未找到有效的JSON数组: {response}")
            
            json_str = response[start_idx:end_idx + 1]
            
            # 解析JSON
            intents = json.loads(json_str)
            
            # 验证结果
            if not isinstance(intents, list):
                raise ValueError(f"解析结果不是列表: {type(intents)}")
            
            # 过滤和清理结果
            intents = [str(intent).strip() for intent in intents if intent]
            
            if not intents:
                logger.warning("LLM返回空的微服务列表")
                return []
            
            logger.debug(f"成功解析出 {len(intents)} 个微服务: {intents}")
            
            return intents
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}, 响应内容: {response}")
            raise Exception(f"LLM响应格式错误，无法解析JSON: {str(e)}")
        
        except Exception as e:
            logger.error(f"响应解析失败: {str(e)}, 响应内容: {response}")
            raise Exception(f"LLM响应解析失败: {str(e)}")
