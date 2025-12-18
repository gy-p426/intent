"""
意图识别服务主程序
FastAPI应用的启动入口
"""

import asyncio
from contextlib import asynccontextmanager

from api.app import api_app
from infrastructure.config import get_settings
from infrastructure.logging_config import setup_logging, get_logger
from infrastructure.nacos_registration import NacosRegistration
from services.intent_recognition_service import IntentRecognitionService
from rag.rag_module import RAGModule
from rag.knowledge_base_loader import KnowledgeBaseLoader
from rag.embedding_service import EmbeddingService
from rag.vector_store import VectorStore
from llm.llm_module import LLMModule
from llm.llm_client import LLMClient


@asynccontextmanager
async def lifespan(app):
    """应用生命周期管理"""
    # 加载配置
    settings = get_settings()
    
    # 配置日志系统
    setup_logging(settings.log_level, settings.service_name)
    logger = get_logger(__name__)
    
    # 启动时初始化
    logger.info("正在启动意图识别服务...")
    nacos_client = None
    
    try:
        logger.info(f"服务配置加载完成: {settings.service_name}:{settings.service_port}")
        
        # 初始化RAG模块
        logger.info("初始化RAG模块...")
        kb_loader = KnowledgeBaseLoader(settings.knowledge_base_path)
        embedding_service = EmbeddingService(settings.embedding_model)
        vector_store = VectorStore(dimension=768)  # text2vec-base-chinese的向量维度
        
        rag_module = RAGModule(kb_loader, embedding_service, vector_store)
        await rag_module.initialize()
        
        api_app.set_knowledge_base_status(True)
        logger.info("RAG模块初始化完成")
        
        # 初始化LLM模块
        logger.info("初始化LLM模块...")
        llm_client = LLMClient(
            api_key=settings.ark_api_key,
            model=settings.ark_model,
            timeout=settings.ark_timeout
        )
        llm_module = LLMModule(llm_client)
        logger.info("LLM模块初始化完成")
        
        # 初始化意图识别服务
        intent_service = IntentRecognitionService(rag_module, llm_module)
        api_app.set_intent_service(intent_service)
        
        # 初始化Nacos注册
        logger.info("初始化Nacos服务注册...")
        nacos_client = NacosRegistration(
            server_addr=settings.nacos_server_addr,
            service_name=settings.service_name,
            service_port=settings.service_port,
            namespace=settings.nacos_namespace
        )
        
        # 注册服务到Nacos
        registration_success = await nacos_client.register()
        if registration_success:
            api_app.set_nacos_client(nacos_client)
            logger.info("Nacos服务注册成功")
        else:
            logger.warning("Nacos服务注册失败，服务将继续运行但无法被发现")
        
        logger.info("意图识别服务启动完成")
        
        yield
        
    except Exception as e:
        logger.error(f"服务启动失败: {str(e)}", exc_info=True)
        raise
    
    # 关闭时清理
    logger.info("正在关闭意图识别服务...")
    
    try:
        # 注销Nacos服务
        if nacos_client and nacos_client.is_registered():
            logger.info("正在从Nacos注销服务...")
            deregistration_success = await nacos_client.deregister()
            if deregistration_success:
                logger.info("Nacos服务注销成功")
            else:
                logger.warning("Nacos服务注销失败")
        
        logger.info("意图识别服务已关闭")
        
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