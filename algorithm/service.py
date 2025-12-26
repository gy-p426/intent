"""
Algorithm Integration Service

Main service class that coordinates all algorithm integration components
and provides the primary interface for algorithm execution workflows.
"""

import logging
import asyncio
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime

from algorithm.models import AlgorithmType, AlgorithmParameters, AlgorithmResponseGenerator
from algorithm.logging import StructuredLogger, LogCategory, get_structured_logger
from algorithm.interfaces import (
    IAlgorithmIntegrationService, IAlgorithmRouter, IParameterExtractor,
    INL2SQLClient, IAlgorithmExecutor, IStreamingResponseHandler,
    IAlgorithmConfigManager, ITaskManager, IDataProcessor
)
from algorithm.config_manager import get_algorithm_config_manager
from algorithm.database import DatabaseSchemaRetriever
from algorithm.error_handler import (
    ErrorHandler, RetryHandler, RetryConfig, AlgorithmError,
    ParameterValidationError, ComponentNotInitializedError,
    IntentRecognitionError, ParameterExtractionError, NL2SQLError,
    AlgorithmExecutionError, TaskTimeoutError, ErrorCode,
    retry_on_failure, error_handler, retry_handler
)


logger = logging.getLogger(__name__)
structured_logger = get_structured_logger(__name__)


# 算法类型中文映射
ALGORITHM_TYPE_CHINESE_MAP = {
    AlgorithmType.CLUSTER: "聚类",
    AlgorithmType.CLASSIFY: "分类",
    AlgorithmType.PREDICT: "预测",
    AlgorithmType.ANOMALY: "异常检测",
    AlgorithmType.ASSOCIATE: "关联分析",
    AlgorithmType.COMPARE: "对比分析",
    AlgorithmType.SIMILARITY: "相似度分析",
    AlgorithmType.TREND: "趋势分析",
    AlgorithmType.PROFILE: "画像分析",
    AlgorithmType.CAUSALITY: "因果分析",
    AlgorithmType.ALERT: "预警分析",
    AlgorithmType.RECOMMEND: "推荐分析"
}


class AlgorithmIntegrationService(IAlgorithmIntegrationService):
    """算法集成服务主类"""
    
    def __init__(
        self,
        router: Optional[IAlgorithmRouter] = None,
        parameter_extractor: Optional[IParameterExtractor] = None,
        nl2sql_client: Optional[INL2SQLClient] = None,
        algorithm_executor: Optional[IAlgorithmExecutor] = None,
        streaming_handler: Optional[IStreamingResponseHandler] = None,
        task_manager: Optional[ITaskManager] = None,
        data_processor: Optional[IDataProcessor] = None,
        config_manager: Optional[IAlgorithmConfigManager] = None,
        schema_retriever: Optional[DatabaseSchemaRetriever] = None,
        error_handler: Optional[ErrorHandler] = None,
        retry_handler: Optional[RetryHandler] = None
    ):
        """
        初始化算法集成服务
        
        Args:
            router: 算法路由器
            parameter_extractor: 参数提取器
            nl2sql_client: NL2SQL客户端
            algorithm_executor: 算法执行器
            streaming_handler: 流式响应处理器
            task_manager: 任务管理器
            data_processor: 数据处理器
            config_manager: 配置管理器
            schema_retriever: 数据库模式获取器
            error_handler: 错误处理器
            retry_handler: 重试处理器
        """
        self.router = router
        self.parameter_extractor = parameter_extractor
        self.nl2sql_client = nl2sql_client
        self.algorithm_executor = algorithm_executor
        self.streaming_handler = streaming_handler
        self.task_manager = task_manager
        self.data_processor = data_processor
        self.config_manager = config_manager or get_algorithm_config_manager()
        self.schema_retriever = schema_retriever or DatabaseSchemaRetriever()
        self.error_handler = error_handler or ErrorHandler()
        self.retry_handler = retry_handler or RetryHandler()
        
        # 如果没有提供算法执行器，创建默认实例
        if self.algorithm_executor is None:
            from algorithm.executor.algorithm_executor import AlgorithmExecutor
            self.algorithm_executor = AlgorithmExecutor()
        
        # 配置重试策略
        self.retry_configs = {
            'nl2sql': RetryConfig(max_attempts=3, base_delay=2.0, max_delay=30.0),
            'algorithm_api': RetryConfig(max_attempts=2, base_delay=1.0, max_delay=10.0),
            'database': RetryConfig(max_attempts=3, base_delay=1.0, max_delay=15.0),
            'parameter_extraction': RetryConfig(max_attempts=2, base_delay=0.5, max_delay=5.0)
        }
        
        logger.info("算法集成服务初始化完成")
    
    async def process_algorithm_request(
        self, 
        question: str, 
        window_id: str, 
        session_id: str,
        user_id: Optional[str] = None
    ) -> AlgorithmResponseGenerator:
        """
        处理算法请求的主要方法
        
        Args:
            question: 用户自然语言查询
            window_id: 窗口ID
            session_id: 会话ID
            user_id: 用户ID（可选）
            
        Yields:
            AlgorithmResponse: 流式响应数据
            
        Raises:
            ValueError: 参数无效或服务未初始化
            RuntimeError: 处理过程中发生错误
        """
        # 生成追踪ID
        trace_id = str(uuid.uuid4())
        
        request_context = {
            'question': question,
            'window_id': window_id,
            'session_id': session_id,
            'user_id': user_id,
            'trace_id': trace_id,
            'start_time': datetime.utcnow()
        }
        
        try:
            # 验证输入参数
            self._validate_request_parameters(question, window_id, session_id)
            
            # 验证必需的组件
            self._validate_components()
            
            # 记录算法请求开始
            structured_logger.log_algorithm_request(
                question, window_id, session_id, trace_id, user_id
            )
            
            logger.info(f"开始处理算法请求: {question[:100]}...", extra={'trace_id': trace_id})
            
            # 使用错误处理包装整个处理流程
            async for response in self._process_with_error_handling(
                question, window_id, session_id, request_context
            ):
                yield response
                
        except AlgorithmError as e:
            logger.error(f"算法处理错误: {e.message}", extra=request_context)
            structured_logger.log_error(e, trace_id, e.step)
            yield e.to_error_response()
            
        except Exception as e:
            logger.error(f"未预期的错误: {str(e)}", extra=request_context, exc_info=True)
            structured_logger.log_error(e, trace_id, StreamingStep.ERROR, request_context)
            error_response = self.error_handler.handle_error(e, request_context)
            yield error_response
    
    async def _process_with_error_handling(
        self,
        question: str,
        window_id: str,
        session_id: str,
        request_context: Dict[str, Any]
    ) -> AlgorithmResponseGenerator:
        """
        带错误处理的处理流程
        
        Args:
            question: 用户查询
            window_id: 窗口ID
            session_id: 会话ID
            request_context: 请求上下文
            
        Yields:
            AlgorithmResponse: 流式响应数据
        """
        try:
            from algorithm.models import AlgorithmResponse, StreamingStep, NL2SQLRequest
            
            # 步骤1: 识别算法类型
            trace_id = request_context.get('trace_id', 'unknown')
            start_time = datetime.utcnow()
            
            logger.info("开始算法类型识别", extra={'trace_id': trace_id})
            yield AlgorithmResponse(
                step=StreamingStep.ALGORITHM_IDENTIFICATION,
                status="processing",
                data={"message": "正在识别算法类型..."},
                timestamp=datetime.utcnow()
            )
            
            try:
                algorithm_type = await self._identify_algorithm_type_with_retry(question)
                execution_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                # 记录结构化日志
                structured_logger.log_algorithm_identification(
                    algorithm_type, None, trace_id, execution_time_ms
                )
                
                logger.info(f"算法类型识别完成: {algorithm_type}", extra={'trace_id': trace_id})
                
                # 流式返回算法类型识别结果
                algorithm_type_chinese = ALGORITHM_TYPE_CHINESE_MAP.get(algorithm_type, algorithm_type.value)
                yield AlgorithmResponse(
                    step=StreamingStep.ALGORITHM_IDENTIFICATION,
                    status="completed",
                    data={
                        "algorithm_type": algorithm_type.value,
                        "algorithm_type_chinese": algorithm_type_chinese,
                        "message": f"识别到算法类型: {algorithm_type_chinese}"
                    },
                    timestamp=datetime.utcnow()
                )
                
            except Exception as e:
                execution_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                structured_logger.log_error(e, trace_id, StreamingStep.ALGORITHM_IDENTIFICATION)
                raise IntentRecognitionError(
                    f"算法类型识别失败: {str(e)}",
                    question=question,
                    original_error=e
                )
            
            # 步骤2: 提取算法参数
            start_time = datetime.utcnow()
            logger.info("开始参数提取", extra={'trace_id': trace_id})
            yield AlgorithmResponse(
                step=StreamingStep.PARAMETER_EXTRACTION,
                status="processing",
                data={"message": "正在提取算法参数..."},
                timestamp=datetime.utcnow()
            )
            
            try:
                parameters = await self._extract_parameters_with_retry(question, algorithm_type, window_id)
                execution_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                
                # 记录结构化日志
                structured_logger.log_parameter_extraction(
                    algorithm_type,
                    parameters.required_columns,
                    len(parameters.parameter_mapping),
                    trace_id,
                    execution_time_ms
                )
                
                logger.info(f"参数提取完成: {len(parameters.required_columns)} 个列", extra={'trace_id': trace_id})
                
                # 流式返回参数提取结果
                yield AlgorithmResponse(
                    step=StreamingStep.PARAMETER_EXTRACTION,
                    status="completed",
                    data={
                        "normalized_query": parameters.normalized_query,
                        "required_columns": parameters.required_columns,
                        "parameter_mapping": parameters.parameter_mapping,
                        "message": "参数提取完成"
                    },
                    timestamp=datetime.utcnow()
                )
                
            except Exception as e:
                execution_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                structured_logger.log_error(e, trace_id, StreamingStep.PARAMETER_EXTRACTION, algorithm_type=algorithm_type)
                raise ParameterExtractionError(
                    f"参数提取失败: {str(e)}",
                    algorithm_type=algorithm_type,
                    original_error=e
                )
            
            # 步骤3: SQL生成和数据检索
            if self.nl2sql_client:
                logger.info("开始SQL生成")
                yield AlgorithmResponse(
                    step=StreamingStep.SQL_GENERATION,
                    status="processing",
                    data={"message": "正在生成SQL查询..."},
                    timestamp=datetime.utcnow()
                )
                
                try:
                    # 检查是否有query_db结果，如果有则使用预先获取的候选表信息
                    if parameters.query_db_result and parameters.query_db_result.get('candidateTables'):
                        logger.info("使用extractor提供的候选表信息，避免重复调用/query-db接口")
                        nl2sql_response = await self._query_nl2sql_with_candidates_retry(
                            parameters.normalized_query,
                            parameters.query_db_result['candidateTables'],
                            parameters.query_db_result.get('keywords', {}),
                            window_id,
                            session_id
                        )
                    else:
                        logger.info("使用传统方式调用NL2SQL接口（内部执行完整两阶段流程）")
                        nl2sql_request = NL2SQLRequest(
                            question=parameters.normalized_query,
                            window_id=window_id,
                            session_id=session_id
                        )
                        nl2sql_response = await self._query_nl2sql_with_retry(nl2sql_request)
                    
                    # 流式返回SQL生成结果
                    yield AlgorithmResponse(
                        step=StreamingStep.SQL_GENERATION,
                        status="completed",
                        data={
                            "sql_statement": nl2sql_response.sql_statement,
                            "execution_time_ms": nl2sql_response.execution_time_ms,
                            "message": "SQL生成完成"
                        },
                        timestamp=datetime.utcnow()
                    )
                    
                    # 流式返回数据检索结果
                    yield AlgorithmResponse(
                        step=StreamingStep.DATA_RETRIEVAL,
                        status="completed",
                        data={
                            "data_rows_count": len(nl2sql_response.execution_result),
                            "sample_data": nl2sql_response.execution_result if nl2sql_response.execution_result else [],
                            "message": f"数据检索完成，获取到 {len(nl2sql_response.execution_result)} 行数据"
                        },
                        timestamp=datetime.utcnow()
                    )
                    
                    # 步骤4: 算法执行
                    if self.algorithm_executor and self.data_processor:
                        logger.info("开始算法执行")
                        algorithm_type_chinese = ALGORITHM_TYPE_CHINESE_MAP.get(algorithm_type, algorithm_type.value)
                        yield AlgorithmResponse(
                            step=StreamingStep.ALGORITHM_EXECUTION,
                            status="processing",
                            data={"message": f"正在执行{algorithm_type_chinese}算法..."},
                            timestamp=datetime.utcnow()
                        )
                        
                        try:
                            # 获取算法配置
                            algorithm_config = self.config_manager.get_algorithm_config(algorithm_type)
                            if not algorithm_config:
                                raise AlgorithmExecutionError(
                                    f"未找到算法配置: {algorithm_type}",
                                    algorithm_type=algorithm_type
                                )
                            
                            # 记录算法执行开始
                            structured_logger.log_algorithm_execution_start(
                                algorithm_type, 
                                len(nl2sql_response.execution_result),
                                trace_id
                            )
                            
                            # 转换数据格式
                            algorithm_request = await self._convert_data_with_validation(
                                nl2sql_response.execution_result,
                                algorithm_config,
                                parameters
                            )
                            
                            # 执行算法
                            execution_response = await self._execute_algorithm_with_retry(
                                algorithm_type, algorithm_request
                            )
                            
                            # 检查是否为异步任务
                            if execution_response.task_id:
                                # 异步任务处理
                                yield AlgorithmResponse(
                                    step=StreamingStep.TASK_POLLING,
                                    status="processing",
                                    data={
                                        "task_id": execution_response.task_id,
                                        "message": "算法正在异步执行，开始轮询任务状态..."
                                    },
                                    timestamp=datetime.utcnow()
                                )
                                
                                # 带超时的异步任务轮询
                                task_response = None
                                async for task_response in self._handle_async_task_with_timeout(
                                    execution_response.task_id, algorithm_type
                                ):
                                    yield AlgorithmResponse(
                                        step=StreamingStep.TASK_POLLING,
                                        status="processing" if task_response.status == "processing" else "completed",
                                        data={
                                            "task_id": task_response.task_id,
                                            "status": task_response.status.value,
                                            "progress": task_response.progress,
                                            "logs": task_response.logs,
                                            "message": f"任务状态: {task_response.status.value}"
                                        },
                                        timestamp=datetime.utcnow()
                                    )
                                    
                                    if task_response.status != "processing":
                                        break
                                
                                # 返回最终结果
                                if task_response and task_response.status == "success" and task_response.result:
                                    yield AlgorithmResponse(
                                        step=StreamingStep.COMPLETED,
                                        status="completed",
                                        data={
                                            "algorithm_type": algorithm_type.value,
                                            "algorithm_result": task_response.result,
                                            "task_id": task_response.task_id,
                                            "message": "算法执行完成"
                                        },
                                        timestamp=datetime.utcnow()
                                    )
                                elif task_response and task_response.status == "failed":
                                    raise AlgorithmExecutionError(
                                        f"异步任务失败: {task_response.error}",
                                        algorithm_type=algorithm_type,
                                        details={'task_id': task_response.task_id}
                                    )
                                else:
                                    raise AlgorithmExecutionError(
                                        "异步任务处理异常",
                                        algorithm_type=algorithm_type,
                                        details={'task_id': execution_response.task_id}
                                    )
                            
                            else:
                                # 同步任务结果 - 记录详细的算法结果日志
                                algorithm_result = execution_response.result
                                
                                # 详细记录算法结果
                                logger.info(f"算法执行完成: {algorithm_type.value}")
                                logger.info(f"算法结果状态: {algorithm_result.get('status', 'unknown')}")
                                
                                # 根据算法类型记录特定信息
                                if algorithm_type.value == "cluster" and algorithm_result.get('status') == 'success':
                                    k_used = algorithm_result.get('k_used', 'unknown')
                                    results = algorithm_result.get('results', [])
                                    logger.info(f"聚类分析完成 - 使用K值: {k_used}, 结果数量: {len(results)}")
                                    
                                    # 计算聚类分布
                                    if results:
                                        cluster_distribution = {}
                                        for item in results:
                                            cluster_id = item.get('cluster_id', 'unknown')
                                            cluster_distribution[cluster_id] = cluster_distribution.get(cluster_id, 0) + 1
                                        logger.info(f"聚类分布: {cluster_distribution}")
                                
                                # 构建增强的算法执行响应
                                algorithm_type_chinese = ALGORITHM_TYPE_CHINESE_MAP.get(algorithm_type, algorithm_type.value)
                                algorithm_execution_data = {
                                    "algorithm_result": algorithm_result,
                                    "message": f"{algorithm_type_chinese}算法执行完成",
                                    "execution_summary": self._generate_algorithm_summary(algorithm_type, algorithm_result)
                                }
                                
                                yield AlgorithmResponse(
                                    step=StreamingStep.ALGORITHM_EXECUTION,
                                    status="completed",
                                    data=algorithm_execution_data,
                                    timestamp=datetime.utcnow()
                                )
                                
                                # 构建增强的最终完成响应
                                algorithm_type_chinese = ALGORITHM_TYPE_CHINESE_MAP.get(algorithm_type, algorithm_type.value)
                                final_data = {
                                    "algorithm_type": algorithm_type.value,
                                    "algorithm_type_chinese": algorithm_type_chinese,
                                    "algorithm_result": algorithm_result,
                                    "sql_statement": nl2sql_response.sql_statement,
                                    "normalized_query": parameters.normalized_query,
                                    "execution_summary": self._generate_algorithm_summary(algorithm_type, algorithm_result),
                                    "data_summary": {
                                        "input_rows": len(nl2sql_response.execution_result),
                                        "sql_execution_time": nl2sql_response.execution_time_ms
                                    },
                                    "readable_result": self._format_readable_result(algorithm_type, algorithm_result, nl2sql_response.execution_result),
                                    "message": f"{algorithm_type_chinese}算法执行完成"
                                }
                                
                                logger.info(f"完整算法流程执行完成: {algorithm_type.value}")
                                logger.info(f"最终结果摘要: {final_data['execution_summary']}")
                                
                                yield AlgorithmResponse(
                                    step=StreamingStep.COMPLETED,
                                    status="completed",
                                    data=final_data,
                                    timestamp=datetime.utcnow()
                                )
                        
                        except AlgorithmError:
                            # 重新抛出算法错误
                            raise
                        except Exception as e:
                            logger.error(f"算法执行失败: {str(e)}", exc_info=True)
                            raise AlgorithmExecutionError(
                                f"算法执行失败: {str(e)}",
                                algorithm_type=algorithm_type,
                                original_error=e
                            )
                    else:
                        logger.warning("算法执行器或数据处理器未初始化，跳过算法执行")
                        yield AlgorithmResponse(
                            step=StreamingStep.COMPLETED,
                            status="completed",
                            data={
                                "algorithm_type": algorithm_type.value,
                                "sql_statement": nl2sql_response.sql_statement,
                                "normalized_query": parameters.normalized_query,
                                "message": "数据检索完成，算法执行器未配置"
                            },
                            timestamp=datetime.utcnow()
                        )
                
                except Exception as e:
                    logger.error(f"SQL生成或数据检索失败: {str(e)}", exc_info=True)
                    raise NL2SQLError(
                        f"SQL生成失败: {str(e)}",
                        service_url=getattr(self.nl2sql_client, 'base_url', None),
                        original_error=e
                    )
            else:
                logger.warning("NL2SQL客户端未初始化，跳过SQL生成")
                yield AlgorithmResponse(
                    step=StreamingStep.COMPLETED,
                    status="completed",
                    data={
                        "algorithm_type": algorithm_type.value,
                        "normalized_query": parameters.normalized_query,
                        "required_columns": parameters.required_columns,
                        "message": "参数提取完成，NL2SQL客户端未配置"
                    },
                    timestamp=datetime.utcnow()
                )
            
        except AlgorithmError:
            # 重新抛出算法错误，让上层处理
            raise
        except Exception as e:
            logger.error(f"处理算法请求失败: {str(e)}", exc_info=True)
            raise AlgorithmError(
                error_code=ErrorCode.INTERNAL_ERROR,
                message=f"处理算法请求失败: {str(e)}",
                original_error=e
            )
    
    async def identify_algorithm_type(self, question: str) -> AlgorithmType:
        """
        识别算法类型
        
        Args:
            question: 用户查询
            
        Returns:
            AlgorithmType: 识别的算法类型
            
        Raises:
            ValueError: 无法识别算法类型
        """
        if not self.router:
            raise ValueError("算法路由器未初始化")
        
        return await self.router.route_to_algorithm(question)
    
    async def extract_parameters(
        self, 
        question: str, 
        algorithm_type: AlgorithmType,
        window_id: str = "default"
    ) -> AlgorithmParameters:
        """
        提取算法参数
        
        Args:
            question: 用户查询
            algorithm_type: 算法类型
            window_id: 窗口ID
            
        Returns:
            AlgorithmParameters: 提取的参数
            
        Raises:
            ValueError: 参数提取失败
        """
        if not self.parameter_extractor:
            raise ValueError("参数提取器未初始化")
        
        # 获取数据库模式信息
        try:
            database_schema = await self.schema_retriever.get_database_schema()
            logger.info(f"获取到 {len(database_schema)} 个数据库列信息")
        except Exception as e:
            logger.warning(f"获取数据库模式信息失败: {str(e)}，使用空模式")
            database_schema = []
        
        return await self.parameter_extractor.extract_parameters(
            question, algorithm_type, database_schema, window_id
        )
    
    def _validate_request_parameters(self, question: str, window_id: str, session_id: str):
        """验证请求参数"""
        if not question or not question.strip():
            raise ParameterValidationError("查询问题不能为空", field_name="question")
        
        if len(question) > 1000:
            raise ParameterValidationError("查询问题长度不能超过1000字符", field_name="question")
        
        if not window_id:
            raise ParameterValidationError("窗口ID不能为空", field_name="window_id")
        
        # 会话ID可以为空，不进行验证
        # if not session_id:
        #     raise ParameterValidationError("会话ID不能为空", field_name="session_id")
    
    def _validate_components(self):
        """验证必需的组件是否已初始化"""
        required_components = {
            'router': self.router,
            'parameter_extractor': self.parameter_extractor,
            'config_manager': self.config_manager
        }
        
        missing_components = [
            name for name, component in required_components.items() 
            if component is None
        ]
        
        if missing_components:
            raise ComponentNotInitializedError(
                f"以下必需组件未初始化: {', '.join(missing_components)}"
            )
    
    async def _identify_algorithm_type_with_retry(self, question: str) -> AlgorithmType:
        """带重试的算法类型识别"""
        return await self.retry_handler.retry_async(
            self.identify_algorithm_type,
            question,
            config=self.retry_configs['parameter_extraction'],
            retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
            context={'operation': 'algorithm_type_identification', 'question': question[:100]}
        )
    
    async def _extract_parameters_with_retry(
        self, 
        question: str, 
        algorithm_type: AlgorithmType,
        window_id: str = "default"
    ) -> AlgorithmParameters:
        """带重试的参数提取"""
        return await self.retry_handler.retry_async(
            self.extract_parameters,
            question,
            algorithm_type,
            window_id,
            config=self.retry_configs['parameter_extraction'],
            retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
            context={'operation': 'parameter_extraction', 'algorithm_type': algorithm_type.value}
        )
    
    async def _query_nl2sql_with_retry(self, request) -> Any:
        """带重试的NL2SQL查询（完整流程）"""
        return await self.retry_handler.retry_async(
            self.nl2sql_client.query,
            request,
            config=self.retry_configs['nl2sql'],
            retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
            context={'operation': 'nl2sql_query', 'question': request.question[:100]}
        )
    
    async def _query_nl2sql_with_candidates_retry(
        self, 
        question: str, 
        candidate_tables: List[str], 
        keywords: Dict[str, Any], 
        window_id: str, 
        session_id: str
    ) -> Any:
        """使用预先获取的候选表信息调用NL2SQL服务（避免重复调用query-db）"""
        return await self.retry_handler.retry_async(
            self.nl2sql_client.query_with_candidates,
            question,
            candidate_tables,
            keywords,
            window_id,
            session_id,
            config=self.retry_configs['nl2sql'],
            retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
            context={'operation': 'nl2sql_query_with_candidates', 'question': question[:100]}
        )
    
    async def _convert_data_with_validation(
        self,
        sql_result: list,
        algorithm_config: Any,
        parameters: AlgorithmParameters
    ) -> Any:
        """带验证的数据转换"""
        try:
            if not sql_result:
                raise AlgorithmExecutionError(
                    "SQL查询结果为空，无法执行算法",
                    algorithm_type=parameters.algorithm_type
                )
            
            algorithm_request = await self.data_processor.convert_sql_result_to_algorithm_input(
                sql_result, algorithm_config, parameters
            )
            
            # 验证转换后的数据
            is_valid = await self.data_processor.validate_algorithm_input(
                algorithm_request, algorithm_config
            )
            
            if not is_valid:
                raise AlgorithmExecutionError(
                    "转换后的算法输入数据验证失败",
                    algorithm_type=parameters.algorithm_type
                )
            
            return algorithm_request
            
        except Exception as e:
            if isinstance(e, AlgorithmError):
                raise
            raise AlgorithmExecutionError(
                f"数据转换失败: {str(e)}",
                algorithm_type=parameters.algorithm_type,
                original_error=e
            )
    
    async def _execute_algorithm_with_retry(
        self,
        algorithm_type: AlgorithmType,
        algorithm_request: Any
    ) -> Any:
        """带重试的算法执行"""
        try:
            if algorithm_type == AlgorithmType.CLUSTER:
                return await self.retry_handler.retry_async(
                    self.algorithm_executor.execute_clustering,
                    algorithm_request,
                    config=self.retry_configs['algorithm_api'],
                    retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
                    context={'operation': 'clustering_execution', 'algorithm_type': algorithm_type.value}
                )
            elif algorithm_type == AlgorithmType.CLASSIFY:
                return await self.retry_handler.retry_async(
                    self.algorithm_executor.execute_classification,
                    algorithm_request,
                    config=self.retry_configs['algorithm_api'],
                    retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
                    context={'operation': 'classification_execution', 'algorithm_type': algorithm_type.value}
                )
            elif algorithm_type == AlgorithmType.ANOMALY:
                return await self.retry_handler.retry_async(
                    self.algorithm_executor.execute_anomaly_detection,
                    algorithm_request,
                    config=self.retry_configs['algorithm_api'],
                    retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
                    context={'operation': 'anomaly_detection_execution', 'algorithm_type': algorithm_type.value}
                )
            # elif algorithm_type == AlgorithmType.DBSCAN:
            #     return await self.retry_handler.retry_async(
            #         self.algorithm_executor.execute_dbscan,
            #         algorithm_request,
            #         config=self.retry_configs['algorithm_api'],
            #         retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
            #         context={'operation': 'dbscan_execution', 'algorithm_type': algorithm_type.value}
            #     )
            # elif algorithm_type == AlgorithmType.IFOREST:
            #     return await self.retry_handler.retry_async(
            #         self.algorithm_executor.execute_iforest,
            #         algorithm_request,
            #         config=self.retry_configs['algorithm_api'],
            #         retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
            #         context={'operation': 'iforest_execution', 'algorithm_type': algorithm_type.value}
            #     )
            elif algorithm_type == AlgorithmType.TREND:
                return await self.retry_handler.retry_async(
                    self.algorithm_executor.execute_trend_analysis,
                    algorithm_request,
                    config=self.retry_configs['algorithm_api'],
                    retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
                    context={'operation': 'trend_analysis_execution', 'algorithm_type': algorithm_type.value}
                )
            else:
                raise AlgorithmExecutionError(
                    f"暂不支持的算法类型: {algorithm_type}",
                    algorithm_type=algorithm_type
                )
        except Exception as e:
            if isinstance(e, AlgorithmError):
                raise
            raise AlgorithmExecutionError(
                f"算法执行失败: {str(e)}",
                algorithm_type=algorithm_type,
                original_error=e
            )
    
    async def _handle_async_task_with_timeout(
        self,
        task_id: str,
        algorithm_type: AlgorithmType,
        timeout_seconds: int = 300
    ):
        """带超时处理的异步任务轮询"""
        try:
            start_time = datetime.utcnow()
            
            # 确保poll_async_task返回的是异步生成器
            poll_generator = self.algorithm_executor.poll_async_task(task_id)
            
            # 检查是否是协程，如果是则等待
            if asyncio.iscoroutine(poll_generator):
                poll_generator = await poll_generator
            
            async for task_response in poll_generator:
                # 检查超时
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                if elapsed > timeout_seconds:
                    if self.task_manager:
                        await self.task_manager.handle_task_timeout(task_id)
                    raise TaskTimeoutError(task_id, timeout_seconds)
                
                yield task_response
                
                # 如果任务完成，退出循环
                if task_response.status != "processing":
                    break
                    
        except asyncio.TimeoutError:
            if self.task_manager:
                await self.task_manager.handle_task_timeout(task_id)
            raise TaskTimeoutError(task_id, timeout_seconds)
        except Exception as e:
            if self.task_manager:
                await self.task_manager.handle_task_failure(task_id, str(e))
            raise AlgorithmExecutionError(
                f"异步任务处理失败: {str(e)}",
                algorithm_type=algorithm_type,
                details={'task_id': task_id},
                original_error=e
            )
    
    def _generate_algorithm_summary(self, algorithm_type: AlgorithmType, algorithm_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        生成算法执行摘要
        
        Args:
            algorithm_type: 算法类型
            algorithm_result: 算法执行结果
            
        Returns:
            Dict[str, Any]: 算法摘要信息
        """
        summary = {
            "algorithm_type": algorithm_type.value,
            "status": algorithm_result.get("status", "unknown"),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        try:
            if algorithm_type == AlgorithmType.CLUSTER:
                # 聚类算法摘要
                if algorithm_result.get("status") == "success":
                    k_used = algorithm_result.get("k_used", 0)
                    results = algorithm_result.get("results", [])
                    
                    # 计算聚类分布
                    cluster_distribution = {}
                    for item in results:
                        cluster_id = item.get("cluster_id", "unknown")
                        cluster_distribution[cluster_id] = cluster_distribution.get(cluster_id, 0) + 1
                    
                    summary.update({
                        "k_value_used": k_used,
                        "total_data_points": len(results),
                        "cluster_distribution": cluster_distribution,
                        "cluster_count": len(cluster_distribution),
                        "largest_cluster_size": max(cluster_distribution.values()) if cluster_distribution else 0,
                        "smallest_cluster_size": min(cluster_distribution.values()) if cluster_distribution else 0
                    })
                    
                    # 添加聚类质量指标（如果有的话）
                    if "metrics" in algorithm_result:
                        summary["quality_metrics"] = algorithm_result["metrics"]
                
            elif algorithm_type == AlgorithmType.CLASSIFY:
                # 分类算法摘要
                if algorithm_result.get("status") == "success":
                    results = algorithm_result.get("results", [])
                    
                    # 统计预测结果分布
                    prediction_distribution = {}
                    confidence_scores = []
                    
                    for item in results:
                        predicted_label = item.get("predicted_label", "unknown")
                        prediction_distribution[predicted_label] = prediction_distribution.get(predicted_label, 0) + 1
                        
                        if "probability" in item:
                            confidence_scores.append(item["probability"])
                    
                    summary.update({
                        "total_predictions": len(results),
                        "prediction_distribution": prediction_distribution,
                        "unique_labels": len(prediction_distribution),
                        "average_confidence": sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0,
                        "min_confidence": min(confidence_scores) if confidence_scores else 0,
                        "max_confidence": max(confidence_scores) if confidence_scores else 0
                    })
            
            # 添加通用错误信息
            if algorithm_result.get("status") != "success":
                summary["error_message"] = algorithm_result.get("error", "未知错误")
                
        except Exception as e:
            logger.warning(f"生成算法摘要时发生错误: {str(e)}")
            summary["summary_generation_error"] = str(e)
        
        return summary
    
    def get_service_health(self) -> Dict[str, Any]:
        """获取服务健康状态"""
        health_status = {
            'service': 'algorithm-integration-service',
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'components': {},
            'error_statistics': self.error_handler.get_error_statistics(),
            'retry_statistics': self.retry_handler.get_retry_statistics()
        }
        
        # 检查各组件状态
        components = {
            'router': self.router,
            'parameter_extractor': self.parameter_extractor,
            'nl2sql_client': self.nl2sql_client,
            'algorithm_executor': self.algorithm_executor,
            'config_manager': self.config_manager,
            'schema_retriever': self.schema_retriever
        }
        
        for name, component in components.items():
            health_status['components'][name] = {
                'initialized': component is not None,
                'status': 'available' if component is not None else 'unavailable'
            }
        
        # 检查是否有组件不可用
        unavailable_components = [
            name for name, status in health_status['components'].items()
            if status['status'] == 'unavailable'
        ]
        
        if unavailable_components:
            health_status['status'] = 'degraded'
            health_status['warnings'] = [
                f"以下组件不可用: {', '.join(unavailable_components)}"
            ]
        
        return health_status
    
    async def initialize(self):
        """初始化服务和所有组件"""
        logger.info("初始化算法集成服务")
        
        # 加载算法配置
        await self.config_manager.load_config()
        
        # 初始化数据库模式获取器
        try:
            await self.schema_retriever.initialize()
            logger.info("数据库模式获取器初始化成功")
        except Exception as e:
            logger.warning(f"数据库模式获取器初始化失败: {str(e)}")
        
        logger.info("算法集成服务初始化完成")
    
    async def cleanup(self):
        """清理资源"""
        logger.info("清理算法集成服务资源")
        
        if self.nl2sql_client:
            await self.nl2sql_client.close()
        
        if self.schema_retriever:
            await self.schema_retriever.close()
        
        logger.info("资源清理完成")
    
    def _format_readable_result(self, algorithm_type: AlgorithmType, algorithm_result: Dict[str, Any], original_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        格式化算法结果为可读格式
        
        Args:
            algorithm_type: 算法类型
            algorithm_result: 算法执行结果
            original_data: 原始数据
            
        Returns:
            Dict[str, Any]: 格式化后的可读结果
        """
        try:
            if algorithm_type == AlgorithmType.CLUSTER and algorithm_result.get("status") == "success":
                return self._format_clustering_result(algorithm_result, original_data)
            elif algorithm_type == AlgorithmType.CLASSIFY and algorithm_result.get("status") == "success":
                return self._format_classification_result(algorithm_result, original_data)
            elif algorithm_type == AlgorithmType.TREND:
                return self._format_trend_result(algorithm_result, original_data)
            elif algorithm_type == AlgorithmType.ANOMALY:
                return self._format_anomaly_result(algorithm_result, original_data)
            # elif algorithm_type == AlgorithmType.DBSCAN:
            #     return self._format_dbscan_result(algorithm_result, original_data)
            # elif algorithm_type == AlgorithmType.IFOREST:
            #     return self._format_iforest_result(algorithm_result, original_data)
            else:
                return {
                    "summary": f"算法执行状态: {algorithm_result.get('status', '未知')}",
                    "details": algorithm_result
                }
        except Exception as e:
            logger.warning(f"格式化算法结果时发生错误: {str(e)}")
            return {
                "summary": "结果格式化失败",
                "raw_result": algorithm_result
            }
    
    def _format_clustering_result(self, algorithm_result: Dict[str, Any], original_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        格式化聚类算法结果
        
        Args:
            algorithm_result: 聚类算法结果
            original_data: 原始数据
            
        Returns:
            Dict[str, Any]: 格式化后的聚类结果
        """
        k_used = algorithm_result.get("k_used", 0)
        results = algorithm_result.get("results", [])
        
        # 按聚类ID分组
        cluster_groups = {}
        for item in results:
            cluster_id = item.get("cluster_id")
            uid = item.get("uid")
            
            if cluster_id is not None and uid is not None:
                if cluster_id not in cluster_groups:
                    cluster_groups[cluster_id] = []
                cluster_groups[cluster_id].append(uid)
        
        # 构建简洁的聚类结果描述
        cluster_descriptions = []
        cluster_summary = {}
        
        for cluster_id in sorted(cluster_groups.keys()):
            member_ids = cluster_groups[cluster_id]
            cluster_name = f"第{cluster_id + 1}类" if cluster_id >= 0 else f"聚类{cluster_id}"
            
            # 创建描述
            if len(member_ids) <= 10:
                # 如果成员不多，显示所有ID
                ids_str = "、".join(member_ids)
                description = f"{cluster_name}包含{len(member_ids)}个成员：{ids_str}"
            else:
                # 如果成员很多，只显示前几个
                ids_str = "、".join(member_ids[:8])
                description = f"{cluster_name}包含{len(member_ids)}个成员：{ids_str}等"
            
            cluster_descriptions.append(description)
            cluster_summary[cluster_name] = {
                "count": len(member_ids),
                "members": member_ids
            }
        
        # 生成总体描述
        total_description = f"聚类分析完成，将{len(results)}个数据点分为{k_used}个聚类。"
        full_description = total_description + " " + "；".join(cluster_descriptions) + "。"
        
        return {
            "summary": full_description,
            "k_value": k_used,
            "total_data_points": len(results),
            "cluster_details": cluster_summary,
            "simple_view": {
                f"第{i+1}类": cluster_groups.get(i, []) 
                for i in sorted(cluster_groups.keys())
            }
        }
    
    def _format_classification_result(self, algorithm_result: Dict[str, Any], original_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        格式化分类算法结果
        
        Args:
            algorithm_result: 分类算法结果
            original_data: 原始数据
            
        Returns:
            Dict[str, Any]: 格式化后的分类结果
        """
        results = algorithm_result.get("results", [])
        
        # 统计预测结果分布
        prediction_distribution = {}
        confidence_scores = []
        
        for item in results:
            predicted_label = item.get("predicted_label", "未知")
            prediction_distribution[predicted_label] = prediction_distribution.get(predicted_label, 0) + 1
            
            if "probability" in item:
                confidence_scores.append(item["probability"])
        
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        
        return {
            "summary": f"分类分析完成，对 {len(results)} 个数据点进行了分类预测",
            "total_predictions": len(results),
            "prediction_distribution": prediction_distribution,
            "average_confidence": round(avg_confidence, 3),
            "confidence_range": {
                "min": round(min(confidence_scores), 3) if confidence_scores else 0,
                "max": round(max(confidence_scores), 3) if confidence_scores else 0
            },
            "sample_predictions": results[:5]  # 显示前5个预测结果
        }
    
    def _format_trend_result(self, algorithm_result: Dict[str, Any], original_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        格式化趋势分析算法结果
        
        Args:
            algorithm_result: 趋势分析算法结果
            original_data: 原始数据
            
        Returns:
            Dict[str, Any]: 格式化后的趋势分析结果
        """
        # 解析趋势分析结果
        success = algorithm_result.get('success', False)
        message = algorithm_result.get('message', '')
        results = algorithm_result.get('results', {})
        metadata = algorithm_result.get('metadata', {})
        
        if not success or not results:
            # 如果分析失败或没有结果，返回基本信息
            return {
                "summary": f"趋势分析状态: {message}",
                "status": "failed" if not success else "no_results",
                "data_points": len(original_data),
                "message": message
            }
        
        # 提取关键结果信息
        trend_direction = results.get('trend_direction', 'unknown')
        slope = results.get('slope', 0)
        p_value = results.get('p_value', 1)
        r_squared = results.get('r_squared', 0)
        statistical_significance = results.get('statistical_significance', False)
        confidence_level = results.get('confidence_level', 0.95)
        method = results.get('method', metadata.get('method_used', '未知方法'))
        interpretation = results.get('interpretation', '')
        confidence_interval = results.get('confidence_interval', [])
        
        # 构建用户友好的趋势方向描述
        direction_map = {
            'increasing': '上升',
            'decreasing': '下降', 
            'stable': '稳定',
            'no_trend': '无明显趋势'
        }
        direction_chinese = direction_map.get(trend_direction, trend_direction)
        
        # 构建趋势强度描述
        r_squared_percent = round(r_squared * 100, 1)
        if r_squared >= 0.7:
            trend_strength = "强"
        elif r_squared >= 0.3:
            trend_strength = "中等"
        else:
            trend_strength = "弱"
        
        # 构建统计显著性描述
        significance_desc = "统计显著" if statistical_significance else "统计不显著"
        confidence_percent = int(confidence_level * 100)
        
        # 构建主要描述
        if trend_direction in ['increasing', 'decreasing']:
            slope_desc = f"每日变化约{abs(slope):.2f}个单位"
            main_description = f"趋势分析完成，检测到{direction_chinese}趋势（{slope_desc}），趋势强度为{trend_strength}（R²={r_squared_percent}%），在{confidence_percent}%置信水平下{significance_desc}。"
        else:
            main_description = f"趋势分析完成，数据呈现{direction_chinese}状态，在{confidence_percent}%置信水平下{significance_desc}。"
        
        # 构建详细分析结果
        analysis_details = {
            "趋势方向": direction_chinese,
            "趋势强度": f"{trend_strength}（R²={r_squared_percent}%）",
            "统计显著性": f"{significance_desc}（p值={p_value:.4f}）",
            "分析方法": method,
            "置信水平": f"{confidence_percent}%",
            "数据点数": len(original_data)
        }
        
        if trend_direction in ['increasing', 'decreasing']:
            analysis_details["变化率"] = f"{slope:.3f}单位/天"
            if confidence_interval and len(confidence_interval) == 2:
                analysis_details["置信区间"] = f"[{confidence_interval[0]:.3f}, {confidence_interval[1]:.3f}]"
        
        # 构建简化视图
        simple_view = {
            "趋势": direction_chinese,
            "强度": trend_strength,
            "显著性": "显著" if statistical_significance else "不显著",
            "解释": interpretation if interpretation else f"数据呈现{direction_chinese}趋势"
        }
        
        # 构建技术细节（供高级用户参考）
        technical_details = {
            "slope": slope,
            "intercept": results.get('intercept', 0),
            "p_value": p_value,
            "r_squared": r_squared,
            "std_error": results.get('std_error', 0),
            "confidence_interval": confidence_interval,
            "sample_size": results.get('sample_size', len(original_data)),
            "method": method
        }
        
        return {
            "summary": main_description,
            "trend_direction": direction_chinese,
            "trend_strength": trend_strength,
            "statistical_significance": statistical_significance,
            "confidence_level": confidence_percent,
            "data_points": len(original_data),
            "analysis_details": analysis_details,
            "simple_view": simple_view,
            "technical_details": technical_details,
            "interpretation": interpretation if interpretation else f"在分析的{len(original_data)}个数据点中，检测到{direction_chinese}趋势模式"
        }
    
    def _format_anomaly_result(self, algorithm_result: Dict[str, Any], original_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        格式化异常检测算法结果（统一的异常检测格式化）
        
        Args:
            algorithm_result: 异常检测算法结果
            original_data: 原始数据
            
        Returns:
            Dict[str, Any]: 格式化后的异常检测结果
        """
        success = algorithm_result.get('success', False)
        status = algorithm_result.get('status', 'unknown')
        
        if not success and status != 'success':
            return {
                "summary": f"异常检测失败: {algorithm_result.get('message', '未知错误')}",
                "status": "failed",
                "data_points": len(original_data)
            }
        
        # 解析新的返回格式
        results = algorithm_result.get('results', [])
        
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
        
        total_points = len(results)
        anomaly_count = len(anomalies)
        normal_count = len(normal_points)
        cluster_count = len(clusters)
        
        # 计算异常比例
        anomaly_rate = (anomaly_count / total_points * 100) if total_points > 0 else 0
        
        # 构建主要描述
        if cluster_count > 0:
            # 有正常聚类的情况
            main_description = f"异常检测完成，在{total_points}个数据点中检测到{anomaly_count}个异常点（异常率{anomaly_rate:.1f}%），{normal_count}个正常点，形成{cluster_count}个聚类。"
            algorithm_type_desc = "基于DBSCAN密度聚类的异常检测"
        else:
            # 全部都是异常点的情况
            main_description = f"异常检测完成，在{total_points}个数据点中检测到{anomaly_count}个异常点（异常率{anomaly_rate:.1f}%），未形成有效聚类。"
            algorithm_type_desc = "基于DBSCAN密度聚类的异常检测"
        
        # 构建详细分析结果
        analysis_details = {
            "总数据点": total_points,
            "异常点数量": anomaly_count,
            "正常点数量": normal_count,
            "异常率": f"{anomaly_rate:.1f}%",
            "算法类型": algorithm_type_desc
        }
        
        if cluster_count > 0:
            analysis_details["聚类数量"] = cluster_count
            # 添加聚类分布信息
            cluster_distribution = {f"聚类{cid}": len(items) for cid, items in clusters.items()}
            analysis_details["聚类分布"] = cluster_distribution
        
        # 构建简化视图
        simple_view = {
            "异常检测": f"发现{anomaly_count}个异常点",
            "异常率": f"{anomaly_rate:.1f}%",
            "状态": "检测完成"
        }
        
        if cluster_count > 0:
            simple_view["聚类结果"] = f"形成{cluster_count}个聚类"
        else:
            simple_view["聚类结果"] = "未形成有效聚类"
        
        # 构建异常点详情（显示前10个，包含实际数据）
        anomaly_details = []
        if anomalies:
            for i, anomaly in enumerate(anomalies[:10]):
                # 提取异常点的所有数据字段，不只是id
                anomaly_info = {"cluster_id": -1}
                
                # 复制异常点的所有字段（除了cluster_id）
                for key, value in anomaly.items():
                    if key != 'cluster_id':
                        anomaly_info[key] = value
                
                # 如果没有id字段，生成一个标识
                if 'id' not in anomaly_info:
                    anomaly_info['id'] = f'异常点{i+1}'
                
                anomaly_details.append(anomaly_info)
        
        # 构建正常点详情（显示前5个，包含实际数据）
        normal_details = []
        if normal_points:
            for i, normal in enumerate(normal_points[:5]):
                # 提取正常点的所有数据字段
                normal_info = {"cluster_id": normal.get('cluster_id', 0)}
                
                # 复制正常点的所有字段（除了cluster_id）
                for key, value in normal.items():
                    if key != 'cluster_id':
                        normal_info[key] = value
                
                # 如果没有id字段，生成一个标识
                if 'id' not in normal_info:
                    normal_info['id'] = f'正常点{i+1}'
                
                normal_details.append(normal_info)
        
        return {
            "summary": main_description,
            "anomaly_count": anomaly_count,
            "normal_count": normal_count,
            "cluster_count": cluster_count,
            "anomaly_rate": round(anomaly_rate, 1),
            "data_points": total_points,
            "analysis_details": analysis_details,
            "simple_view": simple_view,
            "anomaly_samples": anomaly_details,
            "normal_samples": normal_details,
            "interpretation": f"使用DBSCAN异常检测算法分析了{total_points}个数据点，识别出{anomaly_count}个异常点（cluster_id=-1）和{normal_count}个正常点"
        }
    
    def _format_dbscan_result(self, algorithm_result: Dict[str, Any], original_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        格式化DBSCAN密度聚类异常检测结果
        
        Args:
            algorithm_result: DBSCAN算法结果
            original_data: 原始数据
            
        Returns:
            Dict[str, Any]: 格式化后的DBSCAN结果
        """
        success = algorithm_result.get('success', False)
        status = algorithm_result.get('status', 'unknown')
        
        if not success and status != 'success':
            return {
                "summary": f"DBSCAN密度聚类异常检测失败: {algorithm_result.get('message', '未知错误')}",
                "status": "failed",
                "data_points": len(original_data)
            }
        
        # 提取结果信息
        anomalies = algorithm_result.get('anomalies', [])
        normal_points = algorithm_result.get('normal_points', [])
        clusters = algorithm_result.get('clusters', [])
        
        total_points = len(original_data)
        anomaly_count = len(anomalies)
        normal_count = len(normal_points)
        cluster_count = len(clusters)
        
        # 计算异常比例
        anomaly_rate = (anomaly_count / total_points * 100) if total_points > 0 else 0
        
        # 构建主要描述
        main_description = f"DBSCAN密度聚类异常检测完成，在{total_points}个数据点中检测到{anomaly_count}个异常点（异常率{anomaly_rate:.1f}%），{normal_count}个正常点，形成{cluster_count}个聚类。"
        
        # 构建详细分析结果
        analysis_details = {
            "总数据点": total_points,
            "异常点数量": anomaly_count,
            "正常点数量": normal_count,
            "聚类数量": cluster_count,
            "异常率": f"{anomaly_rate:.1f}%",
            "算法类型": "DBSCAN密度聚类"
        }
        
        # 构建简化视图
        simple_view = {
            "异常检测": f"发现{anomaly_count}个异常点",
            "异常率": f"{anomaly_rate:.1f}%",
            "聚类结果": f"形成{cluster_count}个聚类",
            "状态": "检测完成"
        }
        
        # 构建异常点详情（显示前10个）
        anomaly_details = []
        if anomalies:
            for i, anomaly in enumerate(anomalies[:10]):
                anomaly_id = anomaly.get('id', f'异常点{i+1}')
                anomaly_details.append(anomaly_id)
        
        return {
            "summary": main_description,
            "anomaly_count": anomaly_count,
            "normal_count": normal_count,
            "cluster_count": cluster_count,
            "anomaly_rate": round(anomaly_rate, 1),
            "data_points": total_points,
            "analysis_details": analysis_details,
            "simple_view": simple_view,
            "anomaly_samples": anomaly_details,
            "interpretation": f"使用DBSCAN密度聚类算法分析了{total_points}个数据点，识别出{anomaly_count}个异常点和{cluster_count}个正常聚类"
        }
    
    def _format_iforest_result(self, algorithm_result: Dict[str, Any], original_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        格式化IForest孤立森林异常检测结果
        
        Args:
            algorithm_result: IForest算法结果
            original_data: 原始数据
            
        Returns:
            Dict[str, Any]: 格式化后的IForest结果
        """
        success = algorithm_result.get('success', False)
        status = algorithm_result.get('status', 'unknown')
        
        if not success and status != 'success':
            return {
                "summary": f"IForest孤立森林异常检测失败: {algorithm_result.get('message', '未知错误')}",
                "status": "failed",
                "data_points": len(original_data)
            }
        
        # 提取结果信息
        anomalies = algorithm_result.get('anomalies', [])
        normal_points = algorithm_result.get('normal_points', [])
        anomaly_scores = algorithm_result.get('anomaly_scores', [])
        
        total_points = len(original_data)
        anomaly_count = len(anomalies)
        normal_count = len(normal_points)
        
        # 计算异常比例
        anomaly_rate = (anomaly_count / total_points * 100) if total_points > 0 else 0
        
        # 计算异常分数统计
        avg_anomaly_score = 0
        max_anomaly_score = 0
        min_anomaly_score = 0
        
        if anomaly_scores:
            scores = [score.get('score', 0) for score in anomaly_scores if isinstance(score, dict)]
            if scores:
                avg_anomaly_score = sum(scores) / len(scores)
                max_anomaly_score = max(scores)
                min_anomaly_score = min(scores)
        
        # 构建主要描述
        main_description = f"IForest孤立森林异常检测完成，在{total_points}个数据点中检测到{anomaly_count}个异常点（异常率{anomaly_rate:.1f}%），{normal_count}个正常点。"
        
        if avg_anomaly_score > 0:
            main_description += f"平均异常分数为{avg_anomaly_score:.3f}。"
        
        # 构建详细分析结果
        analysis_details = {
            "总数据点": total_points,
            "异常点数量": anomaly_count,
            "正常点数量": normal_count,
            "异常率": f"{anomaly_rate:.1f}%",
            "算法类型": "IForest孤立森林"
        }
        
        if avg_anomaly_score > 0:
            analysis_details.update({
                "平均异常分数": f"{avg_anomaly_score:.3f}",
                "最高异常分数": f"{max_anomaly_score:.3f}",
                "最低异常分数": f"{min_anomaly_score:.3f}"
            })
        
        # 构建简化视图
        simple_view = {
            "异常检测": f"发现{anomaly_count}个异常点",
            "异常率": f"{anomaly_rate:.1f}%",
            "异常程度": "高" if avg_anomaly_score > 0.6 else "中" if avg_anomaly_score > 0.3 else "低",
            "状态": "检测完成"
        }
        
        # 构建异常点详情（显示前10个）
        anomaly_details = []
        if anomalies:
            for i, anomaly in enumerate(anomalies[:10]):
                anomaly_id = anomaly.get('id', f'异常点{i+1}')
                anomaly_score = anomaly.get('score', 0)
                anomaly_details.append({
                    "id": anomaly_id,
                    "score": round(anomaly_score, 3) if anomaly_score else 0
                })
        
        return {
            "summary": main_description,
            "anomaly_count": anomaly_count,
            "normal_count": normal_count,
            "anomaly_rate": round(anomaly_rate, 1),
            "avg_anomaly_score": round(avg_anomaly_score, 3),
            "data_points": total_points,
            "analysis_details": analysis_details,
            "simple_view": simple_view,
            "anomaly_samples": anomaly_details,
            "interpretation": f"使用IForest孤立森林算法分析了{total_points}个数据点，基于数据点的孤立程度识别出{anomaly_count}个异常点"
        }
    
    def _generate_clustering_insights(self, cluster_distribution: Dict[int, int], k_value: int) -> List[str]:
        """
        生成聚类分析的洞察
        
        Args:
            cluster_distribution: 聚类分布
            k_value: K值
            
        Returns:
            List[str]: 洞察列表
        """
        insights = []
        
        if not cluster_distribution:
            return insights
        
        # 最大和最小聚类大小
        max_size = max(cluster_distribution.values())
        min_size = min(cluster_distribution.values())
        
        # 聚类大小差异分析
        if max_size > min_size * 2:
            insights.append(f"聚类大小差异较大，最大聚类有 {max_size} 个成员，最小聚类有 {min_size} 个成员")
        else:
            insights.append(f"各聚类大小相对均衡，成员数量在 {min_size}-{max_size} 之间")
        
        # 聚类数量建议
        if k_value <= 2:
            insights.append("当前使用较少的聚类数，可能存在更细粒度的分组模式")
        elif k_value >= 5:
            insights.append("使用了较多的聚类数，建议检查是否存在过度分割")
        
        return insights