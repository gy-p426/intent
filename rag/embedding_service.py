"""
向量化服务
使用sentence-transformers将文本转换为向量
"""
import logging
import numpy as np
from typing import List, Union
from sentence_transformers import SentenceTransformer


logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    文本向量化服务
    使用sentence-transformers加载预训练模型
    """
    
    _model_cache = {}  # 类级别的模型缓存
    
    def __init__(self, model_name: str = "shibing624/text2vec-base-chinese"):
        """
        初始化向量化服务
        
        Args:
            model_name: 预训练模型名称
        """
        self.model_name = model_name
        self._model = None
    
    def _load_model(self) -> SentenceTransformer:
        """
        加载模型，使用缓存机制避免重复加载
        
        Returns:
            SentenceTransformer: 加载的模型
        """
        if self.model_name in self._model_cache:
            logger.info(f"使用缓存的向量化模型: {self.model_name}")
            return self._model_cache[self.model_name]
        
        logger.info(f"加载向量化模型: {self.model_name}")
        try:
            model = SentenceTransformer(self.model_name)
            self._model_cache[self.model_name] = model
            logger.info(f"向量化模型加载成功: {self.model_name}")
            return model
        except Exception as e:
            logger.error(f"加载向量化模型失败: {str(e)}", exc_info=True)
            raise
    
    @property
    def model(self) -> SentenceTransformer:
        """获取模型实例"""
        if self._model is None:
            self._model = self._load_model()
        return self._model
    
    def encode(
        self, 
        texts: Union[str, List[str]], 
        normalize: bool = True,
        batch_size: int = 32
    ) -> np.ndarray:
        """
        将文本转换为向量
        
        Args:
            texts: 单个文本或文本列表
            normalize: 是否归一化向量（默认True）
            batch_size: 批处理大小
            
        Returns:
            np.ndarray: 向量数组，shape为(n, dim)或(dim,)
        """
        if isinstance(texts, str):
            texts = [texts]
            single_text = True
        else:
            single_text = False
        
        if not texts:
            logger.warning("输入文本列表为空")
            return np.array([])
        
        try:
            logger.debug(f"开始向量化 {len(texts)} 个文本")
            
            # 使用sentence-transformers进行编码
            embeddings = self.model.encode(
                texts,
                normalize_embeddings=normalize,
                batch_size=batch_size,
                show_progress_bar=False
            )
            
            logger.debug(f"向量化完成，输出shape: {embeddings.shape}")
            
            # 如果输入是单个文本，返回一维向量
            if single_text:
                return embeddings[0]
            
            return embeddings
            
        except Exception as e:
            logger.error(f"文本向量化失败: {str(e)}", exc_info=True)
            raise
    
    def get_dimension(self) -> int:
        """
        获取向量维度
        
        Returns:
            int: 向量维度
        """
        return self.model.get_sentence_embedding_dimension()
