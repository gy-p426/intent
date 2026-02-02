"""
Algorithm API Client Implementation

Generic client for interfacing with various algorithm microservices
registered in Nacos, providing unified access to clustering, classification,
prediction, and other algorithm services.

This client provides:
- Service discovery integration with Nacos
- HTTP request encapsulation with timeout and retry mechanisms
- Unified interface for different algorithm services
- Load balancing and failover capabilities
- Comprehensive error handling and logging
"""

import logging
import aiohttp
import asyncio
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from infrastructure.config import get_settings
from infrastructure.service_discovery import get_service_discovery_client


logger = logging.getLogger(__name__)


class AlgorithmAPIClient:
    """算法API客户端（支持服务发现）"""
    
    def __init__(self, timeout: Optional[int] = None):
        """
        初始化算法API客户端
        
        Args:
            timeout: 请求超时时间（秒）
        """
        self.settings = get_settings()
        self.timeout = timeout or self.settings.algorithm_api_timeout
        self.session: Optional[aiohttp.ClientSession] = None
        
        # 服务发现客户端
        self.service_discovery = get_service_discovery_client()
        
        # 服务名称映射
        self.service_mapping = {
            'clustering': self.settings.clustering_service_name,
            'classification': self.settings.classification_service_name,
            'prediction': self.settings.prediction_service_name,
            'anomaly': self.settings.dbscan_service_name,  # 异常检测统一使用DBSCAN服务
            # 'dbscan': self.settings.dbscan_service_name,  # 注释掉单独的DBSCAN映射
            # 'iforest': self.settings.iforest_service_name,  # 注释掉IForest映射
            'association': self.settings.association_service_name,
            'comparison': self.settings.comparison_service_name,
            'similarity': self.settings.similarity_service_name,
            'trend': self.settings.trend_service_name,
            'profile': self.settings.profile_service_name,
            'causality': self.settings.causality_service_name,
            'alert': self.settings.alert_service_name,
            'recommendation': self.settings.recommendation_service_name,
            'compare_proportion' : self.settings.compare_proportion_service_name,
        }
        
        # 服务名称到方法的映射
        self.service_name_to_method_map = {
            'kmeans-service': self.call_clustering_api,
            'clustering-service': self.call_clustering_api,
            'classification-service': self.call_classification_api,
            'prediction-service': self.call_prediction_api,
            'dbscan-service': self.call_anomaly_detection_api,
            'association-service': self.call_association_api,
            'trend-service': self.call_trend_analysis_api,
            'causality-service': self.call_causality_api,
            'compare_proportion-service': self.call_compare_proportion_api,
        }
        
        # 静态URL映射（降级使用）
        self.static_url_mapping = {
            'clustering': self.settings.clustering_api_url,
            'classification': self.settings.classification_api_url,
            'prediction': self.settings.prediction_api_url,
            'anomaly': self.settings.dbscan_api_url,  # 异常检测统一使用DBSCAN服务URL
            # 'dbscan': self.settings.dbscan_api_url,  # 注释掉单独的DBSCAN映射
            # 'iforest': self.settings.iforest_api_url,  # 注释掉IForest映射
            'association': self.settings.association_api_url,
            'comparison': self.settings.comparison_api_url,
            'similarity': self.settings.similarity_api_url,
            'trend': self.settings.trend_api_url,
            'profile': self.settings.profile_api_url,
            'causality': self.settings.causality_api_url,
            'alert': self.settings.alert_api_url,
            'recommendation': self.settings.recommendation_api_url,
            'compare_proportion': self.settings.compare_proportion_api_url,
        }
        
        logger.info(f"算法API客户端初始化完成，服务发现模式: {self.settings.service_discovery_mode}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话，如果不存在则创建"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def _get_service_url(self, algorithm_type: str) -> str:
        """
        获取算法服务URL
        
        Args:
            algorithm_type: 算法类型 (clustering, classification, etc.)
            
        Returns:
            str: 服务URL
            
        Raises:
            ValueError: 不支持的算法类型
            ConnectionError: 无法获取服务URL时抛出
        """
        if algorithm_type not in self.service_mapping:
            raise ValueError(f"不支持的算法类型: {algorithm_type}")
        
        try:
            # 尝试通过服务发现获取URL
            service_name = self.service_mapping[algorithm_type]
            discovered_url = await self.service_discovery.discover_service(service_name)
            
            if discovered_url:
                logger.debug(f"通过服务发现获取{algorithm_type}服务URL: {discovered_url}")
                return discovered_url
            else:
                # 降级到静态配置
                static_url = self.static_url_mapping[algorithm_type]
                logger.warning(f"服务发现失败，使用{algorithm_type}静态配置: {static_url}")
                return static_url
                
        except Exception as e:
            # 降级到静态配置
            static_url = self.static_url_mapping[algorithm_type]
            logger.warning(f"服务发现异常，使用{algorithm_type}静态配置: {str(e)}")
            return static_url
    
    async def call_algorithm_api(
        self, 
        algorithm_type: str, 
        endpoint: str, 
        method: str = "POST",
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        调用算法API
        
        Args:
            algorithm_type: 算法类型 (clustering, classification, etc.)
            endpoint: API端点路径
            method: HTTP方法 (GET, POST, PUT, DELETE)
            data: 请求体数据
            params: URL参数
            
        Returns:
            Dict[str, Any]: API响应数据
            
        Raises:
            ValueError: 请求参数无效
            ConnectionError: 服务连接失败
        """
        start_time = datetime.utcnow()
        logger.info(f"调用{algorithm_type}算法API: {method} {endpoint}")
        
        try:
            # 获取服务URL
            base_url = await self._get_service_url(algorithm_type)
            session = await self._get_session()
            
            # 构建完整URL
            url = f"{base_url.rstrip('/')}{endpoint}"
            
            logger.debug(f"发送请求到: {url}")
            if data:
                logger.debug(f"请求数据: {self._sanitize_log_data(data)}")
            
            # 发送HTTP请求
            async with session.request(
                method=method.upper(),
                url=url,
                json=data if method.upper() in ['POST', 'PUT', 'PATCH'] else None,
                params=params
            ) as response:
                response_data = await self._handle_response(response, algorithm_type)
                
                # 记录成功日志和结果摘要
                execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
                logger.info(f"{algorithm_type}算法API调用成功，耗时: {execution_time:.2f}ms")
                
                # 临时：记录完整的响应数据用于调试
                if algorithm_type == "trend":
                    import json
                    logger.info(f"趋势分析完整响应数据: {json.dumps(response_data, indent=2, ensure_ascii=False)}")
                
                # 记录响应结果摘要
                self._log_response_summary(algorithm_type, response_data)
                
                return response_data
                
        except aiohttp.ClientError as e:
            logger.error(f"{algorithm_type}算法API连接失败: {str(e)}")
            raise ConnectionError(f"无法连接到{algorithm_type}算法API: {str(e)}")
        except asyncio.TimeoutError:
            logger.error(f"{algorithm_type}算法API请求超时")
            raise ConnectionError(f"{algorithm_type}算法API请求超时")
        except Exception as e:
            execution_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"{algorithm_type}算法API调用失败，耗时: {execution_time:.2f}ms，错误: {str(e)}")
            raise
    
    async def _handle_response(self, response: aiohttp.ClientResponse, algorithm_type: str) -> Dict[str, Any]:
        """
        处理HTTP响应
        
        Args:
            response: HTTP响应对象
            algorithm_type: 算法类型
            
        Returns:
            Dict[str, Any]: 响应数据
            
        Raises:
            ConnectionError: 响应状态码非200时抛出
        """
        if response.status == 200:
            try:
                return await response.json()
            except json.JSONDecodeError as e:
                logger.error(f"{algorithm_type}算法API返回无效JSON: {str(e)}")
                raise ConnectionError(f"{algorithm_type}算法API返回无效响应格式")
        elif response.status == 400:
            error_text = await response.text()
            logger.error(f"{algorithm_type}算法API请求参数错误: {error_text}")
            raise ValueError(f"请求参数错误: {error_text}")
        elif response.status == 404:
            logger.error(f"{algorithm_type}算法API端点不存在")
            raise ConnectionError(f"{algorithm_type}算法API端点不存在")
        elif response.status == 500:
            error_text = await response.text()
            logger.error(f"{algorithm_type}算法API内部错误: {error_text}")
            raise ConnectionError(f"{algorithm_type}算法API内部错误: {error_text}")
        elif response.status == 503:
            logger.error(f"{algorithm_type}算法API暂时不可用")
            raise ConnectionError(f"{algorithm_type}算法API暂时不可用，请稍后重试")
        else:
            error_text = await response.text()
            logger.error(f"{algorithm_type}算法API返回未知错误: {response.status} - {error_text}")
            raise ConnectionError(f"{algorithm_type}算法API错误: HTTP {response.status}")
    
    def _sanitize_log_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        清理日志数据，避免记录敏感信息
        
        Args:
            data: 原始数据
            
        Returns:
            Dict[str, Any]: 清理后的数据
        """
        sanitized = data.copy()
        
        # 截断大数据集以避免日志过长
        if "data_rows" in sanitized and isinstance(sanitized["data_rows"], list):
            if len(sanitized["data_rows"]) > 5:
                sanitized["data_rows"] = sanitized["data_rows"][:5] + [f"... 还有 {len(sanitized['data_rows']) - 5} 行数据"]
        
        if "data_sets" in sanitized and isinstance(sanitized["data_sets"], list):
            if len(sanitized["data_sets"]) > 5:
                sanitized["data_sets"] = sanitized["data_sets"][:5] + [f"... 还有 {len(sanitized['data_sets']) - 5} 行数据"]
        
        return sanitized
    
    def _log_response_summary(self, algorithm_type: str, response_data: Dict[str, Any]):
        """
        记录算法响应结果摘要
        
        Args:
            algorithm_type: 算法类型
            response_data: 响应数据
        """
        try:
            if not isinstance(response_data, dict):
                logger.debug(f"{algorithm_type}算法响应: 非字典格式数据")
                return
            
            status = response_data.get("status", "unknown")
            logger.info(f"{algorithm_type}算法响应状态: {status}")
            
            if status == "success":
                if algorithm_type == "clustering":
                    # 聚类结果摘要
                    k_used = response_data.get("k_used", "unknown")
                    results = response_data.get("results", [])
                    logger.info(f"聚类结果: K值={k_used}, 数据点数量={len(results)}")
                    
                    if results:
                        # 计算聚类分布
                        cluster_distribution = {}
                        for item in results:
                            cluster_id = item.get("cluster_id", "unknown")
                            cluster_distribution[cluster_id] = cluster_distribution.get(cluster_id, 0) + 1
                        
                        logger.info(f"聚类分布: {cluster_distribution}")
                        
                        # 显示前几个结果示例
                        sample_results = results[:3]
                        sample_text = ", ".join([f"ID:{item.get('uid', '?')}→簇{item.get('cluster_id', '?')}" for item in sample_results])
                        logger.info(f"结果示例: {sample_text}")
                
                elif algorithm_type == "classification":
                    # 分类结果摘要
                    results = response_data.get("results", [])
                    logger.info(f"分类结果: 预测数量={len(results)}")
                    
                    if results:
                        # 统计预测分布
                        label_distribution = {}
                        confidence_scores = []
                        
                        for item in results:
                            predicted_label = item.get("predicted_label", "unknown")
                            label_distribution[predicted_label] = label_distribution.get(predicted_label, 0) + 1
                            
                            if "probability" in item:
                                confidence_scores.append(item["probability"])
                        
                        logger.info(f"预测分布: {label_distribution}")
                        
                        if confidence_scores:
                            avg_confidence = sum(confidence_scores) / len(confidence_scores)
                            logger.info(f"平均置信度: {avg_confidence:.3f}")
                        
                        # 显示前几个结果示例
                        sample_results = results[:3]
                        sample_text = ", ".join([
                            f"ID:{item.get('uid', '?')}→{item.get('predicted_label', '?')}({item.get('probability', 0):.2f})"
                            for item in sample_results
                        ])
                        logger.info(f"结果示例: {sample_text}")
                
                elif algorithm_type == "anomaly":
                    # 异常检测结果摘要
                    anomalies = response_data.get("anomalies", [])
                    normal_points = response_data.get("normal_points", [])
                    clusters = response_data.get("clusters", [])
                    
                    logger.info(f"异常检测结果: 异常点={len(anomalies)}, 正常点={len(normal_points)}, 聚类数={len(clusters)}")
                    
                    if anomalies:
                        # 显示前几个异常点示例
                        sample_anomalies = anomalies[:3]
                        sample_text = ", ".join([f"ID:{item.get('id', '?')}" for item in sample_anomalies])
                        logger.info(f"异常点示例: {sample_text}")
                    
                    if clusters:
                        # 统计聚类分布
                        cluster_sizes = [len(cluster.get('points', [])) for cluster in clusters]
                        logger.info(f"聚类大小分布: {cluster_sizes}")
                
                else:
                    # 其他算法类型的通用处理
                    if "results" in response_data:
                        results = response_data["results"]
                        if isinstance(results, list):
                            logger.info(f"{algorithm_type}算法结果: {len(results)}个结果")
                        else:
                            logger.info(f"{algorithm_type}算法结果: {type(results).__name__}类型")
            
            elif status == "error":
                error_msg = response_data.get("error", response_data.get("message", "未知错误"))
                logger.error(f"{algorithm_type}算法执行失败: {error_msg}")
            
            elif status == "pending":
                task_id = response_data.get("task_id", "unknown")
                logger.info(f"{algorithm_type}算法异步执行: 任务ID={task_id}")
            
            else:
                logger.warning(f"{algorithm_type}算法返回未知状态: {status}")
                
        except Exception as e:
            logger.warning(f"记录{algorithm_type}算法响应摘要时发生错误: {str(e)}")
    
    # 具体算法API调用方法
    
    async def call_clustering_api(self, data_rows: List[Dict], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用聚类算法API
        
        Args:
            data_rows: 待聚类的数据行
            config: 聚类配置
            
        Returns:
            Dict[str, Any]: 聚类结果
        """
        payload = {
            "data_rows": data_rows,
            "config": config
        }
        return await self.call_algorithm_api("clustering", "/clustering/kmeans", "POST", payload)
    
    async def call_classification_api(self, data_rows: List[Dict], data_sets: List[Dict], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用分类算法API
        
        Args:
            data_rows: 待预测的数据行
            data_sets: 训练数据集
            config: 分类配置
            
        Returns:
            Dict[str, Any]: 分类结果
        """
        payload = {
            "data_rows": data_rows,
            "data_sets": data_sets,
            "config": config
        }
        return await self.call_algorithm_api("classification", "/classification/predict", "POST", payload)

    async def query_tabnet_async_task_status(self, algorithm_type: str, task_id: str) -> Dict[str, Any]:
        """
        查询异步任务状态 (对应 GET /classification/task/{task_id})
        """
        # 根据算法类型构建 endpoint
        if algorithm_type == "classification":
            endpoint = f"/classification/task/{task_id}"
        else:
            # 默认 fallback
            endpoint = f"/task/{task_id}"

        return await self.call_algorithm_api(algorithm_type, endpoint, "GET")

    async def call_prediction_api(self, data_rows: List[Dict], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用预测算法API
        
        Args:
            data_rows: 历史数据
            config: 预测配置
            
        Returns:
            Dict[str, Any]: 预测结果
        """
        payload = {
            "data_rows": data_rows,
            "config": config
        }
        return await self.call_algorithm_api("prediction", "/prediction/forecast", "POST", payload)
    
    async def call_anomaly_detection_api(self, data_rows: List[Dict], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用DBSCAN异常检测API
        
        Args:
            data_rows: 待检测的数据行
            config: 异常检测配置
            
        Returns:
            Dict[str, Any]: 异常检测结果
        """
        payload = {
            "data_rows": data_rows,
            "config": config
        }
        return await self.call_algorithm_api("anomaly", "/api/dbscan", "POST", payload)

    async def call_compare_proportion_api(self, data_rows: List[Dict], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用占比分析API

        Args:
            data_rows: 占比分析数据行
            config: 占比分析配置

        Returns:
            Dict[str, Any]: 占比分析结果
        """
        payload = {
            "data_rows": data_rows,
            "config": config
        }
        return await self.call_algorithm_api("compare_proportion", "/api/compare_analysis_proportion", "POST", payload)
    
    async def call_causality_api(self, data_rows: List[Dict], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用因果分析服务API（新格式：因变量和自变量分开）
        
        Args:
            data_rows: 数据行列表
            config: 算法配置，包含dependent_variable和independent_variables
            
        Returns:
            Dict[str, Any]: API响应结果
        """
        try:
            # 从config中提取因变量和自变量
            dependent_var = config.get('dependent_variable')
            independent_vars = config.get('independent_variables', [])
            
            if not dependent_var:
                logger.error("因果分析配置中缺少dependent_variable字段")
                return {
                    "error": "配置错误：缺少dependent_variable字段",
                    "status": "error"
                }
            
            if not independent_vars or not isinstance(independent_vars, list):
                logger.error("因果分析配置中缺少independent_variables字段或格式不正确")
                return {
                    "error": "配置错误：缺少independent_variables字段或格式不正确",
                    "status": "error"
                }
            
            # 构建新格式的请求数据
            request_data = {
                "dependent_variable": {
                    "name": dependent_var,
                    "values": []
                },
                "independent_variables": [],
                "options": {
                    "analysis_type": "causal"
                }
            }
            
            # 提取因变量的值
            dependent_values = [row.get(dependent_var) for row in data_rows if row.get(dependent_var) is not None]
            if not dependent_values:
                logger.error(f"因变量 {dependent_var} 没有有效数据")
                return {
                    "error": f"数据错误：因变量 {dependent_var} 没有有效数据",
                    "status": "error"
                }
            request_data["dependent_variable"]["values"] = dependent_values
            
            # 提取自变量的值
            for var_name in independent_vars:
                values = [row.get(var_name) for row in data_rows if row.get(var_name) is not None]
                
                if not values:
                    logger.warning(f"自变量 {var_name} 没有有效数据，跳过")
                    continue
                
                request_data["independent_variables"].append({
                    "name": var_name,
                    "values": values
                })
            
            # 验证数据
            if len(request_data["independent_variables"]) < 1:
                logger.error("因果分析至少需要1个有效的自变量")
                return {
                    "error": "数据不足：因果分析至少需要1个有效的自变量",
                    "status": "error"
                }
            
            logger.info(
                f"调用因果分析API - 因变量: {dependent_var}, "
                f"自变量数: {len(request_data['independent_variables'])}"
            )
            logger.debug(f"因果分析请求数据: {request_data}")
            
            # 调用因果分析服务
            result = await self.call_algorithm_api("causality", "/analyze", "POST", request_data)
            
            logger.info("因果分析API调用成功")
            return result
            
        except Exception as e:
            logger.error(f"调用因果分析API异常: {str(e)}")
            return {
                "error": f"API调用失败: {str(e)}",
                "status": "error"
            }
    
    # async def call_dbscan_api(self, data_rows: List[Dict], config: Dict[str, Any]) -> Dict[str, Any]:
    #     """
    #     调用DBSCAN密度聚类异常检测API
    #
    #     Args:
    #         data_rows: 待检测的数据行
    #         config: DBSCAN配置
    #
    #     Returns:
    #         Dict[str, Any]: DBSCAN异常检测结果
    #     """
    #     payload = {
    #         "data_rows": data_rows,
    #         "config": config
    #     }
    #     return await self.call_algorithm_api("dbscan", "/dbscan/analyze", "POST", payload)
    
    # async def call_iforest_api(self, data_rows: List[Dict], config: Dict[str, Any]) -> Dict[str, Any]:
    #     """
    #     调用IForest孤立森林异常检测API
    #     
    #     Args:
    #         data_rows: 待检测的数据行
    #         config: IForest配置
    #         
    #     Returns:
    #         Dict[str, Any]: IForest异常检测结果
    #     """
    #     payload = {
    #         "data_rows": data_rows,
    #         "config": config
    #     }
    #     return await self.call_algorithm_api("iforest", "/iforest/analyze", "POST", payload)
    
    async def call_trend_analysis_api(self, data_rows: List[Dict], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用趋势分析API
        
        Args:
            data_rows: 时间序列数据
            config: 趋势分析配置
            
        Returns:
            Dict[str, Any]: 趋势分析结果
        """
        # 强制使用趋势分解，忽略 detection 请求
        # 原逻辑: analysis_type = config.get('analysis_type', 'decomposition')
        analysis_type = 'decomposition'
        
        # 根据分析类型选择端点（目前只使用 decomposition）
        if analysis_type == 'decomposition':
            endpoint = "/api/v1/trend/decomposition"
            # endpoint = "api/trend_forecast/api/v1/trend/decomposition"
        elif analysis_type == 'detection':
            endpoint = "/api/v1/trend/detection"
        else:
            raise ValueError(f"不支持的趋势分析类型: {analysis_type}")
        
        payload = {
            "data": data_rows,  # 改为 "data" 以匹配远程服务期望的格式
            "config": config
        }
        return await self.call_algorithm_api("trend", endpoint, "POST", payload)
    
    async def call_association_api(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用关联分析API（支持三种模式的路由）
        
        根据analysis_mode参数路由到不同的API端点：
        - bivariate: /api/v1/association/bivariate (二元关联分析)
        - pairwise: /api/v1/association/pairwise (多变量两两关联)
        - multivariate: /api/v1/association/multivariate (多变量综合关联)
        
        Args:
            config: 关联分析配置，包含data和options
            
        Returns:
            Dict[str, Any]: 关联分析结果
        """
        # 获取分析模式
        options = config.get('options', {})
        analysis_mode = options.get('analysis_mode', 'bivariate')
        
        # 根据analysis_mode选择端点
        endpoint_mapping = {
            'bivariate': '/api/v1/association/bivariate',
            'pairwise': '/api/v1/association/pairwise',
            'multivariate': '/api/v1/association/multivariate'
        }
        
        endpoint = endpoint_mapping.get(analysis_mode)
        if not endpoint:
            raise ValueError(f"不支持的分析模式: {analysis_mode}")
        
        logger.info(f"关联分析路由: analysis_mode={analysis_mode} -> {endpoint}")
        
        # 构建请求payload（只包含data数组，不包含options）
        payload = {
            "data": config.get('data', [])
        }
        
        return await self.call_algorithm_api("association", endpoint, "POST", payload)
    
    async def call_univariate_forecast_api(self, data_rows: List[Dict], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用单变量预测API
        
        Args:
            data_rows: 时间序列数据，格式为 [{timestamp, value}, ...]
            config: 预测配置
            
        Returns:
            Dict[str, Any]: 预测结果
        """
        # 转换数据格式：从 [{timestamp, value}, ...] 转为 {timestamp: [], value: []}
        if isinstance(data_rows, list) and len(data_rows) > 0:
            if isinstance(data_rows[0], dict) and 'timestamp' in data_rows[0]:
                timestamps = [row.get('timestamp') for row in data_rows]
                values = [row.get('value') for row in data_rows]
                api_data = {"timestamp": timestamps, "value": values}
            else:
                api_data = data_rows[0].get('data', {"timestamp": [], "value": []})
        else:
            api_data = {"timestamp": [], "value": []}
        
        payload = {
            "data": api_data,
            "config": {
                "forecast_horizon": config.get('forecast_horizon', 24),
                "include_confidence": config.get('include_confidence', True)
            }
        }
        return await self.call_algorithm_api("trend", "/api/v1/forecast/univariate", "POST", payload)

    async def call_multivariate_forecast_api(self, data_rows: List[Dict], config: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用多变量预测API
        
        Args:
            data_rows: 多变量时序数据
            config: 预测配置
            
        Returns:
            Dict[str, Any]: 预测结果
        """
        payload = {
            "data": data_rows,
            "config": {
                "target_column": config.get('target_column'),
                "feature_columns": config.get('feature_columns', []),
                "algorithm": config.get('algorithm', 'lightgbm'),
                "forecast_horizon": config.get('forecast_horizon', 14),
                "model_name": config.get('model_name')
            }
        }
        return await self.call_algorithm_api("trend", "/api/v1/forecast/multivariate", "POST", payload)
    
    async def query_task_status(self, algorithm_type: str, task_id: str) -> Dict[str, Any]:
        """
        查询异步任务状态
        
        Args:
            algorithm_type: 算法类型
            task_id: 任务ID
            
        Returns:
            Dict[str, Any]: 任务状态
        """
        endpoint = f"/classification/task/{task_id}" if algorithm_type == "classification" else f"/task/{task_id}"
        return await self.call_algorithm_api(algorithm_type, endpoint, "GET")
    
    async def health_check(self, algorithm_type: str) -> bool:
        """
        检查算法服务健康状态
        
        Args:
            algorithm_type: 算法类型
            
        Returns:
            bool: 服务是否健康
        """
        try:
            base_url = await self._get_service_url(algorithm_type)
            session = await self._get_session()
            url = f"{base_url.rstrip('/')}/health"
            
            async with session.get(url) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"{algorithm_type}算法服务健康检查失败: {str(e)}")
            return False
    
    async def validate_service_connection(self, algorithm_type: str) -> Dict[str, Any]:
        """
        验证算法服务连接状态
        
        Args:
            algorithm_type: 算法类型
            
        Returns:
            Dict[str, Any]: 连接状态信息
        """
        start_time = datetime.utcnow()
        
        try:
            # 获取当前使用的服务URL
            current_url = await self._get_service_url(algorithm_type)
            
            # 尝试健康检查
            is_healthy = await self.health_check(algorithm_type)
            
            connection_status = "healthy" if is_healthy else "unhealthy"
            error_message = None if is_healthy else "健康检查失败"
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            return {
                "status": connection_status,
                "response_time_ms": round(response_time, 2),
                "error": error_message,
                "timestamp": start_time.isoformat(),
                "current_url": current_url,
                "service_name": self.service_mapping[algorithm_type],
                "discovery_mode": self.settings.service_discovery_mode
            }
            
        except Exception as e:
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.error(f"{algorithm_type}算法服务连接验证失败: {str(e)}")
            
            return {
                "status": "error",
                "response_time_ms": round(response_time, 2),
                "error": str(e),
                "timestamp": start_time.isoformat(),
                "current_url": self.static_url_mapping.get(algorithm_type, "unknown"),
                "service_name": self.service_mapping[algorithm_type],
                "discovery_mode": self.settings.service_discovery_mode
            }
    
    async def validate_all_services(self) -> Dict[str, Dict[str, Any]]:
        """
        验证所有算法服务连接状态
        
        Returns:
            Dict[str, Dict[str, Any]]: 各服务的连接状态
        """
        results = {}
        
        for algorithm_type in self.service_mapping.keys():
            try:
                results[algorithm_type] = await self.validate_service_connection(algorithm_type)
            except Exception as e:
                results[algorithm_type] = {
                    "status": "error",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
        
        return results
    
    def get_service_stats(self) -> Dict[str, Any]:
        """
        获取服务统计信息
        
        Returns:
            Dict[str, Any]: 统计信息
        """
        return {
            "supported_algorithms": list(self.service_mapping.keys()),
            "service_mapping": self.service_mapping,
            "static_url_mapping": self.static_url_mapping,
            "timeout": self.timeout,
            "discovery_mode": self.settings.service_discovery_mode,
            "discovery_enabled": self.settings.service_discovery_enabled
        }
    
    async def close(self):
        """关闭客户端连接"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("算法API客户端连接已关闭")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()


# 全局算法API客户端实例
_algorithm_api_client: Optional[AlgorithmAPIClient] = None


def get_algorithm_api_client() -> AlgorithmAPIClient:
    """
    获取算法API客户端实例
    
    Returns:
        AlgorithmAPIClient: 算法API客户端实例
    """
    global _algorithm_api_client
    
    if _algorithm_api_client is None:
        _algorithm_api_client = AlgorithmAPIClient()
    
    return _algorithm_api_client


def set_algorithm_api_client(client: AlgorithmAPIClient):
    """
    设置算法API客户端实例
    
    Args:
        client: 算法API客户端实例
    """
    global _algorithm_api_client
    _algorithm_api_client = client