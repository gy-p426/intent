"""
LLM API客户端
使用火山引擎豆包大模型API
"""
import logging
import asyncio
from typing import List, Dict, Optional
from volcenginesdkarkruntime import Ark
from infrastructure.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """
    大模型API客户端
    封装火山引擎豆包API调用，支持重试机制
    """
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, 
                 timeout: Optional[int] = None, max_retries: Optional[int] = None, 
                 retry_delay: Optional[int] = None):
        """
        初始化LLM客户端
        
        Args:
            api_key: 火山引擎ARK API密钥（可选，默认从配置获取）
            model: 模型名称（可选，默认从配置获取）
            timeout: API调用超时时间（秒）（可选，默认从配置获取）
            max_retries: 最大重试次数（可选，默认从配置获取）
            retry_delay: 重试间隔（秒）（可选，默认从配置获取）
        """
        # 获取配置
        settings = get_settings()
        
        self.api_key = api_key or settings.ark_api_key
        self.model = model or settings.llm_analysis_model or settings.ark_model
        self.timeout = timeout or settings.llm_analysis_timeout or settings.ark_timeout
        self.max_retries = max_retries or settings.llm_analysis_max_retries or settings.llm_max_retries
        self.retry_delay = retry_delay or settings.llm_retry_delay
        
        # 验证必需参数
        if not self.api_key:
            raise ValueError("API密钥未配置，请设置ARK_API_KEY环境变量或在.env文件中配置")
        
        # 初始化Ark客户端
        self.client = Ark(api_key=self.api_key, timeout=self.timeout)
        logger.info(f"LLMClient initialized with model: {self.model}")
    
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
