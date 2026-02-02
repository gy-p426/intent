"""
Algorithm Integration API

Provides HTTP endpoints for algorithm integration service with streaming support.
"""

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from algorithm.models import AlgorithmRequest, AlgorithmResponse, ManualDBSelectionRequest, ManualRunRequest
from algorithm.service import AlgorithmIntegrationService
from algorithm.streaming.streaming_handler import StreamingResponseHandler
from infrastructure.config import get_settings


logger = logging.getLogger(__name__)


class AlgorithmIntegrationAPI:
    """算法集成API应用"""
    
    def __init__(self):
        """初始化算法集成API"""
        self.settings = get_settings()
        self.algorithm_service: Optional[AlgorithmIntegrationService] = None
        self.streaming_handler = StreamingResponseHandler()
        
        logger.info("算法集成API初始化完成")
    
    def set_algorithm_service(self, service: AlgorithmIntegrationService):
        """设置算法集成服务实例"""
        self.algorithm_service = service
        logger.info("算法集成服务已注入")
    
    def register_routes(self, app: FastAPI):
        """注册算法集成相关的API路由"""
        
        @app.post(
            "/api/v1/algorithm/execute",
            summary="执行算法分析",
            description="接收自然语言查询，执行完整的算法分析流程并返回流式响应"
        )
        async def execute_algorithm(
            request: AlgorithmRequest,
            http_request: Request  # 新增：获取HTTP请求对象，用于检测连接状态
        ) -> StreamingResponse:
            """
            算法执行接口
            
            在流式响应中检测客户端连接状态。
            当客户端关闭连接时，后端立即停止处理，释放资源。
            
            接收用户的自然语言查询，通过算法集成服务执行完整的分析流程，
            包括算法类型识别、参数提取、SQL生成、数据检索和算法执行。
            返回流式响应以提供实时进度反馈。
            """
            try:
                # 检查服务是否可用
                if not self.algorithm_service:
                    logger.error("算法集成服务未初始化")
                    raise HTTPException(
                        status_code=503,
                        detail="Service not available: Algorithm integration service not initialized"
                    )
                
                logger.info(f"收到算法执行请求: {request.question}, window_id={request.window_id},session_id={request.session_id},agent_algorithm={request.agent_algorithm},user_id={request.user_id},fileIds={request.fileIds}")
                
                # 处理 fileIds：如果是数组，转换为逗号分隔的字符串
                fileids_str = None
                if request.fileIds:
                    if isinstance(request.fileIds, list):
                        fileids_str = ','.join(str(fid) for fid in request.fileIds)
                    else:
                        fileids_str = str(request.fileIds)
                    logger.info(f"fileIds 转换结果: {fileids_str}")
                else:
                    logger.info("fileIds 为空，未检测到文件上传")
                
                # 创建响应生成器
                response_generator = self.algorithm_service.process_algorithm_request(
                    question=request.question,
                    window_id=request.window_id,
                    session_id=request.session_id,
                    user_id=request.user_id,
                    auto_analysis=request.auto_analysis,
                    agent_algorithm=request.agent_algorithm,  # 传递agent_algorithm参数
                    fileIds=fileids_str  # 传递fileIds参数
                )
                
                # 根据请求选择响应格式
                if request.stream:
                    # 返回流式响应，传递http_request用于检测连接状态
                    return await self.streaming_handler.create_streaming_response(
                        response_generator,
                        http_request=http_request  # 新增
                    )
                else:
                    # 收集所有响应并返回最终结果
                    final_response = None
                    async for response in response_generator:
                        final_response = response
                    
                    if final_response:
                        return final_response
                    else:
                        raise HTTPException(
                            status_code=500,
                            detail="No response generated"
                        )
                
            except ValueError as e:
                # 参数验证错误
                logger.warning(f"请求参数无效: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid request: {str(e)}"
                )
            
            except Exception as e:
                # 其他服务错误
                logger.error(f"算法执行失败: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Internal server error"
                )
        
        @app.post(
            "/api/v1/algorithm/execute/manual-db-selection",
            summary="手动选择数据库信息：生成新的 normalized_query",
            description="手动模式第二段：用户选择列信息后，服务端基于选择生成新的 normalized_query"
        )
        async def manual_db_selection(request: ManualDBSelectionRequest) -> StreamingResponse:
            try:
                if not self.algorithm_service:
                    raise HTTPException(status_code=503, detail="Service not available")

                response_generator = self.algorithm_service.process_manual_db_selection(
                    manual_selection_token=request.manual_selection_token,
                    manual_parameter_mapping=request.manual_parameter_mapping,
                    user_feedback=request.user_feedback,
                )

                if request.stream:
                    return await self.streaming_handler.create_streaming_response(response_generator)
                else:
                    final_response = None
                    async for response in response_generator:
                        final_response = response
                    if final_response:
                        return final_response
                    raise HTTPException(status_code=500, detail="No response generated")

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"manual-db-selection失败: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail="Internal server error")

        @app.post(
            "/api/v1/algorithm/execute/manual-run",
            summary="手动确认执行：执行SQL与算法",
            description="手动模式第三段：用户确认 normalized_query 后开始执行 Step3/Step4"
        )
        async def manual_run(request: ManualRunRequest) -> StreamingResponse:
            try:
                if not self.algorithm_service:
                    raise HTTPException(status_code=503, detail="Service not available")

                response_generator = self.algorithm_service.process_manual_run(
                    manual_selection_token=request.manual_selection_token,
                    normalized_query=request.normalized_query,
                    manual_parameter_mapping=request.manual_parameter_mapping,
                )

                if request.stream:
                    return await self.streaming_handler.create_streaming_response(response_generator)
                else:
                    final_response = None
                    async for response in response_generator:
                        final_response = response
                    if final_response:
                        return final_response
                    raise HTTPException(status_code=500, detail="No response generated")

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"manual-run失败: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail="Internal server error")

        @app.get(
            "/api/v1/algorithm/execute/sse",
            summary="执行算法分析 (SSE)",
            description="使用Server-Sent Events格式返回算法执行的流式响应"
        )
        async def execute_algorithm_sse(
            question: str,
            window_id: str,
            session_id: str,
            http_request: Request  # 新增：获取HTTP请求对象，用于检测连接状态
        ) -> StreamingResponse:
            """
            算法执行接口 (Server-Sent Events格式)
            
            在流式响应中检测客户端连接状态。
            当客户端关闭连接时，后端立即停止处理，释放资源。
            
            与execute_algorithm相同的功能，但使用SSE格式返回流式响应，
            更适合前端JavaScript EventSource API。
            """
            try:
                # 检查服务是否可用
                if not self.algorithm_service:
                    logger.error("算法集成服务未初始化")
                    raise HTTPException(
                        status_code=503,
                        detail="Service not available: Algorithm integration service not initialized"
                    )
                
                logger.info(f"收到算法执行请求(SSE): {question}")
                
                # 创建响应生成器
                response_generator = self.algorithm_service.process_algorithm_request(
                    question=question,
                    window_id=window_id,
                    session_id=session_id,
                    auto_analysis=None
                )
                
                # 返回SSE格式的流式响应，传递http_request用于检测连接状态
                return await self.streaming_handler.create_sse_response(
                    response_generator,
                    http_request=http_request  # 新增
                )
                
            except ValueError as e:
                # 参数验证错误
                logger.warning(f"请求参数无效: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid request: {str(e)}"
                )
            
            except Exception as e:
                # 其他服务错误
                logger.error(f"算法执行失败: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Internal server error"
                )
        
        @app.get(
            "/api/v1/algorithm/task/{task_id}/progress",
            summary="获取任务进度详情",
            description="获取异步任务的详细进度信息，包括进度快照、指标历史和审计跟踪"
        )
        async def get_task_progress(task_id: str):
            """
            获取任务进度详情
            
            返回指定任务的详细进度信息，包括：
            - 基本任务信息
            - 当前进度状态
            - 进度快照历史
            - 性能指标
            - 训练日志
            - 审计跟踪
            """
            try:
                from algorithm.logging.progress_tracker import get_progress_tracker
                from algorithm.tasks.task_manager import TaskManager
                
                progress_tracker = get_progress_tracker()
                task_manager = TaskManager()
                
                # 获取进度摘要
                progress_summary = progress_tracker.get_task_progress_summary(task_id)
                if not progress_summary:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Task not found: {task_id}"
                    )
                
                # 获取详细进度信息
                detailed_progress = await task_manager.get_task_detailed_progress(task_id)
                
                # 获取进度分析
                progress_analytics = progress_tracker.get_progress_analytics(task_id)
                
                # 获取最近的进度快照
                recent_snapshots = progress_tracker.get_progress_snapshots(task_id, limit=10)
                
                response_data = {
                    "task_id": task_id,
                    "summary": {
                        "algorithm_type": progress_summary.algorithm_type,
                        "start_time": progress_summary.start_time.isoformat(),
                        "current_progress": progress_summary.current_progress,
                        "total_snapshots": progress_summary.total_snapshots,
                        "average_progress_rate": progress_summary.average_progress_rate,
                        "estimated_completion": progress_summary.estimated_completion_time.isoformat() if progress_summary.estimated_completion_time else None
                    },
                    "detailed_progress": detailed_progress,
                    "analytics": progress_analytics,
                    "recent_snapshots": [
                        {
                            "timestamp": snapshot.timestamp.isoformat(),
                            "progress_percent": snapshot.progress_percent,
                            "current_step": snapshot.current_step,
                            "metrics": snapshot.metrics,
                            "logs_count": len(snapshot.logs),
                            "estimated_remaining_seconds": snapshot.estimated_remaining_seconds
                        }
                        for snapshot in recent_snapshots
                    ]
                }
                
                return response_data
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"获取任务进度失败: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get task progress"
                )
        
        @app.get(
            "/api/v1/algorithm/task/{task_id}/audit",
            summary="获取任务审计跟踪",
            description="获取任务的完整审计跟踪记录"
        )
        async def get_task_audit_trail(task_id: str):
            """
            获取任务审计跟踪
            
            返回指定任务的完整审计跟踪记录，包括：
            - 任务创建和状态变更
            - 进度更新事件
            - 训练日志接收
            - 指标更新
            - 错误和异常
            """
            try:
                from algorithm.tasks.task_manager import TaskManager
                
                task_manager = TaskManager()
                
                # 获取审计跟踪
                audit_trail = await task_manager.get_task_audit_trail(task_id)
                
                if not audit_trail:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Task audit trail not found: {task_id}"
                    )
                
                return {
                    "task_id": task_id,
                    "audit_trail": audit_trail,
                    "total_events": len(audit_trail)
                }
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"获取任务审计跟踪失败: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Failed to get task audit trail"
                )
        
        @app.get(
            "/api/v1/algorithm/task/{task_id}/report",
            summary="导出任务执行报告",
            description="导出任务的完整执行报告，包含所有进度、日志、指标和审计信息"
        )
        async def export_task_report(task_id: str):
            """
            导出任务执行报告
            
            生成并返回指定任务的完整执行报告，包括：
            - 任务摘要
            - 执行指标
            - 详细进度
            - 审计跟踪
            - 训练日志
            - 指标历史
            """
            try:
                from algorithm.tasks.task_manager import TaskManager
                
                task_manager = TaskManager()
                
                # 导出执行报告
                execution_report = await task_manager.export_task_execution_report(task_id)
                
                if not execution_report:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Task report not found: {task_id}"
                    )
                
                return execution_report
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"导出任务执行报告失败: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Failed to export task report"
                )
        
        @app.get(
            "/api/v1/algorithm/task/{task_id}/logs/stream",
            summary="流式获取训练日志",
            description="实时流式获取任务的训练日志"
        )
        async def stream_training_logs(task_id: str) -> StreamingResponse:
            """
            流式获取训练日志
            
            为指定任务创建训练日志的实时流式响应，
            客户端可以实时接收任务的训练日志更新。
            """
            try:
                # 创建训练日志流
                return await self.streaming_handler.create_training_log_stream(task_id)
                
            except Exception as e:
                logger.error(f"创建训练日志流失败: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create training log stream"
                )
        
        @app.post(
            "/api/v1/algorithm/execute/progress-aware",
            summary="执行算法分析（进度感知）",
            description="执行算法分析并提供增强的进度跟踪功能"
        )
        async def execute_algorithm_with_progress_tracking(request: AlgorithmRequest) -> StreamingResponse:
            """
            执行算法分析（进度感知版本）
            
            与标准算法执行相同，但提供增强的进度跟踪功能：
            - 详细的进度分析
            - 训练日志流式传输
            - 指标实时更新
            - 完整的审计跟踪
            """
            try:
                # 检查服务是否可用
                if not self.algorithm_service:
                    logger.error("算法集成服务未初始化")
                    raise HTTPException(
                        status_code=503,
                        detail="Service not available: Algorithm integration service not initialized"
                    )
                
                logger.info(f"收到进度感知算法执行请求: {request.question}")
                
                # 创建响应生成器
                response_generator = self.algorithm_service.process_algorithm_request(
                    question=request.question,
                    window_id=request.window_id,
                    session_id=request.session_id,
                    auto_analysis=request.auto_analysis
                )
                
                # 生成任务ID（如果需要）
                import uuid
                task_id = f"task_{uuid.uuid4().hex[:8]}"
                
                # 返回进度感知的流式响应
                return await self.streaming_handler.create_progress_aware_streaming_response(
                    response_generator, task_id, request.session_id
                )
                
            except ValueError as e:
                logger.warning(f"请求参数无效: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid request: {str(e)}"
                )
            
            except Exception as e:
                logger.error(f"进度感知算法执行失败: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Internal server error"
                )
        
        logger.info("算法集成API路由注册完成")


# 创建算法集成API实例
algorithm_api = AlgorithmIntegrationAPI()