"""
服务发现客户端
基于Nacos实现微服务发现和负载均衡
"""

import asyncio
import logging
import random
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from infrastructure.nacos_registration import NacosRegistration
from infrastructure.config import get_settings


logger = logging.getLogger(__name__)


class ServiceInstance:
    """服务实例信息"""
    
    def __init__(self, ip: str, port: int, healthy: bool = True, enabled: bool = True, 
                 weight: float = 1.0, metadata: Optional[Dict[str, Any]] = None):
        self.ip = ip
        self.port = port
        self.healthy = healthy
        self.enabled = enabled
        self.weight = weight
        self.metadata = metadata or {}
        self.last_used = datetime.utcnow()
        self.connection_count = 0
    
    @property
    def url(self) -> str:
        """获取服务实例的URL"""
        return f"http://{self.ip}:{self.port}"
    
    @property
    def is_available(self) -> bool:
        """检查实例是否可用"""
        return self.healthy and self.enabled
    
    def __str__(self) -> str:
        return f"ServiceInstance({self.ip}:{self.port}, healthy={self.healthy})"


class LoadBalancer:
    """负载均衡器"""
    
    def __init__(self, strategy: str = "round_robin"):
        """
        初始化负载均衡器
        
        Args:
            strategy: 负载均衡策略 (round_robin, random, least_connections)
        """
        self.strategy = strategy
        self.round_robin_index = {}
    
    def select_instance(self, service_name: str, instances: List[ServiceInstance]) -> Optional[ServiceInstance]:
        """
        根据负载均衡策略选择服务实例
        
        Args:
            service_name: 服务名称
            instances: 可用实例列表
            
        Returns:
            ServiceInstance: 选中的实例，如果没有可用实例则返回None
        """
        if not instances:
            return None
        
        # 过滤出可用的实例
        available_instances = [inst for inst in instances if inst.is_available]
        
        if not available_instances:
            logger.warning(f"服务 {service_name} 没有可用实例")
            return None
        
        if self.strategy == "round_robin":
            return self._round_robin_select(service_name, available_instances)
        elif self.strategy == "random":
            return self._random_select(available_instances)
        elif self.strategy == "least_connections":
            return self._least_connections_select(available_instances)
        else:
            logger.warning(f"未知的负载均衡策略: {self.strategy}，使用轮询策略")
            return self._round_robin_select(service_name, available_instances)
    
    def _round_robin_select(self, service_name: str, instances: List[ServiceInstance]) -> ServiceInstance:
        """轮询选择"""
        if service_name not in self.round_robin_index:
            self.round_robin_index[service_name] = 0
        
        index = self.round_robin_index[service_name] % len(instances)
        self.round_robin_index[service_name] = (index + 1) % len(instances)
        
        selected = instances[index]
        selected.last_used = datetime.utcnow()
        selected.connection_count += 1
        
        return selected
    
    def _random_select(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """随机选择"""
        selected = random.choice(instances)
        selected.last_used = datetime.utcnow()
        selected.connection_count += 1
        
        return selected
    
    def _least_connections_select(self, instances: List[ServiceInstance]) -> ServiceInstance:
        """最少连接选择"""
        selected = min(instances, key=lambda x: x.connection_count)
        selected.last_used = datetime.utcnow()
        selected.connection_count += 1
        
        return selected


class ServiceDiscoveryClient:
    """服务发现客户端"""
    
    def __init__(self, nacos_registration: Optional[NacosRegistration] = None):
        """
        初始化服务发现客户端
        
        Args:
            nacos_registration: Nacos注册客户端实例
        """
        self.settings = get_settings()
        self.nacos_registration = nacos_registration
        self.load_balancer = LoadBalancer(self.settings.load_balance_strategy)
        
        # 服务实例缓存
        self.service_cache: Dict[str, List[ServiceInstance]] = {}
        self.cache_timestamps: Dict[str, datetime] = {}
        self.cache_ttl = timedelta(seconds=self.settings.service_health_check_interval)
        
        # 静态服务配置映射
        self.static_service_urls = self._build_static_service_mapping()
        
        logger.info(f"服务发现客户端初始化完成，模式: {self.settings.service_discovery_mode}")
    
    def _build_static_service_mapping(self) -> Dict[str, str]:
        """构建静态服务URL映射"""
        return {
            self.settings.nl2sql_service_name: self.settings.nl2sql_base_url,
            self.settings.clustering_service_name: self.settings.clustering_api_url,
            self.settings.classification_service_name: self.settings.classification_api_url,
            self.settings.prediction_service_name: self.settings.prediction_api_url,
            self.settings.anomaly_service_name: self.settings.anomaly_api_url,
            self.settings.association_service_name: self.settings.association_api_url,
            self.settings.comparison_service_name: self.settings.comparison_api_url,
            self.settings.similarity_service_name: self.settings.similarity_api_url,
            self.settings.trend_service_name: self.settings.trend_api_url,
            self.settings.profile_service_name: self.settings.profile_api_url,
            self.settings.causality_service_name: self.settings.causality_api_url,
            self.settings.alert_service_name: self.settings.alert_api_url,
            self.settings.recommendation_service_name: self.settings.recommendation_api_url,
        }
    
    async def discover_service(self, service_name: str) -> Optional[str]:
        """
        发现服务并返回可用的服务URL
        
        Args:
            service_name: 服务名称
            
        Returns:
            str: 服务URL，如果服务不可用则返回None
        """
        try:
            if not self.settings.service_discovery_enabled or self.settings.service_discovery_mode == "static":
                # 使用静态配置
                return self._get_static_service_url(service_name)
            
            # 使用Nacos服务发现
            return await self._discover_from_nacos(service_name)
            
        except Exception as e:
            logger.error(f"服务发现失败 - {service_name}: {str(e)}")
            # 降级到静态配置
            return self._get_static_service_url(service_name)
    
    def _get_static_service_url(self, service_name: str) -> Optional[str]:
        """获取静态配置的服务URL"""
        url = self.static_service_urls.get(service_name)
        if url:
            logger.debug(f"使用静态配置获取服务URL - {service_name}: {url}")
        else:
            logger.warning(f"未找到服务的静态配置 - {service_name}")
        return url
    
    async def _discover_from_nacos(self, service_name: str) -> Optional[str]:
        """从Nacos发现服务"""
        if not self.nacos_registration:
            logger.warning("Nacos注册客户端未初始化，降级到静态配置")
            return self._get_static_service_url(service_name)
        
        try:
            # 检查缓存
            if self._is_cache_valid(service_name):
                instances = self.service_cache[service_name]
                logger.debug(f"使用缓存的服务实例 - {service_name}: {len(instances)}个实例")
            else:
                # 从Nacos获取服务实例
                nacos_instances = await self.nacos_registration.get_service_instances(service_name)
                instances = self._convert_nacos_instances(nacos_instances)
                
                # 更新缓存
                self.service_cache[service_name] = instances
                self.cache_timestamps[service_name] = datetime.utcnow()
                
                logger.debug(f"从Nacos获取服务实例 - {service_name}: {len(instances)}个实例")
            
            # 使用负载均衡选择实例
            selected_instance = self.load_balancer.select_instance(service_name, instances)
            
            if selected_instance:
                logger.debug(f"选择服务实例 - {service_name}: {selected_instance.url}")
                return selected_instance.url
            else:
                logger.warning(f"没有可用的服务实例 - {service_name}")
                return None
                
        except Exception as e:
            logger.error(f"从Nacos发现服务失败 - {service_name}: {str(e)}")
            return None
    
    def _is_cache_valid(self, service_name: str) -> bool:
        """检查缓存是否有效"""
        if service_name not in self.cache_timestamps:
            return False
        
        cache_time = self.cache_timestamps[service_name]
        return datetime.utcnow() - cache_time < self.cache_ttl
    
    def _convert_nacos_instances(self, nacos_instances: List[Any]) -> List[ServiceInstance]:
        """转换Nacos实例为内部ServiceInstance对象"""
        instances = []
        
        for nacos_inst in nacos_instances:
            try:
                instance = ServiceInstance(
                    ip=nacos_inst.ip,
                    port=nacos_inst.port,
                    healthy=getattr(nacos_inst, 'healthy', True),
                    enabled=getattr(nacos_inst, 'enabled', True),
                    weight=getattr(nacos_inst, 'weight', 1.0),
                    metadata=getattr(nacos_inst, 'metadata', {})
                )
                instances.append(instance)
            except Exception as e:
                logger.warning(f"转换Nacos实例失败: {str(e)}")
                continue
        
        return instances
    
    async def get_all_service_instances(self, service_name: str) -> List[ServiceInstance]:
        """
        获取服务的所有实例
        
        Args:
            service_name: 服务名称
            
        Returns:
            List[ServiceInstance]: 服务实例列表
        """
        try:
            if not self.settings.service_discovery_enabled or self.settings.service_discovery_mode == "static":
                # 静态模式，返回单个实例
                url = self._get_static_service_url(service_name)
                if url:
                    # 解析URL获取IP和端口
                    import urllib.parse
                    parsed = urllib.parse.urlparse(url)
                    return [ServiceInstance(
                        ip=parsed.hostname or "localhost",
                        port=parsed.port or 80,
                        healthy=True,
                        enabled=True
                    )]
                return []
            
            # 从Nacos获取
            if not self.nacos_registration:
                return []
            
            nacos_instances = await self.nacos_registration.get_service_instances(service_name)
            return self._convert_nacos_instances(nacos_instances)
            
        except Exception as e:
            logger.error(f"获取服务实例列表失败 - {service_name}: {str(e)}")
            return []
    
    async def health_check_service(self, service_name: str) -> Dict[str, Any]:
        """
        检查服务健康状态
        
        Args:
            service_name: 服务名称
            
        Returns:
            Dict[str, Any]: 健康状态信息
        """
        try:
            instances = await self.get_all_service_instances(service_name)
            
            total_instances = len(instances)
            healthy_instances = len([inst for inst in instances if inst.is_available])
            
            status = "healthy" if healthy_instances > 0 else "unhealthy"
            if total_instances > 0 and healthy_instances < total_instances:
                status = "degraded"
            
            return {
                "service_name": service_name,
                "status": status,
                "total_instances": total_instances,
                "healthy_instances": healthy_instances,
                "discovery_mode": self.settings.service_discovery_mode,
                "load_balance_strategy": self.settings.load_balance_strategy,
                "instances": [
                    {
                        "url": inst.url,
                        "healthy": inst.healthy,
                        "enabled": inst.enabled,
                        "weight": inst.weight,
                        "connection_count": inst.connection_count,
                        "last_used": inst.last_used.isoformat()
                    }
                    for inst in instances
                ],
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"服务健康检查失败 - {service_name}: {str(e)}")
            return {
                "service_name": service_name,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def clear_cache(self, service_name: Optional[str] = None):
        """
        清除服务实例缓存
        
        Args:
            service_name: 服务名称，如果为None则清除所有缓存
        """
        if service_name:
            self.service_cache.pop(service_name, None)
            self.cache_timestamps.pop(service_name, None)
            logger.debug(f"清除服务缓存 - {service_name}")
        else:
            self.service_cache.clear()
            self.cache_timestamps.clear()
            logger.debug("清除所有服务缓存")
    
    def get_service_stats(self) -> Dict[str, Any]:
        """
        获取服务发现统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "discovery_mode": self.settings.service_discovery_mode,
            "discovery_enabled": self.settings.service_discovery_enabled,
            "load_balance_strategy": self.settings.load_balance_strategy,
            "cache_ttl_seconds": self.cache_ttl.total_seconds(),
            "cached_services": list(self.service_cache.keys()),
            "static_services": list(self.static_service_urls.keys()),
            "nacos_available": self.nacos_registration is not None
        }
    
    async def validate_all_services(self) -> Dict[str, Dict[str, Any]]:
        """
        验证所有配置的服务
        
        Returns:
            Dict[str, Dict[str, Any]]: 各服务的验证结果
        """
        results = {}
        
        # 获取所有配置的服务名称
        service_names = list(self.static_service_urls.keys())
        
        for service_name in service_names:
            try:
                health_info = await self.health_check_service(service_name)
                results[service_name] = health_info
            except Exception as e:
                results[service_name] = {
                    "service_name": service_name,
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        return results


# 全局服务发现客户端实例
_service_discovery_client: Optional[ServiceDiscoveryClient] = None


def get_service_discovery_client() -> ServiceDiscoveryClient:
    """
    获取服务发现客户端实例
    
    Returns:
        ServiceDiscoveryClient: 服务发现客户端实例
    """
    global _service_discovery_client
    
    if _service_discovery_client is None:
        # 尝试获取Nacos注册客户端
        try:
            from infrastructure.service_registry import get_service_registry_manager
            registry_manager = get_service_registry_manager()
            nacos_registration = registry_manager.nacos_registration
        except Exception:
            nacos_registration = None
        
        _service_discovery_client = ServiceDiscoveryClient(nacos_registration)
    
    return _service_discovery_client


def set_service_discovery_client(client: ServiceDiscoveryClient):
    """
    设置服务发现客户端实例
    
    Args:
        client: 服务发现客户端实例
    """
    global _service_discovery_client
    _service_discovery_client = client