"""
Progress Tracking Service

Provides comprehensive progress tracking for asynchronous algorithm tasks
including real-time progress monitoring, training log streaming, and metrics collection.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, List, AsyncGenerator
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from algorithm.models import TaskStatus, AsyncTaskResponse, AlgorithmType
from algorithm.logging.async_task_logger import AsyncTaskLogger
from algorithm.logging.structured_logger import StructuredLogger, LogCategory, LogLevel


@dataclass
class ProgressSnapshot:
    """进度快照"""
    timestamp: datetime
    progress_percent: float
    current_step: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    logs: List[str] = field(default_factory=list)
    estimated_remaining_seconds: Optional[float] = None


@dataclass
class TaskProgressSummary:
    """任务进度摘要"""
    task_id: str
    algorithm_type: str
    start_time: datetime
    current_progress: float
    total_snapshots: int
    average_progress_rate: float
    estimated_completion_time: Optional[datetime]
    current_metrics: Dict[str, Any] = field(default_factory=dict)
    recent_logs: List[str] = field(default_factory=list)


class ProgressTracker:
    """进度跟踪器"""
    
    def __init__(
        self,
        async_task_logger: AsyncTaskLogger,
        structured_logger: StructuredLogger
    ):
        """
        初始化进度跟踪器
        
        Args:
            async_task_logger: 异步任务日志记录器
            structured_logger: 结构化日志记录器
        """
        self.logger = logging.getLogger(__name__)
        self.async_task_logger = async_task_logger
        self.structured_logger = structured_logger
        
        # 进度快照存储
        self._progress_snapshots: Dict[str, List[ProgressSnapshot]] = {}
        
        # 任务摘要缓存
        self._task_summaries: Dict[str, TaskProgressSummary] = {}
        
        # 实时流式传输订阅者
        self._streaming_subscribers: Dict[str, List[AsyncGenerator]] = {}
        
        # 配置参数
        self.max_snapshots_per_task = 1000
        self.progress_rate_window_minutes = 5
        self.cleanup_interval_hours = 24
    
    async def start_tracking(
        self,
        task_id: str,
        algorithm_type: AlgorithmType,
        trace_id: str
    ) -> None:
        """
        开始跟踪任务进度
        
        Args:
            task_id: 任务ID
            algorithm_type: 算法类型
            trace_id: 追踪ID
        """
        self.logger.info(f"开始跟踪任务进度: {task_id}")
        
        try:
            # 初始化进度快照列表
            self._progress_snapshots[task_id] = []
            
            # 创建任务摘要
            self._task_summaries[task_id] = TaskProgressSummary(
                task_id=task_id,
                algorithm_type=algorithm_type.value,
                start_time=datetime.utcnow(),
                current_progress=0.0,
                total_snapshots=0,
                average_progress_rate=0.0,
                estimated_completion_time=None
            )
            
            # 初始化流式订阅者列表
            self._streaming_subscribers[task_id] = []
            
            # 记录跟踪开始
            self.structured_logger.log(
                LogLevel.INFO,
                f"进度跟踪开始: {task_id}",
                category=LogCategory.SYSTEM,
                context={
                    "task_id": task_id,
                    "algorithm_type": algorithm_type.value,
                    "tracking_started": True
                },
                trace_id=trace_id,
                algorithm_type=algorithm_type
            )
            
        except Exception as e:
            self.logger.error(f"开始跟踪任务进度失败: {str(e)}")
            raise
    
    async def update_progress(
        self,
        task_id: str,
        progress: Dict[str, Any],
        logs: Optional[List[str]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ) -> None:
        """
        更新任务进度
        
        Args:
            task_id: 任务ID
            progress: 进度信息
            logs: 训练日志
            metrics: 指标数据
            trace_id: 追踪ID
        """
        try:
            if task_id not in self._progress_snapshots:
                self.logger.warning(f"任务未开始跟踪: {task_id}")
                return
            
            # 创建进度快照
            progress_percent = progress.get("percent", progress.get("progress", 0))
            current_step = progress.get("step", progress.get("current_step", "unknown"))
            
            snapshot = ProgressSnapshot(
                timestamp=datetime.utcnow(),
                progress_percent=progress_percent,
                current_step=current_step,
                metrics=metrics or {},
                logs=logs or [],
                estimated_remaining_seconds=progress.get("estimated_remaining_seconds")
            )
            
            # 添加快照
            self._progress_snapshots[task_id].append(snapshot)
            
            # 限制快照数量
            if len(self._progress_snapshots[task_id]) > self.max_snapshots_per_task:
                self._progress_snapshots[task_id] = self._progress_snapshots[task_id][-500:]
            
            # 更新任务摘要
            await self._update_task_summary(task_id, snapshot)
            
            # 流式传输进度更新
            await self._stream_progress_update(task_id, snapshot, trace_id)
            
            self.logger.debug(f"进度更新: {task_id} - {progress_percent}%")
            
        except Exception as e:
            self.logger.error(f"更新任务进度失败: {str(e)}")
    
    async def _update_task_summary(
        self,
        task_id: str,
        snapshot: ProgressSnapshot
    ) -> None:
        """
        更新任务摘要
        
        Args:
            task_id: 任务ID
            snapshot: 进度快照
        """
        try:
            if task_id not in self._task_summaries:
                return
            
            summary = self._task_summaries[task_id]
            snapshots = self._progress_snapshots[task_id]
            
            # 更新基本信息
            summary.current_progress = snapshot.progress_percent
            summary.total_snapshots = len(snapshots)
            summary.current_metrics = snapshot.metrics
            summary.recent_logs = snapshot.logs[-10:] if snapshot.logs else summary.recent_logs[-10:]
            
            # 计算平均进度率
            if len(snapshots) >= 2:
                # 使用最近的快照计算进度率
                window_start = datetime.utcnow() - timedelta(minutes=self.progress_rate_window_minutes)
                recent_snapshots = [s for s in snapshots if s.timestamp >= window_start]
                
                if len(recent_snapshots) >= 2:
                    time_diff = (recent_snapshots[-1].timestamp - recent_snapshots[0].timestamp).total_seconds()
                    progress_diff = recent_snapshots[-1].progress_percent - recent_snapshots[0].progress_percent
                    
                    if time_diff > 0:
                        summary.average_progress_rate = progress_diff / time_diff  # 每秒进度
                        
                        # 估算完成时间
                        if summary.average_progress_rate > 0:
                            remaining_progress = 100 - summary.current_progress
                            remaining_seconds = remaining_progress / summary.average_progress_rate
                            summary.estimated_completion_time = datetime.utcnow() + timedelta(seconds=remaining_seconds)
            
        except Exception as e:
            self.logger.error(f"更新任务摘要失败: {str(e)}")
    
    async def _stream_progress_update(
        self,
        task_id: str,
        snapshot: ProgressSnapshot,
        trace_id: Optional[str] = None
    ) -> None:
        """
        流式传输进度更新
        
        Args:
            task_id: 任务ID
            snapshot: 进度快照
            trace_id: 追踪ID
        """
        try:
            if task_id not in self._streaming_subscribers:
                return
            
            # 构建流式更新数据
            update_data = {
                "task_id": task_id,
                "timestamp": snapshot.timestamp.isoformat(),
                "progress_percent": snapshot.progress_percent,
                "current_step": snapshot.current_step,
                "metrics": snapshot.metrics,
                "logs": snapshot.logs,
                "estimated_remaining_seconds": snapshot.estimated_remaining_seconds
            }
            
            # 发送给所有订阅者
            subscribers = self._streaming_subscribers[task_id].copy()
            for subscriber in subscribers:
                try:
                    await subscriber.asend(update_data)
                except Exception as e:
                    self.logger.warning(f"流式传输失败，移除订阅者: {str(e)}")
                    self._streaming_subscribers[task_id].remove(subscriber)
            
            # 记录流式传输事件
            if trace_id:
                self.structured_logger.log(
                    LogLevel.DEBUG,
                    f"进度流式传输: {task_id}",
                    category=LogCategory.SYSTEM,
                    context={
                        "task_id": task_id,
                        "progress_percent": snapshot.progress_percent,
                        "subscribers_count": len(subscribers),
                        "streaming_update": True
                    },
                    trace_id=trace_id
                )
            
        except Exception as e:
            self.logger.error(f"流式传输进度更新失败: {str(e)}")
    
    async def subscribe_to_progress(
        self,
        task_id: str
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        订阅任务进度更新
        
        Args:
            task_id: 任务ID
            
        Yields:
            Dict[str, Any]: 进度更新数据
        """
        if task_id not in self._streaming_subscribers:
            self._streaming_subscribers[task_id] = []
        
        # 创建异步生成器
        queue = asyncio.Queue()
        
        async def generator():
            try:
                while True:
                    update = await queue.get()
                    if update is None:  # 结束信号
                        break
                    yield update
            except Exception as e:
                self.logger.error(f"进度订阅生成器异常: {str(e)}")
        
        # 添加到订阅者列表
        gen = generator()
        self._streaming_subscribers[task_id].append(gen)
        
        try:
            async for update in gen:
                yield update
        finally:
            # 清理订阅
            if gen in self._streaming_subscribers.get(task_id, []):
                self._streaming_subscribers[task_id].remove(gen)
    
    def get_task_progress_summary(self, task_id: str) -> Optional[TaskProgressSummary]:
        """
        获取任务进度摘要
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[TaskProgressSummary]: 进度摘要
        """
        return self._task_summaries.get(task_id)
    
    def get_progress_snapshots(
        self,
        task_id: str,
        limit: Optional[int] = None
    ) -> List[ProgressSnapshot]:
        """
        获取进度快照
        
        Args:
            task_id: 任务ID
            limit: 限制返回数量
            
        Returns:
            List[ProgressSnapshot]: 进度快照列表
        """
        snapshots = self._progress_snapshots.get(task_id, [])
        if limit:
            return snapshots[-limit:]
        return snapshots
    
    def get_progress_analytics(self, task_id: str) -> Dict[str, Any]:
        """
        获取进度分析数据
        
        Args:
            task_id: 任务ID
            
        Returns:
            Dict[str, Any]: 分析数据
        """
        try:
            snapshots = self._progress_snapshots.get(task_id, [])
            summary = self._task_summaries.get(task_id)
            
            if not snapshots or not summary:
                return {}
            
            # 计算统计信息
            progress_values = [s.progress_percent for s in snapshots]
            
            analytics = {
                "task_id": task_id,
                "total_snapshots": len(snapshots),
                "progress_statistics": {
                    "min_progress": min(progress_values) if progress_values else 0,
                    "max_progress": max(progress_values) if progress_values else 0,
                    "current_progress": summary.current_progress,
                    "average_progress_rate": summary.average_progress_rate
                },
                "time_statistics": {
                    "start_time": summary.start_time.isoformat(),
                    "elapsed_seconds": (datetime.utcnow() - summary.start_time).total_seconds(),
                    "estimated_completion": summary.estimated_completion_time.isoformat() if summary.estimated_completion_time else None
                },
                "metrics_summary": summary.current_metrics,
                "recent_logs_count": len(summary.recent_logs)
            }
            
            # 计算进度趋势
            if len(snapshots) >= 5:
                recent_snapshots = snapshots[-5:]
                progress_trend = []
                for i in range(1, len(recent_snapshots)):
                    time_diff = (recent_snapshots[i].timestamp - recent_snapshots[i-1].timestamp).total_seconds()
                    progress_diff = recent_snapshots[i].progress_percent - recent_snapshots[i-1].progress_percent
                    if time_diff > 0:
                        progress_trend.append(progress_diff / time_diff)
                
                if progress_trend:
                    analytics["progress_trend"] = {
                        "average_rate": sum(progress_trend) / len(progress_trend),
                        "is_accelerating": progress_trend[-1] > progress_trend[0] if len(progress_trend) > 1 else False
                    }
            
            return analytics
            
        except Exception as e:
            self.logger.error(f"获取进度分析数据失败: {str(e)}")
            return {}
    
    async def stop_tracking(self, task_id: str, trace_id: Optional[str] = None) -> None:
        """
        停止跟踪任务进度
        
        Args:
            task_id: 任务ID
            trace_id: 追踪ID
        """
        try:
            # 清理流式订阅者
            if task_id in self._streaming_subscribers:
                subscribers = self._streaming_subscribers[task_id]
                for subscriber in subscribers:
                    try:
                        await subscriber.aclose()
                    except Exception:
                        pass
                del self._streaming_subscribers[task_id]
            
            # 记录跟踪停止
            if trace_id:
                summary = self._task_summaries.get(task_id)
                self.structured_logger.log(
                    LogLevel.INFO,
                    f"进度跟踪停止: {task_id}",
                    category=LogCategory.SYSTEM,
                    context={
                        "task_id": task_id,
                        "final_progress": summary.current_progress if summary else 0,
                        "total_snapshots": summary.total_snapshots if summary else 0,
                        "tracking_stopped": True
                    },
                    trace_id=trace_id
                )
            
            self.logger.info(f"停止跟踪任务进度: {task_id}")
            
        except Exception as e:
            self.logger.error(f"停止跟踪任务进度失败: {str(e)}")
    
    async def cleanup_old_data(self, max_age_hours: int = 24) -> int:
        """
        清理旧的进度数据
        
        Args:
            max_age_hours: 最大保留时间（小时）
            
        Returns:
            int: 清理的任务数量
        """
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            tasks_to_cleanup = []
            
            for task_id, summary in self._task_summaries.items():
                if summary.start_time < cutoff_time:
                    tasks_to_cleanup.append(task_id)
            
            # 清理数据
            for task_id in tasks_to_cleanup:
                self._progress_snapshots.pop(task_id, None)
                self._task_summaries.pop(task_id, None)
                self._streaming_subscribers.pop(task_id, None)
            
            self.logger.info(f"清理了 {len(tasks_to_cleanup)} 个任务的进度数据")
            return len(tasks_to_cleanup)
            
        except Exception as e:
            self.logger.error(f"清理旧进度数据失败: {str(e)}")
            return 0


# 全局进度跟踪器实例
_global_progress_tracker = None

def get_progress_tracker() -> ProgressTracker:
    """
    获取进度跟踪器实例
    
    Returns:
        ProgressTracker: 进度跟踪器
    """
    global _global_progress_tracker
    if _global_progress_tracker is None:
        from algorithm.logging import get_async_task_logger, get_structured_logger
        async_task_logger = get_async_task_logger()
        structured_logger = get_structured_logger(__name__)
        _global_progress_tracker = ProgressTracker(async_task_logger, structured_logger)
    return _global_progress_tracker