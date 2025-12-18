"""
FastAPI应用程序
提供意图识别服务的HTTP API接口
"""

import logging
import time
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from api.models import (
    IntentRecognitionRequest,
    IntentRecognitionResponse,
    HealthCheckResponse,
    ErrorResponse,
    IntentResult
)
from services.intent_recognition_service import IntentRecognitionService


logger = logging.getLogger(__name__)


class IntentRecognitionAPI:
    """意图识别API应用"""
    
    def __init__(self):
        """初始化FastAPI应用"""
        self.app = FastAPI(
            title="Intent Recognition Service",
            description="基于RAG和大模型的意图识别微服务",
            version="1.0.0",
            docs_url="/docs",
            redoc_url="/redoc"
        )
        
        # 添加CORS中间件
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # 服务实例（将在启动时注入）
        self.intent_service: Optional[IntentRecognitionService] = None
        self.nacos_client = None
        self.knowledge_base_loaded = False
        
        # 注册路由
        self._register_routes()
        
        # 注册异常处理器
        self._register_exception_handlers()
        
        logger.info("FastAPI应用初始化完成")
    
    def set_intent_service(self, service: IntentRecognitionService):
        """设置意图识别服务实例"""
        self.intent_service = service
        logger.info("意图识别服务已注入")
    
    def set_nacos_client(self, client):
        """设置Nacos客户端"""
        self.nacos_client = client
        logger.info("Nacos客户端已注入")
    
    def set_knowledge_base_status(self, loaded: bool):
        """设置知识库加载状态"""
        self.knowledge_base_loaded = loaded
        logger.info(f"知识库状态更新: {'已加载' if loaded else '未加载'}")
    
    def _register_routes(self):
        """注册API路由"""
        
        @self.app.post(
            "/api/v1/intent/recognize",
            response_model=IntentRecognitionResponse,
            summary="识别用户意图",
            description="接收用户问题，返回识别出的微服务名称"
        )
        async def recognize_intent(request: IntentRecognitionRequest) -> IntentRecognitionResponse:
            """
            意图识别接口
            
            接收用户问题，通过RAG检索和大模型判断，返回最匹配的微服务名称
            """
            try:
                # 检查服务是否可用
                if not self.intent_service:
                    logger.error("意图识别服务未初始化")
                    raise HTTPException(
                        status_code=503,
                        detail="Service not available: Intent recognition service not initialized"
                    )
                
                logger.info(f"收到意图识别请求: {request.question}")
                
                # 调用意图识别服务
                result = await self.intent_service.recognize_intent(
                    question=request.question,
                    top_k=request.top_k
                )
                
                # 构建响应
                response = IntentRecognitionResponse(
                    code=200,
                    message="success",
                    data=result
                )
                
                logger.info(
                    f"意图识别成功: {result.intents}, "
                    f"耗时: {result.processing_time_ms}ms"
                )
                
                return response
                
            except ValueError as e:
                # 参数验证错误
                logger.warning(f"请求参数无效: {str(e)}")
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid request: {str(e)}"
                )
            
            except Exception as e:
                # 其他服务错误
                logger.error(f"意图识别失败: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Internal server error"
                )
        
        @self.app.get(
            "/health",
            response_model=HealthCheckResponse,
            summary="健康检查",
            description="检查服务状态和各组件连接状态"
        )
        async def health_check() -> HealthCheckResponse:
            """
            健康检查接口
            
            检查服务状态、Nacos连接状态、知识库加载状态等
            """
            try:
                # 检查各组件状态
                checks = {}
                
                # 检查Nacos连接状态
                if self.nacos_client:
                    try:
                        nacos_status = self.nacos_client.get_connection_status()
                        checks["nacos"] = nacos_status["status"]
                    except Exception:
                        checks["nacos"] = "disconnected"
                else:
                    checks["nacos"] = "not_configured"
                
                # 检查知识库状态
                checks["knowledge_base"] = "loaded" if self.knowledge_base_loaded else "not_loaded"
                
                # 检查意图识别服务状态
                checks["intent_service"] = "available" if self.intent_service else "not_available"
                
                # 确定整体状态
                status = "healthy" if all(
                    check in ["connected", "loaded", "available"] 
                    for check in checks.values()
                ) else "unhealthy"
                
                response = HealthCheckResponse(
                    status=status,
                    service="intent-recognition-service",
                    timestamp=datetime.utcnow().isoformat() + "Z",
                    checks=checks
                )
                
                logger.debug(f"健康检查完成: {status}")
                return response
                
            except Exception as e:
                logger.error(f"健康检查失败: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Health check failed"
                )
        
        @self.app.get("/", summary="根路径", description="服务信息")
        async def root():
            """根路径，返回服务基本信息"""
            return {
                "service": "intent-recognition-service",
                "version": "1.0.0",
                "status": "running",
                "docs": "/docs"
            }
    
    def _register_exception_handlers(self):
        """注册全局异常处理器"""
        
        @self.app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            """HTTP异常处理器"""
            logger.warning(
                f"HTTP异常: {exc.status_code} - {exc.detail}, "
                f"请求: {request.method} {request.url}"
            )
            
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "code": exc.status_code,
                    "message": exc.detail,
                    "data": None
                }
            )
        
        @self.app.exception_handler(Exception)
        async def global_exception_handler(request: Request, exc: Exception):
            """全局异常处理器"""
            logger.error(
                f"未处理的异常: {str(exc)}, "
                f"请求: {request.method} {request.url}",
                exc_info=True
            )
            
            return JSONResponse(
                status_code=500,
                content={
                    "code": 500,
                    "message": "Internal server error",
                    "data": None
                }
            )


# 创建应用实例
api_app = IntentRecognitionAPI()
app = api_app.app