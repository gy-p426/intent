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
        执行分类算法
        
        Args:
            request: 算法执行请求
            
        Returns:
            AlgorithmExecutionResponse: 执行响应(可能包含task_id)
        """
        logger.info("开始执行分类算法")
        
        try:
            # 使用新的算法API客户端
            result_data = await self.algorithm_client.call_classification_api(
                data_rows=request.data_rows,
                data_sets=request.data_sets or [],
                config=request.config
            )
            
            # 检查是否返回了task_id（异步处理）
            if "task_id" in result_data:
                task_id = result_data["task_id"]
                # 在任务管理器中创建任务记录
                await self.task_manager.create_task(task_id, AlgorithmType.CLASSIFY)
                
                return AlgorithmExecutionResponse(
                    task_id=task_id,
                    status="processing",
                    message="分类算法异步处理中"
                )
            else:
                # 同步返回结果
                return AlgorithmExecutionResponse(
                    result=result_data,
                    status="success",
                    message="分类算法执行成功"
                )
                
        except Exception as e:
            logger.error(f"分类算法执行失败: {str(e)}")
            return AlgorithmExecutionResponse(
                result={},
                status="error",
                message=f"分类算法执行失败: {str(e)}"
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
            
            if result_data.get('status') == 'success':
                anomalies = result_data.get('anomalies', [])
                normal_points = result_data.get('normal_points', [])
                clusters = result_data.get('clusters', [])
                
                logger.info(f"检测到异常点数量: {len(anomalies)}")
                logger.info(f"正常点数量: {len(normal_points)}")
                logger.info(f"聚类数量: {len(clusters)}")
                
                # 显示异常检测结果摘要
                if anomalies:
                    logger.info(f"异常点示例: {anomalies[:3]}")  # 显示前3个异常点
                else:
                    logger.info("未检测到异常点")
            else:
                logger.error(f"DBSCAN异常检测算法返回错误状态: {result_data}")
            
            return AlgorithmExecutionResponse(
                result=result_data,
                status="success",
                message="DBSCAN异常检测算法执行成功"
            )
            
        except Exception as e:
            logger.error(f"DBSCAN异常检测算法执行失败: {str(e)}")
            return AlgorithmExecutionResponse(
                result={},
                status="error",
                message=f"DBSCAN异常检测算法执行失败: {str(e)}"
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
        执行趋势分析算法（调用 forecast_service）
        
        Args:
            request: 算法执行请求，config 中需包含 analysis_type
            
        Returns:
            AlgorithmExecutionResponse: 执行响应
        """
        logger.info("开始执行趋势分析算法")
        
        session = None
        try:
            config = request.config
            analysis_type = config.get('analysis_type', 'decomposition')
            
            # 根据分析类型选择端点
            if analysis_type == 'decomposition':
                endpoint = "/api/v1/trend/decomposition"
            elif analysis_type == 'detection':
                endpoint = "/api/v1/trend/detection"
            else:
                return AlgorithmExecutionResponse(
                    status="failed",
                    message=f"不支持的分析类型: {analysis_type}"
                )
            
            # 准备请求数据
            request_data = self._prepare_trend_request(request, analysis_type)
            
            # 发送HTTP请求
            session = await self._get_forecast_session()
            base_url = self.algorithm_apis.get("forecast", "")
            url = f"{base_url.rstrip('/')}{endpoint}"
            
            logger.debug(f"发送趋势分析请求到: {url}")
            
            async with session.post(url, json=request_data) as response:
                if response.status == 200:
                    result_data = await response.json()
                    
                    # 转换响应格式
                    internal_result = self._convert_trend_response(result_data, analysis_type)
                    
                    return AlgorithmExecutionResponse(
                        result=internal_result,
                        status="success",
                        message="趋势分析执行成功"
                    )
                else:
                    error_text = await response.text()
                    logger.error(f"趋势分析执行失败: {response.status} - {error_text}")
                    
                    return AlgorithmExecutionResponse(
                        status="failed",
                        message=f"趋势分析执行失败: {error_text}"
                    )
                    
        except Exception as e:
            logger.error(f"趋势分析执行异常: {str(e)}")
            return AlgorithmExecutionResponse(
                status="failed",
                message=f"趋势分析执行异常: {str(e)}"
            )
        finally:
            if session and not session.closed:
                await session.close()
    
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
        
        session = None
        try:
            config = request.config
            data_rows = request.data_rows
            
            # 准备请求数据
            # 内部格式可能是 [{timestamp, value}, ...] 或 {timestamp: [], value: []}
            if isinstance(data_rows, list) and len(data_rows) > 0:
                if isinstance(data_rows[0], dict) and 'timestamp' in data_rows[0]:
                    # 列表格式转换为数组格式
                    timestamps = [row['timestamp'] for row in data_rows]
                    values = [row['value'] for row in data_rows]
                    api_data = {"timestamp": timestamps, "value": values}
                else:
                    api_data = data_rows[0].get('data', {})
            else:
                api_data = {"timestamp": [], "value": []}
            
            request_data = {
                "data": api_data,
                "config": {
                    "forecast_horizon": config.get('forecast_horizon', 24),
                    "include_confidence": config.get('include_confidence', True)
                }
            }
            
            # 发送HTTP请求
            session = await self._get_forecast_session()
            base_url = self.algorithm_apis.get("forecast", "")
            url = f"{base_url.rstrip('/')}/api/v1/forecast/univariate"
            
            logger.debug(f"发送单变量预测请求到: {url}")
            
            async with session.post(url, json=request_data) as response:
                if response.status == 200:
                    result_data = await response.json()
                    
                    # 转换响应格式
                    internal_result = {
                        "success": result_data.get('success', True),
                        "model_used": result_data.get('model_used', 'unknown'),
                        "results": result_data.get('results', {}),
                        "data_analysis": result_data.get('data_analysis', {})
                    }
                    
                    return AlgorithmExecutionResponse(
                        result=internal_result,
                        status="success",
                        message="单变量预测执行成功"
                    )
                else:
                    error_text = await response.text()
                    logger.error(f"单变量预测执行失败: {response.status} - {error_text}")
                    
                    return AlgorithmExecutionResponse(
                        status="failed",
                        message=f"单变量预测执行失败: {error_text}"
                    )
                    
        except Exception as e:
            logger.error(f"单变量预测执行异常: {str(e)}")
            return AlgorithmExecutionResponse(
                status="failed",
                message=f"单变量预测执行异常: {str(e)}"
            )
        finally:
            if session and not session.closed:
                await session.close()
    
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
        
        session = None
        try:
            config = request.config
            data_rows = request.data_rows
            
            # 准备请求数据
            request_data = {
                "data": data_rows,
                "config": {
                    "target_column": config.get('target_column'),
                    "feature_columns": config.get('feature_columns', []),
                    "algorithm": config.get('algorithm', 'lightgbm'),
                    "forecast_horizon": config.get('forecast_horizon', 14),
                    "model_name": config.get('model_name')
                }
            }
            
            # 发送HTTP请求
            session = await self._get_forecast_session()
            base_url = self.algorithm_apis.get("forecast", "")
            url = f"{base_url.rstrip('/')}/api/v1/forecast/multivariate"
            
            logger.debug(f"发送多变量预测请求到: {url}")
            
            async with session.post(url, json=request_data) as response:
                if response.status == 200:
                    result_data = await response.json()
                    
                    # 转换响应格式
                    internal_result = {
                        "success": result_data.get('success', True),
                        "model_id": result_data.get('model_id'),
                        "model_name": result_data.get('model_name'),
                        "model_used": result_data.get('model_used', 'unknown'),
                        "results": result_data.get('results', {}),
                        "metrics": result_data.get('metrics', {}),
                        "reused_model": result_data.get('reused_model', False)
                    }
                    
                    return AlgorithmExecutionResponse(
                        result=internal_result,
                        status="success",
                        message="多变量预测执行成功"
                    )
                else:
                    error_text = await response.text()
                    logger.error(f"多变量预测执行失败: {response.status} - {error_text}")
                    
                    return AlgorithmExecutionResponse(
                        status="failed",
                        message=f"多变量预测执行失败: {error_text}"
                    )
                    
        except Exception as e:
            logger.error(f"多变量预测执行异常: {str(e)}")
            return AlgorithmExecutionResponse(
                status="failed",
                message=f"多变量预测执行异常: {str(e)}"
            )
        finally:
            if session and not session.closed:
                await session.close()
    
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
            elif "异常" in algorithm_config.name or parameters.algorithm_type.value == "anomaly":
                return await self.execute_anomaly_detection(algorithm_request)
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