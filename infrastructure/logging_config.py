"""
日志配置模块
配置Python logging模块，支持通过环境变量设置日志级别
"""
import logging
import sys
from typing import Optional


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
    def setup_logging(cls, log_level: str = "INFO", service_name: str = "intent-recognition-service"):
        """
        配置日志系统
        
        Args:
            log_level: 日志级别 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            service_name: 服务名称，用于日志标识
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
        
        # 配置日志格式：时间戳、级别、模块名、消息
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
        else:
            # 其他模式下减少第三方库日志
            third_party_level = logging.WARNING
        
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
def setup_logging(log_level: str = "INFO", service_name: str = "intent-recognition-service"):
    """
    设置日志配置的便捷函数
    
    Args:
        log_level: 日志级别
        service_name: 服务名称
    """
    LoggingConfig.setup_logging(log_level, service_name)


def get_logger(name: str) -> logging.Logger:
    """
    获取日志记录器的便捷函数
    
    Args:
        name: 日志记录器名称
        
    Returns:
        logging.Logger: 日志记录器实例
    """
    return LoggingConfig.get_logger(name)