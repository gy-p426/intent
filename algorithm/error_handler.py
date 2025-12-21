"""
Error Handling and Retry Mechanisms

Provides comprehensive error handling, retry logic, and error recovery strategies
for the algorithm integration service.
"""

import asyncio
import logging
from typing import Optional, Dict, Any, Callable, TypeVar, List, Union
from functools import wraps
from datetime import datetime, timedelta
from enum import Enum

from algorithm.models import ErrorResponse, StreamingStep, AlgorithmType


logger = logging.getLogger(__name__)

T = TypeVar('T')


class ErrorCode(str, Enum):
    """错误代码枚举"""
    # 参数验证错误
    INVALID_PARAMETERS = "INVALID_PARAMETERS"
    MISSING_REQUIRED_FIELD = "MISSING_REQUIRED_FIELD"
    INVALID_ALGORITHM_TYPE = "INVALID_ALGORITHM_TYPE"
    
    # 组件初始化错误
    COMPONENT_NOT_INITIALIZED = "COMPONENT_NOT_INITIALIZED"
    SERVICE_INITIALIZATION_FAILED = "SERVICE_INITIALIZATION_FAILED"
    
    # 意图识别错误
    INTENT_RECOGNITION_FAILED = "INTENT_RECOGNITION_FAILED"
    ALGORITHM_TYPE_AMBIGUOUS = "ALGORITHM_TYPE_AMBIGUOUS"
    
    # 参数提取错误
    PARAMETER_EXTRACTION_FAILED = "PARAMETER_EXTRACTION_FAILED"
    DATABASE_SCHEMA_UNAVAILABLE = "DATABASE_SCHEMA_UNAVAILABLE"
    COLUMN_MAPPING_FAILED = "COLUMN_MAPPING_FAILED"
    
    # NL2SQL服务错误
    NL2SQL_SERVICE_UNAVAILABLE = "NL2SQL_SERVICE_UNAVAILABLE"
    NL2SQL_REQUEST_FAILED = "NL2SQL_REQUEST_FAILED"
    SQL_GENERATION_FAILED = "SQL_GENERATION_FAILED"
    SQL_EXECUTION_FAILED = "SQL_EXECUTION_FAILED"
    
    # 算法执行错误
    ALGORITHM_API_UNAVAILABLE = "ALGORITHM_API_UNAVAILABLE"
    ALGORITHM_EXECUTION_FAILED = "ALGORITHM_EXECUTION_FAILED"
    DATA_FORMAT_ERROR = "DATA_FORMAT_ERROR"
    ALGORITHM_TIMEOUT = "ALGORITHM_TIMEOUT"
    
    # 异步任务错误
    TASK_CREATION_FAILED = "TASK_CREATION_FAILED"
    TASK_POLLING_FAILED = "TASK_POLLING_FAILED"
    TASK_TIMEOUT = "TASK_TIMEOUT"
    TASK_CANCELLED = "TASK_CANCELLED"
    
    # 网络和连接错误
    CONNECTION_ERROR = "CONNECTION_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    NETWORK_ERROR = "NETWORK_ERROR"
    
    # 系统错误
    INTERNAL_ERROR = "INTERNAL_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"


class RetryConfig:
    """重试配置"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter


class AlgorithmError(Exception):
    """算法集成服务基础异常类"""
    
    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        step: StreamingStep = StreamingStep.ERROR,
        details: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None,
        original_error: Optional[Exception] = None
    ):
        self.error_code = error_code
        self.message = message
        self.step = step
        self.details = details or {}
        self.suggestions = suggestions or []
        self.original_error = original_error
        self.timestamp = datetime.utcnow()
        
        super().__init__(message)
    
    def to_error_response(self) -> ErrorResponse:
        """转换为错误响应模型"""
        return ErrorResponse(
            step=self.step,
            error_code=self.error_code.value,
            error_message=self.message,
            error_details=self.details,
            suggestions=self.suggestions,
            timestamp=self.timestamp
        )


class ParameterValidationError(AlgorithmError):
    """参数验证错误"""
    
    def __init__(self, message: str, field_name: Optional[str] = None, **kwargs):
        details = kwargs.get('details', {})
        if field_name:
            details['field_name'] = field_name
        
        super().__init__(
            error_code=ErrorCode.INVALID_PARAMETERS,
            message=message,
            step=StreamingStep.ALGORITHM_IDENTIFICATION,
            details=details,
            suggestions=[
                "请检查输入参数格式",
                "确认所有必需字段都已提供",
                "参考API文档了解正确的参数格式"
            ],
            **kwargs
        )


class ComponentNotInitializedError(AlgorithmError):
    """组件未初始化错误"""
    
    def __init__(self, component_name: str, **kwargs):
        super().__init__(
            error_code=ErrorCode.COMPONENT_NOT_INITIALIZED,
            message=f"组件未初始化: {component_name}",
            details={'component_name': component_name},
            suggestions=[
                f"请确保{component_name}已正确初始化",
                "检查服务配置",
                "重启服务以重新初始化组件"
            ],
            **kwargs
        )


class IntentRecognitionError(AlgorithmError):
    """意图识别错误"""
    
    def __init__(self, message: str, question: str, **kwargs):
        super().__init__(
            error_code=ErrorCode.INTENT_RECOGNITION_FAILED,
            message=message,
            step=StreamingStep.ALGORITHM_IDENTIFICATION,
            details={'question': question},
            suggestions=[
                "请尝试更明确地描述您的需求",
                "使用关键词如'聚类'、'分类'、'预测'等",
                "参考示例查询格式"
            ],
            **kwargs
        )


class ParameterExtractionError(AlgorithmError):
    """参数提取错误"""
    
    def __init__(self, message: str, algorithm_type: AlgorithmType, **kwargs):
        super().__init__(
            error_code=ErrorCode.PARAMETER_EXTRACTION_FAILED,
            message=message,
            step=StreamingStep.PARAMETER_EXTRACTION,
            details={'algorithm_type': algorithm_type.value},
            suggestions=[
                "请提供更详细的参数信息",
                "确认数据库中存在相关的表和列",
                "检查查询语句的格式"
            ],
            **kwargs
        )


class NL2SQLError(AlgorithmError):
    """NL2SQL服务错误"""
    
    def __init__(self, message: str, service_url: Optional[str] = None, **kwargs):
        details = kwargs.get('details', {})
        if service_url:
            details['service_url'] = service_url
        
        super().__init__(
            error_code=ErrorCode.NL2SQL_SERVICE_UNAVAILABLE,
            message=message,
            step=StreamingStep.SQL_GENERATION,
            details=details,
            suggestions=[
                "检查NL2SQL服务状态",
                "确认服务URL配置正确",
                "稍后重试",
                "联系系统管理员"
            ],
            **kwargs
        )


class AlgorithmExecutionError(AlgorithmError):
    """算法执行错误"""
    
    def __init__(self, message: str, algorithm_type: AlgorithmType, **kwargs):
        details = kwargs.get('details', {})
        details['algorithm_type'] = algorithm_type.value
        kwargs['details'] = details
        
        super().__init__(
            error_code=ErrorCode.ALGORITHM_EXECUTION_FAILED,
            message=message,
            step=StreamingStep.ALGORITHM_EXECUTION,
            suggestions=[
                "检查算法API服务状态",
                "验证输入数据格式",
                "确认算法配置正确",
                "稍后重试"
            ],
            **kwargs
        )


class TaskTimeoutError(AlgorithmError):
    """任务超时错误"""
    
    def __init__(self, task_id: str, timeout_seconds: int, **kwargs):
        details = kwargs.get('details', {})
        details.update({
            'task_id': task_id,
            'timeout_seconds': timeout_seconds
        })
        kwargs['details'] = details
        
        super().__init__(
            error_code=ErrorCode.TASK_TIMEOUT,
            message=f"任务执行超时: {task_id}",
            step=StreamingStep.TASK_POLLING,
            suggestions=[
                "任务可能需要更长时间完成",
                "检查算法API服务状态",
                "考虑增加超时时间",
                "联系系统管理员"
            ],
            **kwargs
        )


class ErrorHandler:
    """错误处理器"""
    
    def __init__(self):
        self.error_stats = {}
        self.last_errors = []
        self.max_error_history = 100
    
    def handle_error(
        self,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
    ) -> ErrorResponse:
        """
        处理错误并生成错误响应
        
        Args:
            error: 异常对象
            context: 错误上下文信息
            
        Returns:
            ErrorResponse: 格式化的错误响应
        """
        context = context or {}
        
        # 记录错误统计
        error_type = type(error).__name__
        self.error_stats[error_type] = self.error_stats.get(error_type, 0) + 1
        
        # 记录错误历史
        error_record = {
            'timestamp': datetime.utcnow(),
            'error_type': error_type,
            'message': str(error),
            'context': context
        }
        self.last_errors.append(error_record)
        if len(self.last_errors) > self.max_error_history:
            self.last_errors.pop(0)
        
        # 记录日志
        logger.error(
            f"处理错误: {error_type} - {str(error)}",
            extra={'context': context},
            exc_info=True
        )
        
        # 生成错误响应
        if isinstance(error, AlgorithmError):
            return error.to_error_response()
        else:
            return self._create_generic_error_response(error, context)
    
    def _create_generic_error_response(
        self,
        error: Exception,
        context: Dict[str, Any]
    ) -> ErrorResponse:
        """创建通用错误响应"""
        error_code = self._map_exception_to_error_code(error)
        
        return ErrorResponse(
            error_code=error_code.value,
            error_message=str(error),
            error_details=context,
            suggestions=self._get_generic_suggestions(error_code)
        )
    
    def _map_exception_to_error_code(self, error: Exception) -> ErrorCode:
        """将异常映射到错误代码"""
        error_mapping = {
            ValueError: ErrorCode.INVALID_PARAMETERS,
            TypeError: ErrorCode.INVALID_PARAMETERS,
            ConnectionError: ErrorCode.CONNECTION_ERROR,
            TimeoutError: ErrorCode.TIMEOUT_ERROR,
            asyncio.TimeoutError: ErrorCode.TIMEOUT_ERROR,
        }
        
        return error_mapping.get(type(error), ErrorCode.INTERNAL_ERROR)
    
    def _get_generic_suggestions(self, error_code: ErrorCode) -> List[str]:
        """获取通用建议"""
        suggestions_mapping = {
            ErrorCode.INVALID_PARAMETERS: [
                "请检查输入参数",
                "确认参数格式正确"
            ],
            ErrorCode.CONNECTION_ERROR: [
                "检查网络连接",
                "确认服务地址正确",
                "稍后重试"
            ],
            ErrorCode.TIMEOUT_ERROR: [
                "请求超时，请稍后重试",
                "检查网络状况",
                "联系系统管理员"
            ],
            ErrorCode.INTERNAL_ERROR: [
                "系统内部错误",
                "请联系技术支持",
                "稍后重试"
            ]
        }
        
        return suggestions_mapping.get(error_code, ["请联系技术支持"])
    
    def get_error_statistics(self) -> Dict[str, Any]:
        """获取错误统计信息"""
        return {
            'error_counts': self.error_stats.copy(),
            'total_errors': sum(self.error_stats.values()),
            'recent_errors': self.last_errors[-10:] if self.last_errors else []
        }


class RetryHandler:
    """重试处理器"""
    
    def __init__(self, default_config: Optional[RetryConfig] = None):
        self.default_config = default_config or RetryConfig()
        self.retry_stats = {}
    
    async def retry_async(
        self,
        func: Callable[..., T],
        *args,
        config: Optional[RetryConfig] = None,
        retryable_exceptions: Optional[tuple] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> T:
        """
        异步重试装饰器
        
        Args:
            func: 要重试的异步函数
            *args: 函数参数
            config: 重试配置
            retryable_exceptions: 可重试的异常类型
            context: 上下文信息
            **kwargs: 函数关键字参数
            
        Returns:
            T: 函数返回值
            
        Raises:
            Exception: 重试失败后抛出最后一次的异常
        """
        config = config or self.default_config
        retryable_exceptions = retryable_exceptions or (
            ConnectionError,
            TimeoutError,
            asyncio.TimeoutError,
        )
        context = context or {}
        
        func_name = getattr(func, '__name__', str(func))
        last_exception = None
        
        for attempt in range(config.max_attempts):
            try:
                logger.debug(f"尝试执行 {func_name} (第 {attempt + 1}/{config.max_attempts} 次)")
                result = await func(*args, **kwargs)
                
                # 记录成功统计
                if attempt > 0:
                    self._record_retry_success(func_name, attempt + 1)
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # 检查是否为可重试的异常
                if not isinstance(e, retryable_exceptions):
                    logger.warning(f"{func_name} 遇到不可重试异常: {type(e).__name__}")
                    raise e
                
                # 如果是最后一次尝试，直接抛出异常
                if attempt == config.max_attempts - 1:
                    logger.error(f"{func_name} 重试失败，已达到最大重试次数")
                    self._record_retry_failure(func_name, config.max_attempts)
                    raise e
                
                # 计算延迟时间
                delay = self._calculate_delay(attempt, config)
                logger.warning(
                    f"{func_name} 第 {attempt + 1} 次尝试失败: {str(e)}, "
                    f"{delay:.2f}秒后重试"
                )
                
                await asyncio.sleep(delay)
        
        # 这里不应该到达，但为了类型安全
        if last_exception:
            raise last_exception
        else:
            raise RuntimeError("重试逻辑异常")
    
    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """计算延迟时间"""
        delay = config.base_delay * (config.exponential_base ** attempt)
        delay = min(delay, config.max_delay)
        
        if config.jitter:
            import random
            delay *= (0.5 + random.random() * 0.5)  # 添加50%的随机抖动
        
        return delay
    
    def _record_retry_success(self, func_name: str, attempts: int):
        """记录重试成功统计"""
        if func_name not in self.retry_stats:
            self.retry_stats[func_name] = {
                'success_count': 0,
                'failure_count': 0,
                'total_attempts': 0
            }
        
        self.retry_stats[func_name]['success_count'] += 1
        self.retry_stats[func_name]['total_attempts'] += attempts
    
    def _record_retry_failure(self, func_name: str, attempts: int):
        """记录重试失败统计"""
        if func_name not in self.retry_stats:
            self.retry_stats[func_name] = {
                'success_count': 0,
                'failure_count': 0,
                'total_attempts': 0
            }
        
        self.retry_stats[func_name]['failure_count'] += 1
        self.retry_stats[func_name]['total_attempts'] += attempts
    
    def get_retry_statistics(self) -> Dict[str, Any]:
        """获取重试统计信息"""
        return self.retry_stats.copy()


def retry_on_failure(
    config: Optional[RetryConfig] = None,
    retryable_exceptions: Optional[tuple] = None,
    context: Optional[Dict[str, Any]] = None
):
    """
    重试装饰器
    
    Args:
        config: 重试配置
        retryable_exceptions: 可重试的异常类型
        context: 上下文信息
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            retry_handler = RetryHandler()
            return await retry_handler.retry_async(
                func, *args,
                config=config,
                retryable_exceptions=retryable_exceptions,
                context=context,
                **kwargs
            )
        return wrapper
    return decorator


# 全局错误处理器和重试处理器实例
error_handler = ErrorHandler()
retry_handler = RetryHandler()