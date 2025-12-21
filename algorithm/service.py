"""
Algorithm Integration Service

Main service class that coordinates all algorithm integration components
and provides the primary interface for algorithm execution workflows.
"""

import logging
import asyncio
import uuid
from typing import Optional, Dict, Any
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
                yield AlgorithmResponse(
                    step=StreamingStep.ALGORITHM_IDENTIFICATION,
                    status="completed",
                    data={
                        "algorithm_type": algorithm_type.value,
                        "message": f"识别到算法类型: {algorithm_type.value}"
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
                parameters = await self._extract_parameters_with_retry(question, algorithm_type)
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
                            "sample_data": nl2sql_response.execution_result[:3] if nl2sql_response.execution_result else [],
                            "message": f"数据检索完成，获取到 {len(nl2sql_response.execution_result)} 行数据"
                        },
                        timestamp=datetime.utcnow()
                    )
                    
                    # 步骤4: 算法执行
                    if self.algorithm_executor and self.data_processor:
                        logger.info("开始算法执行")
                        yield AlgorithmResponse(
                            step=StreamingStep.ALGORITHM_EXECUTION,
                            status="processing",
                            data={"message": f"正在执行{algorithm_type.value}算法..."},
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
                                # 同步任务结果
                                yield AlgorithmResponse(
                                    step=StreamingStep.ALGORITHM_EXECUTION,
                                    status="completed",
                                    data={
                                        "algorithm_result": execution_response.result,
                                        "message": "算法执行完成"
                                    },
                                    timestamp=datetime.utcnow()
                                )
                                
                                # 返回最终完成状态
                                yield AlgorithmResponse(
                                    step=StreamingStep.COMPLETED,
                                    status="completed",
                                    data={
                                        "algorithm_type": algorithm_type.value,
                                        "algorithm_result": execution_response.result,
                                        "sql_statement": nl2sql_response.sql_statement,
                                        "normalized_query": parameters.normalized_query,
                                        "message": "所有步骤完成"
                                    },
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
        algorithm_type: AlgorithmType
    ) -> AlgorithmParameters:
        """
        提取算法参数
        
        Args:
            question: 用户查询
            algorithm_type: 算法类型
            
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
            question, algorithm_type, database_schema
        )
    
    def _validate_request_parameters(self, question: str, window_id: str, session_id: str):
        """验证请求参数"""
        if not question or not question.strip():
            raise ParameterValidationError("查询问题不能为空", field_name="question")
        
        if len(question) > 1000:
            raise ParameterValidationError("查询问题长度不能超过1000字符", field_name="question")
        
        if not window_id:
            raise ParameterValidationError("窗口ID不能为空", field_name="window_id")
        
        if not session_id:
            raise ParameterValidationError("会话ID不能为空", field_name="session_id")
    
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
        algorithm_type: AlgorithmType
    ) -> AlgorithmParameters:
        """带重试的参数提取"""
        return await self.retry_handler.retry_async(
            self.extract_parameters,
            question,
            algorithm_type,
            config=self.retry_configs['parameter_extraction'],
            retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
            context={'operation': 'parameter_extraction', 'algorithm_type': algorithm_type.value}
        )
    
    async def _query_nl2sql_with_retry(self, request) -> Any:
        """带重试的NL2SQL查询"""
        return await self.retry_handler.retry_async(
            self.nl2sql_client.query,
            request,
            config=self.retry_configs['nl2sql'],
            retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
            context={'operation': 'nl2sql_query', 'question': request.question[:100]}
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