"""
Structured Logging Implementation

Provides structured logging capabilities for the algorithm integration service
with performance metrics, business metrics, and comprehensive audit trails.
"""

import json
import logging
import time
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from enum import Enum
from contextlib import contextmanager
from functools import wraps

from algorithm.models import AlgorithmType, StreamingStep


class LogLevel(str, Enum):
    """日志级别枚举"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(str, Enum):
    """日志分类枚举"""
    SYSTEM = "system"
    BUSINESS = "business"
    PERFORMANCE = "performance"
    SECURITY = "security"
    AUDIT = "audit"
    ERROR = "error"


class MetricType(str, Enum):
    """指标类型枚举"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class StructuredLogger:
    """结构化日志记录器"""
    
    def __init__(self, name: str, service_name: str = "algorithm-integration-service"):
        """
        初始化结构化日志记录器
        
        Args:
            name: 日志记录器名称
            service_name: 服务名称
        """
        self.logger = logging.getLogger(name)
        self.service_name = service_name
        self.default_context = {
            "service": service_name,
            "version": "1.0.0"
        }
        
        # 性能指标缓存
        self._metrics_cache: Dict[str, Any] = {}
        
        # 业务指标统计
        self._business_metrics = {
            "algorithm_requests": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "algorithm_type_counts": {},
            "average_execution_time": 0.0,
            "error_counts": {}
        }
    
    def _create_log_entry(
        self,
        level: LogLevel,
        message: str,
        category: LogCategory,
        context: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        step: Optional[StreamingStep] = None,
        algorithm_type: Optional[AlgorithmType] = None,
        execution_time_ms: Optional[float] = None,
        error_code: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建结构化日志条目
        
        Args:
            level: 日志级别
            message: 日志消息
            category: 日志分类
            context: 上下文信息
            metrics: 性能指标
            trace_id: 追踪ID
            step: 处理步骤
            algorithm_type: 算法类型
            execution_time_ms: 执行时间（毫秒）
            error_code: 错误代码
            user_id: 用户ID
            
        Returns:
            Dict[str, Any]: 结构化日志条目
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level.value,
            "message": message,
            "category": category.value,
            **self.default_context
        }
        
        # 添加追踪信息
        if trace_id:
            log_entry["trace_id"] = trace_id
        
        if step:
            log_entry["step"] = step.value
        
        if algorithm_type:
            log_entry["algorithm_type"] = algorithm_type.value
        
        if user_id:
            log_entry["user_id"] = user_id
        
        # 添加性能指标
        if execution_time_ms is not None:
            log_entry["execution_time_ms"] = execution_time_ms
        
        if metrics:
            log_entry["metrics"] = metrics
        
        # 添加错误信息
        if error_code:
            log_entry["error_code"] = error_code
        
        # 添加上下文信息
        if context:
            log_entry["context"] = context
        
        return log_entry
    
    def log(
        self,
        level: LogLevel,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        **kwargs
    ) -> None:
        """
        记录结构化日志
        
        Args:
            level: 日志级别
            message: 日志消息
            category: 日志分类
            **kwargs: 其他参数
        """
        log_entry = self._create_log_entry(level, message, category, **kwargs)
        
        # 使用标准日志记录器输出JSON格式，处理datetime序列化
        def json_serializer(obj):
            if isinstance(obj, datetime):
                return obj.isoformat() + "Z"
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
        
        log_message = json.dumps(log_entry, ensure_ascii=False, separators=(',', ':'), default=json_serializer)
        
        # 根据级别调用相应的日志方法
        if level == LogLevel.DEBUG:
            self.logger.debug(log_message)
        elif level == LogLevel.INFO:
            self.logger.info(log_message)
        elif level == LogLevel.WARNING:
            self.logger.warning(log_message)
        elif level == LogLevel.ERROR:
            self.logger.error(log_message)
        elif level == LogLevel.CRITICAL:
            self.logger.critical(log_message)
    
    def debug(self, message: str, **kwargs) -> None:
        """记录DEBUG级别日志"""
        self.log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs) -> None:
        """记录INFO级别日志"""
        self.log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> None:
        """记录WARNING级别日志"""
        self.log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs) -> None:
        """记录ERROR级别日志"""
        self.log(LogLevel.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs) -> None:
        """记录CRITICAL级别日志"""
        self.log(LogLevel.CRITICAL, message, **kwargs)
    
    def log_algorithm_request(
        self,
        question: str,
        window_id: str,
        session_id: str,
        trace_id: str,
        user_id: Optional[str] = None
    ) -> None:
        """
        记录算法请求日志
        
        Args:
            question: 用户查询
            window_id: 窗口ID
            session_id: 会话ID
            trace_id: 追踪ID
            user_id: 用户ID
        """
        self._business_metrics["algorithm_requests"] += 1
        
        self.log(
            LogLevel.INFO,
            "算法请求开始",
            category=LogCategory.BUSINESS,
            context={
                "question_length": len(question),
                "question_preview": question[:100] + "..." if len(question) > 100 else question,
                "window_id": window_id,
                "session_id": session_id
            },
            trace_id=trace_id,
            user_id=user_id,
            step=StreamingStep.ALGORITHM_IDENTIFICATION
        )
    
    def log_algorithm_identification(
        self,
        algorithm_type: AlgorithmType,
        confidence: Optional[float],
        trace_id: str,
        execution_time_ms: float
    ) -> None:
        """
        记录算法类型识别日志
        
        Args:
            algorithm_type: 识别的算法类型
            confidence: 识别置信度
            trace_id: 追踪ID
            execution_time_ms: 执行时间
        """
        # 更新业务指标
        if algorithm_type.value not in self._business_metrics["algorithm_type_counts"]:
            self._business_metrics["algorithm_type_counts"][algorithm_type.value] = 0
        self._business_metrics["algorithm_type_counts"][algorithm_type.value] += 1
        
        context = {
            "identified_algorithm": algorithm_type.value
        }
        if confidence is not None:
            context["confidence"] = confidence
        
        self.log(
            LogLevel.INFO,
            f"算法类型识别完成: {algorithm_type.value}",
            category=LogCategory.BUSINESS,
            context=context,
            trace_id=trace_id,
            algorithm_type=algorithm_type,
            step=StreamingStep.ALGORITHM_IDENTIFICATION,
            execution_time_ms=execution_time_ms,
            metrics={
                "identification_time_ms": execution_time_ms,
                "confidence_score": confidence
            }
        )
    
    def log_parameter_extraction(
        self,
        algorithm_type: AlgorithmType,
        extracted_columns: List[str],
        parameter_count: int,
        trace_id: str,
        execution_time_ms: float
    ) -> None:
        """
        记录参数提取日志
        
        Args:
            algorithm_type: 算法类型
            extracted_columns: 提取的数据库列
            parameter_count: 参数数量
            trace_id: 追踪ID
            execution_time_ms: 执行时间
        """
        self.log(
            LogLevel.INFO,
            f"参数提取完成: {parameter_count}个参数, {len(extracted_columns)}个列",
            category=LogCategory.BUSINESS,
            context={
                "extracted_columns": extracted_columns,
                "parameter_count": parameter_count
            },
            trace_id=trace_id,
            algorithm_type=algorithm_type,
            step=StreamingStep.PARAMETER_EXTRACTION,
            execution_time_ms=execution_time_ms,
            metrics={
                "extraction_time_ms": execution_time_ms,
                "column_count": len(extracted_columns),
                "parameter_count": parameter_count
            }
        )
    
    def log_sql_generation(
        self,
        sql_statement: str,
        data_rows_count: int,
        trace_id: str,
        execution_time_ms: float
    ) -> None:
        """
        记录SQL生成和执行日志
        
        Args:
            sql_statement: 生成的SQL语句
            data_rows_count: 数据行数
            trace_id: 追踪ID
            execution_time_ms: 执行时间
        """
        self.log(
            LogLevel.INFO,
            f"SQL生成和执行完成: 获取{data_rows_count}行数据",
            category=LogCategory.BUSINESS,
            context={
                "sql_statement": sql_statement,
                "data_rows_count": data_rows_count,
                "sql_length": len(sql_statement)
            },
            trace_id=trace_id,
            step=StreamingStep.SQL_GENERATION,
            execution_time_ms=execution_time_ms,
            metrics={
                "sql_generation_time_ms": execution_time_ms,
                "data_rows_retrieved": data_rows_count,
                "sql_complexity_score": len(sql_statement.split())
            }
        )
    
    def log_algorithm_execution_start(
        self,
        algorithm_type: AlgorithmType,
        data_rows_count: int,
        trace_id: str,
        is_async: bool = False
    ) -> None:
        """
        记录算法执行开始日志
        
        Args:
            algorithm_type: 算法类型
            data_rows_count: 数据行数
            trace_id: 追踪ID
            is_async: 是否异步执行
        """
        self.log(
            LogLevel.INFO,
            f"算法执行开始: {algorithm_type.value}, 数据行数: {data_rows_count}",
            category=LogCategory.BUSINESS,
            context={
                "data_rows_count": data_rows_count,
                "execution_mode": "async" if is_async else "sync"
            },
            trace_id=trace_id,
            algorithm_type=algorithm_type,
            step=StreamingStep.ALGORITHM_EXECUTION,
            metrics={
                "input_data_size": data_rows_count
            }
        )
    
    def log_algorithm_execution_complete(
        self,
        algorithm_type: AlgorithmType,
        success: bool,
        trace_id: str,
        execution_time_ms: float,
        result_size: Optional[int] = None,
        error_message: Optional[str] = None,
        task_id: Optional[str] = None
    ) -> None:
        """
        记录算法执行完成日志
        
        Args:
            algorithm_type: 算法类型
            success: 是否成功
            trace_id: 追踪ID
            execution_time_ms: 执行时间
            result_size: 结果大小
            error_message: 错误消息
            task_id: 任务ID（异步任务）
        """
        # 更新业务指标
        if success:
            self._business_metrics["successful_executions"] += 1
        else:
            self._business_metrics["failed_executions"] += 1
            if error_message:
                error_type = type(error_message).__name__
                if error_type not in self._business_metrics["error_counts"]:
                    self._business_metrics["error_counts"][error_type] = 0
                self._business_metrics["error_counts"][error_type] += 1
        
        # 更新平均执行时间
        total_executions = self._business_metrics["successful_executions"] + self._business_metrics["failed_executions"]
        if total_executions > 0:
            current_avg = self._business_metrics["average_execution_time"]
            self._business_metrics["average_execution_time"] = (
                (current_avg * (total_executions - 1) + execution_time_ms) / total_executions
            )
        
        context = {
            "success": success,
            "execution_time_ms": execution_time_ms
        }
        
        if result_size is not None:
            context["result_size"] = result_size
        
        if error_message:
            context["error_message"] = error_message
        
        if task_id:
            context["task_id"] = task_id
        
        level = LogLevel.INFO if success else LogLevel.ERROR
        message = f"算法执行{'成功' if success else '失败'}: {algorithm_type.value}"
        
        self.log(
            level,
            message,
            category=LogCategory.BUSINESS,
            context=context,
            trace_id=trace_id,
            algorithm_type=algorithm_type,
            step=StreamingStep.ALGORITHM_EXECUTION,
            execution_time_ms=execution_time_ms,
            metrics={
                "algorithm_execution_time_ms": execution_time_ms,
                "result_size": result_size,
                "success_rate": self._business_metrics["successful_executions"] / total_executions if total_executions > 0 else 0
            }
        )
    
    def log_performance_metric(
        self,
        metric_name: str,
        metric_value: Union[int, float],
        metric_type: MetricType,
        trace_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        记录性能指标
        
        Args:
            metric_name: 指标名称
            metric_value: 指标值
            metric_type: 指标类型
            trace_id: 追踪ID
            context: 上下文信息
        """
        self.log(
            LogLevel.INFO,
            f"性能指标: {metric_name} = {metric_value}",
            category=LogCategory.PERFORMANCE,
            context=context,
            trace_id=trace_id,
            metrics={
                "metric_name": metric_name,
                "metric_value": metric_value,
                "metric_type": metric_type.value
            }
        )
        
        # 缓存指标用于聚合
        if metric_name not in self._metrics_cache:
            self._metrics_cache[metric_name] = []
        self._metrics_cache[metric_name].append({
            "value": metric_value,
            "timestamp": datetime.utcnow(),
            "type": metric_type.value
        })
        
        # 保持缓存大小
        if len(self._metrics_cache[metric_name]) > 1000:
            self._metrics_cache[metric_name] = self._metrics_cache[metric_name][-500:]
    
    def log_error(
        self,
        error: Exception,
        trace_id: str,
        step: StreamingStep,
        context: Optional[Dict[str, Any]] = None,
        algorithm_type: Optional[AlgorithmType] = None
    ) -> None:
        """
        记录错误日志
        
        Args:
            error: 异常对象
            trace_id: 追踪ID
            step: 出错步骤
            context: 上下文信息
            algorithm_type: 算法类型
        """
        error_type = type(error).__name__
        error_message = str(error)
        
        # 更新错误统计
        if error_type not in self._business_metrics["error_counts"]:
            self._business_metrics["error_counts"][error_type] = 0
        self._business_metrics["error_counts"][error_type] += 1
        
        self.log(
            LogLevel.ERROR,
            f"错误发生: {error_type} - {error_message}",
            category=LogCategory.ERROR,
            context={
                "error_type": error_type,
                "error_message": error_message,
                "stack_trace": str(error.__traceback__) if error.__traceback__ else None,
                **(context or {})
            },
            trace_id=trace_id,
            step=step,
            algorithm_type=algorithm_type,
            error_code=error_type
        )
    
    def log_audit_event(
        self,
        event_type: str,
        description: str,
        trace_id: str,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        记录审计事件
        
        Args:
            event_type: 事件类型
            description: 事件描述
            trace_id: 追踪ID
            user_id: 用户ID
            context: 上下文信息
        """
        self.log(
            LogLevel.INFO,
            f"审计事件: {event_type} - {description}",
            category=LogCategory.AUDIT,
            context={
                "event_type": event_type,
                "description": description,
                **(context or {})
            },
            trace_id=trace_id,
            user_id=user_id
        )
    
    def get_business_metrics(self) -> Dict[str, Any]:
        """
        获取业务指标统计
        
        Returns:
            Dict[str, Any]: 业务指标
        """
        return self._business_metrics.copy()
    
    def get_performance_metrics_summary(self) -> Dict[str, Any]:
        """
        获取性能指标摘要
        
        Returns:
            Dict[str, Any]: 性能指标摘要
        """
        summary = {}
        
        for metric_name, values in self._metrics_cache.items():
            if not values:
                continue
            
            metric_values = [v["value"] for v in values]
            summary[metric_name] = {
                "count": len(metric_values),
                "min": min(metric_values),
                "max": max(metric_values),
                "avg": sum(metric_values) / len(metric_values),
                "latest": metric_values[-1],
                "type": values[-1]["type"]
            }
        
        return summary
    
    def reset_metrics(self) -> None:
        """重置指标缓存"""
        self._metrics_cache.clear()
        self._business_metrics = {
            "algorithm_requests": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "algorithm_type_counts": {},
            "average_execution_time": 0.0,
            "error_counts": {}
        }
    
    @contextmanager
    def timer(self, operation_name: str, trace_id: Optional[str] = None):
        """
        计时器上下文管理器
        
        Args:
            operation_name: 操作名称
            trace_id: 追踪ID
        """
        start_time = time.time()
        try:
            yield
        finally:
            execution_time_ms = (time.time() - start_time) * 1000
            self.log_performance_metric(
                f"{operation_name}_duration_ms",
                execution_time_ms,
                MetricType.TIMER,
                trace_id=trace_id,
                context={"operation": operation_name}
            )


def log_execution_time(operation_name: str):
    """
    执行时间记录装饰器
    
    Args:
        operation_name: 操作名称
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = StructuredLogger(func.__module__)
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time_ms = (time.time() - start_time) * 1000
                logger.log_performance_metric(
                    f"{operation_name}_duration_ms",
                    execution_time_ms,
                    MetricType.TIMER,
                    context={"function": func.__name__}
                )
                return result
            except Exception as e:
                execution_time_ms = (time.time() - start_time) * 1000
                logger.log_performance_metric(
                    f"{operation_name}_duration_ms",
                    execution_time_ms,
                    MetricType.TIMER,
                    context={"function": func.__name__, "error": str(e)}
                )
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = StructuredLogger(func.__module__)
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time_ms = (time.time() - start_time) * 1000
                logger.log_performance_metric(
                    f"{operation_name}_duration_ms",
                    execution_time_ms,
                    MetricType.TIMER,
                    context={"function": func.__name__}
                )
                return result
            except Exception as e:
                execution_time_ms = (time.time() - start_time) * 1000
                logger.log_performance_metric(
                    f"{operation_name}_duration_ms",
                    execution_time_ms,
                    MetricType.TIMER,
                    context={"function": func.__name__, "error": str(e)}
                )
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator


# 全局结构化日志记录器实例
_global_logger = None

def get_structured_logger(name: str) -> StructuredLogger:
    """
    获取结构化日志记录器实例
    
    Args:
        name: 日志记录器名称
        
    Returns:
        StructuredLogger: 结构化日志记录器
    """
    global _global_logger
    if _global_logger is None:
        _global_logger = StructuredLogger(name)
    return _global_logger