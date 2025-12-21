"""
Monitoring Integration

Provides comprehensive monitoring capabilities including metrics collection,
health checks, performance monitoring, and integration with monitoring systems.
"""

import logging
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from enum import Enum

from algorithm.logging.structured_logger import StructuredLogger, MetricType, LogLevel, LogCategory
from algorithm.logging.async_task_logger import AsyncTaskLogger
from algorithm.models import AlgorithmType


class HealthStatus(str, Enum):
    """健康状态枚举"""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass
class ComponentHealth:
    """组件健康状态"""
    name: str
    status: HealthStatus
    message: str
    last_check: datetime
    metrics: Optional[Dict[str, Any]] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class ServiceMetrics:
    """服务指标"""
    timestamp: datetime
    request_count: int
    success_count: int
    error_count: int
    average_response_time_ms: float
    active_tasks: int
    memory_usage_mb: float
    cpu_usage_percent: float


class MonitoringIntegration:
    """监控集成类"""
    
    def __init__(
        self,
        structured_logger: StructuredLogger,
        async_task_logger: AsyncTaskLogger,
        service_name: str = "algorithm-integration-service"
    ):
        """
        初始化监控集成
        
        Args:
            structured_logger: 结构化日志记录器
            async_task_logger: 异步任务日志记录器
            service_name: 服务名称
        """
        self.logger = logging.getLogger(__name__)
        self.structured_logger = structured_logger
        self.async_task_logger = async_task_logger
        self.service_name = service_name
        
        # 组件健康状态缓存
        self._component_health: Dict[str, ComponentHealth] = {}
        
        # 服务指标历史
        self._metrics_history: List[ServiceMetrics] = []
        self._max_history_size = 1000
        
        # 性能阈值配置
        self._performance_thresholds = {
            "response_time_ms": 5000,  # 5秒
            "error_rate_percent": 5.0,  # 5%
            "memory_usage_mb": 1024,   # 1GB
            "cpu_usage_percent": 80.0,  # 80%
            "active_tasks": 50         # 50个并发任务
        }
        
        # 告警状态
        self._alert_states: Dict[str, Dict[str, Any]] = {}
        
        # 最后一次健康检查时间
        self._last_health_check = datetime.utcnow()
    
    def register_component(
        self,
        component_name: str,
        health_check_func: Optional[callable] = None
    ) -> None:
        """
        注册组件进行监控
        
        Args:
            component_name: 组件名称
            health_check_func: 健康检查函数
        """
        self._component_health[component_name] = ComponentHealth(
            name=component_name,
            status=HealthStatus.UNKNOWN,
            message="未检查",
            last_check=datetime.utcnow()
        )
        
        self.structured_logger.log(
            LogLevel.INFO,
            f"注册监控组件: {component_name}",
            category=LogCategory.SYSTEM,
            context={"component_name": component_name}
        )
    
    async def check_component_health(
        self,
        component_name: str,
        health_check_func: Optional[callable] = None
    ) -> ComponentHealth:
        """
        检查组件健康状态
        
        Args:
            component_name: 组件名称
            health_check_func: 健康检查函数
            
        Returns:
            ComponentHealth: 组件健康状态
        """
        start_time = time.time()
        
        try:
            if health_check_func:
                # 执行自定义健康检查
                is_healthy = await health_check_func() if callable(health_check_func) else True
                status = HealthStatus.HEALTHY if is_healthy else HealthStatus.CRITICAL
                message = "健康检查通过" if is_healthy else "健康检查失败"
            else:
                # 默认健康检查（组件是否存在）
                status = HealthStatus.HEALTHY if component_name in self._component_health else HealthStatus.CRITICAL
                message = "组件正常" if status == HealthStatus.HEALTHY else "组件不存在"
            
            check_time_ms = (time.time() - start_time) * 1000
            
            # 更新组件健康状态
            health = ComponentHealth(
                name=component_name,
                status=status,
                message=message,
                last_check=datetime.utcnow(),
                metrics={"check_time_ms": check_time_ms}
            )
            
            self._component_health[component_name] = health
            
            # 记录健康检查日志
            self.structured_logger.log(
                LogLevel.INFO if status == HealthStatus.HEALTHY else LogLevel.WARNING,
                f"组件健康检查: {component_name} - {status.value}",
                category=LogCategory.SYSTEM,
                context={
                    "component_name": component_name,
                    "status": status.value,
                    "message": message,
                    "check_time_ms": check_time_ms
                },
                metrics={"health_check_duration_ms": check_time_ms}
            )
            
            return health
            
        except Exception as e:
            check_time_ms = (time.time() - start_time) * 1000
            
            # 健康检查异常
            health = ComponentHealth(
                name=component_name,
                status=HealthStatus.CRITICAL,
                message=f"健康检查异常: {str(e)}",
                last_check=datetime.utcnow(),
                metrics={"check_time_ms": check_time_ms},
                details={"error": str(e)}
            )
            
            self._component_health[component_name] = health
            
            # 记录异常日志
            self.structured_logger.log(
                LogLevel.ERROR,
                f"组件健康检查异常: {component_name}",
                category=LogCategory.ERROR,
                context={
                    "component_name": component_name,
                    "error": str(e),
                    "check_time_ms": check_time_ms
                },
                error_code="HEALTH_CHECK_FAILED"
            )
            
            return health
    
    async def perform_full_health_check(self) -> Dict[str, Any]:
        """
        执行完整的健康检查
        
        Returns:
            Dict[str, Any]: 完整的健康检查报告
        """
        start_time = time.time()
        
        # 检查所有注册的组件
        component_results = {}
        overall_status = HealthStatus.HEALTHY
        
        for component_name in self._component_health.keys():
            health = await self.check_component_health(component_name)
            component_results[component_name] = asdict(health)
            
            # 更新整体状态
            if health.status == HealthStatus.CRITICAL:
                overall_status = HealthStatus.CRITICAL
            elif health.status == HealthStatus.WARNING and overall_status != HealthStatus.CRITICAL:
                overall_status = HealthStatus.WARNING
        
        # 获取业务指标
        business_metrics = self.structured_logger.get_business_metrics()
        task_stats = self.async_task_logger.get_task_statistics()
        
        # 计算健康分数
        health_score = self._calculate_health_score(component_results, business_metrics, task_stats)
        
        check_duration_ms = (time.time() - start_time) * 1000
        
        health_report = {
            "service": self.service_name,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "overall_status": overall_status.value,
            "health_score": health_score,
            "check_duration_ms": check_duration_ms,
            "components": component_results,
            "business_metrics": business_metrics,
            "task_statistics": task_stats,
            "performance_thresholds": self._performance_thresholds,
            "alerts": self._get_active_alerts()
        }
        
        # 记录健康检查完成日志
        self.structured_logger.log(
            LogLevel.INFO,
            f"完整健康检查完成: {overall_status.value}",
            category=LogCategory.SYSTEM,
            context={
                "overall_status": overall_status.value,
                "health_score": health_score,
                "component_count": len(component_results),
                "check_duration_ms": check_duration_ms
            },
            metrics={
                "health_check_score": health_score,
                "health_check_duration_ms": check_duration_ms
            }
        )
        
        self._last_health_check = datetime.utcnow()
        return health_report
    
    def collect_service_metrics(self) -> ServiceMetrics:
        """
        收集服务指标
        
        Returns:
            ServiceMetrics: 服务指标
        """
        try:
            import psutil
            import os
            
            # 获取系统资源使用情况
            process = psutil.Process(os.getpid())
            memory_usage_mb = process.memory_info().rss / 1024 / 1024
            cpu_usage_percent = process.cpu_percent()
            
        except ImportError:
            # 如果psutil不可用，使用默认值
            memory_usage_mb = 0.0
            cpu_usage_percent = 0.0
        
        # 获取业务指标
        business_metrics = self.structured_logger.get_business_metrics()
        task_stats = self.async_task_logger.get_task_statistics()
        
        # 计算平均响应时间
        performance_metrics = self.structured_logger.get_performance_metrics_summary()
        avg_response_time = 0.0
        if "algorithm_execution_time_ms" in performance_metrics:
            avg_response_time = performance_metrics["algorithm_execution_time_ms"].get("avg", 0.0)
        
        metrics = ServiceMetrics(
            timestamp=datetime.utcnow(),
            request_count=business_metrics.get("algorithm_requests", 0),
            success_count=business_metrics.get("successful_executions", 0),
            error_count=business_metrics.get("failed_executions", 0),
            average_response_time_ms=avg_response_time,
            active_tasks=task_stats.get("active_tasks", 0),
            memory_usage_mb=memory_usage_mb,
            cpu_usage_percent=cpu_usage_percent
        )
        
        # 添加到历史记录
        self._metrics_history.append(metrics)
        if len(self._metrics_history) > self._max_history_size:
            self._metrics_history = self._metrics_history[-self._max_history_size//2:]
        
        # 检查性能阈值
        self._check_performance_thresholds(metrics)
        
        # 记录指标日志
        self.structured_logger.log(
            LogLevel.INFO,
            "服务指标收集完成",
            category=LogCategory.PERFORMANCE,
            context=asdict(metrics),
            metrics={
                "request_count": metrics.request_count,
                "success_rate": metrics.success_count / max(metrics.request_count, 1),
                "error_rate": metrics.error_count / max(metrics.request_count, 1),
                "memory_usage_mb": metrics.memory_usage_mb,
                "cpu_usage_percent": metrics.cpu_usage_percent,
                "active_tasks": metrics.active_tasks
            }
        )
        
        return metrics
    
    def _calculate_health_score(
        self,
        component_results: Dict[str, Any],
        business_metrics: Dict[str, Any],
        task_stats: Dict[str, Any]
    ) -> float:
        """
        计算健康分数 (0-100)
        
        Args:
            component_results: 组件检查结果
            business_metrics: 业务指标
            task_stats: 任务统计
            
        Returns:
            float: 健康分数
        """
        score = 100.0
        
        # 组件健康状态权重 (40%)
        component_score = 0.0
        if component_results:
            healthy_components = sum(1 for comp in component_results.values() 
                                   if comp["status"] == HealthStatus.HEALTHY.value)
            component_score = (healthy_components / len(component_results)) * 40
        
        # 错误率权重 (30%)
        error_rate_score = 30.0
        total_requests = business_metrics.get("algorithm_requests", 0)
        if total_requests > 0:
            error_rate = business_metrics.get("failed_executions", 0) / total_requests
            if error_rate > 0.1:  # 10%以上错误率
                error_rate_score = max(0, 30 - (error_rate * 300))
        
        # 任务成功率权重 (20%)
        task_score = 20.0
        total_tasks = task_stats.get("total_tasks", 0)
        if total_tasks > 0:
            success_rate = task_stats.get("completed_tasks", 0) / total_tasks
            task_score = success_rate * 20
        
        # 响应时间权重 (10%)
        response_time_score = 10.0
        avg_response_time = business_metrics.get("average_execution_time", 0)
        if avg_response_time > self._performance_thresholds["response_time_ms"]:
            response_time_score = max(0, 10 - (avg_response_time / 1000))
        
        total_score = component_score + error_rate_score + task_score + response_time_score
        return min(100.0, max(0.0, total_score))
    
    def _check_performance_thresholds(self, metrics: ServiceMetrics) -> None:
        """
        检查性能阈值并生成告警
        
        Args:
            metrics: 服务指标
        """
        alerts = []
        
        # 检查响应时间
        if metrics.average_response_time_ms > self._performance_thresholds["response_time_ms"]:
            alerts.append({
                "type": "response_time_high",
                "severity": "warning",
                "message": f"平均响应时间过高: {metrics.average_response_time_ms:.2f}ms",
                "threshold": self._performance_thresholds["response_time_ms"],
                "current_value": metrics.average_response_time_ms
            })
        
        # 检查错误率
        if metrics.request_count > 0:
            error_rate = (metrics.error_count / metrics.request_count) * 100
            if error_rate > self._performance_thresholds["error_rate_percent"]:
                alerts.append({
                    "type": "error_rate_high",
                    "severity": "critical",
                    "message": f"错误率过高: {error_rate:.2f}%",
                    "threshold": self._performance_thresholds["error_rate_percent"],
                    "current_value": error_rate
                })
        
        # 检查内存使用
        if metrics.memory_usage_mb > self._performance_thresholds["memory_usage_mb"]:
            alerts.append({
                "type": "memory_usage_high",
                "severity": "warning",
                "message": f"内存使用过高: {metrics.memory_usage_mb:.2f}MB",
                "threshold": self._performance_thresholds["memory_usage_mb"],
                "current_value": metrics.memory_usage_mb
            })
        
        # 检查CPU使用
        if metrics.cpu_usage_percent > self._performance_thresholds["cpu_usage_percent"]:
            alerts.append({
                "type": "cpu_usage_high",
                "severity": "warning",
                "message": f"CPU使用率过高: {metrics.cpu_usage_percent:.2f}%",
                "threshold": self._performance_thresholds["cpu_usage_percent"],
                "current_value": metrics.cpu_usage_percent
            })
        
        # 检查活跃任务数
        if metrics.active_tasks > self._performance_thresholds["active_tasks"]:
            alerts.append({
                "type": "active_tasks_high",
                "severity": "warning",
                "message": f"活跃任务数过多: {metrics.active_tasks}",
                "threshold": self._performance_thresholds["active_tasks"],
                "current_value": metrics.active_tasks
            })
        
        # 处理告警
        for alert in alerts:
            self._handle_alert(alert)
    
    def _handle_alert(self, alert: Dict[str, Any]) -> None:
        """
        处理告警
        
        Args:
            alert: 告警信息
        """
        alert_key = alert["type"]
        current_time = datetime.utcnow()
        
        # 检查是否是新告警或状态变化
        if alert_key not in self._alert_states:
            # 新告警
            self._alert_states[alert_key] = {
                "first_occurrence": current_time,
                "last_occurrence": current_time,
                "count": 1,
                "severity": alert["severity"],
                "active": True
            }
            
            # 记录告警日志
            self.structured_logger.log(
                LogLevel.WARNING if alert["severity"] == "warning" else LogLevel.ERROR,
                f"性能告警触发: {alert['message']}",
                category=LogCategory.SYSTEM,
                context={
                    "alert_type": alert["type"],
                    "severity": alert["severity"],
                    "threshold": alert["threshold"],
                    "current_value": alert["current_value"],
                    "message": alert["message"]
                },
                error_code=f"PERFORMANCE_ALERT_{alert['type'].upper()}"
            )
        else:
            # 更新现有告警
            self._alert_states[alert_key]["last_occurrence"] = current_time
            self._alert_states[alert_key]["count"] += 1
            self._alert_states[alert_key]["active"] = True
    
    def _get_active_alerts(self) -> List[Dict[str, Any]]:
        """
        获取活跃告警列表
        
        Returns:
            List[Dict[str, Any]]: 活跃告警列表
        """
        active_alerts = []
        current_time = datetime.utcnow()
        
        for alert_type, alert_state in self._alert_states.items():
            if alert_state["active"]:
                # 检查告警是否过期（5分钟无新发生）
                if (current_time - alert_state["last_occurrence"]).total_seconds() > 300:
                    alert_state["active"] = False
                else:
                    active_alerts.append({
                        "type": alert_type,
                        "severity": alert_state["severity"],
                        "first_occurrence": alert_state["first_occurrence"].isoformat() + "Z",
                        "last_occurrence": alert_state["last_occurrence"].isoformat() + "Z",
                        "count": alert_state["count"]
                    })
        
        return active_alerts
    
    def get_metrics_history(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        获取指标历史数据
        
        Args:
            hours: 获取最近几小时的数据
            
        Returns:
            List[Dict[str, Any]]: 指标历史数据
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        filtered_metrics = [
            asdict(metric) for metric in self._metrics_history
            if metric.timestamp >= cutoff_time
        ]
        
        return filtered_metrics
    
    def export_metrics_for_prometheus(self) -> str:
        """
        导出Prometheus格式的指标
        
        Returns:
            str: Prometheus格式的指标数据
        """
        if not self._metrics_history:
            return ""
        
        latest_metrics = self._metrics_history[-1]
        business_metrics = self.structured_logger.get_business_metrics()
        task_stats = self.async_task_logger.get_task_statistics()
        
        prometheus_metrics = []
        
        # 基础指标
        prometheus_metrics.extend([
            f'algorithm_service_requests_total {business_metrics.get("algorithm_requests", 0)}',
            f'algorithm_service_requests_success_total {business_metrics.get("successful_executions", 0)}',
            f'algorithm_service_requests_error_total {business_metrics.get("failed_executions", 0)}',
            f'algorithm_service_response_time_ms {latest_metrics.average_response_time_ms}',
            f'algorithm_service_active_tasks {latest_metrics.active_tasks}',
            f'algorithm_service_memory_usage_mb {latest_metrics.memory_usage_mb}',
            f'algorithm_service_cpu_usage_percent {latest_metrics.cpu_usage_percent}',
        ])
        
        # 任务指标
        prometheus_metrics.extend([
            f'algorithm_service_tasks_total {task_stats.get("total_tasks", 0)}',
            f'algorithm_service_tasks_completed {task_stats.get("completed_tasks", 0)}',
            f'algorithm_service_tasks_failed {task_stats.get("failed_tasks", 0)}',
            f'algorithm_service_tasks_processing {task_stats.get("processing", 0)}',
        ])
        
        # 算法类型指标
        algorithm_counts = business_metrics.get("algorithm_type_counts", {})
        for alg_type, count in algorithm_counts.items():
            prometheus_metrics.append(f'algorithm_service_algorithm_requests{{type="{alg_type}"}} {count}')
        
        return '\n'.join(prometheus_metrics)
    
    def reset_metrics(self) -> None:
        """重置所有指标"""
        self._metrics_history.clear()
        self._alert_states.clear()
        self.structured_logger.reset_metrics()
        
        self.structured_logger.log(
            LogLevel.INFO,
            "监控指标已重置",
            category=LogCategory.SYSTEM
        )


# 全局监控集成实例
_global_monitoring = None

def get_monitoring_integration() -> MonitoringIntegration:
    """
    获取监控集成实例
    
    Returns:
        MonitoringIntegration: 监控集成实例
    """
    global _global_monitoring
    if _global_monitoring is None:
        from algorithm.logging import get_structured_logger, get_async_task_logger
        structured_logger = get_structured_logger(__name__)
        async_task_logger = get_async_task_logger()
        _global_monitoring = MonitoringIntegration(structured_logger, async_task_logger)
    return _global_monitoring