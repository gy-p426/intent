"""
模拟向量化服务
用于测试环境，当无法下载真实模型时使用
"""

import numpy as np
import logging
from typing import List
import hashlib

logger = logging.getLogger(__name__)


class MockEmbeddingService:
    """
    模拟向量化服务
    使用简单的哈希算法生成固定维度的向量
    """
    
    def __init__(self, model_name: str = "mock-embedding-model", dimension: int = 384):
        """
        初始化模拟向量化服务
        
        Args:
            model_name: 模型名称（仅用于日志）
            dimension: 向量维度
        """
        self.model_name = model_name
        self.dimension = dimension
        logger.info(f"使用模拟向量化服务: {model_name}, 维度: {dimension}")
    
    def encode(self, texts: List[str], normalize_embeddings: bool = True) -> np.ndarray:
        """
        将文本列表转换为向量
        使用简单的哈希算法生成确定性的向量
        
        Args:
            texts: 文本列表
            normalize_embeddings: 是否归一化向量
            
        Returns:
            np.ndarray: 向量矩阵，形状为 (len(texts), dimension)
        """
        logger.debug(f"编码 {len(texts)} 个文本")
        
        vectors = []
        
        for text in texts:
            # 使用MD5哈希生成确定性的向量
            hash_obj = hashlib.md5(text.encode('utf-8'))
            hash_bytes = hash_obj.digest()
            
            # 将哈希字节转换为浮点数向量
            vector = []
            for i in range(self.dimension):
                # 使用循环的哈希字节生成向量元素
                byte_idx = i % len(hash_bytes)
                vector.append(float(hash_bytes[byte_idx]) / 255.0 - 0.5)  # 范围 [-0.5, 0.5]
            
            vectors.append(vector)
        
        # 转换为numpy数组
        embeddings = np.array(vectors, dtype=np.float32)
        
        # 归一化向量
        if normalize_embeddings:
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms = np.where(norms == 0, 1, norms)  # 避免除零
            embeddings = embeddings / norms
        
        logger.debug(f"生成向量形状: {embeddings.shape}")
        return embeddings
    
    def similarity(self, text1: str, text2: str) -> float:
        """
        计算两个文本的相似度
        
        Args:
            text1: 第一个文本
            text2: 第二个文本
            
        Returns:
            float: 相似度分数 (0-1)
        """
        vectors = self.encode([text1, text2])
        similarity = np.dot(vectors[0], vectors[1])
        return float(similarity)


# 为了兼容性，也提供EmbeddingService别名
EmbeddingService = MockEmbeddingService