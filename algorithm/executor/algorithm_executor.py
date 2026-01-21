"""
Algorithm Executor Implementation

Executes algorithms via external APIs including clustering and classification
algorithms with support for both synchronous and asynchronous processing.
Supports service discovery integration with Nacos.
"""

import logging
from datetime import datetime

import aiohttp
import asyncio
from typing import Dict, Optional, AsyncGenerator, List, Any
from algorithm.models import (
    AlgorithmExecutionRequest, AlgorithmExecutionResponse, 
    AsyncTaskResponse, TaskStatus, AlgorithmConfig, AlgorithmParameters,
    AlgorithmType
)
from algorithm.interfaces import IAlgorithmExecutor, ITaskManager
from algorithm.processors.data_processor import DataProcessor
from algorithm.tasks.task_manager import TaskManager
from algorithm.clients.algorithm_api_client import get_algorithm_api_client
from infrastructure.config import get_settings


logger = logging.getLogger(__name__)


class AlgorithmExecutor(IAlgorithmExecutor):
    """算法执行器实现（支持服务发现）"""
    
    def __init__(
        self, 
        algorithm_apis: Optional[Dict[str, str]] = None,
        task_manager: Optional[ITaskManager] = None
    ):
        """
        初始化算法执行器
        
        Args:
            algorithm_apis: 算法API URL映射（兼容性保留，优先使用服务发现）
            task_manager: 任务管理器实例
        """
        self.settings = get_settings()
        
        # 保留兼容性，但优先使用服务发现
        self.legacy_algorithm_apis = algorithm_apis or {
            "clustering": self.settings.clustering_api_url,
            "classification": self.settings.classification_api_url,
            "forecast": self.settings.forecast_service_url
        }
        
        self.timeout = self.settings.algorithm_api_timeout
        self.forecast_timeout = self.settings.forecast_service_timeout
        self.session: Optional[aiohttp.ClientSession] = None
        self.data_processor = DataProcessor()
        self.task_manager = task_manager or TaskManager()
        
        # 使用新的算法API客户端（支持服务发现）
        self.algorithm_client = get_algorithm_api_client()
        
        logger.info("算法执行器初始化完成，支持服务发现")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """获取HTTP会话，如果不存在则创建"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def execute_clustering(
        self, 
        request: AlgorithmExecutionRequest
    ) -> AlgorithmExecutionResponse:
        """
        执行聚类算法
        
        Args:
            request: 算法执行请求
            
        Returns:
            AlgorithmExecutionResponse: 执行响应
        """
        logger.info("开始执行聚类算法")
        logger.info(f"输入数据行数: {len(request.data_rows)}")
        logger.info(f"聚类配置: {request.config}")
        
        try:
            # 使用新的算法API客户端
            result_data = await self.algorithm_client.call_clustering_api(
                data_rows=request.data_rows,
                config=request.config
            )
            
            # 详细记录算法结果
            logger.info("聚类算法执行成功")
            logger.info(f"算法返回状态: {result_data.get('status', 'unknown')}")
            
            if result_data.get('status') == 'success':
                k_used = result_data.get('k_used', 'unknown')
                results = result_data.get('results', [])
                logger.info(f"使用的K值: {k_used}")
                logger.info(f"聚类结果数量: {len(results)}")
                
                # 显示聚类结果摘要
                if results:
                    cluster_summary = {}
                    for item in results:
                        cluster_id = item.get('cluster_id', 'unknown')
                        cluster_summary[cluster_id] = cluster_summary.get(cluster_id, 0) + 1
                    
                    logger.info(f"聚类分布: {cluster_summary}")
                    logger.info(f"聚类结果示例: {results[:3]}")  # 显示前3个结果
                else:
                    logger.warning("聚类结果为空")
            else:
                logger.error(f"聚类算法返回错误状态: {result_data}")
            
            return AlgorithmExecutionResponse(
                result=result_data,
                status="success",
                message="聚类算法执行成功"
            )
            
        except Exception as e:
            logger.error(f"聚类算法执行失败: {str(e)}")
            return AlgorithmExecutionResponse(
                result={},
                status="error",
                message=f"聚类算法执行失败: {str(e)}"
            )

    async def execute_classification(
            self,
            request: AlgorithmExecutionRequest
    ) -> AlgorithmExecutionResponse:
        """
        执行分类算法 (支持同步/异步双模式)

        Args:
            request: 算法执行请求 (包含 data_rows 和 data_sets)

        Returns:
            AlgorithmExecutionResponse: 执行响应
        """
        logger.info("开始执行分类算法")
        logger.info(
            f"训练数据: {len(request.data_sets) if request.data_sets else 0}行, 预测数据: {len(request.data_rows)}行")

        try:
            # 1. 调用 API Client (传入训练集 data_sets)
            result_data = await self.algorithm_client.call_classification_api(
                data_rows=request.data_rows,
                data_sets=request.data_sets or [],  # 确保列表不为None
                config=request.config
            )

            # 2. 检查是否为异步任务 (返回了 task_id 或 status=pending)
            if result_data.get("status") == "pending" or "task_id" in result_data:
                task_id = result_data.get("task_id")
                logger.info(f"分类算法进入异步模式, 外部Task ID: {task_id}")

                return AlgorithmExecutionResponse(
                    result=result_data,  # 包含 {"task_id": "...", "status": "pending"}
                    status="success",  # 响应本身是成功的（请求已发送）
                    message=result_data.get("message", "数据量较大，使用TabNet算法，异步的训练任务已创建"),
                    readable_result=None  # 让LLM解释这个异步状态
                )

            # 3. 处理同步结果
            elif result_data.get("status") == "success":
                logger.info("分类算法同步执行成功")
                return AlgorithmExecutionResponse(
                    result=result_data,
                    status="success",
                    message="分类预测执行成功",
                    readable_result=None
                )

            # 4. 处理错误
            else:
                error_msg = result_data.get("message", "未知错误")
                logger.error(f"分类算法返回错误状态: {result_data}")
                return AlgorithmExecutionResponse(
                    result=result_data,
                    status="error",
                    message=f"分类算法执行失败: {error_msg}",
                    readable_result=None
                )

        except Exception as e:
            logger.error(f"分类算法执行异常: {str(e)}")
            return AlgorithmExecutionResponse(
                result={},
                status="error",
                message=f"分类算法执行异常: {str(e)}",
                readable_result=None
            )

    async def execute_anomaly_detection(
        self,
        request: AlgorithmExecutionRequest
    ) -> AlgorithmExecutionResponse:
        """
        执行异常检测算法（DBSCAN）

        Args:
            request: 算法执行请求

        Returns:
            AlgorithmExecutionResponse: 执行响应
        """
        logger.info("开始执行DBSCAN异常检测算法")
        logger.info(f"输入数据行数: {len(request.data_rows)}")
        logger.info(f"异常检测配置: {request.config}")

        try:
            # 使用新的算法API客户端
            result_data = await self.algorithm_client.call_anomaly_detection_api(
                data_rows=request.data_rows,
                config=request.config
            )

            # 详细记录算法结果
            logger.info("DBSCAN异常检测算法执行成功")
            logger.info(f"算法返回状态: {result_data.get('status', 'unknown')}")

            # 将完整的返回结果显示在readable_result中，便于调试和查看原始数据
            import json
            readable_result = f"DBSCAN异常检测完整返回结果：\n{json.dumps(result_data, indent=2, ensure_ascii=False)}"

            if result_data.get('status') == 'success':
                # 解析新的返回格式
                results = result_data.get('results', [])

                # 统计异常点和正常点
                anomalies = []
                normal_points = []
                clusters = {}

                for item in results:
                    cluster_id = item.get('cluster_id')
                    item_id = item.get('id')

                    if cluster_id == -1:
                        # cluster_id = -1 表示异常点
                        anomalies.append(item)
                    else:
                        # cluster_id >= 0 表示正常聚类点
                        normal_points.append(item)
                        if cluster_id not in clusters:
                            clusters[cluster_id] = []
                        clusters[cluster_id].append(item)

                logger.info(f"检测到异常点数量: {len(anomalies)}")
                logger.info(f"正常点数量: {len(normal_points)}")
                logger.info(f"聚类数量: {len(clusters)}")

                # 显示异常检测结果摘要
                if anomalies:
                    anomaly_ids = [item.get('id', 'unknown') for item in anomalies[:3]]
                    logger.info(f"异常点示例: {anomaly_ids}")  # 显示前3个异常点ID
                else:
                    logger.info("未检测到异常点")

                # 显示聚类摘要
                if clusters:
                    cluster_summary = {f"聚类{cid}": len(items) for cid, items in clusters.items()}
                    logger.info(f"聚类分布: {cluster_summary}")

                return AlgorithmExecutionResponse(
                    result=result_data,
                    status="success",
                    message="DBSCAN异常检测算法执行成功",
                    readable_result=readable_result
                )
            else:
                error_msg = result_data.get('error', result_data.get('message', '未知错误'))
                logger.error(f"DBSCAN异常检测算法返回错误状态: {result_data}")
                return AlgorithmExecutionResponse(
                    result=result_data,  # 即使失败也返回完整结果用于调试
                    status="error",
                    message=f"DBSCAN异常检测算法执行失败: {error_msg}",
                    readable_result=readable_result
                )

        except Exception as e:
            logger.error(f"DBSCAN异常检测算法执行失败: {str(e)}")
            return AlgorithmExecutionResponse(
                result={},
                status="error",
                message=f"DBSCAN异常检测算法执行失败: {str(e)}",
                readable_result=f"DBSCAN异常检测异常：{str(e)}"
            )

    async def execute_compare_proportion(
            self,
            request: AlgorithmExecutionRequest
    ) -> AlgorithmExecutionResponse:
        """
        执行占比分析算法

        Args:
            request: 算法执行请求

        Returns:
            AlgorithmExecutionResponse: 执行响应
        """
        logger.info("开始执行占比分析算法")
        logger.info(f"输入数据行数: {len(request.data_rows)}")
        logger.info(f"占比分析配置: {request.config}")

        try:
            # 使用新的算法API客户端
            result_data = await self.algorithm_client.call_compare_proportion_api(
                data_rows=request.data_rows,
                config=request.config
            )

            # 详细记录算法结果
            logger.info("占比分析算法执行成功")
            logger.info(f"算法返回状态: {result_data.get('status', 'unknown')}")

            # 将完整的返回结果显示在readable_result中，便于调试和查看原始数据
            import json
            readable_result = f"占比分析算法完整返回结果：\n{json.dumps(result_data, indent=2, ensure_ascii=False)}"


            if result_data.get('status') == 'success':

                return AlgorithmExecutionResponse(
                    result=result_data,
                    status="success",
                    message="占比分析算法执行成功",
                    readable_result = None
                )
            else:
                error_msg = result_data.get('error', result_data.get('message', '未知错误'))
                logger.error(f"占比分析算法返回错误状态: {result_data}")
                return AlgorithmExecutionResponse(
                    result=result_data,  # 即使失败也返回完整结果用于调试
                    status="error",
                    message=f"占比分析算法执行失败: {error_msg}",
                    readable_result = None
                )

        except Exception as e:
            logger.error(f"占比分析算法执行失败: {str(e)}")
            return AlgorithmExecutionResponse(
                result={},
                status="error",
                message=f"占比分析算法执行失败: {str(e)}",
                readable_result= None
            )

    # async def execute_dbscan(
    #     self, 
    #     request: AlgorithmExecutionRequest
    # ) -> AlgorithmExecutionResponse:
    #     """
    #     执行DBSCAN密度聚类异常检测算法
    #     
    #     Args:
    #         request: 算法执行请求
    #         
    #     Returns:
    #         AlgorithmExecutionResponse: 执行响应
    #     """
    #     logger.info("开始执行DBSCAN密度聚类异常检测算法")
    #     logger.info(f"输入数据行数: {len(request.data_rows)}")
    #     logger.info(f"DBSCAN配置: {request.config}")
    #     
    #     try:
    #         # 使用算法API客户端
    #         result_data = await self.algorithm_client.call_anomaly_detection_api(
    #             data_rows=request.data_rows,
    #             config=request.config
    #         )
    #         
    #         logger.info("DBSCAN密度聚类异常检测算法执行成功")
    #         logger.info(f"算法返回状态: {result_data.get('status', 'unknown')}")
    #         
    #         if result_data.get('status') == 'success':
    #             anomalies = result_data.get('anomalies', [])
    #             normal_points = result_data.get('normal_points', [])
    #             clusters = result_data.get('clusters', [])
    #             
    #             logger.info(f"检测到异常点数量: {len(anomalies)}")
    #             logger.info(f"正常点数量: {len(normal_points)}")
    #             logger.info(f"聚类数量: {len(clusters)}")
    #         
    #         return AlgorithmExecutionResponse(
    #             result=result_data,
    #             status="success",
    #             message="DBSCAN密度聚类异常检测执行成功"
    #         )
    #         
    #     except Exception as e:
    #         logger.error(f"DBSCAN密度聚类异常检测执行失败: {str(e)}")
    #         return AlgorithmExecutionResponse(
    #             result={},
    #             status="error",
    #             message=f"DBSCAN密度聚类异常检测执行失败: {str(e)}"
    #         )
    
    # async def execute_iforest(
    #     self, 
    #     request: AlgorithmExecutionRequest
    # ) -> AlgorithmExecutionResponse:
    #     """
    #     执行IForest孤立森林异常检测算法
    #     
    #     Args:
    #         request: 算法执行请求
    #         
    #     Returns:
    #         AlgorithmExecutionResponse: 执行响应
    #     """
    #     logger.info("开始执行IForest孤立森林异常检测算法")
    #     logger.info(f"输入数据行数: {len(request.data_rows)}")
    #     logger.info(f"IForest配置: {request.config}")
    #     
    #     try:
    #         # 使用算法API客户端
    #         result_data = await self.algorithm_client.call_iforest_api(
    #             data_rows=request.data_rows,
    #             config=request.config
    #         )
    #         
    #         logger.info("IForest孤立森林异常检测算法执行成功")
    #         logger.info(f"算法返回状态: {result_data.get('status', 'unknown')}")
    #         
    #         if result_data.get('status') == 'success':
    #             anomalies = result_data.get('anomalies', [])
    #             normal_points = result_data.get('normal_points', [])
    #             anomaly_scores = result_data.get('anomaly_scores', [])
    #             
    #             logger.info(f"检测到异常点数量: {len(anomalies)}")
    #             logger.info(f"正常点数量: {len(normal_points)}")
    #             logger.info(f"异常分数数量: {len(anomaly_scores)}")
    #         
    #         return AlgorithmExecutionResponse(
    #             result=result_data,
    #             status="success",
    #             message="IForest孤立森林异常检测执行成功"
    #         )
    #         
    #     except Exception as e:
    #         logger.error(f"IForest孤立森林异常检测执行失败: {str(e)}")
    #         return AlgorithmExecutionResponse(
    #             result={},
    #             status="error",
    #             message=f"IForest孤立森林异常检测执行失败: {str(e)}"
    #         )
    
    # =========================================================================
    # Association Analysis 执行方法
    # =========================================================================
    
    async def execute_association(
        self,
        request: AlgorithmExecutionRequest
    ) -> AlgorithmExecutionResponse:
        """
        执行关联分析算法
        
        Args:
            request: 算法执行请求
            
        Returns:
            AlgorithmExecutionResponse: 执行响应
        """
        logger.info("开始执行关联分析算法")
        logger.info(f"算法配置: {request.config}")
        
        try:
            # 调用关联分析API
            result_data = await self.algorithm_client.call_association_api(
                config=request.config
            )
            
            logger.info("关联分析算法执行成功")
            
            # 🎉 新版本：无需编写复杂的格式化逻辑！
            # 只需要返回原始结果，大模型会自动生成用户友好的分析
            
            # 检查响应是否包含错误信息
            if 'error' in result_data:
                error_msg = result_data.get('error', '未知错误')
                logger.error(f"关联分析返回错误: {error_msg}")
                return AlgorithmExecutionResponse(
                    result=result_data,
                    status="error",
                    message=f"关联分析执行失败: {error_msg}",
                    readable_result=None
                )
            
            # 检查响应中是否包含有效结果字段
            # 支持新格式（'解释'、'算法结果'）和旧格式（'column1_name'）
            has_valid_result = (
                '解释' in result_data or 
                '算法结果' in result_data or 
                'column1_name' in result_data or
                'analysis_result' in result_data
            )
            
            if has_valid_result and result_data:
                # 统一添加status字段，确保与其他算法响应格式一致
                if 'status' not in result_data:
                    result_data['status'] = 'success'
                
                logger.info(f"关联分析执行成功，响应包含字段: {list(result_data.keys())}")
                
                return AlgorithmExecutionResponse(
                    result=result_data,
                    status="success",
                    message="关联分析执行成功",
                    readable_result=None  # 🆕 设置为None，系统会自动调用大模型分析
                )
            else:
                # 响应格式不符合预期
                error_msg = result_data.get('message', '响应格式不符合预期')
                logger.error(f"关联分析返回未知格式: {result_data}")
                return AlgorithmExecutionResponse(
                    result=result_data,
                    status="error",
                    message=f"关联分析执行失败: {error_msg}",
                    readable_result=None
                )
        
        except Exception as e:
            logger.error(f"关联分析执行失败: {str(e)}")
            return AlgorithmExecutionResponse(
                result={},
                status="error",
                message=f"关联分析执行失败: {str(e)}",
                readable_result=None
            )
    
    # =========================================================================
    # Forecast Service 执行方法
    # =========================================================================
    
    async def _get_forecast_session(self) -> aiohttp.ClientSession:
        """获取 Forecast Service 专用的 HTTP 会话"""
        timeout = aiohttp.ClientTimeout(total=self.forecast_timeout)
        return aiohttp.ClientSession(timeout=timeout)
    
    async def execute_trend_analysis(
        self,
        request: AlgorithmExecutionRequest
    ) -> AlgorithmExecutionResponse:
        """
        执行趋势分析算法
        
        Args:
            request: 算法执行请求
            
        Returns:
            AlgorithmExecutionResponse: 执行响应
        """
        logger.info("开始执行趋势分析算法")
        logger.info(f"输入数据行数: {len(request.data_rows)}")
        logger.info(f"趋势分析配置: {request.config}")
        
        try:
            # 使用新的算法API客户端
            result_data = await self.algorithm_client.call_trend_analysis_api(
                data_rows=request.data_rows,
                config=request.config
            )
            
            logger.info("趋势分析算法执行成功")
            
            # 检查响应格式：支持 'status' 或其他成功标识
            status = result_data.get('status', 'unknown')
            
            # 🆕 新版本：设置 readable_result=None，系统会自动调用大模型分析
            if status == 'success' or (status == 'unknown' and result_data and 'error' not in result_data):
                # 统一添加status字段，确保与其他算法响应格式一致
                if 'status' not in result_data:
                    result_data['status'] = 'success'
                
                logger.info(f"趋势分析执行成功，响应包含字段: {list(result_data.keys())}")
                
                return AlgorithmExecutionResponse(
                    result=result_data,
                    status="success",
                    message="趋势分析执行成功",
                    readable_result=None  # 🆕 自动调用大模型分析
                )
            else:
                error_msg = result_data.get('error', result_data.get('message', '未知错误'))
                logger.error(f"趋势分析执行失败: {error_msg}")
                return AlgorithmExecutionResponse(
                    result=result_data,
                    status="error",
                    message=f"趋势分析执行失败: {error_msg}",
                    readable_result=None  # 🆕 错误情况下也会自动生成分析
                )
                
        except Exception as e:
            logger.error(f"趋势分析执行失败: {str(e)}")
            return AlgorithmExecutionResponse(
                result={},
                status="error",
                message=f"趋势分析执行失败: {str(e)}",
                readable_result=None  # 🆕 异常情况下也会自动处理
            )
    
    def _prepare_trend_request(
        self,
        request: AlgorithmExecutionRequest,
        analysis_type: str
    ) -> Dict[str, Any]:
        """准备趋势分析请求数据"""
        config = request.config
        data_rows = request.data_rows
        
        # 转换数据格式
        api_data = [
            {"timestamp": row["timestamp"], "value": row["value"]}
            for row in data_rows
            if "timestamp" in row and "value" in row
        ]
        
        if analysis_type == 'decomposition':
            payload = {"data": api_data}
            if config.get('period') is not None:
                payload["period"] = config["period"]
            if config.get('decomposition_model'):
                payload["decomposition_model"] = config["decomposition_model"]
            if config.get('algorithm'):
                payload["algorithm"] = config["algorithm"]
        else:  # detection
            payload = {"data": api_data}
            if config.get('detection_method'):
                payload["method"] = config["detection_method"]
            if config.get('confidence_level') is not None:
                payload["confidence_level"] = config["confidence_level"]
            payload["include_seasonal_adjustment"] = config.get('include_seasonal_adjustment', True)
        
        return payload
    
    def _convert_trend_response(
        self,
        api_response: Dict[str, Any],
        analysis_type: str
    ) -> Dict[str, Any]:
        """转换趋势分析响应为内部格式"""
        metadata = api_response.get('metadata', {})
        results = api_response.get('results', {})
        
        if analysis_type == 'decomposition':
            return {
                "decomposition": {
                    "trend": results.get('trend', []),
                    "seasonal": results.get('seasonal', []),
                    "residual": results.get('residual', []),
                },
                "analysis_type": "decomposition",
                "algorithm_used": metadata.get('algorithm_selected', 'unknown'),
                "period_used": metadata.get('period_detected', 0),
                "data_characteristics": metadata.get('data_characteristics', {}),
                "data_points": metadata.get('data_points', 0),
            }
        else:  # detection
            return {
                "detection": results,
                "analysis_type": "detection",
                "method_used": metadata.get('method_selected', 'unknown'),
                "data_characteristics": metadata.get('data_characteristics', {}),
                "data_points": metadata.get('data_points', 0),
            }
    
    async def execute_univariate_forecast(
        self,
        request: AlgorithmExecutionRequest
    ) -> AlgorithmExecutionResponse:
        """
        执行单变量预测算法（调用 forecast_service）
        
        Args:
            request: 算法执行请求
            
        Returns:
            AlgorithmExecutionResponse: 执行响应
        """
        logger.info("开始执行单变量预测算法")
        logger.info(f"输入数据行数: {len(request.data_rows)}")
        logger.info(f"单变量预测配置: {request.config}")
        
        try:
            # 使用算法API客户端调用
            result_data = await self.algorithm_client.call_univariate_forecast_api(
                data_rows=request.data_rows,
                config=request.config
            )
            
            logger.info("单变量预测算法执行成功")
            
            # 检查响应格式：支持 'success' 或 'status' 字段
            is_success = result_data.get('success', False) or result_data.get('status') == 'success'
            
            if is_success:
                # 统一添加status字段，确保与其他算法响应格式一致
                if 'status' not in result_data:
                    result_data['status'] = 'success'
                
                logger.info(f"单变量预测执行成功，响应包含字段: {list(result_data.keys())}")
                
                return AlgorithmExecutionResponse(
                    result=result_data,
                    status="success",
                    message="单变量预测执行成功",
                    readable_result=None  # 🆕 自动调用大模型分析
                )
            else:
                error_msg = result_data.get('message', result_data.get('error', '未知错误'))
                logger.error(f"单变量预测执行失败: {error_msg}")
                return AlgorithmExecutionResponse(
                    result=result_data,
                    status="error",
                    message=f"单变量预测执行失败: {error_msg}",
                    readable_result=None  # 🆕 错误情况下也会自动生成分析
                )
                
        except Exception as e:
            logger.error(f"单变量预测执行异常: {str(e)}")
            return AlgorithmExecutionResponse(
                result={},
                status="error",
                message=f"单变量预测执行异常: {str(e)}",
                readable_result=None  # 🆕 异常情况下也会自动处理
            )
            
    async def execute_multivariate_forecast(
        self,
        request: AlgorithmExecutionRequest
    ) -> AlgorithmExecutionResponse:
        """
        执行多变量预测算法（调用 forecast_service）
        
        Args:
            request: 算法执行请求
            
        Returns:
            AlgorithmExecutionResponse: 执行响应
        """
        logger.info("开始执行多变量预测算法")
        logger.info(f"输入数据行数: {len(request.data_rows)}")
        logger.info(f"多变量预测配置: {request.config}")
        
        try:
            # 使用算法API客户端调用
            result_data = await self.algorithm_client.call_multivariate_forecast_api(
                data_rows=request.data_rows,
                config=request.config
            )
            
            logger.info("多变量预测算法执行成功")
            
            # 检查响应格式：支持 'success' 或 'status' 字段
            is_success = result_data.get('success', False) or result_data.get('status') == 'success'
            
            if is_success:
                # 统一添加status字段，确保与其他算法响应格式一致
                if 'status' not in result_data:
                    result_data['status'] = 'success'
                
                logger.info(f"多变量预测执行成功，响应包含字段: {list(result_data.keys())}")
                
                return AlgorithmExecutionResponse(
                    result=result_data,
                    status="success",
                    message="多变量预测执行成功",
                    readable_result=None  # 🆕 自动调用大模型分析
                )
            else:
                error_msg = result_data.get('message', result_data.get('error', '未知错误'))
                logger.error(f"多变量预测执行失败: {error_msg}")
                return AlgorithmExecutionResponse(
                    result=result_data,
                    status="error",
                    message=f"多变量预测执行失败: {error_msg}",
                    readable_result=None  # 🆕 错误情况下也会自动生成分析
                )
                
        except Exception as e:
            logger.error(f"多变量预测执行异常: {str(e)}")
            return AlgorithmExecutionResponse(
                result={},
                status="error",
                message=f"多变量预测执行异常: {str(e)}",
                readable_result=None  # 🆕 异常情况下也会自动处理
            )

    # =========================================================================
    # Causality Analysis 执行方法
    # =========================================================================

    async def execute_causality_analysis(
        self,
        request: AlgorithmExecutionRequest
    ) -> AlgorithmExecutionResponse:
        """
        执行因果分析算法

        Args:
            request: 算法执行请求

        Returns:
            AlgorithmExecutionResponse: 执行响应
        """
        logger.info("开始执行因果分析算法")
        logger.info(f"输入数据行数: {len(request.data_rows)}")
        logger.info(f"因果分析配置: {request.config}")

        try:
            # 调用因果分析API
            result_data = await self.algorithm_client.call_causality_api(
                data_rows=request.data_rows,
                config=request.config
            )

            logger.info("因果分析算法执行成功")

            # 检查响应是否包含错误信息
            if 'error' in result_data:
                error_msg = result_data.get('error', '未知错误')
                logger.error(f"因果分析返回错误: {error_msg}")
                return AlgorithmExecutionResponse(
                    result=result_data,
                    status="error",
                    message=f"因果分析执行失败: {error_msg}",
                    readable_result=None
                )

            # 检查响应中是否包含有效结果字段
            has_valid_result = (
                result_data.get('status') == 'success' or
                result_data.get('success', False) or
                ('解释' in result_data and 'error' not in result_data)
            )

            if has_valid_result and result_data:
                # 统一添加status字段
                if 'status' not in result_data:
                    result_data['status'] = 'success'

                logger.info(f"因果分析执行成功，响应包含字段: {list(result_data.keys())}")

                return AlgorithmExecutionResponse(
                    result=result_data,
                    status="success",
                    message="因果分析执行成功",
                    readable_result=None  # 设置为None，系统会自动调用大模型分析
                )
            else:
                error_msg = result_data.get('message', '响应格式不符合预期')
                logger.error(f"因果分析返回未知格式: {result_data}")
                return AlgorithmExecutionResponse(
                    result=result_data,
                    status="error",
                    message=f"因果分析执行失败: {error_msg}",
                    readable_result=None
                )

        except Exception as e:
            logger.error(f"因果分析执行失败: {str(e)}")
            return AlgorithmExecutionResponse(
                result={},
                status="error",
                message=f"因果分析执行失败: {str(e)}",
                readable_result=None
            )

    async def forecast_service_health_check(self) -> bool:
        """
        检查 Forecast Service 健康状态
        
        Returns:
            bool: 服务是否健康
        """
        session = None
        try:
            base_url = self.algorithm_apis.get("forecast", "")
            if not base_url:
                return False
            
            session = await self._get_forecast_session()
            url = f"{base_url.rstrip('/')}/health"
            
            async with session.get(url) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Forecast Service 健康检查失败: {str(e)}")
            return False
        finally:
            if session and not session.closed:
                await session.close()
    
    async def poll_async_task(self, task_id: str) -> AsyncGenerator[AsyncTaskResponse, None]:
        """
        轮询异步任务状态（增强版本，支持详细进度跟踪）
        
        Args:
            task_id: 任务ID
            
        Yields:
            AsyncTaskResponse: 任务状态更新
        """
        logger.info(f"开始轮询异步任务: {task_id}")
        
        poll_interval = self.settings.async_task_poll_interval
        max_wait_time = self.settings.async_task_max_wait_time
        elapsed_time = 0
        poll_count = 0
        last_progress_percent = 0
        
        try:
            while elapsed_time < max_wait_time:
                poll_count += 1
                poll_start_time = datetime.utcnow()
                
                try:
                    # 使用新的算法API客户端查询任务状态
                    task_data = await self.algorithm_client.query_task_status("classification", task_id)
                    
                    # 解析任务状态
                    status_str = task_data.get("status", "processing")
                    try:
                        status = TaskStatus(status_str)
                    except ValueError:
                        status = TaskStatus.PROCESSING
                    
                    # 增强进度信息
                    progress = task_data.get("progress", {})
                    if progress:
                        current_progress = progress.get("percent", 0)
                        progress_delta = current_progress - last_progress_percent
                        
                        # 添加进度分析
                        progress["poll_count"] = poll_count
                        progress["progress_delta"] = progress_delta
                        progress["elapsed_time_seconds"] = elapsed_time
                        
                        # 估算剩余时间
                        if progress_delta > 0 and current_progress > 0:
                            estimated_total_time = elapsed_time * (100 / current_progress)
                            estimated_remaining_time = estimated_total_time - elapsed_time
                            progress["estimated_remaining_seconds"] = max(0, estimated_remaining_time)
                        
                        last_progress_percent = current_progress
                    
                    # 增强训练日志
                    logs = task_data.get("logs", [])
                    if logs:
                        # 为每个日志条目添加时间戳
                        enhanced_logs = []
                        for log_entry in logs:
                            if isinstance(log_entry, str):
                                enhanced_logs.append({
                                    "timestamp": datetime.utcnow().isoformat(),
                                    "content": log_entry,
                                    "poll_count": poll_count
                                })
                            else:
                                enhanced_logs.append(log_entry)
                        logs = enhanced_logs
                    
                    # 提取和增强指标信息
                    metrics = task_data.get("metrics", {})
                    if not metrics and logs:
                        # 尝试从日志中提取指标
                        metrics = self._extract_metrics_from_logs(logs)
                    
                    # 添加轮询指标
                    poll_metrics = {
                        "poll_count": poll_count,
                        "poll_interval_seconds": poll_interval,
                        "elapsed_time_seconds": elapsed_time,
                        "poll_response_time_ms": (datetime.utcnow() - poll_start_time).total_seconds() * 1000
                    }
                    
                    if metrics:
                        metrics.update(poll_metrics)
                    else:
                        metrics = poll_metrics
                    
                    task_response = AsyncTaskResponse(
                        task_id=task_id,
                        status=status,
                        progress=progress,
                        result=task_data.get("result"),
                        error=task_data.get("error"),
                        logs=[log.get("content", log) if isinstance(log, dict) else log for log in logs],
                        metrics=metrics
                    )
                    
                    yield task_response
                    
                    # 如果任务完成或失败，停止轮询
                    if status in [TaskStatus.SUCCESS, TaskStatus.FAILED]:
                        logger.info(f"异步任务完成: {task_id}, 状态: {status.value}, 轮询次数: {poll_count}")
                        return
                
                except Exception as e:
                    logger.error(f"轮询任务状态异常: {str(e)}")
                    yield AsyncTaskResponse(
                        task_id=task_id,
                        status=TaskStatus.FAILED,
                        error=f"轮询异常: {str(e)}",
                        metrics={"poll_count": poll_count, "exception_at_poll": poll_count}
                    )
                    return
                
                # 等待下次轮询
                await asyncio.sleep(poll_interval)
                elapsed_time += poll_interval
            
            # 超时
            logger.warning(f"异步任务轮询超时: {task_id}, 轮询次数: {poll_count}")
            yield AsyncTaskResponse(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error="任务轮询超时",
                metrics={
                    "poll_count": poll_count,
                    "timeout_after_seconds": elapsed_time,
                    "max_wait_time": max_wait_time
                }
            )
            
        except Exception as e:
            logger.error(f"轮询异步任务失败: {str(e)}")
            yield AsyncTaskResponse(
                task_id=task_id,
                status=TaskStatus.FAILED,
                error=f"轮询失败: {str(e)}",
                metrics={"poll_count": poll_count, "fatal_error": True}
            )
    
    def _extract_metrics_from_logs(self, logs: List[Any]) -> Dict[str, Any]:
        """
        从训练日志中提取指标信息
        
        Args:
            logs: 训练日志列表
            
        Returns:
            Dict[str, Any]: 提取的指标
        """
        import re
        
        metrics = {}
        
        try:
            for log_entry in logs:
                log_content = log_entry.get("content", log_entry) if isinstance(log_entry, dict) else str(log_entry)
                
                # 提取常见的训练指标
                # 匹配模式: loss=0.123, accuracy=0.95, epoch=5
                metric_patterns = [
                    r'(\w+)=([0-9.]+)',  # key=value
                    r'(\w+):\s*([0-9.]+)',  # key: value
                    r'(\w+)\s+([0-9.]+)'  # key value
                ]
                
                for pattern in metric_patterns:
                    matches = re.findall(pattern, log_content.lower())
                    for metric_name, metric_value in matches:
                        try:
                            # 尝试转换为数值
                            if '.' in metric_value:
                                metrics[metric_name] = float(metric_value)
                            else:
                                metrics[metric_name] = int(metric_value)
                        except ValueError:
                            # 如果转换失败，保存为字符串
                            metrics[metric_name] = metric_value
                
                # 提取特殊指标
                if 'epoch' in log_content.lower():
                    epoch_match = re.search(r'epoch[:\s]+(\d+)', log_content.lower())
                    if epoch_match:
                        metrics['current_epoch'] = int(epoch_match.group(1))
                
                if 'step' in log_content.lower():
                    step_match = re.search(r'step[:\s]+(\d+)', log_content.lower())
                    if step_match:
                        metrics['current_step'] = int(step_match.group(1))
        
        except Exception as e:
            logger.error(f"从日志提取指标失败: {str(e)}")
        
        return metrics
    
    async def health_check(self, service_type: str) -> bool:
        """
        检查算法服务健康状态
        
        Args:
            service_type: 服务类型 ("clustering" 或 "classification")
            
        Returns:
            bool: 服务是否健康
        """
        try:
            base_url = self.algorithm_apis.get(service_type, "")
            if not base_url:
                return False
            
            session = await self._get_session()
            url = f"{base_url.rstrip('/')}/health"
            
            async with session.get(url) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"{service_type}算法服务健康检查失败: {str(e)}")
            return False
    
    async def close(self):
        """关闭执行器连接"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.debug("算法执行器连接已关闭")
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        await self.close()
    
    async def convert_sql_result_to_algorithm_input(
        self,
        sql_result: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """
        将SQL结果转换为算法兼容的输入格式
        
        Args:
            sql_result: SQL查询结果
            algorithm_config: 算法配置
            parameters: 算法参数
            
        Returns:
            AlgorithmExecutionRequest: 算法执行请求
            
        Raises:
            ValueError: 数据转换失败时抛出
        """
        logger.info(f"转换SQL结果为{algorithm_config.name}算法输入格式")
        
        try:
            # 使用数据处理器进行转换
            algorithm_request = await self.data_processor.convert_sql_result_to_algorithm_input(
                sql_result, algorithm_config, parameters
            )
            
            # 验证转换后的数据
            is_valid = await self.data_processor.validate_algorithm_input(
                algorithm_request, algorithm_config
            )
            
            if not is_valid:
                raise ValueError("转换后的算法输入数据验证失败")
            
            logger.info(f"成功转换{len(sql_result)}行数据为{algorithm_config.name}算法输入")
            return algorithm_request
            
        except Exception as e:
            logger.error(f"SQL结果转换为算法输入失败: {str(e)}")
            raise ValueError(f"数据转换失败: {str(e)}")
    
    async def execute_algorithm_with_sql_data(
        self,
        sql_result: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        parameters: AlgorithmParameters
    ) -> AlgorithmExecutionResponse:
        """
        使用SQL数据执行算法的便捷方法
        
        Args:
            sql_result: SQL查询结果
            algorithm_config: 算法配置
            parameters: 算法参数
            
        Returns:
            AlgorithmExecutionResponse: 执行响应
        """
        logger.info(f"使用SQL数据执行{algorithm_config.name}算法")
        
        try:
            # 转换SQL结果为算法输入
            algorithm_request = await self.convert_sql_result_to_algorithm_input(
                sql_result, algorithm_config, parameters
            )
            
            # 根据算法类型执行相应的算法
            algorithm_type = parameters.algorithm_type.value
            algorithm_name = algorithm_config.name
            
            if "聚类" in algorithm_name or algorithm_type == "cluster":
                return await self.execute_clustering(algorithm_request)
            elif "分类" in algorithm_name or algorithm_type == "classify":
                return await self.execute_classification(algorithm_request)
            elif "趋势" in algorithm_name or algorithm_type == "trend":
                return await self.execute_trend_analysis(algorithm_request)
            elif "单变量" in algorithm_name or algorithm_type == "univariate_forecast":
                return await self.execute_univariate_forecast(algorithm_request)
            elif "多变量" in algorithm_name or algorithm_type == "multivariate_forecast":
                return await self.execute_multivariate_forecast(algorithm_request)
            elif "因果" in algorithm_name or algorithm_type == "causality":
                return await self.execute_causality_analysis(algorithm_request)
            elif algorithm_type == "predict":
                # 预测类型需要根据子类型判断
                sub_type = parameters.parameter_mapping.get('sub_algorithm', '')
                if 'univariate' in sub_type or '单变量' in sub_type:
                    return await self.execute_univariate_forecast(algorithm_request)
                elif 'multivariate' in sub_type or '多变量' in sub_type:
                    return await self.execute_multivariate_forecast(algorithm_request)
                else:
                    # 默认使用单变量预测
                    return await self.execute_univariate_forecast(algorithm_request)
            # elif algorithm_type == "dbscan" or "dbscan" in algorithm_name.lower() or "密度聚类" in algorithm_name:
            #     return await self.execute_dbscan(algorithm_request)
            # elif algorithm_type == "iforest" or "iforest" in algorithm_name.lower() or "孤立森林" in algorithm_name:
            #     return await self.execute_iforest(algorithm_request)
            elif "异常" in algorithm_config.name or parameters.algorithm_type.value == "anomaly":
                return await self.execute_anomaly_detection(algorithm_request)
            elif "关联" in algorithm_name or algorithm_type == "associate":
                return await self.execute_association(algorithm_request)
            elif ("占比" in algorithm_name
                  or "贡献" in algorithm_name or "排行" in algorithm_name
                  or "proportion" in algorithm_type):
                return await self.execute_compare_proportion(algorithm_request)
            else:
                # 对于其他算法类型，可以扩展支持
                logger.warning(f"暂不支持的算法类型: {parameters.algorithm_type}")
                return AlgorithmExecutionResponse(
                    status="failed",
                    message=f"暂不支持的算法类型: {parameters.algorithm_type}"
                )
                
        except Exception as e:
            logger.error(f"使用SQL数据执行算法失败: {str(e)}")
            return AlgorithmExecutionResponse(
                status="failed",
                message=f"算法执行失败: {str(e)}"
            )
    
    async def poll_async_task_with_manager(
        self,
        task_id: str,
        timeout_seconds: Optional[int] = None
    ) -> AsyncGenerator[AsyncTaskResponse, None]:
        """
        使用任务管理器轮询异步任务状态
        
        Args:
            task_id: 任务ID
            timeout_seconds: 超时时间（秒）
            
        Yields:
            AsyncTaskResponse: 任务状态更新
        """
        logger.info(f"使用任务管理器轮询异步任务: {task_id}")
        
        # 使用任务管理器的轮询机制
        async for response in self.task_manager.start_task_polling(
            task_id, 
            self.poll_async_task,  # 使用现有的轮询函数
            timeout_seconds
        ):
            yield response