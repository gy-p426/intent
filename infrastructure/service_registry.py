"""
服务注册管理器
管理算法集成服务的Nacos注册和元数据更新
"""

import asyncio
import logging
from typing import Optional
from infrastructure.nacos_registration import NacosRegistration
from infrastructure.config import get_settings


logger = logging.getLogger(__name__)


class ServiceRegistryManager:
    """
    服务注册管理器
    负责管理服务注册、元数据更新和健康检查
    """
    
    def __init__(self):
        """初始化服务注册管理器"""
        self.settings = get_settings()
        self.nacos_registration: Optional[NacosRegistration] = None
        self._health_check_task: Optional[asyncio.Task] = None
        self._is_running = False
    
    async def initialize(self) -> bool:
        """
        初始化服务注册
        
        Returns:
            bool: 初始化是否成功
        """
        try:
            # 创建Nacos注册实例
            self.nacos_registration = NacosRegistration(
                server_addr=self.settings.nacos_server_addr,
                service_name=self.settings.service_name,
                service_port=self.settings.service_port,
                namespace=self.settings.nacos_namespace
            )
            
            # 注册服务
            success = await self.nacos_registration.register()
            if success:
                logger.info("服务注册管理器初始化成功")
                
                # 启动健康检查
                await self.start_health_monitoring()
                
                # 注册配置更新回调
                await self._register_config_callbacks()
                
                return True
            else:
                logger.error("服务注册失败")
                return False
                
        except Exception as e:
            logger.error(f"服务注册管理器初始化失败: {str(e)}")
            return False
    
    async def shutdown(self) -> None:
        """关闭服务注册管理器"""
        try:
            self._is_running = False
            
            # 停止健康检查
            await self.stop_health_monitoring()
            
            # 注销服务
            if self.nacos_registration:
                await self.nacos_registration.deregister()
                logger.info("服务注册管理器已关闭")
                
        except Exception as e:
            logger.error(f"关闭服务注册管理器失败: {str(e)}")
    
    async def start_health_monitoring(self) -> None:
        """启动健康检查监控"""
        if self._health_check_task and not self._health_check_task.done():
            logger.warning("健康检查监控已在运行")
            return
        
        self._is_running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info(f"启动健康检查监控，检查间隔: {self.settings.health_check_interval}秒")
    
    async def stop_health_monitoring(self) -> None:
        """停止健康检查监控"""
        self._is_running = False
        
        if self._health_check_task and not self._health_check_task.done():
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        
        logger.info("停止健康检查监控")
    
    async def _health_check_loop(self) -> None:
        """健康检查循环"""
        while self._is_running:
            try:
                if self.nacos_registration:
                    # 发送心跳（SDK自动处理，这里主要用于日志记录）
                    await self.nacos_registration.send_heartbeat()
                
                await asyncio.sleep(self.settings.health_check_interval)
                
            except Exception as e:
                logger.error(f"健康检查异常: {str(e)}")
                await asyncio.sleep(self.settings.health_check_interval)
    
    async def _register_config_callbacks(self) -> None:
        """注册配置更新回调"""
        try:
            from algorithm.config_manager import get_algorithm_config_manager
            
            config_manager = get_algorithm_config_manager()
            config_manager.register_reload_callback(self._on_algorithm_config_updated)
            
            logger.info("已注册算法配置更新回调")
            
        except Exception as e:
            logger.error(f"注册配置更新回调失败: {str(e)}")
    
    async def _on_algorithm_config_updated(self) -> None:
        """算法配置更新回调"""
        try:
            logger.info("检测到算法配置更新，正在更新服务元数据")
            
            if self.nacos_registration:
                success = await self.nacos_registration.update_service_metadata()
                if success:
                    logger.info("服务元数据更新成功")
                else:
                    logger.error("服务元数据更新失败")
            
        except Exception as e:
            logger.error(f"处理算法配置更新失败: {str(e)}")
    
    async def get_service_status(self) -> dict:
        """
        获取服务状态
        
        Returns:
            dict: 服务状态信息
        """
        try:
            if not self.nacos_registration:
                return {
                    "status": "not_initialized",
                    "error": "服务注册管理器未初始化"
                }
            
            # 获取Nacos连接状态
            connection_status = await self.nacos_registration.get_connection_status()
            
            # 获取服务健康信息
            health_info = await self.nacos_registration.get_service_health_info()
            
            return {
                "status": "running" if self._is_running else "stopped",
                "nacos_connection": connection_status,
                "health_info": health_info,
                "health_monitoring": self._is_running,
                "service_registered": self.nacos_registration.is_registered()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def force_metadata_update(self) -> bool:
        """
        强制更新服务元数据
        
        Returns:
            bool: 更新是否成功
        """
        try:
            if not self.nacos_registration:
                logger.error("服务注册管理器未初始化")
                return False
            
            logger.info("强制更新服务元数据")
            return await self.nacos_registration.update_service_metadata()
            
        except Exception as e:
            logger.error(f"强制更新服务元数据失败: {str(e)}")
            return False
    
    def is_registered(self) -> bool:
        """
        检查服务是否已注册
        
        Returns:
            bool: 是否已注册
        """
        return (self.nacos_registration is not None and 
                self.nacos_registration.is_registered())
    
    def is_running(self) -> bool:
        """
        检查服务注册管理器是否正在运行
        
        Returns:
            bool: 是否正在运行
        """
        return self._is_running


# 全局服务注册管理器实例
service_registry_manager = ServiceRegistryManager()


def get_service_registry_manager() -> ServiceRegistryManager:
    """
    获取服务注册管理器实例
    
    Returns:
        ServiceRegistryManager: 服务注册管理器实例
    """
    return service_registry_manager