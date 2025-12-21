"""
Async Task Progress Tracking and Logging

Provides detailed progress tracking and audit trails for asynchronous algorithm tasks
including training logs, metrics streaming, and comprehensive task execution monitoring.
"""

import logging
import json
from typing import Dict, Any, Optional, List, AsyncGenerator
from datetime import datetime
from enum import Enum

from algorithm.models import TaskStatus, AsyncTaskResponse, AlgorithmType
from algorithm.logging.structured_logger import StructuredLogger, LogCategory, MetricType, LogLevel


class TaskEventType(str, Enum):
    """任务事件类型枚举"""
    TASK_CREATED = "task_created"
    TASK_STARTED = "task_started"
    TASK_PROGRESS_UPDATE = "task_progress_update"
    TASK_LOG_RECEIVED = "task_log_received"
    TASK_METRIC_UPDATE = "task_metric_update"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_TIMEOUT = "task_timeout"
    TASK_CANCELLED = "task_cancelled"
    POLLING_STARTED = "polling_started"
    POLLING_STOPPED = "polling_stopped"


class AsyncTaskLogger:
    """异步任务日志记录器"""
    
    def __init__(self, structured_logger: StructuredLogger):
        """
        初始化异步任务日志记录器
        
        Args:
            structured_logger: 结构化日志记录器实例
        """
        self.logger = logging.getLogger(__name__)
        self.structured_logger = structured_logger
        
        # 任务执行统计
        self._task_stats = {
            "total_tasks": 0,
            "active_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "cancelled_tasks": 0,
            "timeout_tasks": 0,
            "average_execution_time": 0.0,
            "task_types": {}
        }
        
        # 任务审计跟踪
        self._task_audit_trail: Dict[str, List[Dict[str, Any]]] = {}
        
        # 任务性能指标
        self._task_metrics: Dict[str, Dict[str, Any]] = {}
    
    def log_task_created(
        self,
        task_id: str,
        algorithm_type: AlgorithmType,
        trace_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        记录任务创建日志
        
        Args:
            task_id: 任务ID
            algorithm_type: 算法类型
            trace_id: 追踪ID
            context: 上下文信息
        """
        self._task_stats["total_tasks"] += 1
        self._task_stats["active_tasks"] += 1
        
        # 更新算法类型统计
        alg_type = algorithm_type.value
        if alg_type not in self._task_stats["task_types"]:
            self._task_stats["task_types"][alg_type] = 0
        self._task_stats["task_types"][alg_type] += 1
        
        # 初始化任务审计跟踪
        self._task_audit_trail[task_id] = []
        
        # 记录任务创建事件
        self._add_audit_event(
            task_id,
            TaskEventType.TASK_CREATED,
            f"异步任务创建: {algorithm_type.value}",
            context
        )
        
        self.structured_logger.log(
            LogLevel.INFO,
            f"异步任务创建: {task_id}",
            category=LogCategory.AUDIT,
            context={
                "task_id": task_id,
                "algorithm_type": algorithm_type.value,
                "event_type": TaskEventType.TASK_CREATED.value,
                **(context or {})
            },
            trace_id=trace_id,
            algorithm_type=algorithm_type
        )
    
    def log_task_started(
        self,
        task_id: str,
        algorithm_type: AlgorithmType,
        trace_id: str,
        input_data_size: Optional[int] = None
    ) -> None:
        """
        记录任务开始执行日志
        
        Args:
            task_id: 任务ID
            algorithm_type: 算法类型
            trace_id: 追踪ID
            input_data_size: 输入数据大小
        """
        context = {
            "task_id": task_id,
            "algorithm_type": algorithm_type.value,
            "event_type": TaskEventType.TASK_STARTED.value
        }
        
        if input_data_size is not None:
            context["input_data_size"] = input_data_size
        
        # 记录审计事件
        self._add_audit_event(
            task_id,
            TaskEventType.TASK_STARTED,
            "任务开始执行",
            context
        )
        
        self.structured_logger.log(
            LogLevel.INFO,
            f"异步任务开始执行: {task_id}",
            category=LogCategory.BUSINESS,
            context=context,
            trace_id=trace_id,
            algorithm_type=algorithm_type,
            metrics={
                "active_tasks": self._task_stats["active_tasks"],
                "input_data_size": input_data_size
            }
        )
    
    def log_task_progress_update(
        self,
        task_id: str,
        progress: Dict[str, Any],
        trace_id: str,
        algorithm_type: Optional[AlgorithmType] = None
    ) -> None:
        """
        记录任务进度更新日志
        
        Args:
            task_id: 任务ID
            progress: 进度信息
            trace_id: 追踪ID
            algorithm_type: 算法类型
        """
        # 提取进度百分比
        progress_percent = progress.get("percent", progress.get("progress", 0))
        current_step = progress.get("step", progress.get("current_step", "unknown"))
        
        context = {
            "task_id": task_id,
            "progress_percent": progress_percent,
            "current_step": current_step,
            "event_type": TaskEventType.TASK_PROGRESS_UPDATE.value,
            "progress_details": progress
        }
        
        # 记录审计事件
        self._add_audit_event(
            task_id,
            TaskEventType.TASK_PROGRESS_UPDATE,
            f"任务进度更新: {progress_percent}%",
            context
        )
        
        # 记录性能指标
        self.structured_logger.log_performance_metric(
            f"task_{task_id}_progress",
            progress_percent,
            MetricType.GAUGE,
            trace_id=trace_id,
            context={"task_id": task_id, "step": current_step}
        )
        
        self.structured_logger.log(
            LogLevel.INFO,
            f"任务进度更新: {task_id} - {progress_percent}%",
            category=LogCategory.PERFORMANCE,
            context=context,
            trace_id=trace_id,
            algorithm_type=algorithm_type
        )
    
    def log_task_training_logs(
        self,
        task_id: str,
        logs: List[str],
        trace_id: str,
        algorithm_type: Optional[AlgorithmType] = None
    ) -> None:
        """
        记录任务训练日志
        
        Args:
            task_id: 任务ID
            logs: 训练日志列表
            trace_id: 追踪ID
            algorithm_type: 算法类型
        """
        for log_entry in logs:
            context = {
                "task_id": task_id,
                "training_log": log_entry,
                "event_type": TaskEventType.TASK_LOG_RECEIVED.value
            }
            
            # 记录审计事件
            self._add_audit_event(
                task_id,
                TaskEventType.TASK_LOG_RECEIVED,
                f"训练日志: {log_entry[:100]}...",
                context
            )
            
            self.structured_logger.log(
                LogLevel.DEBUG,
                f"任务训练日志: {task_id}",
                category=LogCategory.AUDIT,
                context=context,
                trace_id=trace_id,
                algorithm_type=algorithm_type
            )
    
    def log_task_metrics_update(
        self,
        task_id: str,
        metrics: Dict[str, Any],
        trace_id: str,
        algorithm_type: Optional[AlgorithmType] = None
    ) -> None:
        """
        记录任务指标更新日志
        
        Args:
            task_id: 任务ID
            metrics: 指标数据
            trace_id: 追踪ID
            algorithm_type: 算法类型
        """
        # 缓存任务指标
        if task_id not in self._task_metrics:
            self._task_metrics[task_id] = {}
        self._task_metrics[task_id].update(metrics)
        
        context = {
            "task_id": task_id,
            "metrics": metrics,
            "event_type": TaskEventType.TASK_METRIC_UPDATE.value
        }
        
        # 记录审计事件
        self._add_audit_event(
            task_id,
            TaskEventType.TASK_METRIC_UPDATE,
            f"指标更新: {len(metrics)} 个指标",
            context
        )
        
        # 记录各个指标
        for metric_name, metric_value in metrics.items():
            if isinstance(metric_value, (int, float)):
                self.structured_logger.log_performance_metric(
                    f"task_{task_id}_{metric_name}",
                    metric_value,
                    MetricType.GAUGE,
                    trace_id=trace_id,
                    context={"task_id": task_id, "metric_type": "training"}
                )
        
        self.structured_logger.log(
            LogLevel.INFO,
            f"任务指标更新: {task_id}",
            category=LogCategory.PERFORMANCE,
            context=context,
            trace_id=trace_id,
            algorithm_type=algorithm_type
        )
    
    def log_task_completed(
        self,
        task_id: str,
        result: Dict[str, Any],
        execution_time_ms: float,
        trace_id: str,
        algorithm_type: Optional[AlgorithmType] = None
    ) -> None:
        """
        记录任务完成日志
        
        Args:
            task_id: 任务ID
            result: 任务结果
            execution_time_ms: 执行时间（毫秒）
            trace_id: 追踪ID
            algorithm_type: 算法类型
        """
        self._task_stats["active_tasks"] -= 1
        self._task_stats["completed_tasks"] += 1
        
        # 更新平均执行时间
        total_completed = self._task_stats["completed_tasks"]
        current_avg = self._task_stats["average_execution_time"]
        self._task_stats["average_execution_time"] = (
            (current_avg * (total_completed - 1) + execution_time_ms) / total_completed
        )
        
        result_size = len(str(result)) if result else 0
        
        context = {
            "task_id": task_id,
            "execution_time_ms": execution_time_ms,
            "result_size": result_size,
            "event_type": TaskEventType.TASK_COMPLETED.value,
            "success": True
        }
        
        # 记录审计事件
        self._add_audit_event(
            task_id,
            TaskEventType.TASK_COMPLETED,
            f"任务成功完成，耗时: {execution_time_ms:.2f}ms",
            context
        )
        
        # 记录性能指标
        self.structured_logger.log_performance_metric(
            f"task_execution_time_ms",
            execution_time_ms,
            MetricType.HISTOGRAM,
            trace_id=trace_id,
            context={"task_id": task_id, "algorithm_type": algorithm_type.value if algorithm_type else None}
        )
        
        self.structured_logger.log(
            LogLevel.INFO,
            f"异步任务完成: {task_id}",
            category=LogCategory.BUSINESS,
            context=context,
            trace_id=trace_id,
            algorithm_type=algorithm_type,
            execution_time_ms=execution_time_ms,
            metrics={
                "task_success_rate": self._task_stats["completed_tasks"] / self._task_stats["total_tasks"],
                "average_execution_time": self._task_stats["average_execution_time"]
            }
        )
    
    def log_task_failed(
        self,
        task_id: str,
        error_message: str,
        execution_time_ms: float,
        trace_id: str,
        algorithm_type: Optional[AlgorithmType] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        记录任务失败日志
        
        Args:
            task_id: 任务ID
            error_message: 错误消息
            execution_time_ms: 执行时间（毫秒）
            trace_id: 追踪ID
            algorithm_type: 算法类型
            error_details: 错误详情
        """
        self._task_stats["active_tasks"] -= 1
        self._task_stats["failed_tasks"] += 1
        
        context = {
            "task_id": task_id,
            "error_message": error_message,
            "execution_time_ms": execution_time_ms,
            "event_type": TaskEventType.TASK_FAILED.value,
            "success": False
        }
        
        if error_details:
            context["error_details"] = error_details
        
        # 记录审计事件
        self._add_audit_event(
            task_id,
            TaskEventType.TASK_FAILED,
            f"任务执行失败: {error_message}",
            context
        )
        
        self.structured_logger.log(
            LogLevel.ERROR,
            f"异步任务失败: {task_id} - {error_message}",
            category=LogCategory.ERROR,
            context=context,
            trace_id=trace_id,
            algorithm_type=algorithm_type,
            execution_time_ms=execution_time_ms,
            error_code="ASYNC_TASK_FAILED"
        )
    
    def log_task_timeout(
        self,
        task_id: str,
        timeout_seconds: int,
        trace_id: str,
        algorithm_type: Optional[AlgorithmType] = None
    ) -> None:
        """
        记录任务超时日志
        
        Args:
            task_id: 任务ID
            timeout_seconds: 超时时间（秒）
            trace_id: 追踪ID
            algorithm_type: 算法类型
        """
        self._task_stats["active_tasks"] -= 1
        self._task_stats["timeout_tasks"] += 1
        
        context = {
            "task_id": task_id,
            "timeout_seconds": timeout_seconds,
            "event_type": TaskEventType.TASK_TIMEOUT.value
        }
        
        # 记录审计事件
        self._add_audit_event(
            task_id,
            TaskEventType.TASK_TIMEOUT,
            f"任务执行超时: {timeout_seconds}秒",
            context
        )
        
        self.structured_logger.log(
            LogLevel.WARNING,
            f"异步任务超时: {task_id}",
            category=LogCategory.ERROR,
            context=context,
            trace_id=trace_id,
            algorithm_type=algorithm_type,
            error_code="TASK_TIMEOUT"
        )
    
    def log_polling_started(
        self,
        task_id: str,
        trace_id: str,
        poll_interval: int,
        max_wait_time: int
    ) -> None:
        """
        记录轮询开始日志
        
        Args:
            task_id: 任务ID
            trace_id: 追踪ID
            poll_interval: 轮询间隔（秒）
            max_wait_time: 最大等待时间（秒）
        """
        context = {
            "task_id": task_id,
            "poll_interval": poll_interval,
            "max_wait_time": max_wait_time,
            "event_type": TaskEventType.POLLING_STARTED.value
        }
        
        # 记录审计事件
        self._add_audit_event(
            task_id,
            TaskEventType.POLLING_STARTED,
            f"开始轮询任务状态，间隔: {poll_interval}秒",
            context
        )
        
        self.structured_logger.log(
            LogLevel.INFO,
            f"开始轮询异步任务: {task_id}",
            category=LogCategory.SYSTEM,
            context=context,
            trace_id=trace_id
        )
    
    def log_polling_stopped(
        self,
        task_id: str,
        trace_id: str,
        reason: str,
        total_polls: int,
        total_time_ms: float
    ) -> None:
        """
        记录轮询停止日志
        
        Args:
            task_id: 任务ID
            trace_id: 追踪ID
            reason: 停止原因
            total_polls: 总轮询次数
            total_time_ms: 总轮询时间（毫秒）
        """
        context = {
            "task_id": task_id,
            "reason": reason,
            "total_polls": total_polls,
            "total_time_ms": total_time_ms,
            "event_type": TaskEventType.POLLING_STOPPED.value
        }
        
        # 记录审计事件
        self._add_audit_event(
            task_id,
            TaskEventType.POLLING_STOPPED,
            f"轮询停止: {reason}，共轮询{total_polls}次",
            context
        )
        
        # 记录轮询性能指标
        self.structured_logger.log_performance_metric(
            "task_polling_duration_ms",
            total_time_ms,
            MetricType.HISTOGRAM,
            trace_id=trace_id,
            context={"task_id": task_id, "total_polls": total_polls}
        )
        
        self.structured_logger.log(
            LogLevel.INFO,
            f"停止轮询异步任务: {task_id} - {reason}",
            category=LogCategory.SYSTEM,
            context=context,
            trace_id=trace_id,
            metrics={
                "polling_efficiency": total_polls / (total_time_ms / 1000) if total_time_ms > 0 else 0
            }
        )
    
    def _add_audit_event(
        self,
        task_id: str,
        event_type: TaskEventType,
        description: str,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        添加审计事件到任务审计跟踪
        
        Args:
            task_id: 任务ID
            event_type: 事件类型
            description: 事件描述
            context: 上下文信息
        """
        if task_id not in self._task_audit_trail:
            self._task_audit_trail[task_id] = []
        
        audit_event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type.value,
            "description": description,
            "context": context or {}
        }
        
        self._task_audit_trail[task_id].append(audit_event)
        
        # 限制审计跟踪的大小
        if len(self._task_audit_trail[task_id]) > 100:
            self._task_audit_trail[task_id] = self._task_audit_trail[task_id][-50:]
    
    def get_task_audit_trail(self, task_id: str) -> List[Dict[str, Any]]:
        """
        获取任务的完整审计跟踪
        
        Args:
            task_id: 任务ID
            
        Returns:
            List[Dict[str, Any]]: 审计事件列表
        """
        return self._task_audit_trail.get(task_id, [])
    
    def get_task_statistics(self) -> Dict[str, Any]:
        """
        获取任务统计信息
        
        Returns:
            Dict[str, Any]: 任务统计
        """
        return self._task_stats.copy()
    
    def get_task_metrics(self, task_id: str) -> Dict[str, Any]:
        """
        获取任务的性能指标
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict[str, Any]: 任务指标
        """
        return self._task_metrics.get(task_id, {})
    
    def cleanup_task_data(self, task_id: str) -> None:
        """
        清理任务相关数据
        
        Args:
            task_id: 任务ID
        """
        self._task_audit_trail.pop(task_id, None)
        self._task_metrics.pop(task_id, None)
    
    async def stream_task_progress(
        self,
        task_response_generator: AsyncGenerator[AsyncTaskResponse, None],
        task_id: str,
        trace_id: str,
        algorithm_type: Optional[AlgorithmType] = None
    ) -> AsyncGenerator[AsyncTaskResponse, None]:
        """
        流式处理任务进度并记录详细日志
        
        Args:
            task_response_generator: 任务响应生成器
            task_id: 任务ID
            trace_id: 追踪ID
            algorithm_type: 算法类型
            
        Yields:
            AsyncTaskResponse: 任务响应
        """
        start_time = datetime.utcnow()
        poll_count = 0
        last_progress_percent = 0
        
        # 记录轮询开始
        self.log_polling_started(task_id, trace_id, 5, 300)  # 默认值
        
        try:
            async for response in task_response_generator:
                poll_count += 1
                
                # 记录详细的轮询信息
                self._log_polling_iteration(task_id, poll_count, trace_id, response)
                
                # 记录进度更新（包含更详细的进度分析）
                if response.progress:
                    current_progress = response.progress.get("percent", 0)
                    progress_delta = current_progress - last_progress_percent
                    
                    self.log_task_progress_update(
                        task_id, response.progress, trace_id, algorithm_type
                    )
                    
                    # 记录进度变化率
                    if progress_delta > 0:
                        self._log_progress_rate(
                            task_id, progress_delta, poll_count, trace_id, algorithm_type
                        )
                    
                    last_progress_percent = current_progress
                
                # 记录训练日志（增强版本）
                if response.logs:
                    self.log_task_training_logs(
                        task_id, response.logs, trace_id, algorithm_type
                    )
                    
                    # 分析训练日志中的关键指标
                    self._analyze_training_logs(
                        task_id, response.logs, trace_id, algorithm_type
                    )
                
                # 记录任务指标更新
                if hasattr(response, 'metrics') and response.metrics:
                    self.log_task_metrics_update(
                        task_id, response.metrics, trace_id, algorithm_type
                    )
                
                # 记录任务完成或失败
                if response.status == TaskStatus.SUCCESS:
                    execution_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                    self.log_task_completed(
                        task_id, response.result or {}, execution_time_ms, trace_id, algorithm_type
                    )
                elif response.status == TaskStatus.FAILED:
                    execution_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                    self.log_task_failed(
                        task_id, response.error or "Unknown error", execution_time_ms, trace_id, algorithm_type
                    )
                
                yield response
                
                # 如果任务完成，停止流式处理
                if response.status in [TaskStatus.SUCCESS, TaskStatus.FAILED]:
                    break
        
        finally:
            # 记录轮询停止
            total_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.log_polling_stopped(
                task_id, trace_id, "task_completed", poll_count, total_time_ms
            )
    
    def _log_polling_iteration(
        self,
        task_id: str,
        poll_count: int,
        trace_id: str,
        response: AsyncTaskResponse
    ) -> None:
        """
        记录轮询迭代详情
        
        Args:
            task_id: 任务ID
            poll_count: 轮询次数
            trace_id: 追踪ID
            response: 任务响应
        """
        context = {
            "task_id": task_id,
            "poll_iteration": poll_count,
            "response_status": response.status.value,
            "has_progress": bool(response.progress),
            "has_logs": bool(response.logs),
            "has_result": bool(response.result),
            "has_error": bool(response.error)
        }
        
        self.structured_logger.log(
            LogLevel.DEBUG,
            f"轮询迭代 #{poll_count}: {task_id}",
            category=LogCategory.SYSTEM,
            context=context,
            trace_id=trace_id
        )
    
    def _log_progress_rate(
        self,
        task_id: str,
        progress_delta: float,
        poll_count: int,
        trace_id: str,
        algorithm_type: Optional[AlgorithmType] = None
    ) -> None:
        """
        记录进度变化率
        
        Args:
            task_id: 任务ID
            progress_delta: 进度变化量
            poll_count: 轮询次数
            trace_id: 追踪ID
            algorithm_type: 算法类型
        """
        # 估算完成时间
        if progress_delta > 0:
            estimated_remaining_polls = (100 - progress_delta) / progress_delta
            estimated_completion_time = estimated_remaining_polls * 5  # 假设5秒轮询间隔
        else:
            estimated_completion_time = None
        
        context = {
            "task_id": task_id,
            "progress_delta": progress_delta,
            "poll_count": poll_count,
            "estimated_completion_seconds": estimated_completion_time
        }
        
        self.structured_logger.log(
            LogLevel.INFO,
            f"任务进度变化: {task_id} +{progress_delta:.2f}%",
            category=LogCategory.PERFORMANCE,
            context=context,
            trace_id=trace_id,
            algorithm_type=algorithm_type
        )
    
    def _analyze_training_logs(
        self,
        task_id: str,
        logs: List[str],
        trace_id: str,
        algorithm_type: Optional[AlgorithmType] = None
    ) -> None:
        """
        分析训练日志中的关键信息
        
        Args:
            task_id: 任务ID
            logs: 训练日志列表
            trace_id: 追踪ID
            algorithm_type: 算法类型
        """
        import re
        
        metrics_found = {}
        errors_found = []
        warnings_found = []
        
        for log_entry in logs:
            # 提取数值指标 (例如: loss=0.123, accuracy=0.95)
            metric_matches = re.findall(r'(\w+)=([0-9.]+)', log_entry)
            for metric_name, metric_value in metric_matches:
                try:
                    metrics_found[metric_name] = float(metric_value)
                except ValueError:
                    pass
            
            # 检测错误信息
            if any(keyword in log_entry.lower() for keyword in ['error', 'exception', 'failed']):
                errors_found.append(log_entry)
            
            # 检测警告信息
            if any(keyword in log_entry.lower() for keyword in ['warning', 'warn']):
                warnings_found.append(log_entry)
        
        # 记录发现的指标
        if metrics_found:
            self.log_task_metrics_update(
                task_id, metrics_found, trace_id, algorithm_type
            )
        
        # 记录错误和警告
        if errors_found or warnings_found:
            context = {
                "task_id": task_id,
                "errors_count": len(errors_found),
                "warnings_count": len(warnings_found),
                "errors": errors_found[:5],  # 只记录前5个错误
                "warnings": warnings_found[:5]  # 只记录前5个警告
            }
            
            self.structured_logger.log(
                LogLevel.WARNING if errors_found else LogLevel.INFO,
                f"训练日志分析: {task_id} - {len(errors_found)}个错误, {len(warnings_found)}个警告",
                category=LogCategory.AUDIT,
                context=context,
                trace_id=trace_id,
                algorithm_type=algorithm_type
            )


# 全局异步任务日志记录器实例
_global_async_task_logger = None

def get_async_task_logger() -> AsyncTaskLogger:
    """
    获取异步任务日志记录器实例
    
    Returns:
        AsyncTaskLogger: 异步任务日志记录器
    """
    global _global_async_task_logger
    if _global_async_task_logger is None:
        from algorithm.logging import get_structured_logger
        structured_logger = get_structured_logger(__name__)
        _global_async_task_logger = AsyncTaskLogger(structured_logger)
    return _global_async_task_logger