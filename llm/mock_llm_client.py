"""
模拟LLM客户端
用于测试环境，当真实的volcenginesdkarkruntime不可用时使用
"""

import asyncio
import json
import logging
from typing import List, Dict, Any
import random

logger = logging.getLogger(__name__)


class MockArk:
    """模拟的Ark客户端"""
    
    def __init__(self, api_key: str, timeout: int = 60):
        self.api_key = api_key
        self.timeout = timeout
        self.chat = MockChatCompletions()
        logger.info("使用模拟LLM客户端进行测试")


class MockChatCompletions:
    """模拟的聊天完成接口"""
    
    def create(self, model: str, messages: List[Dict[str, str]], **kwargs) -> 'MockResponse':
        """模拟创建聊天完成"""
        # 模拟处理延迟
        import time
        time.sleep(random.uniform(0.5, 2.0))
        
        # 解析用户问题，尝试识别意图
        user_message = ""
        for msg in messages:
            if msg.get("role") == "user":
                user_message = msg.get("content", "")
                break
        
        # 简单的意图识别逻辑
        intents = []
        if any(keyword in user_message.lower() for keyword in ["分类", "分组", "聚类", "classify", "分为"]):
            intents.append("classify")
        if any(keyword in user_message.lower() for keyword in ["预测", "predict", "预估", "趋势"]):
            intents.append("predict")
        
        # 如果没有识别到特定意图，随机选择一个
        if not intents:
            intents = [random.choice(["classify", "predict"])]
        
        # 构造响应
        response_content = json.dumps(intents, ensure_ascii=False)
        
        return MockResponse(response_content)


class MockResponse:
    """模拟的响应对象"""
    
    def __init__(self, content: str):
        self.choices = [MockChoice(content)]


class MockChoice:
    """模拟的选择对象"""
    
    def __init__(self, content: str):
        self.message = MockMessage(content)


class MockMessage:
    """模拟的消息对象"""
    
    def __init__(self, content: str):
        self.content = content


# 导出模拟的Ark类
Ark = MockArk