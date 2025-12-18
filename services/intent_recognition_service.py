"""
意图识别服务
协调RAG检索和LLM判断流程
"""
import logging
import time
from typing import List, Optional
from pydantic import BaseModel

from rag.rag_module import RAGModule, IntentCandidate
from llm.llm_module import LLMModule


logger = logging.getLogger(__name__)


class IntentResult(BaseModel):
    """意图识别结果"""
    question: str
    intents: List[str]  # 识别出的微服务名称列表
    candidates: List[IntentCandidate]  # RAG检索的候选结果
    processing_time_ms: int  # 处理时间（毫秒）
    confidence: Optional[float] = None  # 置信度（可选）


class IntentRecognitionService:
    """
    意图识别服务
    负责协调RAG模块和LLM模块完成意图识别
    """
    
    def __init__(self, rag_module: RAGModule, llm_module: LLMModule):
        """
        初始化意图识别服务
        
        Args:
            rag_module: RAG模块实例
            llm_module: LLM模块实例
        """
        self.rag = rag_module
        self.llm = llm_module
        logger.info("IntentRecognitionService initialized")
    
    async def recognize_intent(
        self, 
        question: str, 
        top_k: int = 20
    ) -> IntentResult:
        """
        识别用户意图
        
        处理流程:
        1. 使用RAG模块检索相关微服务候选
        2. 调用LLM模块判断最终意图
        3. 记录处理时间和中间结果
        
        Args:
            question: 用户问题
            top_k: RAG检索返回的候选数量，默认20
        
        Returns:
            IntentResult: 意图识别结果，包含识别的微服务、候选列表和处理时间
        
        Raises:
            ValueError: 输入参数无效
            RuntimeError: RAG模块未初始化
            Exception: 处理过程中发生错误
        """
        start_time = time.time()
        
        try:
            # 参数验证
            if not question or not question.strip():
                raise ValueError("问题不能为空")
            
            if top_k < 1 or top_k > 100:
                raise ValueError("top_k必须在1-100之间")
            
            logger.info(f"开始意图识别，问题: {question}, top_k: {top_k}")
            
            # 步骤1: RAG检索候选微服务
            logger.debug("步骤1: 使用RAG检索候选微服务")
            rag_start = time.time()
            candidates = await self.rag.retrieve(question, top_k)
            rag_time = (time.time() - rag_start) * 1000
            
            logger.info(
                f"RAG检索完成，耗时: {rag_time:.2f}ms, "
                f"返回 {len(candidates)} 个候选"
            )
            
            # 如果没有候选结果，直接返回空结果
            if not candidates:
                logger.warning("RAG检索未返回任何候选结果")
                processing_time = int((time.time() - start_time) * 1000)
                return IntentResult(
                    question=question,
                    intents=[],
                    candidates=[],
                    processing_time_ms=processing_time,
                    confidence=0.0
                )
            
            # 记录候选结果详情
            if logger.isEnabledFor(logging.DEBUG):
                for idx, candidate in enumerate(candidates[:5], 1):
                    logger.debug(
                        f"  候选{idx}: {candidate.intent} "
                        f"(score: {candidate.score:.3f}, text: {candidate.text[:50]}...)"
                    )
            
            # 步骤2: LLM判断最终意图
            logger.debug("步骤2: 使用LLM判断最终意图")
            llm_start = time.time()
            
            # 将候选结果转换为字典格式供LLM使用
            candidates_dict = [
                {
                    'intent': c.intent,
                    'text': c.text,
                    'score': c.score
                }
                for c in candidates
            ]
            
            intents = await self.llm.classify(question, candidates_dict)
            llm_time = (time.time() - llm_start) * 1000
            
            logger.info(
                f"LLM判断完成，耗时: {llm_time:.2f}ms, "
                f"识别出 {len(intents)} 个微服务: {intents}"
            )
            
            # 计算总处理时间
            processing_time = int((time.time() - start_time) * 1000)
            
            # 计算置信度（基于最高相似度分数）
            confidence = candidates[0].score if candidates else 0.0
            
            # 构建结果
            result = IntentResult(
                question=question,
                intents=intents,
                candidates=candidates,
                processing_time_ms=processing_time,
                confidence=confidence
            )
            
            logger.info(
                f"意图识别完成，总耗时: {processing_time}ms "
                f"(RAG: {rag_time:.2f}ms, LLM: {llm_time:.2f}ms), "
                f"结果: {intents}"
            )
            
            return result
            
        except ValueError as e:
            logger.error(f"参数验证失败: {str(e)}")
            raise
        
        except Exception as e:
            processing_time = int((time.time() - start_time) * 1000)
            logger.error(
                f"意图识别失败，耗时: {processing_time}ms, "
                f"错误: {str(e)}",
                exc_info=True
            )
            raise
