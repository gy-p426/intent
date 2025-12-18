"""
Configuration Manager
使用pydantic-settings加载配置文件和环境变量
"""
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """
    应用配置类
    支持从.env文件和环境变量加载配置
    环境变量优先级高于配置文件
    """
    
    # 服务配置
    service_name: str = Field(
        default="intent-recognition-service",
        description="服务名称"
    )
    service_port: int = Field(
        default=8000,
        description="服务端口",
        ge=1,
        le=65535
    )
    
    # Nacos配置
    nacos_server_addr: str = Field(
        default="127.0.0.1:8848",
        description="Nacos服务器地址，格式: host:port"
    )
    nacos_namespace: str = Field(
        default="public",
        description="Nacos命名空间"
    )
    
    # 知识库配置
    knowledge_base_path: str = Field(
        default="intent.txt",
        description="知识库文件路径"
    )
    rag_top_k: int = Field(
        default=20,
        description="RAG检索返回的候选数量",
        ge=1,
        le=100
    )
    
    # 向量模型配置
    embedding_model: str = Field(
        default="shibing624/text2vec-base-chinese",
        description="文本向量化模型名称"
    )
    
    # LLM配置（火山引擎豆包）
    ark_api_key: str = Field(
        default="",
        description="火山引擎ARK API密钥"
    )
    ark_model: str = Field(
        default="deepseek-v3-2-251201",
        description="火山模型名称"
    )
    ark_timeout: int = Field(
        default=60,
        description="LLM API超时时间（秒）",
        ge=1
    )
    llm_max_retries: int = Field(
        default=3,
        description="LLM API调用失败最大重试次数",
        ge=0
    )
    llm_retry_delay: int = Field(
        default=2,
        description="LLM API重试间隔（秒）",
        ge=0
    )
    
    # 日志配置
    log_level: str = Field(
        default="INFO",
        description="日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"


class ConfigManager:
    """
    配置管理器
    单例模式，确保全局只有一个配置实例
    """
    _instance = None
    _settings = None
    
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
            self._validate_settings()
        except Exception as e:
            raise RuntimeError(f"配置加载失败: {str(e)}")
    
    def _validate_settings(self):
        """验证必需的配置参数"""
        required_fields = ['nacos_server_addr', 'ark_api_key']
        missing_fields = []
        
        for field in required_fields:
            value = getattr(self._settings, field, None)
            if not value:
                missing_fields.append(field.upper())
        
        if missing_fields:
            raise ValueError(
                f"缺少必需的配置参数: {', '.join(missing_fields)}。"
                f"请在.env文件或环境变量中设置这些参数。"
            )
    
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
