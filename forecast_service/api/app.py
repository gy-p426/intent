"""
FastAPI应用配置
Forecast Microservice FastAPI Application
"""
from datetime import datetime
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel, Field
import sys
import os
import logging

logger = logging.getLogger(__name__)

# 添加父目录到路径以便导入config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import get_settings


# 响应模型
class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = Field(..., description="服务状态: healthy/degraded/unhealthy")
    service: str = Field(..., description="服务名称")
    version: str = Field(..., description="服务版本")
    timestamp: str = Field(..., description="响应时间戳")
    components: Dict[str, str] = Field(default_factory=dict, description="组件状态")


class BaseAPIResponse(BaseModel):
    """基础API响应"""
    success: bool = Field(..., description="请求是否成功")
    message: str | None = Field(default=None, description="响应消息")
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="响应时间戳"
    )


def create_app() -> FastAPI:
    """创建FastAPI应用实例"""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.service_name,
        description="趋势分析与预测微服务 - 提供趋势分解、趋势检测、单变量预测和多变量预测功能",
        version=settings.service_version,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    
    # 422 验证错误详细输出
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """处理请求验证错误，输出详细信息"""
        errors = exc.errors()
        error_details = []
        for error in errors:
            error_details.append({
                "field": " -> ".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
                "input": error.get("input")
            })
        
        # 控制台输出详细错误
        logger.error(f"请求验证失败 [{request.method}] {request.url}")
        logger.error(f"客户端: {request.client.host if request.client else 'unknown'}")
        for detail in error_details:
            logger.error(f"  字段: {detail['field']}, 错误: {detail['message']}, 类型: {detail['type']}")
        
        # 尝试获取请求体
        try:
            body = await request.body()
            body_str = body.decode('utf-8')[:500]  # 限制长度
            logger.error(f"请求体: {body_str}")
        except:
            pass
        
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "message": "请求参数验证失败",
                "timestamp": datetime.utcnow().isoformat(),
                "errors": error_details
            }
        )
    
    # HTTP 异常处理 (400, 401, 403, 404, 500 等)
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """处理 HTTP 异常"""
        logger.error(f"HTTP 错误 {exc.status_code} [{request.method}] {request.url}")
        logger.error(f"客户端: {request.client.host if request.client else 'unknown'}")
        logger.error(f"详情: {exc.detail}")
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "message": str(exc.detail),
                "status_code": exc.status_code,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    # 通用异常处理
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """处理所有未捕获的异常"""
        logger.error(f"未处理异常 [{request.method}] {request.url}: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "message": f"服务器内部错误: {str(exc)}",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    # 请求日志中间件
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        """记录所有请求的详细信息"""
        start_time = datetime.utcnow()
        
        # 记录请求信息
        logger.info(f"收到请求 [{request.method}] {request.url}")
        logger.info(f"客户端: {request.client.host if request.client else 'unknown'}")
        
        response = await call_next(request)
        
        # 记录响应信息
        duration = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.info(f"响应完成 [{request.method}] {request.url} - 状态: {response.status_code} - 耗时: {duration:.2f}ms")
        
        return response
    
    # 配置CORS中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.get_cors_origins_list(),
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.get_cors_methods_list(),
        allow_headers=settings.get_cors_headers_list(),
    )
    
    # 注册API路由
    from .routes.trend import router as trend_router
    from .routes.univariate import router as univariate_router
    from .routes.multivariate import router as multivariate_router
    from .routes.models import router as models_router
    app.include_router(trend_router)
    app.include_router(univariate_router)
    app.include_router(multivariate_router)
    app.include_router(models_router)
    
    # 注册健康检查端点
    @app.get(
        "/health",
        response_model=HealthResponse,
        tags=["Health"],
        summary="健康检查",
        description="检查服务健康状态"
    )
    async def health_check() -> HealthResponse:
        """
        健康检查端点
        返回服务的健康状态和组件信息
        """
        components = {
            "api": "healthy",
            "trend_analysis": "healthy",
            "univariate_forecast": "healthy",
            "multivariate_forecast": "healthy"
        }
        
        # 检查所有组件状态
        all_healthy = all(status == "healthy" for status in components.values())
        any_unhealthy = any(status == "unhealthy" for status in components.values())
        
        if all_healthy:
            status = "healthy"
        elif any_unhealthy:
            status = "unhealthy"
        else:
            status = "degraded"
        
        return HealthResponse(
            status=status,
            service=settings.service_name,
            version=settings.service_version,
            timestamp=datetime.utcnow().isoformat(),
            components=components
        )
    
    # 根路径
    @app.get(
        "/",
        response_model=BaseAPIResponse,
        tags=["Root"],
        summary="服务信息",
        description="获取服务基本信息"
    )
    async def root() -> BaseAPIResponse:
        """根路径，返回服务基本信息"""
        return BaseAPIResponse(
            success=True,
            message=f"{settings.service_name} v{settings.service_version} is running",
            timestamp=datetime.utcnow().isoformat()
        )
    
    return app


# 创建应用实例
app = create_app()
