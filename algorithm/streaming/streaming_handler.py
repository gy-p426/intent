"""
Streaming Response Handler Implementation

Manages streaming HTTP responses to provide real-time feedback
during long-running algorithm execution processes.
"""

import json
import logging
from typing import Any, Optional
from datetime import datetime
from algorithm.models import AlgorithmResponse, AlgorithmResponseGenerator
from algorithm.interfaces import IStreamingResponseHandler
from infrastructure.config import get_settings


logger = logging.getLogger(__name__)


class StreamingResponseHandler(IStreamingResponseHandler):
    """流式响应处理器实现"""
    
    def __init__(self):
        """初始化流式响应处理器"""
        self.settings = get_settings()
        self.chunk_size = self.settings.stream_chunk_size
        
    async def create_streaming_response(
        self, 
        generator: AlgorithmResponseGenerator
    ) -> Any:
        """
        创建流式HTTP响应（增强版本，支持进度跟踪）
        
        Args:
            generator: 算法响应生成器
            
        Returns:
            StreamingResponse: FastAPI流式响应对象
        """
        try:
            # 导入FastAPI的StreamingResponse
            from fastapi.responses import StreamingResponse
            from algorithm.logging.progress_tracker import get_progress_tracker
            
            progress_tracker = get_progress_tracker()
            
            # 创建流式响应生成器
            async def response_generator():
                task_id = None
                try:
                    async for response in generator:
                        # 提取任务ID用于进度跟踪
                        if hasattr(response, 'task_id') and response.task_id:
                            task_id = response.task_id
                        
                        # 如果是异步任务响应，更新进度跟踪
                        if hasattr(response, 'progress') and response.progress and task_id:
                            await progress_tracker.update_progress(
                                task_id=task_id,
                                progress=response.progress,
                                logs=getattr(response, 'logs', None),
                                metrics=getattr(response, 'metrics', None)
                            )
                        
                        # 格式化响应数据
                        chunk = self.format_stream_chunk(response)
                        yield chunk
                        
                except Exception as e:
                    logger.error(f"流式响应生成失败: {str(e)}")
                    # 发送错误响应
                    from algorithm.models import ErrorResponse
                    error_response = ErrorResponse(
                        error_code="STREAMING_ERROR",
                        error_message=str(e)
                    )
                    error_chunk = self.format_stream_chunk(error_response)
                    yield error_chunk
                finally:
                    # 停止进度跟踪
                    if task_id:
                        try:
                            await progress_tracker.stop_tracking(task_id)
                        except Exception as e:
                            logger.warning(f"停止进度跟踪失败: {str(e)}")
            
            # 创建StreamingResponse
            return StreamingResponse(
                response_generator(),
                media_type="text/plain; charset=utf-8",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"  # 禁用nginx缓冲
                }
            )
            
        except Exception as e:
            logger.error(f"创建流式响应失败: {str(e)}")
            raise
    
    def format_stream_chunk(self, data: AlgorithmResponse) -> str:
        """
        格式化流式数据块
        
        Args:
            data: 算法响应数据
            
        Returns:
            str: 格式化的数据块
        """
        try:
            # 将响应数据转换为字典
            if hasattr(data, 'dict'):
                data_dict = data.dict()
            elif hasattr(data, 'model_dump'):
                data_dict = data.model_dump()
            else:
                data_dict = dict(data)
            
            # 转换为JSON字符串
            json_str = json.dumps(data_dict, ensure_ascii=False, default=str)
            
            # 添加换行符，便于客户端解析
            return f"data: {json_str}\n\n"
            
        except Exception as e:
            logger.error(f"格式化流式数据块失败: {str(e)}")
            # 返回错误信息
            error_data = {
                "step": "error",
                "status": "error",
                "error": f"数据格式化失败: {str(e)}"
            }
            json_str = json.dumps(error_data, ensure_ascii=False)
            return f"data: {json_str}\n\n"
    
    def format_sse_chunk(self, data: AlgorithmResponse, event_type: str = "message") -> str:
        """
        格式化Server-Sent Events (SSE)数据块
        
        Args:
            data: 算法响应数据
            event_type: 事件类型
            
        Returns:
            str: SSE格式的数据块
        """
        try:
            # 将响应数据转换为字典
            if hasattr(data, 'dict'):
                data_dict = data.dict()
            elif hasattr(data, 'model_dump'):
                data_dict = data.model_dump()
            else:
                data_dict = dict(data)
            
            # 转换为JSON字符串
            json_str = json.dumps(data_dict, ensure_ascii=False, default=str)
            
            # 构建SSE格式
            sse_chunk = f"event: {event_type}\ndata: {json_str}\n\n"
            
            return sse_chunk
            
        except Exception as e:
            logger.error(f"格式化SSE数据块失败: {str(e)}")
            # 返回错误事件
            error_data = {
                "step": "error",
                "status": "error",
                "error": f"数据格式化失败: {str(e)}"
            }
            json_str = json.dumps(error_data, ensure_ascii=False)
            return f"event: error\ndata: {json_str}\n\n"
    
    async def create_sse_response(
        self, 
        generator: AlgorithmResponseGenerator
    ) -> Any:
        """
        创建Server-Sent Events (SSE)响应
        
        Args:
            generator: 算法响应生成器
            
        Returns:
            StreamingResponse: SSE格式的流式响应
        """
        try:
            from fastapi.responses import StreamingResponse
            
            async def sse_generator():
                try:
                    async for response in generator:
                        # 根据响应步骤确定事件类型
                        event_type = "message"
                        if hasattr(response, 'step'):
                            event_type = response.step.value if hasattr(response.step, 'value') else str(response.step)
                        
                        # 格式化SSE数据块
                        chunk = self.format_sse_chunk(response, event_type)
                        yield chunk
                        
                except Exception as e:
                    logger.error(f"SSE响应生成失败: {str(e)}")
                    # 发送错误事件
                    from algorithm.models import ErrorResponse
                    error_response = ErrorResponse(
                        error_code="SSE_ERROR",
                        error_message=str(e)
                    )
                    error_chunk = self.format_sse_chunk(error_response, "error")
                    yield error_chunk
            
            # 创建SSE StreamingResponse
            return StreamingResponse(
                sse_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no"
                }
            )
            
        except Exception as e:
            logger.error(f"创建SSE响应失败: {str(e)}")
            raise
    
    def validate_chunk_size(self, data: str) -> bool:
        """
        验证数据块大小是否合适
        
        Args:
            data: 数据块内容
            
        Returns:
            bool: 大小是否合适
        """
        try:
            data_size = len(data.encode('utf-8'))
            return data_size <= self.chunk_size
            
        except Exception as e:
            logger.error(f"验证数据块大小失败: {str(e)}")
            return False
    
    def split_large_chunk(self, data: str) -> list:
        """
        分割过大的数据块
        
        Args:
            data: 原始数据
            
        Returns:
            list: 分割后的数据块列表
        """
        try:
            if self.validate_chunk_size(data):
                return [data]
            
            # 简单分割策略：按字符数分割
            max_chars = self.chunk_size // 2  # 预留编码空间
            chunks = []
            
            for i in range(0, len(data), max_chars):
                chunk = data[i:i + max_chars]
                chunks.append(chunk)
            
            return chunks
            
        except Exception as e:
            logger.error(f"分割数据块失败: {str(e)}")
            return [data]  # 返回原始数据
    
    async def create_progress_aware_streaming_response(
        self,
        generator: AlgorithmResponseGenerator,
        task_id: str,
        trace_id: Optional[str] = None
    ) -> Any:
        """
        创建支持进度跟踪的流式响应
        
        Args:
            generator: 算法响应生成器
            task_id: 任务ID
            trace_id: 追踪ID
            
        Returns:
            StreamingResponse: 支持进度跟踪的流式响应
        """
        try:
            from fastapi.responses import StreamingResponse
            from algorithm.logging.progress_tracker import get_progress_tracker
            from algorithm.logging.async_task_logger import get_async_task_logger
            
            progress_tracker = get_progress_tracker()
            async_task_logger = get_async_task_logger()
            
            async def progress_aware_generator():
                try:
                    # 使用异步任务日志记录器的流式处理方法
                    async for response in async_task_logger.stream_task_progress(
                        generator, task_id, trace_id or "unknown"
                    ):
                        # 更新进度跟踪器
                        if hasattr(response, 'progress') and response.progress:
                            await progress_tracker.update_progress(
                                task_id=task_id,
                                progress=response.progress,
                                logs=getattr(response, 'logs', None),
                                metrics=getattr(response, 'metrics', None),
                                trace_id=trace_id
                            )
                        
                        # 格式化并发送响应
                        chunk = self.format_stream_chunk(response)
                        yield chunk
                        
                        # 如果任务完成，发送最终的进度摘要
                        if hasattr(response, 'status') and response.status in ['success', 'failed']:
                            summary = progress_tracker.get_task_progress_summary(task_id)
                            if summary:
                                summary_response = {
                                    "step": "progress_summary",
                                    "status": "completed",
                                    "data": {
                                        "task_id": task_id,
                                        "final_progress": summary.current_progress,
                                        "total_snapshots": summary.total_snapshots,
                                        "average_progress_rate": summary.average_progress_rate,
                                        "total_execution_time": (datetime.utcnow() - summary.start_time).total_seconds()
                                    }
                                }
                                summary_chunk = self.format_stream_chunk(summary_response)
                                yield summary_chunk
                            break
                
                except Exception as e:
                    logger.error(f"进度感知流式响应生成失败: {str(e)}")
                    from algorithm.models import ErrorResponse
                    error_response = ErrorResponse(
                        error_code="PROGRESS_STREAMING_ERROR",
                        error_message=str(e)
                    )
                    error_chunk = self.format_stream_chunk(error_response)
                    yield error_chunk
                finally:
                    # 停止进度跟踪
                    try:
                        await progress_tracker.stop_tracking(task_id, trace_id)
                    except Exception as e:
                        logger.warning(f"停止进度跟踪失败: {str(e)}")
            
            return StreamingResponse(
                progress_aware_generator(),
                media_type="text/plain; charset=utf-8",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "X-Task-ID": task_id,  # 添加任务ID到响应头
                    "X-Trace-ID": trace_id or "unknown"
                }
            )
            
        except Exception as e:
            logger.error(f"创建进度感知流式响应失败: {str(e)}")
            raise
    
    async def create_training_log_stream(
        self,
        task_id: str,
        trace_id: Optional[str] = None
    ) -> Any:
        """
        创建训练日志流式响应
        
        Args:
            task_id: 任务ID
            trace_id: 追踪ID
            
        Returns:
            StreamingResponse: 训练日志流式响应
        """
        try:
            from fastapi.responses import StreamingResponse
            from algorithm.logging.progress_tracker import get_progress_tracker
            
            progress_tracker = get_progress_tracker()
            
            async def training_log_generator():
                try:
                    # 订阅进度更新
                    async for update in progress_tracker.subscribe_to_progress(task_id):
                        if update.get("logs"):
                            log_response = {
                                "step": "training_logs",
                                "status": "streaming",
                                "data": {
                                    "task_id": task_id,
                                    "timestamp": update.get("timestamp"),
                                    "logs": update["logs"]
                                }
                            }
                            chunk = self.format_stream_chunk(log_response)
                            yield chunk
                
                except Exception as e:
                    logger.error(f"训练日志流生成失败: {str(e)}")
                    error_response = {
                        "step": "error",
                        "status": "error",
                        "error": f"训练日志流失败: {str(e)}"
                    }
                    error_chunk = self.format_stream_chunk(error_response)
                    yield error_chunk
            
            return StreamingResponse(
                training_log_generator(),
                media_type="text/plain; charset=utf-8",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "X-Task-ID": task_id,
                    "X-Stream-Type": "training-logs"
                }
            )
            
        except Exception as e:
            logger.error(f"创建训练日志流失败: {str(e)}")
            raise