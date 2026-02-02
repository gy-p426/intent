"""
日志配置模块
配置Python logging模块，支持通过环境变量设置日志级别
支持结构化日志记录和性能监控
"""
import logging
import sys
import json
from typing import Optional, Dict, Any
from datetime import datetime


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""
    
    def __init__(self, service_name: str = "algorithm-integration-service"):
        super().__init__()
        self.service_name = service_name
    
    def format(self, record: logging.LogRecord) -> str:
        """格式化日志记录为JSON结构"""
        # 检查是否已经是JSON格式的消息
        try:
            # 尝试解析消息是否为JSON
            json.loads(record.getMessage())
            # 如果是JSON，直接返回
            return record.getMessage()
        except (json.JSONDecodeError, ValueError):
            # 如果不是JSON，创建结构化格式
            log_entry = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": record.levelname,
                "message": record.getMessage(),
                "service": self.service_name,
                "logger": record.name,
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno
            }
            
            # 添加异常信息
            if record.exc_info:
                log_entry["exception"] = self.formatException(record.exc_info)
            
            # 添加额外的上下文信息
            if hasattr(record, 'context'):
                log_entry["context"] = self._serialize_context(record.context)
            
            if hasattr(record, 'trace_id'):
                log_entry["trace_id"] = record.trace_id
            
            if hasattr(record, 'user_id'):
                log_entry["user_id"] = record.user_id
            
            return json.dumps(log_entry, ensure_ascii=False, separators=(',', ':'), default=self._json_serializer)
    
    def _json_serializer(self, obj):
        """自定义JSON序列化器，处理datetime等特殊类型"""
        if isinstance(obj, datetime):
            return obj.isoformat() + "Z"
        # 对于其他不可序列化的对象，返回其字符串表示
        return str(obj)
    
    def _serialize_context(self, context):
        """序列化上下文信息，处理datetime等特殊类型"""
        if isinstance(context, dict):
            return {k: self._serialize_value(v) for k, v in context.items()}
        return context
    
    def _serialize_value(self, value):
        """序列化单个值"""
        if isinstance(value, datetime):
            return value.isoformat() + "Z"
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        elif isinstance(value, (list, tuple)):
            return [self._serialize_value(v) for v in value]
        return value


class LoggingConfig:
    """
    日志配置类
    提供统一的日志配置和管理
    """
    
    # 支持的日志级别
    VALID_LOG_LEVELS = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }
    
    @classmethod
    def setup_logging(
        cls, 
        log_level: str = "DEBUG",
        service_name: str = "algorithm-integration-service",
        structured: bool = True
    ):
        """
        配置日志系统
        
        Args:
            log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            service_name: 服务名称，用于日志标识
            structured: 是否使用结构化日志格式
        """
        # 验证日志级别
        log_level = log_level.upper()
        if log_level not in cls.VALID_LOG_LEVELS:
            log_level = "INFO"
            print(f"警告: 无效的日志级别，使用默认级别 INFO")
        
        # 配置根日志记录器
        root_logger = logging.getLogger()
        root_logger.setLevel(cls.VALID_LOG_LEVELS[log_level])
        
        # 清除现有的处理器
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # 创建控制台处理器，输出到标准输出
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(cls.VALID_LOG_LEVELS[log_level])
        
        # 根据配置选择格式化器
        if structured:
            formatter = StructuredFormatter(service_name)
        else:
            # 传统格式：时间戳、级别、模块名、消息
            formatter = logging.Formatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        
        console_handler.setFormatter(formatter)
        
        # 添加处理器到根日志记录器
        root_logger.addHandler(console_handler)
        
        # 设置第三方库的日志级别，避免过多噪音
        cls._configure_third_party_loggers(log_level)
        
        # 记录日志配置完成
        logger = logging.getLogger(__name__)
        if structured:
            # 使用结构化格式记录初始化日志
            init_log = {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "level": "INFO",
                "message": "日志系统初始化完成",
                "service": service_name,
                "log_level": log_level,
                "structured_logging": True,
                "category": "system"
            }
            logger.info(json.dumps(init_log, ensure_ascii=False, separators=(',', ':')))
        else:
            logger.info(f"日志系统初始化完成 - 服务: {service_name}, 级别: {log_level}")
    
    @classmethod
    def _configure_third_party_loggers(cls, log_level: str):
        """
        配置第三方库的日志级别
        
        Args:
            log_level: 当前日志级别
        """
        # 根据当前日志级别调整第三方库日志
        if log_level == "DEBUG":
            # DEBUG模式下显示更多信息
            third_party_level = logging.INFO
            grpc_level = logging.WARNING  # 即使在DEBUG模式下，gRPC也只显示WARNING以上
        else:
            # 其他模式下减少第三方库日志
            third_party_level = logging.WARNING
            grpc_level = logging.ERROR  # 非DEBUG模式下，gRPC只显示ERROR以上
        
        # 配置常见第三方库的日志级别
        third_party_loggers = [
            'uvicorn',
            'uvicorn.access',
            'uvicorn.error',
            'fastapi',
            'httpx',
            'urllib3',
            'sentence_transformers',
            'transformers',
            'torch',
            'nacos',
            'volcenginesdkarkruntime'
        ]
        
        for logger_name in third_party_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(third_party_level)
        
        # 特别处理gRPC相关日志，设置更严格的级别
        grpc_loggers = [
            'grpc',
            'grpc._cython.cygrpc',
            'grpc._channel',
            'grpc._common',
            'grpc.aio',
            'grpc._cygrpc'
        ]
        
        for logger_name in grpc_loggers:
            logger = logging.getLogger(logger_name)
            logger.setLevel(grpc_level)
    
    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        获取指定名称的日志记录器
        
        Args:
            name: 日志记录器名称，通常使用 __name__
            
        Returns:
            logging.Logger: 日志记录器实例
        """
        return logging.getLogger(name)
    
    @classmethod
    def set_log_level(cls, log_level: str):
        """
        动态设置日志级别
        
        Args:
            log_level: 新的日志级别
        """
        log_level = log_level.upper()
        if log_level not in cls.VALID_LOG_LEVELS:
            logger = cls.get_logger(__name__)
            logger.warning(f"无效的日志级别: {log_level}，保持当前级别")
            return
        
        # 更新根日志记录器级别
        root_logger = logging.getLogger()
        root_logger.setLevel(cls.VALID_LOG_LEVELS[log_level])
        
        # 更新所有处理器的级别
        for handler in root_logger.handlers:
            handler.setLevel(cls.VALID_LOG_LEVELS[log_level])
        
        # 重新配置第三方库日志级别
        cls._configure_third_party_loggers(log_level)
        
        logger = cls.get_logger(__name__)
        logger.info(f"日志级别已更新为: {log_level}")


# 便捷函数
def setup_logging(
    log_level: str = "DEBUG",
    service_name: str = "algorithm-integration-service",
    structured: bool = True
):
    """
    设置日志配置的便捷函数
    
    Args:
        log_level: 日志级别
        service_name: 服务名称
        structured: 是否使用结构化日志格式
    """
    LoggingConfig.setup_logging(log_level, service_name, structured)


def get_logger(name: str) -> logging.Logger:
    """
    获取日志记录器的便捷函数
    
    Args:
        name: 日志记录器名称
        
    Returns:
        logging.Logger: 日志记录器实例
    """
    return LoggingConfig.get_logger(name)