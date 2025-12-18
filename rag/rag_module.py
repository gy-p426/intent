"""
RAG模块
整合知识库加载、向量化和检索功能
"""
import logging
from typing import List
from pydantic import BaseModel
from .knowledge_base_loader import KnowledgeBaseLoader, IntentEntry
from .embedding_service import EmbeddingService
from .vector_store import VectorStore


logger = logging.getLogger(__name__)


class IntentCandidate(BaseModel):
    """检索候选结果"""
    intent: str  # 微服务名称
    text: str  # 匹配的问题文本
    score: float  # 相似度分数


class RAGModule:
    """
    RAG模块
    整合知识库加载、向量化和检索功能
    """
    
    def __init__(
        self,
        kb_loader: KnowledgeBaseLoader,
        embedding_service: EmbeddingService,
        vector_store: VectorStore
    ):
        """
        初始化RAG模块
        
        Args:
            kb_loader: 知识库加载器
            embedding_service: 向量化服务
            vector_store: 向量存储
        """
        self.kb_loader = kb_loader
        self.embedding = embedding_service
        self.vector_store = vector_store
        self._initialized = False
    
    async def initialize(self):
        """
        初始化RAG模块
        加载知识库并构建向量索引
        """
        logger.info("开始初始化RAG模块")
        
        try:
            # 加载知识库
            entries = self.kb_loader.load()
            
            if not entries:
                logger.warning("知识库为空，RAG模块初始化完成但无数据")
                self._initialized = True
                return
            
            # 提取文本
            texts = [entry.text for entry in entries]
            
            # 向量化
            logger.info(f"开始向量化 {len(texts)} 个文本")
            vectors = self.embedding.encode(texts, normalize=True)
            
            # 添加到向量存储
            self.vector_store.add(vectors, entries)
            
            self._initialized = True
            logger.info(
                f"RAG模块初始化完成，加载 {len(entries)} 条知识库记录，"
                f"向量维度: {self.embedding.get_dimension()}"
            )
            
        except Exception as e:
            logger.error(f"RAG模块初始化失败: {str(e)}", exc_info=True)
            raise
    
    async def retrieve(
        self, 
        question: str, 
        top_k: int = 20
    ) -> List[IntentCandidate]:
        """
        检索最相关的top_k个微服务
        
        Args:
            question: 用户问题
            top_k: 返回的候选数量
            
        Returns:
            List[IntentCandidate]: 候选结果列表，按相似度从高到低排序
        """
        if not self._initialized:
            raise RuntimeError("RAG模块未初始化，请先调用initialize()")
        
        if not question or not question.strip():
            logger.warning("输入问题为空")
            return []
        
        try:
            logger.debug(f"检索问题: {question}, top_k: {top_k}")
            
            # 向量化查询问题
            query_vector = self.embedding.encode(question, normalize=True)
            
            # 检索相似向量
            results = self.vector_store.search(query_vector, top_k)
            
            # 转换为IntentCandidate
            candidates = [
                IntentCandidate(
                    intent=entry.intent,
                    text=entry.text,
                    score=score
                )
                for entry, score in results
            ]
            
            logger.info(f"检索完成，返回 {len(candidates)} 个候选结果")
            
            return candidates
            
        except Exception as e:
            logger.error(f"检索失败: {str(e)}", exc_info=True)
            raise
    
    async def reload_knowledge_base(self):
        """
        重新加载知识库
        动态更新向量索引
        """
        logger.info("开始重新加载知识库")
        
        try:
            # 清空现有索引
            self.vector_store.clear()
            
            # 重新初始化
            await self.initialize()
            
            logger.info("知识库重新加载完成")
            
        except Exception as e:
            logger.error(f"重新加载知识库失败: {str(e)}", exc_info=True)
            raise
    
    @property
    def is_initialized(self) -> bool:
        """检查RAG模块是否已初始化"""
        return self._initialized
    
    @property
    def knowledge_base_size(self) -> int:
        """获取知识库大小"""
        return self.vector_store.size()
