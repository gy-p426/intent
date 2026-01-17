"""
Agent算法分析客户端（SSE纯透传版本）
调用Agent服务并原封不动地透传SSE事件
"""
import logging
import json
from typing import Dict, Any, AsyncGenerator
import httpx
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentAlgorithmClient:
    """Agent算法分析服务客户端（SSE纯透传版本）"""
    
    def __init__(self, base_url: str, timeout: int = 300):
        """
        初始化客户端
        
        Args:
            base_url: Agent服务地址（如 http://localhost:8010）
            timeout: 超时时间（秒），默认5分钟
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        # 使用更长的超时时间用于流式请求
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(timeout, read=None))
        logger.info(f"AgentAlgorithmClient initialized: {self.base_url}, timeout={timeout}s")
    
    async def analyze_streaming(
        self,
        question: str,
        csv_data: bytes,
        config: Dict[str, Any] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        调用Agent算法分析（SSE流式，纯透传）
        
        Args:
            question: 用户问题
            csv_data: CSV格式的数据（字节）
            config: 额外配置参数（可选）
            
        Yields:
            Agent返回的原始SSE事件（不做任何修改）
            格式: {"event_type": "...", "timestamp": "...", "data": {...}}
        """
        try:
            # 构建request_data
            request_data = {"query": question}
            if config:
                request_data["config"] = config
            
            # 构建multipart/form-data
            files = {
                'file': ('data.csv', csv_data, 'text/csv'),
            }
            data = {
                'request_data': json.dumps(request_data)
            }
            
            logger.info(f"调用Agent服务: {self.base_url}/query_agents_stream")
            logger.info(f"问题: {question}, CSV大小: {len(csv_data)} bytes")
            
            # 发起SSE流式请求
            async with self.client.stream(
                "POST",
                f"{self.base_url}/query_agents_stream",
                files=files,
                data=data
            ) as response:
                response.raise_for_status()
                
                # 验证响应类型
                content_type = response.headers.get("content-type", "")
                if "text/event-stream" not in content_type:
                    logger.error(f"Agent服务返回的不是SSE格式: {content_type}")
                    raise ValueError(f"期望 text/event-stream，实际: {content_type}")
                
                logger.info("开始接收Agent的SSE事件流")
                
                # 解析并透传SSE流
                async for event in self._parse_sse_stream(response):
                    # 原封不动地yield给上层
                    yield event
            
            logger.info("Agent SSE事件流接收完成")
            
        except httpx.HTTPStatusError as e:
            logger.error(f"Agent服务返回错误: {e.response.status_code}")
            try:
                error_text = await e.response.aread()
                logger.error(f"错误详情: {error_text.decode('utf-8', errors='ignore')}")
            except:
                pass
            raise
        except Exception as e:
            logger.error(f"调用Agent服务失败: {str(e)}", exc_info=True)
            raise
    
    async def _parse_sse_stream(self, response: httpx.Response) -> AsyncGenerator[Dict[str, Any], None]:
        """
        解析SSE流（不做任何修改，只解析格式）
        
        Args:
            response: httpx响应对象
            
        Yields:
            解析后的事件字典（保持原始结构）
        """
        buffer = ""
        event_count = 0
        
        async for chunk in response.aiter_text():
            buffer += chunk
            
            # 按行分割
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                
                if not line:
                    continue
                
                # 解析SSE格式: data: {...}
                if line.startswith("data: "):
                    data_str = line[6:]  # 移除 "data: " 前缀
                    
                    # 跳过结束标记
                    if data_str == "[DONE]":
                        logger.info("收到Agent流结束标记 [DONE]")
                        break
                    
                    try:
                        # 解析JSON
                        event = json.loads(data_str)
                        event_count += 1
                        
                        # 记录事件（用于调试）
                        event_type = event.get("event_type", "unknown")
                        logger.debug(f"收到Agent事件 #{event_count}: {event_type}")
                        
                        # 原封不动地yield
                        yield event
                        
                    except json.JSONDecodeError as e:
                        logger.warning(f"解析Agent SSE数据失败: {data_str[:100]}..., 错误: {e}")
                        # 如果不是JSON，包装为错误事件
                        yield {
                            "event_type": "parse_error",
                            "timestamp": datetime.utcnow().isoformat(),
                            "data": {
                                "error": f"JSON解析失败: {str(e)}",
                                "raw_data": data_str[:200]
                            }
                        }
        
        logger.info(f"SSE流解析完成，共接收 {event_count} 个事件")
    
    async def close(self):
        """关闭客户端"""
        await self.client.aclose()
        logger.info("AgentAlgorithmClient closed")
