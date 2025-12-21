"""
FastAPI应用程序
提供意图识别服务的HTTP API接口
"""

import logging
import time
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware

from api.models import (
    IntentRecognitionRequest,
    IntentRecognitionResponse,
    HealthCheckResponse,
    ErrorResponse,
    IntentResult
)
from services.intent_recognition_service import IntentRecognitionService
from api.algorithm_api import algorithm_api
from algorithm.logging import get_monitoring_integration


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
        self.service_registry = None
        self.knowledge_base_loaded = False
        
        # 监控集成
        self.monitoring = get_monitoring_integration()
        
        # 注册路由
        self._register_routes()
        
        # 注册算法集成路由
        algorithm_api.register_routes(self.app)
        
        # 注册算法服务专用健康检查路由
        self._register_algorithm_health_routes()
        
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
    
    def set_service_registry(self, registry):
        """设置服务注册管理器"""
        self.service_registry = registry
        logger.info("服务注册管理器已注入")
    
    def set_knowledge_base_status(self, loaded: bool):
        """设置知识库加载状态"""
        self.knowledge_base_loaded = loaded
        logger.info(f"知识库状态更新: {'已加载' if loaded else '未加载'}")
    
    def set_algorithm_service(self, service):
        """设置算法集成服务实例"""
        self._algorithm_service = service  # Store reference for cleanup
        algorithm_api.set_algorithm_service(service)
        logger.info("算法集成服务已注入到API")
    
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
            
            检查服务状态、Nacos连接状态、知识库加载状态、算法服务组件状态等
            """
            try:
                # 检查各组件状态
                checks = {}
                
                # 检查服务注册状态
                if self.service_registry:
                    try:
                        registry_status = await self.service_registry.get_service_status()
                        checks["service_registry"] = registry_status["status"]
                        checks["nacos"] = registry_status["nacos_connection"]["status"]
                        checks["service_registered"] = "yes" if registry_status["service_registered"] else "no"
                    except Exception:
                        checks["service_registry"] = "error"
                        checks["nacos"] = "disconnected"
                        checks["service_registered"] = "no"
                else:
                    checks["service_registry"] = "not_configured"
                    checks["nacos"] = "not_configured"
                    checks["service_registered"] = "no"
                
                # 检查知识库状态
                checks["knowledge_base"] = "loaded" if self.knowledge_base_loaded else "not_loaded"
                
                # 检查意图识别服务状态
                checks["intent_service"] = "available" if self.intent_service else "not_available"
                
                # 检查算法集成服务状态
                if hasattr(self, '_algorithm_service') and self._algorithm_service:
                    try:
                        algorithm_health = self._algorithm_service.get_service_health()
                        checks["algorithm_service"] = algorithm_health["status"]
                        
                        # 添加算法服务组件的详细状态
                        for component_name, component_status in algorithm_health["components"].items():
                            checks[f"algorithm_{component_name}"] = component_status["status"]
                        
                        # 添加错误和重试统计信息
                        if "error_statistics" in algorithm_health:
                            checks["algorithm_errors"] = "normal" if algorithm_health["error_statistics"]["total_errors"] < 10 else "high"
                        
                        if "retry_statistics" in algorithm_health:
                            checks["algorithm_retries"] = "normal" if algorithm_health["retry_statistics"]["total_retries"] < 20 else "high"
                            
                    except Exception as e:
                        logger.warning(f"获取算法服务健康状态失败: {str(e)}")
                        checks["algorithm_service"] = "error"
                else:
                    checks["algorithm_service"] = "not_available"
                
                # 确定整体状态
                healthy_statuses = ["connected", "loaded", "available", "healthy", "normal"]
                degraded_statuses = ["degraded", "high"]
                
                healthy_count = sum(1 for status in checks.values() if status in healthy_statuses)
                degraded_count = sum(1 for status in checks.values() if status in degraded_statuses)
                total_checks = len(checks)
                
                if healthy_count == total_checks:
                    status = "healthy"
                elif healthy_count + degraded_count >= total_checks * 0.8:
                    status = "degraded"
                else:
                    status = "unhealthy"
                
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
        
        @self.app.get(
            "/metrics",
            summary="服务指标",
            description="获取服务运行指标和统计信息"
        )
        async def get_metrics():
            """
            服务指标接口
            
            返回服务运行指标，包括算法服务的错误统计、重试统计等
            """
            try:
                # 收集当前服务指标
                current_metrics = self.monitoring.collect_service_metrics()
                
                metrics = {
                    "service": "algorithm-integration-service",
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "current_metrics": {
                        "request_count": current_metrics.request_count,
                        "success_count": current_metrics.success_count,
                        "error_count": current_metrics.error_count,
                        "average_response_time_ms": current_metrics.average_response_time_ms,
                        "active_tasks": current_metrics.active_tasks,
                        "memory_usage_mb": current_metrics.memory_usage_mb,
                        "cpu_usage_percent": current_metrics.cpu_usage_percent
                    },
                    "intent_service": {
                        "available": self.intent_service is not None
                    },
                    "algorithm_service": {
                        "available": False
                    }
                }
                
                # 获取算法服务指标
                if hasattr(self, '_algorithm_service') and self._algorithm_service:
                    try:
                        algorithm_health = self._algorithm_service.get_service_health()
                        metrics["algorithm_service"] = {
                            "available": True,
                            "status": algorithm_health["status"],
                            "components": algorithm_health["components"],
                            "error_statistics": algorithm_health.get("error_statistics", {}),
                            "retry_statistics": algorithm_health.get("retry_statistics", {})
                        }
                    except Exception as e:
                        logger.warning(f"获取算法服务指标失败: {str(e)}")
                        metrics["algorithm_service"]["error"] = str(e)
                
                return metrics
                
            except Exception as e:
                logger.error(f"获取服务指标失败: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Failed to retrieve metrics"
                )
        
        @self.app.get(
            "/metrics/prometheus",
            summary="Prometheus格式指标",
            description="获取Prometheus格式的监控指标"
        )
        async def get_prometheus_metrics():
            """
            Prometheus格式指标接口
            
            返回Prometheus格式的监控指标，用于监控系统集成
            """
            try:
                prometheus_metrics = self.monitoring.export_metrics_for_prometheus()
                return Response(content=prometheus_metrics, media_type="text/plain")
                
            except Exception as e:
                logger.error(f"获取Prometheus指标失败: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Failed to retrieve Prometheus metrics"
                )
        
        @self.app.get(
            "/monitoring/health",
            summary="完整健康检查",
            description="执行完整的健康检查，包括所有组件和性能指标"
        )
        async def comprehensive_health_check():
            """
            完整健康检查接口
            
            执行完整的健康检查，包括组件状态、性能指标、告警状态等
            """
            try:
                # 注册组件进行监控
                self.monitoring.register_component("intent_service")
                self.monitoring.register_component("nacos_client")
                self.monitoring.register_component("service_registry")
                
                if hasattr(self, '_algorithm_service') and self._algorithm_service:
                    self.monitoring.register_component("algorithm_service")
                
                # 执行完整健康检查
                health_report = await self.monitoring.perform_full_health_check()
                
                return health_report
                
            except Exception as e:
                logger.error(f"完整健康检查失败: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Comprehensive health check failed"
                )
        
        @self.app.get(
            "/monitoring/metrics/history",
            summary="指标历史数据",
            description="获取指定时间范围内的指标历史数据"
        )
        async def get_metrics_history(hours: int = 24):
            """
            指标历史数据接口
            
            获取指定时间范围内的指标历史数据，用于趋势分析
            """
            try:
                if hours < 1 or hours > 168:  # 限制在1小时到7天之间
                    raise HTTPException(
                        status_code=400,
                        detail="Hours parameter must be between 1 and 168"
                    )
                
                history_data = self.monitoring.get_metrics_history(hours)
                
                return {
                    "service": "algorithm-integration-service",
                    "time_range_hours": hours,
                    "data_points": len(history_data),
                    "metrics_history": history_data,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"获取指标历史数据失败: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail="Failed to retrieve metrics history"
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
    
    def _register_algorithm_health_routes(self):
        """注册算法服务专用健康检查路由"""
        
        @self.app.get(
            "/health/algorithm",
            summary="算法服务健康检查",
            description="专门检查算法集成服务及其依赖的健康状态"
        )
        async def algorithm_health_check():
            """
            算法服务健康检查接口
            
            专门检查算法集成服务的各个组件状态，包括外部依赖服务
            """
            try:
                if not hasattr(self, '_algorithm_service') or not self._algorithm_service:
                    return {
                        "status": "unavailable",
                        "message": "Algorithm integration service not initialized",
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                
                # 获取算法服务详细健康状态
                health_status = self._algorithm_service.get_service_health()
                
                # 检查外部依赖服务
                external_dependencies = {}
                
                # 检查NL2SQL服务
                if self._algorithm_service.nl2sql_client:
                    try:
                        # 这里可以添加对NL2SQL服务的ping检查
                        external_dependencies["nl2sql_service"] = "available"
                    except Exception:
                        external_dependencies["nl2sql_service"] = "unavailable"
                else:
                    external_dependencies["nl2sql_service"] = "not_configured"
                
                # 检查算法API服务
                if self._algorithm_service.algorithm_executor:
                    try:
                        # 这里可以添加对算法API的ping检查
                        external_dependencies["clustering_api"] = "unknown"
                        external_dependencies["classification_api"] = "unknown"
                    except Exception:
                        external_dependencies["clustering_api"] = "unavailable"
                        external_dependencies["classification_api"] = "unavailable"
                else:
                    external_dependencies["clustering_api"] = "not_configured"
                    external_dependencies["classification_api"] = "not_configured"
                
                # 合并健康状态信息
                health_status["external_dependencies"] = external_dependencies
                
                return health_status
                
            except Exception as e:
                logger.error(f"算法服务健康检查失败: {str(e)}", exc_info=True)
                return {
                    "status": "error",
                    "message": f"Health check failed: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
        
        @self.app.get(
            "/health/dependencies",
            summary="依赖服务状态检查",
            description="检查所有外部依赖服务的连接状态"
        )
        async def dependencies_health_check():
            """
            依赖服务健康检查接口
            
            检查所有外部依赖服务的连接状态，包括Nacos、NL2SQL、算法API等
            """
            try:
                dependencies = {}
                
                # 检查Nacos
                if self.nacos_client:
                    try:
                        nacos_status = self.nacos_client.get_connection_status()
                        dependencies["nacos"] = {
                            "status": nacos_status["status"],
                            "details": nacos_status
                        }
                    except Exception as e:
                        dependencies["nacos"] = {
                            "status": "error",
                            "error": str(e)
                        }
                else:
                    dependencies["nacos"] = {"status": "not_configured"}
                
                # 检查算法服务依赖
                if hasattr(self, '_algorithm_service') and self._algorithm_service:
                    # NL2SQL服务
                    if self._algorithm_service.nl2sql_client:
                        try:
                            # 可以添加实际的连接测试
                            dependencies["nl2sql"] = {"status": "configured"}
                        except Exception as e:
                            dependencies["nl2sql"] = {
                                "status": "error",
                                "error": str(e)
                            }
                    else:
                        dependencies["nl2sql"] = {"status": "not_configured"}
                    
                    # 算法执行器
                    if self._algorithm_service.algorithm_executor:
                        dependencies["algorithm_apis"] = {"status": "configured"}
                    else:
                        dependencies["algorithm_apis"] = {"status": "not_configured"}
                
                # 计算整体依赖状态
                available_count = sum(
                    1 for dep in dependencies.values() 
                    if dep["status"] in ["connected", "configured", "available"]
                )
                total_count = len(dependencies)
                
                overall_status = "healthy" if available_count == total_count else "degraded"
                
                return {
                    "status": overall_status,
                    "dependencies": dependencies,
                    "summary": {
                        "total": total_count,
                        "available": available_count,
                        "unavailable": total_count - available_count
                    },
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                
            except Exception as e:
                logger.error(f"依赖服务健康检查失败: {str(e)}", exc_info=True)
                return {
                    "status": "error",
                    "message": f"Dependencies check failed: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
        
        @self.app.get(
            "/health/registry",
            summary="服务注册状态检查",
            description="检查服务注册管理器和Nacos注册状态"
        )
        async def registry_health_check():
            """
            服务注册健康检查接口
            
            检查服务注册管理器的状态，包括Nacos连接和服务注册状态
            """
            try:
                if not self.service_registry:
                    return {
                        "status": "not_configured",
                        "message": "Service registry not configured",
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                
                # 获取服务注册状态
                registry_status = await self.service_registry.get_service_status()
                
                return {
                    "status": registry_status["status"],
                    "service_registry": registry_status,
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
                
            except Exception as e:
                logger.error(f"服务注册健康检查失败: {str(e)}", exc_info=True)
                return {
                    "status": "error",
                    "message": f"Registry health check failed: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                }
        
        @self.app.post(
            "/admin/registry/update-metadata",
            summary="强制更新服务元数据",
            description="强制更新Nacos中的服务元数据信息"
        )
        async def force_update_metadata():
            """
            强制更新服务元数据接口
            
            手动触发服务元数据更新，用于管理和调试
            """
            try:
                if not self.service_registry:
                    raise HTTPException(
                        status_code=503,
                        detail="Service registry not configured"
                    )
                
                success = await self.service_registry.force_metadata_update()
                
                if success:
                    return {
                        "code": 200,
                        "message": "Service metadata updated successfully",
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                else:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to update service metadata"
                    )
                
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"强制更新服务元数据失败: {str(e)}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to update metadata: {str(e)}"
                )
    
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