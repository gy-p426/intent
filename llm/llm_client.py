"""
LLM API客户端
使用火山引擎豆包大模型API
"""
import logging
import asyncio
from typing import List, Dict
from volcenginesdkarkruntime import Ark

logger = logging.getLogger(__name__)


class LLMClient:
    """
    大模型API客户端
    封装火山引擎豆包API调用，支持重试机制
    """
    
    def __init__(self, api_key: str, model: str, timeout: int = 60, 
                 max_retries: int = 3, retry_delay: int = 2):
        """
        初始化LLM客户端
        
        Args:
            api_key: 火山引擎ARK API密钥
            model: 模型名称
            timeout: API调用超时时间（秒）
            max_retries: 最大重试次数
            retry_delay: 重试间隔（秒）
        """
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        # 初始化Ark客户端
        self.client = Ark(api_key=api_key, timeout=timeout)
        logger.info(f"LLMClient initialized with model: {model}")
    
    async def chat_completion(self, messages: List[Dict[str, str]]) -> str:
        """
        调用大模型API
        支持重试机制：最多重试 max_retries 次，每次间隔retry_delay秒
        
        Args:
            messages: 对话消息列表，格式: [{"role": "system/user/assistant", "content": "..."}]
        
        Returns:
            str: 大模型返回的响应内容
        
        Raises:
            Exception: API调用失败且重试次数用尽
        """
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Calling LLM API (attempt {attempt + 1}/{self.max_retries})")
                
                # 调用API
                response = await asyncio.to_thread(
                    self._sync_chat_completion,
                    messages
                )
                
                logger.info(f"LLM API call succeeded on attempt {attempt + 1}")
                return response
                
            except Exception as e:
                logger.warning(
                    f"LLM API call failed on attempt {attempt + 1}/{self.max_retries}: {str(e)}"
                )
                
                # 如果还有重试机会，等待后重试
                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
                else:
                    # 重试次数用尽，抛出异常
                    logger.error(
                        f"LLM API call failed after {self.max_retries} retries: {str(e)}"
                    )
                    raise Exception(
                        f"LLM API调用失败，已重试{self.max_retries}次: {str(e)}"
                    )
    
    def _sync_chat_completion(self, messages: List[Dict[str, str]]) -> str:
        """
        同步调用API（内部方法）
        
        Args:
            messages: 对话消息列表
        
        Returns:
            str: 大模型返回的响应内容
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages
            # thinking={"type": "disabled"}  # 不使用深度思考能力以提高响应速度
        )
        
        # 提取响应内容
        if response.choices and len(response.choices) > 0:
            content = response.choices[0].message.content
            logger.debug(f"LLM response: {content[:100]}...")  # 只记录前100个字符
            return content
        else:
            raise Exception("LLM API返回空响应")
