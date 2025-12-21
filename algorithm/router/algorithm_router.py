"""
Algorithm Router Implementation

Routes user queries to appropriate algorithm types based on intent recognition
and keyword matching using the existing RAG and LLM modules.
"""

import logging
from typing import Dict, List, Optional
from algorithm.models import AlgorithmType
from algorithm.interfaces import IAlgorithmRouter, IAlgorithmConfigManager
from algorithm.config_manager import get_algorithm_config_manager


logger = logging.getLogger(__name__)


class AlgorithmRouter(IAlgorithmRouter):
    """算法路由器实现"""
    
    def __init__(
        self,
        intent_service=None,  # Will be injected from services module
        config_manager: Optional[IAlgorithmConfigManager] = None
    ):
        """
        初始化算法路由器
        
        Args:
            intent_service: 意图识别服务实例
            config_manager: 配置管理器
        """
        self.intent_service = intent_service
        self.config_manager = config_manager or get_algorithm_config_manager()
        self._algorithm_mapping: Dict[str, AlgorithmType] = {}
        
    async def route_to_algorithm(self, question: str) -> AlgorithmType:
        """
        将用户问题路由到算法类型
        
        Args:
            question: 用户自然语言查询
            
        Returns:
            AlgorithmType: 识别的算法类型
            
        Raises:
            ValueError: 无法识别算法类型时抛出
        """
        logger.info(f"开始路由算法类型: {question}")
        
        try:
            # 方法1: 使用意图识别服务（优先级最高）
            if self.intent_service:
                algorithm_type = await self._match_by_intent_service(question)
                if algorithm_type:
                    logger.info(f"通过意图识别服务识别算法类型: {algorithm_type.value}")
                    return algorithm_type
            
            # 方法2: 基于关键词匹配（备选方案）
            algorithm_type = await self._match_by_keywords(question)
            if algorithm_type:
                logger.info(f"通过关键词匹配识别算法类型: {algorithm_type.value}")
                return algorithm_type
            
            # 方法3: 基于LLM的智能匹配（最后备选）
            algorithm_type = await self._match_by_llm(question)
            if algorithm_type:
                logger.info(f"通过LLM识别算法类型: {algorithm_type.value}")
                return algorithm_type
            
            # 无法识别算法类型
            raise ValueError(f"无法识别查询的算法类型: {question}")
            
        except Exception as e:
            logger.error(f"算法路由失败: {str(e)}")
            raise
    
    async def _match_by_keywords(self, question: str) -> Optional[AlgorithmType]:
        """
        基于关键词匹配算法类型
        
        Args:
            question: 用户查询
            
        Returns:
            Optional[AlgorithmType]: 匹配的算法类型
        """
        try:
            # 加载算法配置
            algorithms_config = await self.config_manager.load_config()
            
            question_lower = question.lower()
            
            # 遍历所有算法配置，查找关键词匹配
            for alg_type, config in algorithms_config.items():
                if config.intent_keywords:
                    for keyword in config.intent_keywords:
                        if keyword.lower() in question_lower:
                            try:
                                return AlgorithmType(alg_type)
                            except ValueError:
                                logger.warning(f"无效的算法类型: {alg_type}")
                                continue
            
            return None
            
        except Exception as e:
            logger.error(f"关键词匹配失败: {str(e)}")
            return None
    
    async def _match_by_intent_service(self, question: str) -> Optional[AlgorithmType]:
        """
        使用意图识别服务匹配算法类型
        
        Args:
            question: 用户查询
            
        Returns:
            Optional[AlgorithmType]: 匹配的算法类型
        """
        try:
            if not self.intent_service:
                logger.debug("意图识别服务未初始化")
                return None
            
            logger.debug(f"使用意图识别服务分析查询: {question}")
            
            # 调用意图识别服务
            intent_result = await self.intent_service.recognize_intent(question, top_k=10)
            
            if not intent_result.intents:
                logger.debug("意图识别服务未返回任何意图")
                return None
            
            # 将识别的意图映射到算法类型
            for intent in intent_result.intents:
                try:
                    # 直接尝试将意图作为算法类型
                    algorithm_type = AlgorithmType(intent)
                    logger.debug(f"成功映射意图 '{intent}' 到算法类型 '{algorithm_type.value}'")
                    return algorithm_type
                except ValueError:
                    logger.debug(f"意图 '{intent}' 不是有效的算法类型")
                    continue
            
            logger.debug(f"无法将识别的意图 {intent_result.intents} 映射到算法类型")
            return None
            
        except Exception as e:
            logger.error(f"意图识别服务匹配失败: {str(e)}")
            return None
    
    async def _match_by_llm(self, question: str) -> Optional[AlgorithmType]:
        """
        使用LLM智能匹配算法类型
        
        Args:
            question: 用户查询
            
        Returns:
            Optional[AlgorithmType]: 匹配的算法类型
        """
        try:
            # 如果没有意图识别服务，无法使用LLM匹配
            if not self.intent_service:
                logger.debug("意图识别服务未初始化，无法使用LLM匹配")
                return None
            
            # 使用意图识别服务的RAG模块获取候选
            rag_module = getattr(self.intent_service, 'rag', None)
            if not rag_module:
                logger.debug("RAG模块未找到，无法使用LLM匹配")
                return None
            
            # 检索相关的算法示例
            candidates = await rag_module.retrieve(question, top_k=10)
            
            if not candidates:
                logger.debug("未找到相关的算法示例")
                return None
            
            # 使用算法专用LLM模块进行识别
            from llm.algorithm_llm_module import AlgorithmLLMModule
            llm_client = getattr(self.intent_service, 'llm', None)
            if not llm_client:
                logger.debug("LLM客户端未找到")
                return None
            
            algorithm_llm = AlgorithmLLMModule(llm_client.client)
            
            # 将候选结果转换为字典格式
            candidates_dict = [
                {
                    'intent': c.intent,
                    'text': c.text,
                    'score': c.score
                }
                for c in candidates
            ]
            
            # 识别算法类型
            algorithm_type_str = await algorithm_llm.identify_algorithm_type(question, candidates_dict)
            
            if algorithm_type_str:
                try:
                    return AlgorithmType(algorithm_type_str)
                except ValueError:
                    logger.warning(f"LLM返回的算法类型无效: {algorithm_type_str}")
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"LLM智能匹配失败: {str(e)}")
            return None
    
    def get_supported_algorithms(self) -> List[AlgorithmType]:
        """
        获取支持的算法类型列表
        
        Returns:
            List[AlgorithmType]: 支持的算法类型
        """
        try:
            return [AlgorithmType(alg_type) for alg_type in AlgorithmType.__members__.values()]
        except Exception as e:
            logger.error(f"获取支持的算法类型失败: {str(e)}")
            return []
    
    async def get_algorithm_suggestions(self, question: str) -> List[Dict[str, str]]:
        """
        获取算法建议列表（当无法确定唯一算法类型时使用）
        
        Args:
            question: 用户查询
            
        Returns:
            List[Dict[str, str]]: 算法建议列表，包含类型、名称和描述
        """
        try:
            suggestions = []
            algorithms_config = await self.config_manager.load_config()
            
            # 基于关键词匹配获取可能的算法类型
            question_lower = question.lower()
            matched_algorithms = set()
            
            for alg_type, config in algorithms_config.items():
                if config.intent_keywords:
                    for keyword in config.intent_keywords:
                        if keyword.lower() in question_lower:
                            matched_algorithms.add(alg_type)
                            break
            
            # 如果通过关键词匹配找到算法，返回这些建议
            if matched_algorithms:
                for alg_type in matched_algorithms:
                    config = algorithms_config[alg_type]
                    suggestions.append({
                        "type": alg_type,
                        "name": config.name,
                        "description": config.description
                    })
            else:
                # 如果没有匹配，返回所有支持的算法类型
                for alg_type, config in algorithms_config.items():
                    suggestions.append({
                        "type": alg_type,
                        "name": config.name,
                        "description": config.description
                    })
            
            return suggestions
            
        except Exception as e:
            logger.error(f"获取算法建议失败: {str(e)}")
            return []