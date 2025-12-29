"""
配置管理模块
使用pydantic-settings加载配置文件和环境变量
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path


class Settings(BaseSettings):
    """
    微服务配置类
    支持从.env文件和环境变量加载配置
    环境变量优先级高于配置文件
    """
    
    # 服务配置
    service_name: str = Field(
        default="forecast-microservice",
        description="服务名称"
    )
    service_version: str = Field(
        default="1.0.0",
        description="服务版本"
    )
    service_host: str = Field(
        default="0.0.0.0",
        description="服务监听地址"
    )
    service_port: int = Field(
        default=8100,
        description="服务端口",
        ge=1,
        le=65535
    )
    
    # 调试配置
    debug: bool = Field(
        default=False,
        description="是否启用调试模式"
    )
    log_level: str = Field(
        default="INFO",
        description="日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )
    
    # 模型存储配置
    model_storage_dir: str = Field(
        default="",
        description="模型存储目录，为空时使用默认目录"
    )
    
    # CORS配置
    cors_origins: str = Field(
        default="*",
        description="允许的CORS来源，多个用逗号分隔"
    )
    cors_allow_credentials: bool = Field(
        default=True,
        description="是否允许携带凭证"
    )
    cors_allow_methods: str = Field(
        default="*",
        description="允许的HTTP方法，多个用逗号分隔"
    )
    cors_allow_headers: str = Field(
        default="*",
        description="允许的HTTP头，多个用逗号分隔"
    )
    
    # 请求配置
    request_timeout: int = Field(
        default=300,
        description="请求超时时间（秒）",
        ge=1
    )
    max_request_size: int = Field(
        default=10 * 1024 * 1024,
        description="最大请求体大小（字节）",
        ge=1024
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"
        env_prefix = "FORECAST_"
    
    def get_cors_origins_list(self) -> list:
        """获取CORS来源列表"""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    def get_cors_methods_list(self) -> list:
        """获取CORS方法列表"""
        if self.cors_allow_methods == "*":
            return ["*"]
        return [method.strip() for method in self.cors_allow_methods.split(",")]
    
    def get_cors_headers_list(self) -> list:
        """获取CORS头列表"""
        if self.cors_allow_headers == "*":
            return ["*"]
        return [header.strip() for header in self.cors_allow_headers.split(",")]
    
    def get_model_storage_dir(self) -> str:
        """获取模型存储目录"""
        if self.model_storage_dir:
            return self.model_storage_dir
        return str(Path.cwd() / "models")


class ConfigManager:
    """
    配置管理器
    单例模式，确保全局只有一个配置实例
    """
    _instance: Optional['ConfigManager'] = None
    _settings: Optional[Settings] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._settings is None:
            self._load_settings()
    
    def _load_settings(self):
        """加载配置"""
        try:
            self._settings = Settings()
        except Exception as e:
            raise RuntimeError(f"配置加载失败: {str(e)}")
    
    @property
    def settings(self) -> Settings:
        """获取配置对象"""
        if self._settings is None:
            self._load_settings()
        return self._settings
    
    def reload(self):
        """重新加载配置"""
        self._settings = None
        self._load_settings()


# 全局配置管理器实例
config_manager = ConfigManager()


def get_settings() -> Settings:
    """
    获取配置对象的便捷函数
    
    Returns:
        Settings: 配置对象
    """
    return config_manager.settings
