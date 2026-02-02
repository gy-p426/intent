"""
意图识别服务主程序
FastAPI应用的启动入口
"""

import asyncio
from contextlib import asynccontextmanager

from api.app import api_app
from infrastructure.config import get_settings
from infrastructure.logging_config import setup_logging, get_logger
from infrastructure.service_registry import get_service_registry_manager
from services.intent_recognition_service import IntentRecognitionService
from rag.rag_module import RAGModule
from rag.knowledge_base_loader import KnowledgeBaseLoader
from rag.embedding_service import EmbeddingService
from rag.vector_store import VectorStore
from llm.llm_module import LLMModule
from llm.llm_client import LLMClient
from llm.algorithm_llm_module import AlgorithmLLMModule

# Algorithm Integration Service imports
from algorithm.service import AlgorithmIntegrationService
from algorithm.router.algorithm_router import AlgorithmRouter
from algorithm.extractor.parameter_extractor import ParameterExtractor
from algorithm.clients.nl2sql_client import NL2SQLClient
from algorithm.executor.algorithm_executor import AlgorithmExecutor
from algorithm.streaming.streaming_handler import StreamingResponseHandler
from algorithm.tasks.task_manager import TaskManager
from algorithm.processors.data_processor import DataProcessor


@asynccontextmanager
async def lifespan(app):
    """应用生命周期管理"""
    # 加载配置
    settings = get_settings()
    
    # 配置日志系统
    setup_logging(settings.log_level, settings.service_name)
    logger = get_logger(__name__)
    
    # 启动时初始化
    logger.info("正在启动算法集成服务...")
    service_registry = get_service_registry_manager()
    
    try:
        logger.info(f"服务配置加载完成: {settings.service_name}:{settings.service_port}")
        
        # 初始化LLM模块（总是需要）
        logger.info("初始化LLM模块...")
        llm_client = LLMClient(
            api_key=settings.ark_api_key,
            model=settings.ark_model,
            timeout=settings.ark_timeout
        )
        llm_module = LLMModule(llm_client)
        logger.info("LLM模块初始化完成")
        
        # 根据配置决定是否初始化RAG模块
        rag_module = None
        intent_service = None
        
        if settings.enable_pure_llm_algorithm_detection:
            # 纯LLM模式：不初始化RAG模块
            logger.info("使用纯LLM算法识别模式，跳过RAG模块初始化")
            api_app.set_knowledge_base_status(False)
        else:
            # 传统模式：初始化RAG模块
            logger.info("使用传统RAG+关键词模式，初始化RAG模块...")
            kb_loader = KnowledgeBaseLoader(settings.knowledge_base_path)
            embedding_service = EmbeddingService(settings.embedding_model)
            vector_store = VectorStore(dimension=768)  # text2vec-base-chinese的向量维度
            
            rag_module = RAGModule(kb_loader, embedding_service, vector_store)
            await rag_module.initialize()
            
            api_app.set_knowledge_base_status(True)
            logger.info("RAG模块初始化完成")
            
            # 初始化意图识别服务（仅在传统模式下需要）
            intent_service = IntentRecognitionService(rag_module, llm_module)
            api_app.set_intent_service(intent_service)
            logger.info("意图识别服务初始化完成")
        
        # 初始化算法集成服务
        logger.info("初始化算法集成服务...")
        
        # 初始化算法专用LLM模块
        logger.info("初始化算法LLM模块...")
        algorithm_llm_module = AlgorithmLLMModule(llm_client)
        logger.info("算法LLM模块初始化完成")
        
        # 初始化配置管理器
        logger.info("初始化配置管理器...")
        from algorithm.config_manager import get_algorithm_config_manager
        config_manager = get_algorithm_config_manager()
        logger.info("配置管理器初始化完成")
        
        # 初始化各个组件
        logger.info("初始化任务管理器...")
        task_manager = TaskManager()
        
        # 先初始化 NL2SQL 客户端和参数提取器（会注册算法）
        logger.info("初始化NL2SQL客户端...")
        nl2sql_client = NL2SQLClient(
            base_url=settings.nl2sql_base_url,
            timeout=settings.nl2sql_timeout
        )
        logger.info(f"[main.py] 创建的 NL2SQLClient: {nl2sql_client}, base_url: {settings.nl2sql_base_url}")
        logger.info("初始化参数提取器...")
        parameter_extractor = ParameterExtractor(llm_client, config_manager, nl2sql_client)
        logger.info(f"[main.py] 参数提取器初始化完成")
        
        # 然后初始化其他组件（会使用已注册的算法）
        logger.info("初始化数据处理器...")
        data_processor = DataProcessor()
        logger.info("初始化流式处理器...")
        streaming_handler = StreamingResponseHandler()
        
        logger.info("初始化算法路由器...")
        algorithm_router = AlgorithmRouter(intent_service, config_manager)
        logger.info("初始化算法执行器...")
        algorithm_executor = AlgorithmExecutor(
            task_manager=task_manager
        )
        logger.info("所有组件初始化完成")
        
        # 创建算法集成服务
        algorithm_service = AlgorithmIntegrationService(
            router=algorithm_router,
            parameter_extractor=parameter_extractor,
            nl2sql_client=nl2sql_client,
            algorithm_executor=algorithm_executor,
            streaming_handler=streaming_handler,
            task_manager=task_manager,
            data_processor=data_processor,
            config_manager=config_manager
        )
        
        # 初始化算法服务
        await algorithm_service.initialize()
        
        # 注入到API应用
        api_app.set_algorithm_service(algorithm_service)
        
        logger.info("算法集成服务初始化完成")
        
        # 初始化服务注册管理器
        logger.info("初始化服务注册管理器...")
        registration_success = await service_registry.initialize()
        if registration_success:
            api_app.set_service_registry(service_registry)
            
            # 初始化服务发现客户端
            from infrastructure.service_discovery import get_service_discovery_client, set_service_discovery_client
            from infrastructure.service_discovery import ServiceDiscoveryClient
            
            # 创建服务发现客户端并注入Nacos注册实例
            discovery_client = ServiceDiscoveryClient(service_registry.nacos_registration)
            set_service_discovery_client(discovery_client)
            
            logger.info("服务注册管理器和服务发现客户端初始化成功")
        else:
            logger.warning("服务注册管理器初始化失败，服务将继续运行但无法被发现")
        
        logger.info("算法集成服务启动完成")
        
        yield
        
    except Exception as e:
        logger.error(f"服务启动失败: {str(e)}", exc_info=True)
        raise
    
    # 关闭时清理
    logger.info("正在关闭算法集成服务...")
    
    try:
        # 关闭服务注册管理器
        if service_registry.is_running():
            logger.info("正在关闭服务注册管理器...")
            await service_registry.shutdown()
            logger.info("服务注册管理器已关闭")
        
        # 清理算法集成服务
        if hasattr(api_app, '_algorithm_service'):
            logger.info("正在清理算法集成服务...")
            try:
                await api_app._algorithm_service.cleanup()
                logger.info("算法集成服务清理完成")
            except Exception as e:
                logger.error(f"算法集成服务清理失败: {str(e)}", exc_info=True)
        
        logger.info("算法集成服务已关闭")
        
    except Exception as e:
        logger.error(f"服务关闭时发生错误: {str(e)}", exc_info=True)


# 设置应用生命周期
api_app.app.router.lifespan_context = lifespan

# 导出应用实例供uvicorn使用
app = api_app.app


if __name__ == "__main__":
    import uvicorn
    
    # 加载配置
    settings = get_settings()
    
    # 配置日志系统
    setup_logging(settings.log_level, settings.service_name)
    logger = get_logger(__name__)
    
    logger.info(f"启动服务器 - 地址: 0.0.0.0:{settings.service_port}")
    
    # 启动服务
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.service_port,
        reload=False,
        log_level=settings.log_level.lower()
    )