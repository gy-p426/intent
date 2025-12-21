"""
Nacos服务注册模块
使用nacos-sdk-python 3.0.0实现服务注册与发现
"""
import asyncio
import socket
import os
from typing import Optional
from v2.nacos import NacosNamingService, ClientConfigBuilder, GRPCConfig, RegisterInstanceParam, DeregisterInstanceParam, ListInstanceParam
from infrastructure.logging_config import get_logger


class NacosRegistration:
    """
    Nacos服务注册类
    负责服务的注册、注销和心跳维护
    """
    
    def __init__(self, 
                 server_addr: str,
                 service_name: str,
                 service_port: int,
                 namespace: str = "public",
                 ip: Optional[str] = None):
        """
        初始化Nacos注册客户端
        
        Args:
            server_addr: Nacos服务器地址，格式: host:port
            service_name: 服务名称
            service_port: 服务端口
            namespace: 命名空间，默认为public
            ip: 服务IP地址，如果不提供则自动获取
        """
        self.server_addr = server_addr
        self.service_name = service_name
        self.service_port = service_port
        self.namespace = namespace
        self.logger = get_logger(__name__)
        self.ip = ip or self._get_local_ip()
        
        # 构建客户端配置
        self.client_config = (ClientConfigBuilder()
                             .server_address(server_addr)
                             .namespace_id(namespace)
                             .log_level('ERROR')  # 设置为ERROR级别，减少gRPC调试日志
                             .grpc_config(GRPCConfig(grpc_timeout=5000))
                             .build())
        
        self.client = None
        self._registered = False
    
    def _get_local_ip(self) -> str:
        """
        获取本机IP地址
        
        Returns:
            str: 本机IP地址
        """
        try:
            # 创建一个UDP socket连接到外部地址来获取本机IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
            self.logger.debug(f"自动获取本机IP地址: {local_ip}")
            return local_ip
        except Exception as e:
            self.logger.warning(f"无法自动获取IP地址，使用默认值: {str(e)}")
            return "127.0.0.1"
    
    def _build_service_metadata(self) -> dict:
        """
        构建服务元数据
        
        Returns:
            dict: 服务元数据字典
        """
        from infrastructure.config import get_settings
        
        try:
            settings = get_settings()
            
            # 基础元数据
            metadata = {
                "version": "2.0.0",
                "service_type": "algorithm-integration",
                "framework": "fastapi",
                "python_version": os.environ.get("PYTHON_VERSION", "3.11"),
                "deployment_env": os.environ.get("DEPLOYMENT_ENV", "production")
            }
            
            # 算法服务能力
            try:
                from algorithm.config_manager import get_algorithm_config_manager
                config_manager = get_algorithm_config_manager()
                
                # 获取支持的算法类型
                supported_algorithms = config_manager.get_supported_algorithms()
                if supported_algorithms:
                    metadata["supported_algorithms"] = ",".join(supported_algorithms)
                    metadata["algorithms_count"] = str(len(supported_algorithms))
                
                # 配置版本
                config_version = config_manager.get_config_version()
                if config_version:
                    metadata["algorithm_config_version"] = config_version
                
            except Exception as e:
                self.logger.warning(f"无法获取算法配置信息: {str(e)}")
            
            # 服务特性
            features = []
            if settings.algorithm_config_hot_reload:
                features.append("hot_reload")
            if settings.cache_enabled:
                features.append("caching")
            features.append("streaming")
            features.append("async_tasks")
            
            metadata["features"] = ",".join(features)
            
            # 依赖服务
            dependencies = []
            if settings.nl2sql_base_url:
                dependencies.append("nl2sql")
            if settings.clustering_api_url:
                dependencies.append("clustering")
            if settings.classification_api_url:
                dependencies.append("classification")
            
            metadata["dependencies"] = ",".join(dependencies)
            
            # 性能配置
            metadata["async_task_max_concurrent"] = str(settings.async_task_max_concurrent)
            metadata["stream_enabled"] = "true"
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"构建服务元数据失败: {str(e)}")
            # 返回基础元数据
            return {
                "version": "2.0.0",
                "service_type": "algorithm-integration",
                "framework": "fastapi"
            }
    
    async def register(self) -> bool:
        """
        注册服务到Nacos
        
        Returns:
            bool: 注册是否成功
        """
        try:
            # 初始化客户端（如果还没有初始化）
            if self.client is None:
                self.logger.info(f"正在连接Nacos服务器: {self.server_addr}")
                self.client = await NacosNamingService.create_naming_service(self.client_config)
                self.logger.info(f"Nacos客户端初始化成功 - 服务器: {self.server_addr}, 命名空间: {self.namespace}")
            
            self.logger.info(f"正在注册服务到Nacos - 服务: {self.service_name}, "
                           f"地址: {self.ip}:{self.service_port}")
            
            # 注册服务实例
            response = await self.client.register_instance(
                request=RegisterInstanceParam(
                    service_name=self.service_name,
                    group_name='DEFAULT_GROUP',
                    ip=self.ip,
                    port=self.service_port,
                    weight=1.0,
                    cluster_name='DEFAULT',
                    metadata=self._build_service_metadata(),
                    enabled=True,
                    healthy=True,
                    ephemeral=True
                )
            )
            
            if response:
                self._registered = True
                self.logger.info(f"服务注册成功 - {self.service_name}@{self.ip}:{self.service_port}")
                
                # 验证注册状态
                await asyncio.sleep(1)  # 等待注册生效
                if await self._verify_registration():
                    self.logger.info("服务注册状态验证成功")
                    return True
                else:
                    self.logger.warning("服务注册状态验证失败")
                    return False
            else:
                self.logger.error("服务注册失败")
                return False
                
        except Exception as e:
            error_msg = str(e)
            if "failed to connect server" in error_msg:
                self.logger.error(f"无法连接到Nacos服务器 {self.server_addr}，请检查：")
                self.logger.error("1. Nacos服务器是否正在运行")
                self.logger.error("2. 服务器地址配置是否正确")
                self.logger.error("3. 网络连接是否正常")
            else:
                self.logger.error(f"服务注册异常: {error_msg}", exc_info=True)
            return False
    
    async def deregister(self) -> bool:
        """
        从Nacos注销服务
        
        Returns:
            bool: 注销是否成功
        """
        if not self._registered or self.client is None:
            self.logger.info("服务未注册，无需注销")
            return True
        
        try:
            self.logger.info(f"正在从Nacos注销服务 - {self.service_name}@{self.ip}:{self.service_port}")
            
            response = await self.client.deregister_instance(
                request=DeregisterInstanceParam(
                    service_name=self.service_name,
                    group_name='DEFAULT_GROUP',
                    ip=self.ip,
                    port=self.service_port,
                    cluster_name='DEFAULT',
                    ephemeral=True
                )
            )
            
            if response:
                self._registered = False
                self.logger.info("服务注销成功")
                return True
            else:
                self.logger.error("服务注销失败")
                return False
                
        except Exception as e:
            self.logger.error(f"服务注销异常: {str(e)}", exc_info=True)
            return False
    
    async def _verify_registration(self) -> bool:
        """
        验证服务是否已成功注册
        
        Returns:
            bool: 验证是否成功
        """
        try:
            if self.client is None:
                return False
                
            instance_list = await self.client.list_instances(
                ListInstanceParam(
                    service_name=self.service_name,
                    group_name='DEFAULT_GROUP',
                    healthy_only=True,
                    subscribe=False
                )
            )
            
            # 检查当前实例是否在列表中
            for instance in instance_list:
                if (instance.ip == self.ip and 
                    instance.port == self.service_port and
                    instance.enabled and
                    instance.healthy):
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"验证服务注册状态失败: {str(e)}")
            return False
    
    async def send_heartbeat(self) -> bool:
        """
        发送心跳（Nacos SDK 3.0.0会自动处理心跳，此方法仅用于兼容性）
        
        Returns:
            bool: 心跳是否成功
        """
        # 新版本SDK自动处理心跳，直接返回注册状态
        return self._registered
    
    async def get_service_instances(self, service_name: Optional[str] = None) -> list:
        """
        获取服务实例列表
        
        Args:
            service_name: 服务名称，如果不提供则使用当前服务名称
            
        Returns:
            list: 服务实例列表
        """
        try:
            if self.client is None:
                self.logger.warning("Nacos客户端未初始化")
                return []
                
            target_service = service_name or self.service_name
            instances = await self.client.list_instances(
                ListInstanceParam(
                    service_name=target_service,
                    group_name='DEFAULT_GROUP',
                    healthy_only=True,
                    subscribe=False
                )
            )
            
            self.logger.debug(f"获取服务实例列表成功 - {target_service}: {len(instances)}个实例")
            return instances
            
        except Exception as e:
            self.logger.error(f"获取服务实例列表失败: {str(e)}")
            return []
    
    def is_registered(self) -> bool:
        """
        检查服务是否已注册
        
        Returns:
            bool: 是否已注册
        """
        return self._registered
    
    async def update_service_metadata(self) -> bool:
        """
        更新服务元数据（重新注册以更新元数据）
        
        Returns:
            bool: 更新是否成功
        """
        if not self._registered or self.client is None:
            self.logger.warning("服务未注册，无法更新元数据")
            return False
        
        try:
            self.logger.info("正在更新服务元数据")
            
            # 重新注册以更新元数据
            response = await self.client.register_instance(
                request=RegisterInstanceParam(
                    service_name=self.service_name,
                    group_name='DEFAULT_GROUP',
                    ip=self.ip,
                    port=self.service_port,
                    weight=1.0,
                    cluster_name='DEFAULT',
                    metadata=self._build_service_metadata(),
                    enabled=True,
                    healthy=True,
                    ephemeral=True
                )
            )
            
            if response:
                self.logger.info("服务元数据更新成功")
                return True
            else:
                self.logger.error("服务元数据更新失败")
                return False
                
        except Exception as e:
            self.logger.error(f"更新服务元数据异常: {str(e)}")
            return False
    
    async def get_connection_status(self) -> dict:
        """
        获取Nacos连接状态
        
        Returns:
            dict: 连接状态信息
        """
        try:
            if self.client is None:
                return {
                    "status": "disconnected",
                    "server_addr": self.server_addr,
                    "namespace": self.namespace,
                    "registered": False,
                    "error": "客户端未初始化"
                }
            
            # 尝试获取服务列表来测试连接
            await self.client.list_instances(
                ListInstanceParam(
                    service_name=self.service_name,
                    group_name='DEFAULT_GROUP',
                    healthy_only=False,
                    subscribe=False
                )
            )
            
            return {
                "status": "connected",
                "server_addr": self.server_addr,
                "namespace": self.namespace,
                "registered": self._registered,
                "metadata": self._build_service_metadata()
            }
            
        except Exception as e:
            return {
                "status": "disconnected",
                "server_addr": self.server_addr,
                "namespace": self.namespace,
                "registered": False,
                "error": str(e)
            }
    
    async def get_service_health_info(self) -> dict:
        """
        获取服务健康信息
        
        Returns:
            dict: 服务健康信息
        """
        try:
            connection_status = await self.get_connection_status()
            
            health_info = {
                "service_name": self.service_name,
                "service_address": f"{self.ip}:{self.service_port}",
                "nacos_connection": connection_status["status"],
                "registered": self._registered,
                "metadata": connection_status.get("metadata", {}),
                "timestamp": asyncio.get_event_loop().time()
            }
            
            # 如果已注册，获取实例健康状态
            if self._registered:
                instances = await self.get_service_instances()
                current_instance = None
                
                for instance in instances:
                    if instance.ip == self.ip and instance.port == self.service_port:
                        current_instance = instance
                        break
                
                if current_instance:
                    health_info.update({
                        "instance_healthy": current_instance.healthy,
                        "instance_enabled": current_instance.enabled,
                        "instance_weight": current_instance.weight,
                        "cluster_name": current_instance.cluster_name
                    })
            
            return health_info
            
        except Exception as e:
            return {
                "service_name": self.service_name,
                "service_address": f"{self.ip}:{self.service_port}",
                "nacos_connection": "error",
                "registered": False,
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time()
            }