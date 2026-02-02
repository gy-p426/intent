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
from algorithm.router.pure_llm_selector import PureLLMAlgorithmSelector
from infrastructure.config import get_settings


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
        self.settings = get_settings()
        self._algorithm_mapping: Dict[str, AlgorithmType] = {}
        
        # 初始化纯LLM选择器（如果启用）
        self.pure_llm_selector = None
        if self.settings.enable_pure_llm_algorithm_detection:
            try:
                self.pure_llm_selector = PureLLMAlgorithmSelector()
                logger.info("纯LLM算法选择器已启用")
            except Exception as e:
                logger.error(f"纯LLM算法选择器初始化失败: {str(e)}")
                logger.warning("将使用传统RAG+关键词方法")
        else:
            logger.info("使用传统RAG+关键词算法识别方法")
            # 验证intent_service是否提供
            if not self.intent_service:
                logger.warning("传统模式下未提供intent_service，算法识别可能失败")
        
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
            # 优先使用纯LLM方法（如果启用）
            if self.settings.enable_pure_llm_algorithm_detection and self.pure_llm_selector:
                try:
                    algorithm_type = await self._match_by_pure_llm(question)
                    if algorithm_type:
                        logger.info(f"通过纯LLM识别算法类型: {algorithm_type.value}")
                        return algorithm_type
                    else:
                        logger.warning("纯LLM识别失败")
                except Exception as e:
                    logger.error(f"纯LLM算法选择失败: {str(e)}")
                    # 如果纯LLM失败且没有intent_service，返回AGENT作为保底
                    if not self.intent_service:
                        logger.warning("纯LLM失败且无intent_service，返回AGENT类型")
                        return AlgorithmType.AGENT
                    # 否则尝试降级到传统方法
                    logger.info("降级到传统RAG+关键词方法")
            
            # 传统方法：RAG + 关键词 + LLM
            # 方法1: 使用意图识别服务（优先级最高）
            if self.intent_service:
                algorithm_type = await self._match_by_intent_service(question)
                if algorithm_type:
                    logger.info(f"通过意图识别服务识别算法类型: {algorithm_type.value}")
                    return algorithm_type
            else:
                # 传统模式下intent_service未初始化
                logger.error("传统模式下intent_service未初始化")
                return AlgorithmType.AGENT
            
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
            
            # 无法识别算法类型，返回AGENT作为保底
            logger.warning(f"无法识别查询的算法类型，返回AGENT作为保底: {question}")
            return AlgorithmType.AGENT
            
        except Exception as e:
            logger.error(f"算法路由失败: {str(e)}")
            # 发生异常时返回AGENT作为保底
            logger.warning("算法路由异常，返回AGENT类型作为保底")
            return AlgorithmType.AGENT
    
    async def _match_by_pure_llm(self, question: str) -> Optional[AlgorithmType]:
        """
        使用纯LLM匹配算法类型
        
        Args:
            question: 用户查询
            
        Returns:
            Optional[AlgorithmType]: 匹配的算法类型
        """
        try:
            if not self.pure_llm_selector:
                logger.debug("纯LLM选择器未初始化")
                return None
            
            return await self.pure_llm_selector.select_algorithm(question)
            
        except Exception as e:
            logger.error(f"纯LLM匹配失败: {str(e)}")
            return None
    
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
                # 首先尝试intent_keywords
                if config.intent_keywords:
                    for keyword in config.intent_keywords:
                        if keyword.lower() in question_lower:
                            try:
                                return AlgorithmType(alg_type)
                            except ValueError:
                                logger.warning(f"无效的算法类型: {alg_type}")
                                continue
                
                # 如果没有intent_keywords，使用examples中的关键词
                if config.examples:
                    for example in config.examples:
                        # 从示例中提取关键词进行匹配
                        example_lower = example.lower()
                        # 简单的关键词匹配：如果查询和示例有共同的重要词汇
                        if self._has_common_keywords(question_lower, example_lower):
                            try:
                                return AlgorithmType(alg_type)
                            except ValueError:
                                logger.warning(f"无效的算法类型: {alg_type}")
                                continue
            
            return None
            
        except Exception as e:
            logger.error(f"关键词匹配失败: {str(e)}")
            return None
    
    def _has_common_keywords(self, question: str, example: str) -> bool:
        """
        检查查询和示例是否有共同的关键词
        
        Args:
            question: 用户查询（小写）
            example: 示例文本（小写）
            
        Returns:
            bool: 是否有共同关键词
        """
        # 定义重要的关键词及其权重
        keyword_weights = {
            # 高权重关键词 - 核心动作和目标
            "异常点": 3, "异常值": 3, "异常波动": 3, "离群点": 3, "outlier": 3,
            "趋势": 3, "变化趋势": 3, "趋势变化": 3, "走势": 3,
            "预测": 3, "分群": 3, "聚类": 3, "分组": 3, "分类": 3,
            
            # 中权重关键词 - 动作词
            "检测": 2, "发现": 2, "识别": 2, "分析": 2, "查看": 2, "查询": 2,
            "预估": 2, "预报": 2, "对比": 2, "比较": 2, "计算": 2,
            
            # 低权重关键词 - 修饰词
            "异常": 1, "数据": 1, "变化": 1, "模式": 1, "行为": 1,
            "每日": 1, "每月": 1, "每周": 1, "每小时": 1,
        }
        
        question_score = 0
        example_score = 0
        
        # 计算查询的关键词得分
        for keyword, weight in keyword_weights.items():
            if keyword in question:
                question_score += weight
        
        # 计算示例的关键词得分
        for keyword, weight in keyword_weights.items():
            if keyword in example:
                example_score += weight
        
        # 特殊规则：如果查询包含"趋势"相关词汇，优先匹配趋势分析
        trend_keywords = ["趋势", "变化趋势", "趋势变化", "走势"]
        question_has_trend = any(kw in question for kw in trend_keywords)
        example_has_trend = any(kw in example for kw in trend_keywords)
        
        if question_has_trend and example_has_trend:
            return True
        
        # 特殊规则：如果查询包含"异常点/异常值/异常波动"，优先匹配异常检测
        anomaly_specific_keywords = ["异常点", "异常值", "异常波动", "离群点", "outlier"]
        question_has_anomaly_specific = any(kw in question for kw in anomaly_specific_keywords)
        example_has_anomaly_specific = any(kw in example for kw in anomaly_specific_keywords)
        
        if question_has_anomaly_specific and example_has_anomaly_specific:
            return True
        
        # 特殊规则：如果查询包含"预测"，优先匹配预测分析
        predict_keywords = ["预测", "预估", "预报"]
        question_has_predict = any(kw in question for kw in predict_keywords)
        example_has_predict = any(kw in example for kw in predict_keywords)
        
        if question_has_predict and example_has_predict:
            return True
        
        # 特殊规则：如果查询包含"分群/聚类/分组"，优先匹配聚类分析
        cluster_keywords = ["分群", "聚类", "分组", "归类"]
        question_has_cluster = any(kw in question for kw in cluster_keywords)
        example_has_cluster = any(kw in example for kw in cluster_keywords)
        
        if question_has_cluster and example_has_cluster:
            return True
        
        # 避免误判：如果查询包含"异常XX的趋势"模式，不应该匹配异常检测
        if question_has_trend and "异常" in question and not question_has_anomaly_specific:
            # 这种情况下，只有示例也是趋势分析才匹配
            return example_has_trend
        
        # 通用匹配：基于得分
        # 如果两者都有足够的关键词得分，认为匹配
        return question_score >= 3 and example_score >= 3
    
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