"""
Algorithm Configuration Manager

Manages loading, validation, and hot-reloading of algorithm configurations
from the algorithm_input.json file.
"""

import json
import logging
import os
import asyncio
from typing import Dict, Optional, List, Callable
from datetime import datetime
from pathlib import Path
from algorithm.models import AlgorithmConfig, AlgorithmType, AlgorithmField, ResponseFormat
from algorithm.interfaces import IAlgorithmConfigManager
from infrastructure.config import get_settings


logger = logging.getLogger(__name__)


class AlgorithmConfigManager(IAlgorithmConfigManager):
    """算法配置管理器实现"""
    
    def __init__(self):
        """初始化配置管理器"""
        self.settings = get_settings()
        self._config_cache: Dict[str, AlgorithmConfig] = {}
        self._config_version: Optional[str] = None
        self._last_modified: Optional[float] = None
        self._backup_config: Optional[Dict[str, AlgorithmConfig]] = None
        self._reload_callbacks: List[Callable] = []
        self._reload_task: Optional[asyncio.Task] = None
        self._is_monitoring = False
        
    async def load_config(self) -> Dict[str, AlgorithmConfig]:
        """
        加载算法配置
        
        Returns:
            Dict[str, AlgorithmConfig]: 算法配置字典
            
        Raises:
            FileNotFoundError: 配置文件不存在
            ValueError: 配置格式无效
        """
        try:
            config_path = self.settings.algorithm_config_path
            
            # 检查文件是否存在
            if not os.path.exists(config_path):
                raise FileNotFoundError(f"算法配置文件不存在: {config_path}")
            
            # 检查文件修改时间
            current_modified = os.path.getmtime(config_path)
            if (self._last_modified is not None and 
                current_modified == self._last_modified and 
                self._config_cache):
                logger.debug("配置文件未修改，使用缓存配置")
                return self._config_cache
            
            # 读取配置文件
            with open(config_path, 'r', encoding='utf-8') as f:
                raw_config = json.load(f)
            
            # 验证配置格式
            if not self.validate_config(raw_config):
                raise ValueError("算法配置格式无效")
            
            # 解析配置
            algorithms_config = {}
            algorithms_data = raw_config.get('algorithms', {})
            
            for alg_type, alg_data in algorithms_data.items():
                try:
                    # 解析字段定义
                    required_fields = [
                        AlgorithmField(**field) for field in alg_data.get('required_fields', [])
                    ]
                    optional_fields = [
                        AlgorithmField(**field) for field in alg_data.get('optional_fields', [])
                    ]
                    
                    # 确定响应格式
                    response_format = ResponseFormat.SYNC
                    if 'response_format' in alg_data:
                        response_format = ResponseFormat(alg_data['response_format'])
                    elif 'response_modes' in alg_data:
                        response_format = ResponseFormat.SYNC_OR_ASYNC
                    
                    # 创建算法配置对象
                    config = AlgorithmConfig(
                        name=alg_data['name'],
                        description=alg_data['description'],
                        api_endpoint=alg_data['api_endpoint'],
                        method=alg_data.get('method', 'POST'),
                        required_fields=required_fields,
                        optional_fields=optional_fields,
                        data_format=alg_data['data_format'],
                        sql_template=alg_data.get('sql_template'),
                        response_format=response_format,
                        examples=alg_data.get('examples', []),
                        intent_keywords=alg_data.get('intent_keywords', [])
                    )
                    
                    algorithms_config[alg_type] = config
                    
                except Exception as e:
                    logger.error(f"解析算法配置失败 {alg_type}: {str(e)}")
                    continue
            
            # 备份当前配置（如果存在）
            if self._config_cache:
                self._backup_config = self._config_cache.copy()
            
            # 更新缓存
            self._config_cache = algorithms_config
            self._last_modified = current_modified
            self._config_version = raw_config.get('metadata', {}).get('version', '1.0')
            
            logger.info(f"成功加载 {len(algorithms_config)} 个算法配置，版本: {self._config_version}")
            
            # 通知配置更新回调
            await self._notify_config_updated()
            
            return algorithms_config
            
        except Exception as e:
            logger.error(f"加载算法配置失败: {str(e)}")
            
            # 如果有备份配置，恢复使用
            if self._backup_config:
                logger.warning("使用备份配置继续运行")
                self._config_cache = self._backup_config
                return self._config_cache
            
            raise
    
    async def reload_config(self) -> None:
        """重新加载配置"""
        logger.info("重新加载算法配置")
        self._last_modified = None  # 强制重新加载
        await self.load_config()
    
    def register_reload_callback(self, callback: Callable) -> None:
        """
        注册配置重载回调函数
        
        Args:
            callback: 配置更新时调用的回调函数
        """
        if callback not in self._reload_callbacks:
            self._reload_callbacks.append(callback)
            logger.debug(f"注册配置重载回调: {callback.__name__}")
    
    def unregister_reload_callback(self, callback: Callable) -> None:
        """
        取消注册配置重载回调函数
        
        Args:
            callback: 要取消的回调函数
        """
        if callback in self._reload_callbacks:
            self._reload_callbacks.remove(callback)
            logger.debug(f"取消注册配置重载回调: {callback.__name__}")
    
    async def _notify_config_updated(self) -> None:
        """通知所有注册的回调函数配置已更新"""
        for callback in self._reload_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback()
                else:
                    callback()
            except Exception as e:
                logger.error(f"配置更新回调执行失败 {callback.__name__}: {str(e)}")
    
    async def start_hot_reload_monitoring(self) -> None:
        """启动配置文件热重载监控"""
        if not self.settings.algorithm_config_hot_reload:
            logger.info("配置热重载已禁用")
            return
        
        if self._is_monitoring:
            logger.warning("配置监控已在运行")
            return
        
        self._is_monitoring = True
        self._reload_task = asyncio.create_task(self._monitor_config_file())
        logger.info(f"启动配置文件热重载监控，检查间隔: {self.settings.algorithm_config_reload_interval}秒")
    
    async def stop_hot_reload_monitoring(self) -> None:
        """停止配置文件热重载监控"""
        self._is_monitoring = False
        
        if self._reload_task and not self._reload_task.done():
            self._reload_task.cancel()
            try:
                await self._reload_task
            except asyncio.CancelledError:
                pass
        
        logger.info("停止配置文件热重载监控")
    
    async def _monitor_config_file(self) -> None:
        """监控配置文件变化"""
        config_path = Path(self.settings.algorithm_config_path)
        
        while self._is_monitoring:
            try:
                if config_path.exists():
                    current_modified = config_path.stat().st_mtime
                    
                    if (self._last_modified is not None and 
                        current_modified > self._last_modified):
                        logger.info("检测到配置文件变化，重新加载配置")
                        try:
                            await self.load_config()
                            logger.info("配置热重载成功")
                        except Exception as e:
                            logger.error(f"配置热重载失败: {str(e)}")
                
                await asyncio.sleep(self.settings.algorithm_config_reload_interval)
                
            except Exception as e:
                logger.error(f"配置文件监控异常: {str(e)}")
                await asyncio.sleep(self.settings.algorithm_config_reload_interval)
    
    def get_algorithm_config(self, algorithm_type: AlgorithmType) -> Optional[AlgorithmConfig]:
        """
        获取指定算法的配置
        
        Args:
            algorithm_type: 算法类型
            
        Returns:
            Optional[AlgorithmConfig]: 算法配置
        """
        return self._config_cache.get(algorithm_type.value)
    
    def validate_config(self, config: Dict) -> bool:
        """
        验证配置格式
        
        Args:
            config: 配置字典
            
        Returns:
            bool: 配置是否有效
        """
        try:
            # 检查基本结构
            if not isinstance(config, dict):
                logger.error("配置必须是字典格式")
                return False
            
            if 'algorithms' not in config:
                logger.error("配置中缺少 'algorithms' 字段")
                return False
            
            algorithms = config['algorithms']
            if not isinstance(algorithms, dict):
                logger.error("'algorithms' 字段必须是字典格式")
                return False
            
            if not algorithms:
                logger.error("算法配置不能为空")
                return False
            
            # 验证元数据
            if not self._validate_metadata(config.get('metadata', {})):
                return False
            
            # 验证每个算法配置
            for alg_type, alg_config in algorithms.items():
                if not self._validate_algorithm_config(alg_type, alg_config):
                    return False
            
            # 验证算法类型是否重复
            if len(set(algorithms.keys())) != len(algorithms.keys()):
                logger.error("发现重复的算法类型")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"配置验证失败: {str(e)}")
            return False
    
    def _validate_metadata(self, metadata: Dict) -> bool:
        """
        验证元数据配置
        
        Args:
            metadata: 元数据字典
            
        Returns:
            bool: 元数据是否有效
        """
        if not isinstance(metadata, dict):
            logger.error("metadata必须是字典格式")
            return False
        
        # 验证版本格式
        version = metadata.get('version')
        if version and not isinstance(version, str):
            logger.error("版本号必须是字符串格式")
            return False
        
        # 验证支持的数据格式
        supported_formats = metadata.get('supported_data_formats', [])
        if supported_formats and not isinstance(supported_formats, list):
            logger.error("supported_data_formats必须是列表格式")
            return False
        
        return True
    
    def _validate_algorithm_config(self, alg_type: str, alg_config: Dict) -> bool:
        """
        验证单个算法配置
        
        Args:
            alg_type: 算法类型
            alg_config: 算法配置
            
        Returns:
            bool: 配置是否有效
        """
        required_keys = ['name', 'description', 'api_endpoint', 'data_format']
        
        # 验证必需字段
        for key in required_keys:
            if key not in alg_config:
                logger.error(f"算法 {alg_type} 配置中缺少必需字段: {key}")
                return False
            
            value = alg_config[key]
            if not value or (isinstance(value, str) and not value.strip()):
                logger.error(f"算法 {alg_type} 的 {key} 字段不能为空")
                return False
        
        # 验证API端点格式
        api_endpoint = alg_config['api_endpoint']
        if not api_endpoint.startswith('/'):
            logger.error(f"算法 {alg_type} 的API端点必须以'/'开头")
            return False
        
        # 验证HTTP方法
        method = alg_config.get('method', 'POST')
        if method not in ['GET', 'POST', 'PUT', 'DELETE']:
            logger.error(f"算法 {alg_type} 的HTTP方法无效: {method}")
            return False
        
        # 验证数据格式
        data_format = alg_config['data_format']
        valid_formats = ['tabular', 'time_series', 'transactional', 'real_time', 'none']
        if data_format not in valid_formats:
            logger.error(f"算法 {alg_type} 的数据格式无效: {data_format}")
            return False
        
        # 验证字段定义格式
        for field_type in ['required_fields', 'optional_fields']:
            if field_type in alg_config:
                fields = alg_config[field_type]
                if not isinstance(fields, list):
                    logger.error(f"算法 {alg_type} 的 {field_type} 必须是列表格式")
                    return False
                
                for i, field in enumerate(fields):
                    if not self._validate_field_definition(alg_type, field_type, i, field):
                        return False
        
        # 验证响应格式
        response_format = alg_config.get('response_format')
        if response_format and response_format not in ['sync', 'async', 'sync_or_async']:
            logger.error(f"算法 {alg_type} 的响应格式无效: {response_format}")
            return False
        
        # 验证示例列表
        examples = alg_config.get('examples', [])
        if examples and not isinstance(examples, list):
            logger.error(f"算法 {alg_type} 的示例必须是列表格式")
            return False
        
        # 验证意图关键词
        intent_keywords = alg_config.get('intent_keywords', [])
        if intent_keywords and not isinstance(intent_keywords, list):
            logger.error(f"算法 {alg_type} 的意图关键词必须是列表格式")
            return False
        
        return True
    
    def _validate_field_definition(self, alg_type: str, field_type: str, index: int, field: Dict) -> bool:
        """
        验证字段定义
        
        Args:
            alg_type: 算法类型
            field_type: 字段类型（required_fields或optional_fields）
            index: 字段索引
            field: 字段定义
            
        Returns:
            bool: 字段定义是否有效
        """
        if not isinstance(field, dict):
            logger.error(f"算法 {alg_type} 的 {field_type}[{index}] 必须是字典格式")
            return False
        
        required_field_keys = ['field', 'type', 'description']
        for key in required_field_keys:
            if key not in field:
                logger.error(f"算法 {alg_type} 的 {field_type}[{index}] 缺少必需字段: {key}")
                return False
            
            if not field[key] or (isinstance(field[key], str) and not field[key].strip()):
                logger.error(f"算法 {alg_type} 的 {field_type}[{index}].{key} 不能为空")
                return False
        
        # 验证字段类型
        field_data_type = field['type']
        valid_types = ['string', 'integer', 'float', 'boolean', 'array', 'object', 'number']
        if field_data_type not in valid_types:
            logger.error(f"算法 {alg_type} 的 {field_type}[{index}] 字段类型无效: {field_data_type}")
            return False
        
        # 验证可选字段的选项
        options = field.get('options')
        if options and not isinstance(options, list):
            logger.error(f"算法 {alg_type} 的 {field_type}[{index}] 选项必须是列表格式")
            return False
        
        return True
    
    def get_config_version(self) -> Optional[str]:
        """获取配置版本"""
        return self._config_version
    
    def get_last_modified(self) -> Optional[datetime]:
        """获取配置最后修改时间"""
        if self._last_modified:
            return datetime.fromtimestamp(self._last_modified)
        return None
    
    def get_supported_algorithms(self) -> List[str]:
        """获取支持的算法类型列表"""
        return list(self._config_cache.keys())
    
    def get_algorithm_by_keywords(self, keywords: List[str]) -> Optional[AlgorithmType]:
        """
        根据关键词匹配算法类型
        
        Args:
            keywords: 关键词列表
            
        Returns:
            Optional[AlgorithmType]: 匹配的算法类型
        """
        for alg_type, config in self._config_cache.items():
            if config.intent_keywords:
                for keyword in keywords:
                    if any(intent_keyword in keyword.lower() 
                          for intent_keyword in config.intent_keywords):
                        try:
                            return AlgorithmType(alg_type)
                        except ValueError:
                            continue
        return None
    
    def get_config_health_status(self) -> Dict:
        """
        获取配置健康状态
        
        Returns:
            Dict: 配置健康状态信息
        """
        config_path = Path(self.settings.algorithm_config_path)
        
        return {
            "config_file_exists": config_path.exists(),
            "config_file_path": str(config_path.absolute()),
            "last_modified": self.get_last_modified().isoformat() if self.get_last_modified() else None,
            "config_version": self._config_version,
            "algorithms_count": len(self._config_cache),
            "supported_algorithms": self.get_supported_algorithms(),
            "hot_reload_enabled": self.settings.algorithm_config_hot_reload,
            "is_monitoring": self._is_monitoring,
            "has_backup_config": self._backup_config is not None,
            "reload_callbacks_count": len(self._reload_callbacks)
        }
    
    def validate_algorithm_type(self, algorithm_type: str) -> bool:
        """
        验证算法类型是否支持
        
        Args:
            algorithm_type: 算法类型字符串
            
        Returns:
            bool: 是否支持该算法类型
        """
        return algorithm_type in self._config_cache
    
    def get_algorithm_examples(self, algorithm_type: str) -> List[str]:
        """
        获取算法示例
        
        Args:
            algorithm_type: 算法类型
            
        Returns:
            List[str]: 算法示例列表
        """
        config = self._config_cache.get(algorithm_type)
        return config.examples if config else []
    
    def get_algorithm_intent_keywords(self, algorithm_type: str) -> List[str]:
        """
        获取算法意图关键词
        
        Args:
            algorithm_type: 算法类型
            
        Returns:
            List[str]: 意图关键词列表
        """
        config = self._config_cache.get(algorithm_type)
        return config.intent_keywords if config else []
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        await self.load_config()
        await self.start_hot_reload_monitoring()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.stop_hot_reload_monitoring()


# 全局配置管理器实例
algorithm_config_manager = AlgorithmConfigManager()


def get_algorithm_config_manager() -> AlgorithmConfigManager:
    """
    获取算法配置管理器实例的便捷函数
    
    Returns:
        AlgorithmConfigManager: 配置管理器实例
    """
    return algorithm_config_manager