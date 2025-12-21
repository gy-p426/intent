"""
Task Manager Implementation

Manages asynchronous algorithm tasks including creation, status tracking,
polling mechanism, timeout handling, and result retrieval for long-running 
algorithm operations.
"""

import logging
import asyncio
from typing import Dict, Optional, AsyncGenerator, Set, Any, List
from datetime import datetime, timedelta
from algorithm.models import AlgorithmType, TaskStatus, AsyncTaskResponse
from algorithm.interfaces import ITaskManager
from algorithm.logging import get_async_task_logger
from infrastructure.config import get_settings


logger = logging.getLogger(__name__)
async_task_logger = get_async_task_logger()


class TaskManager(ITaskManager):
    """任务管理器实现"""
    
    def __init__(self):
        """初始化任务管理器"""
        # 使用内存存储任务信息（生产环境中应使用数据库）
        self._tasks: Dict[str, Dict] = {}
        # 正在轮询的任务集合
        self._polling_tasks: Set[str] = set()
        # 配置设置
        self.settings = get_settings()
        # 轮询任务的后台任务字典
        self._background_tasks: Dict[str, asyncio.Task] = {}
        
    async def create_task(self, task_id: str, algorithm_type: AlgorithmType, trace_id: Optional[str] = None) -> None:
        """
        创建任务记录
        
        Args:
            task_id: 任务ID
            algorithm_type: 算法类型
            trace_id: 追踪ID
        """
        logger.info(f"创建任务记录: {task_id}, 算法类型: {algorithm_type.value}")
        
        try:
            task_info = {
                "task_id": task_id,
                "algorithm_type": algorithm_type.value,
                "status": "created",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "result": None,
                "error": None,
                "progress": None,
                "trace_id": trace_id
            }
            
            self._tasks[task_id] = task_info
            
            # 记录异步任务创建日志
            if trace_id:
                async_task_logger.log_task_created(task_id, algorithm_type, trace_id)
            
            logger.debug(f"任务记录创建成功: {task_id}")
            
        except Exception as e:
            logger.error(f"创建任务记录失败: {str(e)}")
            raise
    
    async def update_task_status(
        self, 
        task_id: str, 
        status: str, 
        result: Optional[Dict] = None
    ) -> None:
        """
        更新任务状态
        
        Args:
            task_id: 任务ID
            status: 任务状态
            result: 任务结果(可选)
        """
        logger.info(f"更新任务状态: {task_id}, 状态: {status}")
        
        try:
            if task_id not in self._tasks:
                logger.warning(f"任务不存在: {task_id}")
                return
            
            task_info = self._tasks[task_id]
            task_info["status"] = status
            task_info["updated_at"] = datetime.utcnow()
            
            if result is not None:
                task_info["result"] = result
            
            logger.debug(f"任务状态更新成功: {task_id}")
            
        except Exception as e:
            logger.error(f"更新任务状态失败: {str(e)}")
            raise
    
    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[Dict]: 任务状态信息
        """
        logger.debug(f"获取任务状态: {task_id}")
        
        try:
            task_info = self._tasks.get(task_id)
            if task_info:
                # 返回任务信息的副本
                return dict(task_info)
            else:
                logger.warning(f"任务不存在: {task_id}")
                return None
                
        except Exception as e:
            logger.error(f"获取任务状态失败: {str(e)}")
            return None
    
    async def update_task_progress(
        self, 
        task_id: str, 
        progress: Dict
    ) -> None:
        """
        更新任务进度
        
        Args:
            task_id: 任务ID
            progress: 进度信息
        """
        logger.debug(f"更新任务进度: {task_id}")
        
        try:
            if task_id not in self._tasks:
                logger.warning(f"任务不存在: {task_id}")
                return
            
            task_info = self._tasks[task_id]
            task_info["progress"] = progress
            task_info["updated_at"] = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"更新任务进度失败: {str(e)}")
            raise
    
    async def set_task_error(
        self, 
        task_id: str, 
        error: str
    ) -> None:
        """
        设置任务错误信息
        
        Args:
            task_id: 任务ID
            error: 错误信息
        """
        logger.info(f"设置任务错误: {task_id}, 错误: {error}")
        
        try:
            if task_id not in self._tasks:
                logger.warning(f"任务不存在: {task_id}")
                return
            
            task_info = self._tasks[task_id]
            task_info["status"] = "failed"
            task_info["error"] = error
            task_info["updated_at"] = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"设置任务错误失败: {str(e)}")
            raise
    
    async def delete_task(self, task_id: str) -> bool:
        """
        删除任务记录
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否删除成功
        """
        logger.info(f"删除任务记录: {task_id}")
        
        try:
            if task_id in self._tasks:
                del self._tasks[task_id]
                logger.debug(f"任务记录删除成功: {task_id}")
                return True
            else:
                logger.warning(f"任务不存在: {task_id}")
                return False
                
        except Exception as e:
            logger.error(f"删除任务记录失败: {str(e)}")
            return False
    
    async def list_tasks(
        self, 
        algorithm_type: Optional[AlgorithmType] = None,
        status: Optional[str] = None
    ) -> list:
        """
        列出任务
        
        Args:
            algorithm_type: 算法类型过滤器(可选)
            status: 状态过滤器(可选)
            
        Returns:
            list: 任务列表
        """
        logger.debug("列出任务")
        
        try:
            tasks = []
            
            for task_info in self._tasks.values():
                # 应用过滤器
                if algorithm_type and task_info["algorithm_type"] != algorithm_type.value:
                    continue
                
                if status and task_info["status"] != status:
                    continue
                
                tasks.append(dict(task_info))
            
            logger.debug(f"找到 {len(tasks)} 个任务")
            return tasks
            
        except Exception as e:
            logger.error(f"列出任务失败: {str(e)}")
            return []
    
    async def cleanup_old_tasks(self, max_age_hours: int = 24) -> int:
        """
        清理旧任务
        
        Args:
            max_age_hours: 最大保留时间（小时）
            
        Returns:
            int: 清理的任务数量
        """
        logger.info(f"清理超过 {max_age_hours} 小时的旧任务")
        
        try:
            from datetime import timedelta
            
            cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
            tasks_to_delete = []
            
            for task_id, task_info in self._tasks.items():
                if task_info["updated_at"] < cutoff_time:
                    tasks_to_delete.append(task_id)
            
            # 删除旧任务
            for task_id in tasks_to_delete:
                del self._tasks[task_id]
            
            logger.info(f"清理了 {len(tasks_to_delete)} 个旧任务")
            return len(tasks_to_delete)
            
        except Exception as e:
            logger.error(f"清理旧任务失败: {str(e)}")
            return 0
    
    def get_task_count(self) -> int:
        """
        获取任务总数
        
        Returns:
            int: 任务总数
        """
        return len(self._tasks)
    
    def get_task_statistics(self) -> Dict[str, int]:
        """
        获取任务统计信息
        
        Returns:
            Dict[str, int]: 任务统计
        """
        try:
            stats = {
                "total": 0,
                "created": 0,
                "processing": 0,
                "success": 0,
                "failed": 0
            }
            
            for task_info in self._tasks.values():
                stats["total"] += 1
                status = task_info.get("status", "unknown")
                if status in stats:
                    stats[status] += 1
            
            return stats
            
        except Exception as e:
            logger.error(f"获取任务统计失败: {str(e)}")
            return {"total": 0}
    
    async def start_task_polling(
        self, 
        task_id: str, 
        poll_function, 
        timeout_seconds: Optional[int] = None,
        trace_id: Optional[str] = None,
        algorithm_type: Optional[AlgorithmType] = None
    ) -> AsyncGenerator[AsyncTaskResponse, None]:
        """
        开始任务轮询
        
        Args:
            task_id: 任务ID
            poll_function: 轮询函数，应该返回AsyncGenerator[AsyncTaskResponse, None]
            timeout_seconds: 超时时间（秒），如果为None则使用配置中的默认值
            trace_id: 追踪ID
            algorithm_type: 算法类型
            
        Yields:
            AsyncTaskResponse: 任务状态更新
        """
        logger.info(f"开始轮询任务: {task_id}")
        
        if task_id in self._polling_tasks:
            logger.warning(f"任务已在轮询中: {task_id}")
            return
        
        self._polling_tasks.add(task_id)
        timeout = timeout_seconds or self.settings.async_task_max_wait_time
        start_time = datetime.utcnow()
        poll_count = 0
        
        # 记录轮询开始
        if trace_id:
            async_task_logger.log_polling_started(
                task_id, trace_id, self.settings.async_task_poll_interval, timeout
            )
            async_task_logger.log_task_started(task_id, algorithm_type, trace_id)
        
        try:
            # 更新任务状态为处理中
            await self.update_task_status(task_id, TaskStatus.PROCESSING.value)
            
            # 创建超时任务
            timeout_task = asyncio.create_task(self._handle_task_timeout(task_id, timeout))
            
            try:
                # 开始轮询
                async for response in poll_function(task_id):
                    poll_count += 1
                    
                    # 检查是否超时
                    elapsed = (datetime.utcnow() - start_time).total_seconds()
                    if elapsed > timeout:
                        logger.warning(f"任务轮询超时: {task_id}, 耗时: {elapsed}秒")
                        
                        # 记录超时日志
                        if trace_id:
                            async_task_logger.log_task_timeout(task_id, timeout, trace_id, algorithm_type)
                        
                        await self.handle_task_timeout(task_id)
                        yield AsyncTaskResponse(
                            task_id=task_id,
                            status=TaskStatus.FAILED,
                            error=f"任务轮询超时，耗时: {elapsed:.1f}秒"
                        )
                        break
                    
                    # 记录详细的进度更新
                    if response.progress and trace_id:
                        async_task_logger.log_task_progress_update(
                            task_id, response.progress, trace_id, algorithm_type
                        )
                        
                        # 更新任务进度并记录详细信息
                        await self._update_task_progress_detailed(
                            task_id, response.progress, trace_id, algorithm_type
                        )
                    
                    # 记录训练日志和指标
                    if response.logs and trace_id:
                        async_task_logger.log_task_training_logs(
                            task_id, response.logs, trace_id, algorithm_type
                        )
                        
                        # 流式传输训练日志
                        await self._stream_training_logs(
                            task_id, response.logs, trace_id, algorithm_type
                        )
                    
                    # 记录任务指标
                    if hasattr(response, 'metrics') and response.metrics and trace_id:
                        async_task_logger.log_task_metrics_update(
                            task_id, response.metrics, trace_id, algorithm_type
                        )
                        
                        # 流式传输指标更新
                        await self._stream_metrics_update(
                            task_id, response.metrics, trace_id, algorithm_type
                        )
                    
                    # 更新任务进度
                    if response.progress:
                        await self.update_task_progress(task_id, response.progress)
                    
                    # 如果任务失败，处理失败逻辑
                    if response.status == TaskStatus.FAILED:
                        execution_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                        
                        # 记录失败日志
                        if trace_id:
                            async_task_logger.log_task_failed(
                                task_id, response.error or "任务执行失败", 
                                execution_time_ms, trace_id, algorithm_type
                            )
                        
                        await self.handle_task_failure(task_id, response.error or "任务执行失败")
                        yield response
                        break
                    
                    # 如果任务成功，更新最终结果
                    elif response.status == TaskStatus.SUCCESS:
                        execution_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                        
                        # 记录成功日志
                        if trace_id:
                            async_task_logger.log_task_completed(
                                task_id, response.result or {}, 
                                execution_time_ms, trace_id, algorithm_type
                            )
                        
                        await self.update_task_status(task_id, TaskStatus.SUCCESS.value, response.result)
                        yield response
                        break
                    
                    # 处理中状态，继续轮询
                    else:
                        yield response
                        
            finally:
                # 取消超时任务
                if not timeout_task.done():
                    timeout_task.cancel()
                    try:
                        await timeout_task
                    except asyncio.CancelledError:
                        pass
                        
        except Exception as e:
            logger.error(f"任务轮询异常: {task_id}, 错误: {str(e)}")
            execution_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # 记录异常日志
            if trace_id:
                async_task_logger.log_task_failed(
                    task_id, f"轮询异常: {str(e)}", 
                    execution_time_ms, trace_id, algorithm_type
                )
            
            await self.handle_task_failure(task_id, f"轮询异常: {str(e)}")
            yield AsyncTaskResponse(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=f"轮询异常: {str(e)}"
            )
        finally:
            # 记录轮询停止
            total_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            if trace_id:
                async_task_logger.log_polling_stopped(
                    task_id, trace_id, "轮询完成", poll_count, total_time_ms
                )
            
            # 清理轮询状态
            self._polling_tasks.discard(task_id)
            logger.info(f"任务轮询结束: {task_id}")
    
    async def _handle_task_timeout(self, task_id: str, timeout_seconds: int):
        """
        处理任务超时的后台任务
        
        Args:
            task_id: 任务ID
            timeout_seconds: 超时时间（秒）
        """
        try:
            await asyncio.sleep(timeout_seconds)
            if task_id in self._polling_tasks:
                logger.warning(f"任务超时: {task_id}")
                await self.handle_task_timeout(task_id)
        except asyncio.CancelledError:
            # 正常取消，任务在超时前完成
            pass
        except Exception as e:
            logger.error(f"处理任务超时异常: {task_id}, 错误: {str(e)}")
    
    async def handle_task_timeout(self, task_id: str) -> None:
        """
        处理任务超时
        
        Args:
            task_id: 任务ID
        """
        logger.warning(f"处理任务超时: {task_id}")
        
        try:
            if task_id not in self._tasks:
                logger.warning(f"任务不存在: {task_id}")
                return
            
            task_info = self._tasks[task_id]
            task_info["status"] = TaskStatus.FAILED.value
            task_info["error"] = f"任务超时，超过最大等待时间 {self.settings.async_task_max_wait_time} 秒"
            task_info["updated_at"] = datetime.utcnow()
            
            # 从轮询集合中移除
            self._polling_tasks.discard(task_id)
            
            logger.info(f"任务超时处理完成: {task_id}")
            
        except Exception as e:
            logger.error(f"处理任务超时失败: {str(e)}")
            raise
    
    async def handle_task_failure(self, task_id: str, error_message: str) -> None:
        """
        处理任务失败
        
        Args:
            task_id: 任务ID
            error_message: 错误消息
        """
        logger.warning(f"处理任务失败: {task_id}, 错误: {error_message}")
        
        try:
            if task_id not in self._tasks:
                logger.warning(f"任务不存在: {task_id}")
                return
            
            task_info = self._tasks[task_id]
            task_info["status"] = TaskStatus.FAILED.value
            task_info["error"] = error_message
            task_info["updated_at"] = datetime.utcnow()
            
            # 从轮询集合中移除
            self._polling_tasks.discard(task_id)
            
            # 记录失败统计
            self._record_failure_stats(task_id, error_message)
            
            logger.info(f"任务失败处理完成: {task_id}")
            
        except Exception as e:
            logger.error(f"处理任务失败异常: {str(e)}")
            raise
    
    def _record_failure_stats(self, task_id: str, error_message: str) -> None:
        """
        记录失败统计信息
        
        Args:
            task_id: 任务ID
            error_message: 错误消息
        """
        try:
            # 这里可以扩展为更详细的失败统计
            # 例如：按错误类型分类、失败率统计等
            logger.debug(f"记录任务失败统计: {task_id}, 错误类型: {type(error_message).__name__}")
        except Exception as e:
            logger.error(f"记录失败统计异常: {str(e)}")
    
    async def cancel_task(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否取消成功
        """
        logger.info(f"取消任务: {task_id}")
        
        try:
            if task_id not in self._tasks:
                logger.warning(f"任务不存在: {task_id}")
                return False
            
            task_info = self._tasks[task_id]
            
            # 只能取消处理中的任务
            if task_info["status"] not in ["created", "processing"]:
                logger.warning(f"任务状态不允许取消: {task_id}, 状态: {task_info['status']}")
                return False
            
            # 更新任务状态
            task_info["status"] = "cancelled"
            task_info["updated_at"] = datetime.utcnow()
            
            # 从轮询集合中移除
            self._polling_tasks.discard(task_id)
            
            # 取消后台任务
            if task_id in self._background_tasks:
                background_task = self._background_tasks[task_id]
                if not background_task.done():
                    background_task.cancel()
                del self._background_tasks[task_id]
            
            logger.info(f"任务取消成功: {task_id}")
            return True
            
        except Exception as e:
            logger.error(f"取消任务失败: {str(e)}")
            return False
    
    async def is_task_polling(self, task_id: str) -> bool:
        """
        检查任务是否正在轮询
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否正在轮询
        """
        return task_id in self._polling_tasks
    
    async def get_polling_tasks(self) -> list:
        """
        获取正在轮询的任务列表
        
        Returns:
            list: 正在轮询的任务ID列表
        """
        return list(self._polling_tasks)
    
    async def cleanup_completed_tasks(self, max_completed_age_hours: int = 1) -> int:
        """
        清理已完成的任务
        
        Args:
            max_completed_age_hours: 已完成任务的最大保留时间（小时）
            
        Returns:
            int: 清理的任务数量
        """
        logger.info(f"清理超过 {max_completed_age_hours} 小时的已完成任务")
        
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=max_completed_age_hours)
            tasks_to_delete = []
            
            for task_id, task_info in self._tasks.items():
                # 只清理已完成或失败的任务
                if task_info["status"] in ["success", "failed", "cancelled"]:
                    if task_info["updated_at"] < cutoff_time:
                        tasks_to_delete.append(task_id)
            
            # 删除已完成的旧任务
            for task_id in tasks_to_delete:
                del self._tasks[task_id]
                # 确保从轮询集合中移除
                self._polling_tasks.discard(task_id)
                # 清理后台任务
                if task_id in self._background_tasks:
                    del self._background_tasks[task_id]
            
            logger.info(f"清理了 {len(tasks_to_delete)} 个已完成任务")
            return len(tasks_to_delete)
            
        except Exception as e:
            logger.error(f"清理已完成任务失败: {str(e)}")
            return 0
    
    async def _update_task_progress_detailed(
        self,
        task_id: str,
        progress: Dict[str, Any],
        trace_id: str,
        algorithm_type: Optional[AlgorithmType] = None
    ) -> None:
        """
        更新任务进度的详细信息
        
        Args:
            task_id: 任务ID
            progress: 进度信息
            trace_id: 追踪ID
            algorithm_type: 算法类型
        """
        try:
            if task_id not in self._tasks:
                return
            
            task_info = self._tasks[task_id]
            
            # 更新进度信息
            current_progress = progress.get("percent", 0)
            previous_progress = task_info.get("progress", {}).get("percent", 0)
            
            # 计算进度变化
            progress_delta = current_progress - previous_progress
            
            # 增强的进度信息
            enhanced_progress = {
                **progress,
                "progress_delta": progress_delta,
                "updated_at": datetime.utcnow().isoformat(),
                "poll_count": task_info.get("poll_count", 0) + 1,
                "trace_id": trace_id
            }
            
            # 估算剩余时间
            if progress_delta > 0 and current_progress > 0:
                elapsed_time = (datetime.utcnow() - task_info["created_at"]).total_seconds()
                estimated_total_time = elapsed_time * (100 / current_progress)
                estimated_remaining_time = estimated_total_time - elapsed_time
                enhanced_progress["estimated_remaining_seconds"] = max(0, estimated_remaining_time)
            
            task_info["progress"] = enhanced_progress
            task_info["poll_count"] = enhanced_progress["poll_count"]
            task_info["updated_at"] = datetime.utcnow()
            
            logger.debug(f"详细进度更新: {task_id} - {current_progress}% (+{progress_delta}%)")
            
        except Exception as e:
            logger.error(f"更新详细任务进度失败: {str(e)}")
    
    async def _stream_training_logs(
        self,
        task_id: str,
        logs: List[str],
        trace_id: str,
        algorithm_type: Optional[AlgorithmType] = None
    ) -> None:
        """
        流式传输训练日志
        
        Args:
            task_id: 任务ID
            logs: 训练日志列表
            trace_id: 追踪ID
            algorithm_type: 算法类型
        """
        try:
            if task_id not in self._tasks:
                return
            
            task_info = self._tasks[task_id]
            
            # 初始化训练日志历史
            if "training_logs" not in task_info:
                task_info["training_logs"] = []
            
            # 添加新的训练日志
            for log_entry in logs:
                log_record = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "content": log_entry,
                    "trace_id": trace_id
                }
                task_info["training_logs"].append(log_record)
            
            # 限制日志历史大小
            if len(task_info["training_logs"]) > 1000:
                task_info["training_logs"] = task_info["training_logs"][-500:]
            
            # 记录流式传输事件
            async_task_logger.log_task_training_logs(
                task_id, logs, trace_id, algorithm_type
            )
            
            logger.debug(f"流式传输训练日志: {task_id} - {len(logs)}条日志")
            
        except Exception as e:
            logger.error(f"流式传输训练日志失败: {str(e)}")
    
    async def _stream_metrics_update(
        self,
        task_id: str,
        metrics: Dict[str, Any],
        trace_id: str,
        algorithm_type: Optional[AlgorithmType] = None
    ) -> None:
        """
        流式传输指标更新
        
        Args:
            task_id: 任务ID
            metrics: 指标数据
            trace_id: 追踪ID
            algorithm_type: 算法类型
        """
        try:
            if task_id not in self._tasks:
                return
            
            task_info = self._tasks[task_id]
            
            # 初始化指标历史
            if "metrics_history" not in task_info:
                task_info["metrics_history"] = []
            
            # 添加新的指标记录
            metrics_record = {
                "timestamp": datetime.utcnow().isoformat(),
                "metrics": metrics,
                "trace_id": trace_id
            }
            task_info["metrics_history"].append(metrics_record)
            
            # 限制指标历史大小
            if len(task_info["metrics_history"]) > 100:
                task_info["metrics_history"] = task_info["metrics_history"][-50:]
            
            # 更新当前指标
            if "current_metrics" not in task_info:
                task_info["current_metrics"] = {}
            task_info["current_metrics"].update(metrics)
            
            # 记录流式传输事件
            async_task_logger.log_task_metrics_update(
                task_id, metrics, trace_id, algorithm_type
            )
            
            logger.debug(f"流式传输指标更新: {task_id} - {len(metrics)}个指标")
            
        except Exception as e:
            logger.error(f"流式传输指标更新失败: {str(e)}")
    
    async def get_task_detailed_progress(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务的详细进度信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[Dict[str, Any]]: 详细进度信息
        """
        try:
            if task_id not in self._tasks:
                return None
            
            task_info = self._tasks[task_id]
            
            detailed_progress = {
                "task_id": task_id,
                "basic_info": {
                    "algorithm_type": task_info.get("algorithm_type"),
                    "status": task_info.get("status"),
                    "created_at": task_info.get("created_at"),
                    "updated_at": task_info.get("updated_at")
                },
                "progress": task_info.get("progress", {}),
                "current_metrics": task_info.get("current_metrics", {}),
                "training_logs_count": len(task_info.get("training_logs", [])),
                "metrics_history_count": len(task_info.get("metrics_history", [])),
                "poll_count": task_info.get("poll_count", 0)
            }
            
            # 添加最近的训练日志
            training_logs = task_info.get("training_logs", [])
            if training_logs:
                detailed_progress["recent_training_logs"] = training_logs[-5:]
            
            # 添加最近的指标历史
            metrics_history = task_info.get("metrics_history", [])
            if metrics_history:
                detailed_progress["recent_metrics"] = metrics_history[-3:]
            
            return detailed_progress
            
        except Exception as e:
            logger.error(f"获取详细进度信息失败: {str(e)}")
            return None
    
    async def get_task_audit_trail(self, task_id: str) -> List[Dict[str, Any]]:
        """
        获取任务的完整审计跟踪
        
        Args:
            task_id: 任务ID
            
        Returns:
            List[Dict[str, Any]]: 审计跟踪记录
        """
        try:
            # 从异步任务日志记录器获取审计跟踪
            audit_trail = async_task_logger.get_task_audit_trail(task_id)
            
            # 添加任务管理器的内部事件
            if task_id in self._tasks:
                task_info = self._tasks[task_id]
                
                # 添加任务创建事件
                audit_trail.insert(0, {
                    "timestamp": task_info["created_at"].isoformat() + "Z",
                    "event_type": "task_manager_created",
                    "description": f"任务在任务管理器中创建",
                    "context": {
                        "algorithm_type": task_info.get("algorithm_type"),
                        "trace_id": task_info.get("trace_id")
                    }
                })
                
                # 添加状态变更事件
                if task_info.get("status") != "created":
                    audit_trail.append({
                        "timestamp": task_info["updated_at"].isoformat() + "Z",
                        "event_type": "status_changed",
                        "description": f"任务状态变更为: {task_info['status']}",
                        "context": {
                            "new_status": task_info["status"],
                            "poll_count": task_info.get("poll_count", 0)
                        }
                    })
            
            return sorted(audit_trail, key=lambda x: x["timestamp"])
            
        except Exception as e:
            logger.error(f"获取任务审计跟踪失败: {str(e)}")
            return []
    
    async def export_task_execution_report(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        导出任务执行报告
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[Dict[str, Any]]: 完整的任务执行报告
        """
        try:
            if task_id not in self._tasks:
                return None
            
            task_info = self._tasks[task_id]
            
            # 构建完整报告
            execution_report = {
                "task_summary": {
                    "task_id": task_id,
                    "algorithm_type": task_info.get("algorithm_type"),
                    "status": task_info.get("status"),
                    "created_at": task_info.get("created_at"),
                    "updated_at": task_info.get("updated_at"),
                    "trace_id": task_info.get("trace_id")
                },
                "execution_metrics": {
                    "total_polls": task_info.get("poll_count", 0),
                    "current_progress": task_info.get("progress", {}),
                    "current_metrics": task_info.get("current_metrics", {}),
                    "training_logs_count": len(task_info.get("training_logs", [])),
                    "metrics_updates_count": len(task_info.get("metrics_history", []))
                },
                "detailed_progress": await self.get_task_detailed_progress(task_id),
                "audit_trail": await self.get_task_audit_trail(task_id),
                "training_logs": task_info.get("training_logs", []),
                "metrics_history": task_info.get("metrics_history", []),
                "result": task_info.get("result"),
                "error": task_info.get("error"),
                "generated_at": datetime.utcnow().isoformat()
            }
            
            return execution_report
            
        except Exception as e:
            logger.error(f"导出任务执行报告失败: {str(e)}")
            return None
    
    async def get_task_health_status(self) -> Dict[str, Any]:
        """
        获取任务管理器健康状态
        
        Returns:
            Dict[str, Any]: 健康状态信息
        """
        try:
            stats = self.get_task_statistics()
            
            health_status = {
                "status": "healthy",
                "task_statistics": stats,
                "polling_tasks_count": len(self._polling_tasks),
                "background_tasks_count": len(self._background_tasks),
                "polling_tasks": list(self._polling_tasks),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # 检查是否有异常情况
            if stats["failed"] > stats["success"] * 2:  # 失败任务过多
                health_status["status"] = "warning"
                health_status["warning"] = "失败任务数量过多"
            
            if len(self._polling_tasks) > 10:  # 轮询任务过多
                health_status["status"] = "warning" 
                health_status["warning"] = "轮询任务数量过多"
            
            return health_status
            
        except Exception as e:
            logger.error(f"获取任务健康状态失败: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }