"""
向量存储和检索
使用FAISS进行高效向量检索
"""
import logging
import numpy as np
from typing import List, Tuple
import faiss
from .knowledge_base_loader import IntentEntry


logger = logging.getLogger(__name__)


class VectorStore:
    """
    向量存储和检索类
    使用FAISS IndexFlatIP索引进行内积相似度检索
    """
    
    def __init__(self, dimension: int):
        """
        初始化向量存储
        
        Args:
            dimension: 向量维度
        """
        self.dimension = dimension
        # 使用IndexFlatIP进行内积相似度检索（适用于归一化向量）
        self.index = faiss.IndexFlatIP(dimension)
        self.entries: List[IntentEntry] = []
        logger.info(f"初始化向量存储，维度: {dimension}")
    
    def add(self, vectors: np.ndarray, entries: List[IntentEntry]):
        """
        添加向量到索引
        
        Args:
            vectors: 向量数组，shape为(n, dim)
            entries: 对应的IntentEntry列表
        """
        if len(vectors) == 0:
            logger.warning("尝试添加空向量列表")
            return
        
        if len(vectors) != len(entries):
            raise ValueError(
                f"向量数量({len(vectors)})与条目数量({len(entries)})不匹配"
            )
        
        # 确保向量是float32类型（FAISS要求）
        if vectors.dtype != np.float32:
            vectors = vectors.astype(np.float32)
        
        # 确保向量是二维数组
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        
        # 验证向量维度
        if vectors.shape[1] != self.dimension:
            raise ValueError(
                f"向量维度({vectors.shape[1]})与索引维度({self.dimension})不匹配"
            )
        
        # 添加到FAISS索引
        self.index.add(vectors)
        self.entries.extend(entries)
        
        logger.info(f"添加 {len(vectors)} 个向量到索引，当前总数: {self.index.ntotal}")
    
    def search(
        self, 
        query_vector: np.ndarray, 
        top_k: int = 20
    ) -> List[Tuple[IntentEntry, float]]:
        """
        检索最相似的top_k个条目
        
        Args:
            query_vector: 查询向量，shape为(dim,)或(1, dim)
            top_k: 返回的结果数量
            
        Returns:
            List[Tuple[IntentEntry, float]]: 
                (IntentEntry, 相似度分数)的列表，按相似度从高到低排序
        """
        if self.index.ntotal == 0:
            logger.warning("向量索引为空，无法检索")
            return []
        
        # 确保查询向量是float32类型
        if query_vector.dtype != np.float32:
            query_vector = query_vector.astype(np.float32)
        
        # 确保查询向量是二维数组
        if query_vector.ndim == 1:
            query_vector = query_vector.reshape(1, -1)
        
        # 验证向量维度
        if query_vector.shape[1] != self.dimension:
            raise ValueError(
                f"查询向量维度({query_vector.shape[1]})与索引维度({self.dimension})不匹配"
            )
        
        # 限制top_k不超过索引中的向量数量
        k = min(top_k, self.index.ntotal)
        
        # 执行检索
        scores, indices = self.index.search(query_vector, k)
        
        # 构建结果列表
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(self.entries):
                logger.warning(f"检索到无效的索引: {idx}")
                continue
            results.append((self.entries[idx], float(score)))
        
        logger.debug(f"检索完成，返回 {len(results)} 个结果")
        return results
    
    def clear(self):
        """清空索引"""
        self.index.reset()
        self.entries.clear()
        logger.info("向量索引已清空")
    
    def size(self) -> int:
        """
        获取索引中的向量数量
        
        Returns:
            int: 向量数量
        """
        return self.index.ntotal
