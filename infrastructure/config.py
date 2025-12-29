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
        default="DEBUG",
        description="日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )
    
    # 算法集成服务配置
    algorithm_config_path: str = Field(
        default="algorithm_input.json",
        description="算法配置文件路径"
    )
    algorithm_config_hot_reload: bool = Field(
        default=True,
        description="是否启用算法配置热重载"
    )
    algorithm_config_reload_interval: int = Field(
        default=60,
        description="配置文件检查间隔（秒）",
        ge=10
    )
    
    # 服务发现配置
    service_discovery_enabled: bool = Field(
        default=True,
        description="是否启用Nacos服务发现"
    )
    service_discovery_mode: str = Field(
        default="nacos",
        description="服务发现模式: nacos 或 static"
    )
    load_balance_strategy: str = Field(
        default="round_robin",
        description="负载均衡策略: round_robin, random, least_connections"
    )
    service_health_check_interval: int = Field(
        default=30,
        description="服务健康检查间隔（秒）",
        ge=10
    )
    
    # NL2SQL服务配置
    nl2sql_service_name: str = Field(
        default="nl2sql-service",
        description="NL2SQL服务在Nacos中的服务名称"
    )
    nl2sql_base_url: str = Field(
        default="http://localhost:8080",
        description="NL2SQL服务静态URL（禁用服务发现时使用）"
    )
    nl2sql_timeout: int = Field(
        default=30,
        description="NL2SQL服务超时时间（秒）",
        ge=1
    )
    nl2sql_max_retries: int = Field(
        default=3,
        description="NL2SQL服务最大重试次数",
        ge=0
    )
    nl2sql_retry_delay: int = Field(
        default=2,
        description="NL2SQL服务重试间隔（秒）",
        ge=0
    )
    
    # 算法服务配置
    clustering_service_name: str = Field(
        default="clustering-service",
        description="聚类服务名称"
    )
    clustering_api_url: str = Field(
        default="http://localhost:8001",
        description="聚类算法API静态URL"
    )
    
    classification_service_name: str = Field(
        default="classification-service",
        description="分类服务名称"
    )
    classification_api_url: str = Field(
        default="http://localhost:8002",
        description="分类算法API静态URL"
    )
    
    prediction_service_name: str = Field(
        default="prediction-service",
        description="预测服务名称"
    )
    prediction_api_url: str = Field(
        default="http://localhost:8003",
        description="预测算法API静态URL"
    )
    
    anomaly_service_name: str = Field(
        default="dbscan-service",  # 异常检测统一使用DBSCAN服务
        description="异常检测服务名称"
    )
    anomaly_api_url: str = Field(
        default="http://localhost:8014",  # 异常检测统一使用DBSCAN服务URL
        description="异常检测API静态URL"
    )
    
    dbscan_service_name: str = Field(
        default="dbscan-service",
        description="DBSCAN密度聚类服务名称"
    )
    dbscan_api_url: str = Field(
        default="http://localhost:8014",
        description="DBSCAN密度聚类API静态URL"
    )
    
    # iforest_service_name: str = Field(
    #     default="iforest-service",
    #     description="IForest孤立森林服务名称"
    # )
    # iforest_api_url: str = Field(
    #     default="http://localhost:8015",
    #     description="IForest孤立森林API静态URL"
    # )
    forecast_service_url: str = Field(
        default="http://192.168.1.125:8100",
        description="Forecast Service 微服务地址（趋势分析、单变量预测、多变量预测）"
    )
    forecast_service_timeout: int = Field(
        default=60,
        description="Forecast Service 请求超时时间（秒）",
        ge=1
    )
    
    association_service_name: str = Field(
        default="association-service",
        description="关联分析服务名称"
    )
    association_api_url: str = Field(
        default="http://localhost:8005",
        description="关联分析API静态URL"
    )
    
    comparison_service_name: str = Field(
        default="comparison-service",
        description="对比分析服务名称"
    )
    comparison_api_url: str = Field(
        default="http://localhost:8006",
        description="对比分析API静态URL"
    )
    
    similarity_service_name: str = Field(
        default="similarity-service",
        description="相似度分析服务名称"
    )
    similarity_api_url: str = Field(
        default="http://localhost:8007",
        description="相似度分析API静态URL"
    )
    
    trend_service_name: str = Field(
        default="trend-service",
        description="趋势分析服务名称"
    )
    trend_api_url: str = Field(
        default="http://localhost:8008",
        description="趋势分析API静态URL"
    )
    
    profile_service_name: str = Field(
        default="profile-service",
        description="用户画像服务名称"
    )
    profile_api_url: str = Field(
        default="http://localhost:8009",
        description="用户画像API静态URL"
    )
    
    causality_service_name: str = Field(
        default="causality-service",
        description="因果分析服务名称"
    )
    causality_api_url: str = Field(
        default="http://localhost:8010",
        description="因果分析API静态URL"
    )
    
    alert_service_name: str = Field(
        default="alert-service",
        description="预警系统服务名称"
    )
    alert_api_url: str = Field(
        default="http://localhost:8011",
        description="预警系统API静态URL"
    )
    
    recommendation_service_name: str = Field(
        default="recommendation-service",
        description="推荐系统服务名称"
    )
    recommendation_api_url: str = Field(
        default="http://localhost:8012",
        description="推荐系统API静态URL"
    )
    
    algorithm_api_timeout: int = Field(
        default=60,
        description="算法API超时时间（秒）",
        ge=1
    )
    algorithm_api_max_retries: int = Field(
        default=3,
        description="算法API最大重试次数",
        ge=0
    )
    algorithm_api_retry_delay: int = Field(
        default=2,
        description="算法API重试间隔（秒）",
        ge=0
    )
    
    # 异步任务配置
    async_task_poll_interval: int = Field(
        default=5,
        description="异步任务轮询间隔（秒）",
        ge=1
    )
    async_task_max_wait_time: int = Field(
        default=300,
        description="异步任务最大等待时间（秒）",
        ge=1
    )
    async_task_max_concurrent: int = Field(
        default=10,
        description="最大并发异步任务数",
        ge=1
    )
    
    # 流式响应配置
    stream_chunk_size: int = Field(
        default=1024,
        description="流式响应块大小",
        ge=256
    )
    stream_timeout: int = Field(
        default=120,
        description="流式响应超时时间（秒）",
        ge=1
    )
    stream_buffer_size: int = Field(
        default=8192,
        description="流式响应缓冲区大小",
        ge=1024
    )
    
    # 算法服务健康检查配置
    health_check_interval: int = Field(
        default=30,
        description="健康检查间隔（秒）",
        ge=10
    )
    health_check_timeout: int = Field(
        default=5,
        description="健康检查超时时间（秒）",
        ge=1
    )
    
    # 缓存配置
    cache_enabled: bool = Field(
        default=True,
        description="是否启用缓存"
    )
    cache_ttl: int = Field(
        default=300,
        description="缓存过期时间（秒）",
        ge=60
    )
    cache_max_size: int = Field(
        default=1000,
        description="缓存最大条目数",
        ge=100
    )
    
    # 数据库配置（用于获取表结构信息）
    mysql_host: str = Field(
        default="localhost",
        description="MySQL主机地址"
    )
    mysql_port: int = Field(
        default=3306,
        description="MySQL端口",
        ge=1,
        le=65535
    )
    mysql_database: str = Field(
        default="nl2sql",
        description="MySQL数据库名"
    )
    mysql_username: str = Field(
        default="root",
        description="MySQL用户名"
    )
    mysql_password: str = Field(
        default="root",
        description="MySQL密码"
    )
    
    # 🆕 大模型分析配置
    enable_llm_result_analysis: bool = Field(
        default=True,
        description="是否启用大模型结果分析"
    )
    llm_analysis_model: str = Field(
        default="deepseek-v3-2-251201",
        description="大模型分析使用的模型名称"
    )
    llm_analysis_timeout: int = Field(
        default=30,
        description="大模型分析超时时间（秒）",
        ge=1
    )
    llm_analysis_max_retries: int = Field(
        default=2,
        description="大模型分析最大重试次数",
        ge=0
    )
    llm_analysis_fallback_enabled: bool = Field(
        default=True,
        description="大模型分析失败时是否启用降级处理"
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
        
        # 验证算法服务配置
        self._validate_algorithm_settings()
    
    def _validate_algorithm_settings(self):
        """验证算法服务相关配置"""
        import os
        
        # 验证算法配置文件是否存在
        config_path = self._settings.algorithm_config_path
        if not os.path.exists(config_path):
            raise ValueError(f"算法配置文件不存在: {config_path}")
        
        # 验证URL格式
        url_fields = [
            'nl2sql_base_url', 'clustering_api_url', 'classification_api_url',
            'prediction_api_url', 'anomaly_api_url', 'forecast_service_url'
        ]
        
        for field in url_fields:
            url = getattr(self._settings, field, '')
            if url and not (url.startswith('http://') or url.startswith('https://')):
                raise ValueError(f"无效的URL格式: {field} = {url}")
        
        # 验证数值范围
        if self._settings.async_task_poll_interval > self._settings.async_task_max_wait_time:
            raise ValueError("异步任务轮询间隔不能大于最大等待时间")
        
        if self._settings.stream_chunk_size > self._settings.stream_buffer_size:
            raise ValueError("流式响应块大小不能大于缓冲区大小")
    
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
