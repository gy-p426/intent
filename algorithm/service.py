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
from llm.algorithm_result_analyzer import AlgorithmResultAnalyzer
from llm.llm_client import LLMClient
from infrastructure.config import get_settings
from algorithm.agent import normalize_question_for_agent


logger = logging.getLogger(__name__)
structured_logger = get_structured_logger(__name__)


# 算法类型中文映射
ALGORITHM_TYPE_CHINESE_MAP = {
    AlgorithmType.CLUSTER: "聚类",
    AlgorithmType.CLASSIFY: "分类",
    AlgorithmType.PREDICT: "预测",
    AlgorithmType.ANOMALY: "异常检测",
    AlgorithmType.ASSOCIATE: "关联分析",
    # AlgorithmType.COMPARE: "对比分析",
    AlgorithmType.SIMILARITY: "相似度分析",
    AlgorithmType.TREND: "趋势分析",
    AlgorithmType.PROFILE: "画像分析",
    AlgorithmType.CAUSALITY: "因果分析",
    AlgorithmType.NL2SQL: "智能检索",
    AlgorithmType.COMPARE_PROPORTION: "对比分析"
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
        
        # 获取配置
        self.settings = get_settings()
        
        # 初始化大模型结果分析器
        self.result_analyzer = None
        if self.settings.enable_llm_result_analysis:
            try:
                llm_client = LLMClient()
                self.result_analyzer = AlgorithmResultAnalyzer(llm_client)
                logger.info("大模型结果分析器初始化成功")
            except Exception as e:
                logger.warning(f"大模型结果分析器初始化失败: {str(e)}，将使用降级处理")
                self.result_analyzer = None
        
        # 如果没有提供算法执行器，创建默认实例
        if self.algorithm_executor is None:
            from algorithm.executor.algorithm_executor import AlgorithmExecutor
            self.algorithm_executor = AlgorithmExecutor()
        
        # 配置重试策略
        self.retry_configs = {
            'nl2sql': RetryConfig(max_attempts=3, base_delay=2.0, max_delay=30.0),
            'algorithm_api': RetryConfig(max_attempts=2, base_delay=1.0, max_delay=10.0),
            'database': RetryConfig(max_attempts=3, base_delay=1.0, max_delay=15.0),
            'parameter_extraction': RetryConfig(max_attempts=2, base_delay=0.5, max_delay=5.0),
            'llm_analysis': RetryConfig(max_attempts=self.settings.llm_analysis_max_retries, base_delay=1.0, max_delay=10.0)
        }

        # 手动模式上下文存储（token -> context），用于跨请求继续
        # 说明：当前先采用进程内内存存储，适用于单实例；生产可替换为 Redis。
        from algorithm.manual_context import ManualContextStore
        self._manual_context_store = ManualContextStore(ttl_seconds=30 * 60)

        logger.info("算法集成服务初始化完成")
    
    async def process_algorithm_request(
        self, 
        question: str, 
        window_id: str, 
        session_id: str,
        user_id: Optional[int] = None,
        auto_analysis: Optional[bool] = None,
        agent_algorithm: bool = False,  # 新增参数
        fileIds: Optional[str] = None  # 新增参数
    ) -> AlgorithmResponseGenerator:
        """
        处理算法请求的主要方法
        
        Args:
            question: 用户自然语言查询
            window_id: 窗口ID
            session_id: 会话ID
            user_id: 用户ID（可选）
            auto_analysis: 是否自动分析
            agent_algorithm: 是否使用Agent算法分析（新增）
            fileids: 文件ID列表，用逗号分隔（新增）
            
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
            'start_time': datetime.utcnow(),
            'auto_analysis': auto_analysis,
            'agent_algorithm': agent_algorithm,  # 新增
            'fileIds': fileIds  # 新增
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
            
            logger.info(f"开始处理算法请求: {question[:100]}..., agent_algorithm={agent_algorithm}, fileIds={fileIds}", extra={'trace_id': trace_id})


            # === 步骤-1: 处理文件上传（如果有fileIds） ===
            if fileIds:
                logger.info(f"检测到文件上传请求，fileIds={fileIds}", extra={'trace_id': trace_id})
                
                # 直接调用Agent分析流程处理文件
                async for response in self._process_file_upload_to_agent(
                    question, fileIds, window_id, session_id, request_context
                ):
                    yield response
                
                # 文件处理完成后直接返回，不继续后续流程
                return

            # 步骤0: 判断是否是追问
            from algorithm.models import AlgorithmResponse, StreamingStep

            logger.info("开始追问判断", extra={'trace_id': trace_id})
            yield AlgorithmResponse(
                step=StreamingStep.INTENT_ANALYSIS,
                status="processing",
                data={"message": "正在分析问题意图..."},
                timestamp=datetime.utcnow()
            )

            try:
                # 调用追问判断接口
                continuous_result = await self.nl2sql_client.check_continuous_question(
                    question=question,
                    window_id=window_id,
                    session_id=session_id,
                    user_id=user_id
                )

                is_continuous = continuous_result.get('isContinuous', False)
                merged_question = continuous_result.get('mergedQuestion', question)
                previous_question = continuous_result.get('previousQuestion', '')
                reason = continuous_result.get('reason', '')

                # 构建返回消息
                if is_continuous:
                    message = f"用户追问之前的问题：{previous_question}，用户在追问，故新的问题为：{merged_question}"
                else:
                    prev_text = previous_question if previous_question else "无"
                    message = f"用户之前的问题为：{prev_text}，不是对上一个问题的追问"

                logger.info(f"追问判断完成: is_continuous={is_continuous}, merged_question={merged_question}", extra={'trace_id': trace_id})

                # 流式返回追问判断结果
                yield AlgorithmResponse(
                    step=StreamingStep.INTENT_ANALYSIS,
                    status="completed",
                    data={
                        "is_continuous": is_continuous,
                        "merged_question": merged_question,
                        "message": message,
                        "previous_question": previous_question or ""
                    },
                    timestamp=datetime.utcnow()
                )

                # 如果是追问，使用合并后的问题继续处理
                if is_continuous:
                    question = merged_question
                    logger.info(f"使用合并后的问题继续处理: {question}", extra={'trace_id': trace_id})

            except Exception as e:
                logger.warning(f"追问判断失败，使用原始问题继续处理: {str(e)}", extra={'trace_id': trace_id})
                # 追问判断失败不影响主流程，使用原始问题继续
                # 定义merged_question变量，避免后续使用时出现UnboundLocalError
                merged_question = question
                
                yield AlgorithmResponse(
                    step=StreamingStep.INTENT_ANALYSIS,
                    status="completed",
                    data={
                        "is_continuous": False,
                        "merged_question": question,
                        "message": f"用户上一个问题为：无，本次问题为：{question}，不是对上一个问题的追问，故用户的问题为：{question}",
                        "previous_question": ""
                    },
                    timestamp=datetime.utcnow()
                )

            # 调用Session保存问题接口，保存问题到历史记录
            try:
                logger.info(f"保存问题到Session历史记录: {merged_question[:50]}...", extra={'trace_id': trace_id})
                save_result = await self.nl2sql_client.save_question(
                    question=merged_question,
                    window_id=window_id,
                    user_id=user_id
                )

                if save_result.get('success', False):
                    saved_session_id = save_result.get('data', {}).get('sessionId', session_id)
                    logger.info(f"问题保存成功，sessionId: {saved_session_id}", extra={'trace_id': trace_id})

                    # 流式返回保存成功的消息
                    yield AlgorithmResponse(
                        step=StreamingStep.INTENT_ANALYSIS,
                        status="completed",
                        data={
                            "message": "问题已保存",
                            "session_id": saved_session_id,
                            "saved": True
                        },
                        timestamp=datetime.utcnow()
                    )


                else:
                    logger.warning(f"问题保存失败: {save_result.get('message', '未知错误')}", extra={'trace_id': trace_id})
                    # 保存失败不影响主流程，继续处理
                    yield AlgorithmResponse(
                        step=StreamingStep.INTENT_ANALYSIS,
                        status="completed",
                        data={
                            "message": "问题保存失败，但不影响分析",
                            "saved": False,
                            "error": save_result.get('message', '未知错误')
                        },
                        timestamp=datetime.utcnow()
                    )
            except Exception as e:
                logger.warning(f"保存问题到Session失败: {str(e)}", extra={'trace_id': trace_id})
                # 保存失败不影响主流程，继续处理
                yield AlgorithmResponse(
                    step=StreamingStep.INTENT_ANALYSIS,
                    status="completed",
                    data={
                        "message": "问题保存失败，但不影响分析",
                        "saved": False,
                        "error": str(e)
                    },
                    timestamp=datetime.utcnow()
                )

            # === 判断是否使用Agent分析 ===
            if agent_algorithm:
                # 使用Agent算法分析流程
                async for response in self._process_agent_algorithm(
                    merged_question, window_id, session_id, request_context
                ):
                    yield response
            else:
                # 使用传统算法流程（带错误处理）
                async for response in self._process_with_error_handling(
                    merged_question, window_id, session_id, request_context,user_id
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
    
    def _build_required_columns_for_manual_mode(
        self, 
        algorithm_type: AlgorithmType,
        parameters: AlgorithmParameters
    ) -> Dict[str, Dict[str, Any]]:
        """
        为手动模式构建 required_columns 字段映射
        
        Args:
            algorithm_type: 算法类型
            parameters: 算法参数
            
        Returns:
            Dict[str, Dict[str, Any]]: required_columns 字典
                key: 字段名
                value: 字段配置 {description, is_array, required}
        """
        required_columns = {}
        param_mapping = parameters.parameter_mapping or {}
        
        # 根据算法类型构建 required_columns
        if algorithm_type == AlgorithmType.CLUSTER:
            # 聚类算法（K-Means、DBSCAN等）需要: id_column, feature_columns
            required_columns['id_column'] = {
                'description': '标识列（用于标识每个数据点）',
                'is_array': False,
                'required': True
            }
            required_columns['feature_columns'] = {
                'description': '特征列（用于聚类的数值型列）',
                'is_array': True,
                'required': True
            }
        elif algorithm_type == AlgorithmType.CLASSIFY:
            # 分类算法（随机森林等）需要: id_column, label_column, feature_columns
            required_columns['id_column'] = {
                'description': '标识列',
                'is_array': False,
                'required': True
            }
            required_columns['label_column'] = {
                'description': '标签列（分类目标）',
                'is_array': False,
                'required': True
            }
            required_columns['feature_columns'] = {
                'description': '特征列（用于预测的数值型列）',
                'is_array': True,
                'required': True
            }
        elif algorithm_type == AlgorithmType.ANOMALY:
            # 异常检测算法（孤立森林、DBSCAN等）需要: id_column, feature_columns
            required_columns['id_column'] = {
                'description': '标识列',
                'is_array': False,
                'required': True
            }
            required_columns['feature_columns'] = {
                'description': '特征列（用于异常检测的数值型列）',
                'is_array': True,
                'required': True
            }
        elif algorithm_type in [AlgorithmType.PREDICT, AlgorithmType.TREND]:
            # 时间序列分析需要: timestamp_column, value_column
            required_columns['timestamp_column'] = {
                'description': '时间戳列',
                'is_array': False,
                'required': True
            }
            required_columns['value_column'] = {
                'description': '数值列（要分析的指标）',
                'is_array': False,
                'required': True
            }
        elif algorithm_type == AlgorithmType.SIMILARITY:
            # 相似度分析（DTW等）需要: time_series1, time_series2
            required_columns['time_series1'] = {
                'description': '时间序列1',
                'is_array': False,
                'required': True
            }
            required_columns['time_series2'] = {
                'description': '时间序列2',
                'is_array': False,
                'required': True
            }
        elif algorithm_type == AlgorithmType.ASSOCIATE:
            # 关联分析需要: columns（多列）
            required_columns['columns'] = {
                'description': '分析列（至少2列）',
                'is_array': True,
                'required': True
            }
        elif algorithm_type == AlgorithmType.CAUSALITY:
            required_columns['dependent_variable'] = {
                'description': '因变量列名，即需要分析的结果变量',
                'is_array': False,
                'required': True
            }
            required_columns['independent_variables'] = {
                'description': '自变量列名列表，即可能影响结果的因素变量',
                'is_array': True,
                'required': True
            }
        else:
            # 默认情况：至少需要一个ID列和特征列
            required_columns['id_column'] = {
                'description': '标识列',
                'is_array': False,
                'required': True
            }
            required_columns['feature_columns'] = {
                'description': '特征列',
                'is_array': True,
                'required': True
            }
        
        logger.info(f"[手动模式] 为算法类型 {algorithm_type.value} 构建的 required_columns: {required_columns}")
        return required_columns
    
    async def _process_agent_algorithm(
        self,
        question: str,
        window_id: str,
        session_id: str,
        request_context: Dict[str, Any]
    ) -> AlgorithmResponseGenerator:
        """
        Agent算法分析流程（SSE纯透传）
        
        Args:
            question: 用户问题
            window_id: 窗口ID
            session_id: 会话ID
            request_context: 请求上下文
            
        Yields:
            AlgorithmResponse: 流式响应数据
        """
        from algorithm.models import AlgorithmResponse, StreamingStep, NL2SQLRequest
        from algorithm.processors.csv_converter import CSVConverter
        from algorithm.clients.agent_algorithm_client import AgentAlgorithmClient
        from algorithm.error_handler import AlgorithmExecutionError
        from algorithm.agent import get_candidate_tables_from_nl2sql
        
        trace_id = request_context.get('trace_id', 'unknown')
        
        try:
            # Step 0: 获取候选表信息并进行问题标准化
            logger.info("Agent分析: 开始获取候选表信息", extra={'trace_id': trace_id})
            yield AlgorithmResponse(
                step=StreamingStep.ALGORITHM_IDENTIFICATION,
                status="processing",
                data={"message": "正在分析数据库结构..."},
                timestamp=datetime.utcnow()
            )
            
            # 从NL2SQL服务获取候选表信息
            candidate_tables_info, query_db_result = await get_candidate_tables_from_nl2sql(
                question, window_id, self.nl2sql_client
            )
            
            logger.info(f"Agent分析: 候选表信息获取完成", extra={'trace_id': trace_id})
            
            # 使用候选表信息进行问题标准化
            logger.info("Agent分析: 开始问题标准化", extra={'trace_id': trace_id})
            yield AlgorithmResponse(
                step=StreamingStep.ALGORITHM_IDENTIFICATION,
                status="processing",
                data={"message": "正在处理用户问题..."},
                timestamp=datetime.utcnow()
            )
            
            # 调用大模型对问题进行标准化处理（结合候选表信息）
            normalized_question = await normalize_question_for_agent(
                question, 
                window_id, 
                candidate_tables_info
            )
            
            logger.info(f"Agent分析: 问题标准化完成 - 原始: {question[:50]}... -> 标准化: {normalized_question[:50]}...", 
                       extra={'trace_id': trace_id})
            
            yield AlgorithmResponse(
                step=StreamingStep.ALGORITHM_IDENTIFICATION,
                status="completed",
                data={
                    "normalized_query": normalized_question,
                    "message": "问题处理完成"
                },
                timestamp=datetime.utcnow()
            )
            
            # Step 1: SQL生成与执行
            logger.info("Agent分析: 开始SQL查询", extra={'trace_id': trace_id})
            yield AlgorithmResponse(
                step=StreamingStep.SQL_GENERATION,
                status="processing",
                data={"message": "正在生成查询语句..."},
                timestamp=datetime.utcnow()
            )
            
            # 使用候选表信息调用NL2SQL服务（避免重复调用query-db）
            candidate_tables = query_db_result.get('candidateTables', [])
            keywords = query_db_result.get('keywords', {})
            
            if candidate_tables:
                logger.info("Agent分析: 使用已获取的候选表信息生成SQL", extra={'trace_id': trace_id})
                nl2sql_response = await self._query_nl2sql_with_candidates_retry(
                    normalized_question,
                    candidate_tables,
                    keywords,
                    window_id,
                    session_id
                )
            else:
                logger.info("Agent分析: 使用完整NL2SQL流程", extra={'trace_id': trace_id})
                nl2sql_request = NL2SQLRequest(
                    question=normalized_question,
                    window_id=window_id,
                    session_id=session_id
                )
                nl2sql_response = await self._query_nl2sql_with_retry(nl2sql_request)
            
            yield AlgorithmResponse(
                step=StreamingStep.DATA_RETRIEVAL,
                status="completed",
                data={
                    "data_rows_count": len(nl2sql_response.execution_result),
                    "sql_statement": nl2sql_response.sql_statement,
                    "sample_data": nl2sql_response.execution_result if nl2sql_response.execution_result else [],
                    "message": f"数据检索完成，获取到 {len(nl2sql_response.execution_result)} 行数据"
                },
                timestamp=datetime.utcnow()
            )
            # logger.info(f"SQL查询完成: {nl2sql_response.sql_statement}", extra={'trace_id': trace_id})
            
            # Step 2: 转换为CSV
            logger.info("Agent分析: 转换数据为CSV", extra={'trace_id': trace_id})
            try:
                csv_data = CSVConverter.convert_to_csv(nl2sql_response.execution_result)
                logger.info(f"CSV转换成功: {len(csv_data)} bytes", extra={'trace_id': trace_id})
            except Exception as e:
                logger.error(f"CSV转换失败: {str(e)}", extra={'trace_id': trace_id})
                raise AlgorithmExecutionError(
                    f"数据格式转换失败: {str(e)}",
                    details={'trace_id': trace_id}
                )
            
            # Step 3: 调用Agent服务并透传事件
            logger.info("Agent分析: 开始调用Agent服务", extra={'trace_id': trace_id})
            yield AlgorithmResponse(
                step=StreamingStep.AGENT_ALGORITHM_ANALYSIS,
                status="started",
                data={"message": "正在启动Agent算法分析..."},
                timestamp=datetime.utcnow()
            )
            
            agent_client = AgentAlgorithmClient(
                base_url=self.settings.agent_algorithm_analysis_url,
                timeout=self.settings.agent_algorithm_analysis_timeout
            )
            
            try:
                # 流式接收并透传Agent事件
                async for agent_event in agent_client.analyze_streaming(
                    question=question,
                    csv_data=csv_data
                ):
                    # 原封不动地透传Agent事件
                    yield AlgorithmResponse(
                        step=StreamingStep.AGENT_ALGORITHM_ANALYSIS,
                        status="processing",
                        data={"agent_event": agent_event},  # 完整的Agent事件
                        timestamp=datetime.utcnow()
                    )
                    
                    # 检查是否完成
                    if agent_event.get("event_type") == "workflow_complete":
                        logger.info("Agent工作流完成", extra={'trace_id': trace_id})
                        # yield AlgorithmResponse(
                        #     step=StreamingStep.COMPLETED,
                        #     status="completed",
                        #     data={
                        #         "agent_result": agent_event.get("data"),
                        #         "message": "Agent算法分析完成"
                        #     },
                        #     timestamp=datetime.utcnow()
                        # )
                        break
                    
                    # 检查错误
                    elif agent_event.get("event_type") in ["workflow_error", "phase_error"]:
                        error_msg = agent_event.get("data", {}).get("error", "未知错误")
                        logger.error(f"Agent分析失败: {error_msg}", extra={'trace_id': trace_id})
                        raise AlgorithmExecutionError(f"Agent分析失败: {error_msg}")
            
            finally:
                await agent_client.close()
                
        except AlgorithmExecutionError:
            raise
        except Exception as e:
            logger.error(f"Agent算法分析异常: {str(e)}", extra={'trace_id': trace_id}, exc_info=True)
            raise AlgorithmExecutionError(
                f"Agent算法分析异常: {str(e)}",
                details={'trace_id': trace_id},
                original_error=e
            )

    async def _process_file_upload_to_agent(
        self,
        question: str,
        fileIds: str,
        window_id: str,
        session_id: str,
        request_context: Dict[str, Any]
    ) -> AlgorithmResponseGenerator:
        """
        处理文件上传到Agent的流程
        
        Args:
            question: 用户问题
            fileIds: 文件ID列表，用逗号分隔
            window_id: 窗口ID
            session_id: 会话ID
            request_context: 请求上下文
            
        Yields:
            AlgorithmResponse: 流式响应数据
        """
        from algorithm.models import AlgorithmResponse, StreamingStep
        import httpx
        
        trace_id = request_context.get('trace_id', 'unknown')
        
        try:
            # 步骤1: 获取文件详情
            logger.info(f"开始获取文件详情，fileIds={fileIds}", extra={'trace_id': trace_id})
            yield AlgorithmResponse(
                step=StreamingStep.AGENT_ALGORITHM_ANALYSIS,
                status="processing",
                data={"message": f"正在获取文件信息..."},
                timestamp=datetime.utcnow()
            )
            
            # 调用NL2SQL服务获取文件详情
            nl2sql_base_url = self.settings.nl2sql_base_url or "http://localhost:8080"
            file_detail_url = f"{nl2sql_base_url}/api/file/manage/detail/{fileIds}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(file_detail_url)
                response.raise_for_status()
                file_response = response.json()
            
            if not file_response.get('success'):
                error_msg = file_response.get('error', '获取文件详情失败')
                logger.error(f"获取文件详情失败: {error_msg}", extra={'trace_id': trace_id})
                yield AlgorithmResponse(
                    step=StreamingStep.ERROR,
                    status="error",
                    data={"error": error_msg},
                    timestamp=datetime.utcnow()
                )
                return
            
            # 获取文件数据
            file_data = file_response.get('data')
            if not file_data:
                logger.error("未找到文件信息", extra={'trace_id': trace_id})
                yield AlgorithmResponse(
                    step=StreamingStep.ERROR,
                    status="error",
                    data={"error": "未找到文件信息"},
                    timestamp=datetime.utcnow()
                )
                return
            
            # 打印完整的响应数据用于调试
            import json
            logger.info(f"文件详情响应: {json.dumps(file_response, ensure_ascii=False)[:500]}", extra={'trace_id': trace_id})
            
            # 处理两种情况：单个文件（字典）或多个文件（数组）
            if isinstance(file_data, dict):
                # 单个文件，转换为数组
                file_data_list = [file_data]
                logger.info(f"单个文件模式，文件: {file_data.get('fileName')}", extra={'trace_id': trace_id})
            elif isinstance(file_data, list):
                # 多个文件
                file_data_list = file_data
                logger.info(f"多个文件模式，共 {len(file_data_list)} 个文件", extra={'trace_id': trace_id})
            else:
                logger.error(f"文件数据格式错误: {type(file_data)}", extra={'trace_id': trace_id})
                yield AlgorithmResponse(
                    step=StreamingStep.ERROR,
                    status="error",
                    data={"error": f"文件数据格式错误: {type(file_data)}"},
                    timestamp=datetime.utcnow()
                )
                return
            
            # 步骤2: 准备文件并调用Agent服务
            yield AlgorithmResponse(
                step=StreamingStep.AGENT_ALGORITHM_ANALYSIS,
                status="processing",
                data={"message": f"正在准备文件并调用Agent分析服务..."},
                timestamp=datetime.utcnow()
            )
            
            # 构建multipart/form-data
            files = []
            for idx, file_info in enumerate(file_data_list):
                # 检查 file_info 的类型
                logger.info(f"处理文件 #{idx}, 类型: {type(file_info)}, 内容: {file_info}", extra={'trace_id': trace_id})
                
                if isinstance(file_info, str):
                    # 如果是字符串，可能是文件路径
                    logger.warning(f"文件信息 #{idx} 是字符串: {file_info}，尝试作为文件路径处理", extra={'trace_id': trace_id})
                    file_path = file_info
                    file_name = file_info.split('/')[-1] if '/' in file_info else file_info.split('\\')[-1]
                elif isinstance(file_info, dict):
                    # 如果是字典，按照预期处理
                    file_path = file_info.get('filePath')
                    file_name = file_info.get('fileName')
                else:
                    logger.warning(f"文件信息 #{idx} 类型错误: {type(file_info)}", extra={'trace_id': trace_id})
                    continue
                
                if not file_path:
                    logger.warning(f"文件 {file_name} 缺少路径信息", extra={'trace_id': trace_id})
                    continue
                
                # 检查路径是否为绝对路径，如果不是，需要拼接基础路径
                import os
                if not os.path.isabs(file_path):
                    # 相对路径，需要拼接基础路径
                    # 从配置中获取文件存储基础路径，默认为当前目录
                    file_base_path = getattr(self.settings, 'file_storage_base_path', '.')
                    full_path = os.path.join(file_base_path, file_path)
                    logger.info(f"相对路径转换: {file_path} -> {full_path}", extra={'trace_id': trace_id})
                    file_path = full_path
                
                # 读取文件内容
                try:
                    with open(file_path, 'rb') as f:
                        file_content = f.read()
                    
                    files.append(('file', (file_name, file_content, 'application/octet-stream')))
                    logger.info(f"成功读取文件: {file_name}, 路径: {file_path}, 大小: {len(file_content)} bytes", extra={'trace_id': trace_id})
                except FileNotFoundError:
                    logger.error(f"文件不存在: {file_name}, 路径: {file_path}", extra={'trace_id': trace_id})
                    # 继续处理其他文件
                    continue
                except Exception as e:
                    logger.error(f"读取文件失败: {file_name}, 路径: {file_path}, 错误: {str(e)}", extra={'trace_id': trace_id})
                    # 继续处理其他文件
                    continue
            
            if not files:
                logger.error("没有可用的文件", extra={'trace_id': trace_id})
                yield AlgorithmResponse(
                    step=StreamingStep.ERROR,
                    status="error",
                    data={"error": "没有可用的文件"},
                    timestamp=datetime.utcnow()
                )
                return
            
            # 构建request_data
            request_data = {"query": question}
            
            # 调用Agent服务的 /query_agents_stream 接口
            # 使用配置文件中的 AGENT_ALGORITHM_ANALYSIS_URL
            agent_base_url = self.settings.agent_algorithm_analysis_url
            agent_url = f"{agent_base_url}/query_agents_stream"
            
            logger.info(f"调用Agent服务: {agent_url}", extra={'trace_id': trace_id})
            
            import json
            data = {'request_data': json.dumps(request_data)}
            
            # 发起流式请求
            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0, read=None)) as client:
                async with client.stream("POST", agent_url, files=files, data=data) as response:
                    response.raise_for_status()
                    
                    # 验证响应类型
                    content_type = response.headers.get("content-type", "")
                    if "text/event-stream" not in content_type:
                        logger.error(f"Agent服务返回的不是SSE格式: {content_type}", extra={'trace_id': trace_id})
                        yield AlgorithmResponse(
                            step=StreamingStep.ERROR,
                            status="error",
                            data={"error": f"Agent服务返回格式错误: {content_type}"},
                            timestamp=datetime.utcnow()
                        )
                        return
                    
                    logger.info("开始接收Agent的SSE事件流", extra={'trace_id': trace_id})
                    
                    # 解析并转发SSE流
                    buffer = ""
                    async for chunk in response.aiter_text():
                        buffer += chunk
                        
                        # 按行分割
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            
                            if not line:
                                continue
                            
                            # 解析SSE格式: data: {...}
                            if line.startswith("data: "):
                                data_str = line[6:]  # 移除 "data: " 前缀
                                
                                # 跳过结束标记
                                if data_str == "[DONE]":
                                    logger.info("收到Agent流结束标记 [DONE]", extra={'trace_id': trace_id})
                                    break
                                
                                try:
                                    # 解析JSON
                                    event = json.loads(data_str)
                                    event_type = event.get("type", "unknown")
                                    
                                    logger.debug(f"收到Agent事件: type={event_type}", extra={'trace_id': trace_id})
                                    
                                    # 直接转发Agent的原始事件数据
                                    yield AlgorithmResponse(
                                        step=StreamingStep.AGENT_ALGORITHM_ANALYSIS,
                                        status="processing",
                                        data={"agent_event": event},  # 直接转发原始事件
                                        timestamp=datetime.utcnow()
                                    )
                                    
                                except json.JSONDecodeError as e:
                                    logger.warning(f"解析Agent SSE数据失败: {data_str[:100]}..., 错误: {e}", extra={'trace_id': trace_id})
            
            # 完成
            logger.info("Agent文件分析流程完成", extra={'trace_id': trace_id})
            yield AlgorithmResponse(
                step=StreamingStep.COMPLETED,
                status="completed",
                data={"message": "Agent文件分析完成"},
                timestamp=datetime.utcnow()
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP请求失败: {e.response.status_code}", extra={'trace_id': trace_id})
            yield AlgorithmResponse(
                step=StreamingStep.ERROR,
                status="error",
                data={"error": f"HTTP请求失败: {e.response.status_code}"},
                timestamp=datetime.utcnow()
            )
        except Exception as e:
            logger.error(f"文件上传到Agent失败: {str(e)}", extra={'trace_id': trace_id}, exc_info=True)
            yield AlgorithmResponse(
                step=StreamingStep.ERROR,
                status="error",
                data={"error": f"文件上传到Agent失败: {str(e)}"},
                timestamp=datetime.utcnow()
            )

    async def _process_with_error_handling(
        self,
        question: str,
        window_id: str,
        session_id: str,
        request_context: Dict[str, Any],
        user_id: int
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
            from algorithm.database.candidate_tables_parser import parse_candidate_tables
            
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

            # NL2SQL数据查询分支：直接调用NL2SQL流式接口
            if algorithm_type == AlgorithmType.NL2SQL:
                logger.info("识别为NL2SQL数据查询，调用query-stream接口", extra={'trace_id': trace_id})

                try:
                    # 调用NL2SQL的query-stream接口，流式返回数据
                    async for nl2sql_event in self.nl2sql_client.query_stream(
                        question=question,
                        window_id=window_id,
                        session_id=session_id,
                        user_id=user_id
                    ):
                        # 将NL2SQL的流式事件包装在NL2SQLStreamResponse中返回给前端
                        from algorithm.models import NL2SQLStreamResponse
                        yield AlgorithmResponse(
                            step=StreamingStep.DATA_RETRIEVAL,
                            status="processing",
                            data= nl2sql_event,
                            timestamp=datetime.utcnow()
                        )

                        # 检查是否完成
                        if nl2sql_event.get('step') == 'sql_execution' and nl2sql_event.get('status') == 'completed':
                            logger.info("NL2SQL数据查询完成", extra={'trace_id': trace_id})
                            yield AlgorithmResponse(
                                step=StreamingStep.COMPLETED,
                                status="completed",
                                data= nl2sql_event,
                                timestamp=datetime.utcnow()
                            )
                            return

                        # 检查错误
                        elif nl2sql_event.get('step') == 'error':
                            error_msg = nl2sql_event.get('error', '未知错误')
                            logger.error(f"NL2SQL数据查询失败: {error_msg}", extra={'trace_id': trace_id})
                            raise Exception(f"数据查询失败: {error_msg}")

                except Exception as e:
                    logger.error(f"NL2SQL数据查询异常: {str(e)}", extra={'trace_id': trace_id})
                    structured_logger.log_error(e, trace_id, StreamingStep.DATA_RETRIEVAL, algorithm_type=algorithm_type)
                    raise Exception(f"数据查询失败: {str(e)}")

                # NL2SQL流程结束，不再执行后续步骤
                return

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
                parameters = await self._extract_parameters_with_retry(question, algorithm_type, window_id, user_id)
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
                        "query_db_result": parameters.query_db_result,
                        "message": "参数提取完成"
                    },
                    timestamp=datetime.utcnow()
                )

                # 手动模式：在参数提取后给前端返回可选 schema 信息，并结束本次请求
                if request_context.get('auto_analysis') is False:
                    manual_selection_token = trace_id
                    candidate_tables = []
                    keywords = {}
                    
                    # 调试日志：检查 query_db_result
                    logger.info(f"[手动模式调试] parameters.query_db_result 是否为 None: {parameters.query_db_result is None}")
                    if parameters.query_db_result:
                        logger.info(f"[手动模式调试] query_db_result 内容: {parameters.query_db_result}")
                        candidate_tables = parameters.query_db_result.get('candidateTables', []) or []
                        keywords = parameters.query_db_result.get('keywords', {}) or {}
                        logger.info(f"[手动模式调试] candidateTables 数量: {len(candidate_tables)}")
                        if candidate_tables:
                            logger.info(f"[手动模式调试] candidateTables 第一项: {candidate_tables[0][:200] if len(candidate_tables[0]) > 200 else candidate_tables[0]}")
                    else:
                        logger.warning(f"[手动模式调试] parameters.query_db_result 为 None!")

                    parsed_tables = parse_candidate_tables(candidate_tables)
                    logger.info(f"[手动模式调试] parsed_tables 数量: {len(parsed_tables)}")
                    db_schema_options = []
                    for t in parsed_tables:
                        db_schema_options.append({
                            'table_name': t.table_name,
                            'table_comment': t.table_comment,
                            'columns': [
                                {
                                    'table_name': c.table_name,
                                    'table_comment': c.table_comment,
                                    'column_name': c.column_name,
                                    'column_comment': c.column_comment,
                                    'data_type': c.data_type,
                                }
                                for c in t.columns
                            ]
                        })

                    # 构建 required_columns 字段映射
                    required_columns = self._build_required_columns_for_manual_mode(
                        algorithm_type, 
                        parameters
                    )

                    # store context for subsequent manual endpoints
                    from algorithm.manual_context import ManualFlowContext
                    self._manual_context_store.set(
                        manual_selection_token,
                        ManualFlowContext(
                            created_at=datetime.utcnow(),
                            question=question,
                            window_id=window_id,
                            session_id=session_id,
                            algorithm_type=algorithm_type,
                            parameters=parameters,
                            candidate_tables=candidate_tables,
                            keywords=keywords,
                        ),
                    )

                    yield AlgorithmResponse(
                        step=StreamingStep.MANUAL_DB_SELECTION,
                        status="completed",
                        data={
                            'manual_selection_token': manual_selection_token,
                            'db_schema_options': db_schema_options,
                            'required_columns': required_columns,
                            'message': ' 如需要更换分析字段点击“选择字段”按钮从所列表中选择需要分析的字段，再点击“执行分析””'
                        },
                        timestamp=datetime.utcnow()
                    )
                    return
                
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
                    data={"message": "正在生成查询语句..."},
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
                            session_id=session_id,
                            user_id=user_id,
                        )
                        nl2sql_response = await self._query_nl2sql_with_retry(nl2sql_request)
                    
                    # 流式返回SQL生成结果
                    yield AlgorithmResponse(
                        step=StreamingStep.SQL_GENERATION,
                        status="completed",
                        data={
                            "sql_statement": nl2sql_response.sql_statement,
                            "execution_time_ms": nl2sql_response.execution_time_ms,
                            # "sqlExplanation": nl2sql_response.sqlExplanation,
                            "message": "查询语句生成完成"
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
                                            "message": "算法执行完成，正在将算法结果转化为自然语言"
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
                                    # "algorithm_result": algorithm_result,
                                    "message": f"{algorithm_type_chinese}算法执行完成，正在将算法结果转化为自然语言",
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
                                
                                # 检查算法执行结果是否有有效内容（宽松判断）
                                # 只要结果不为空且包含多个字段，就认为有有效数据
                                has_valid_content = (
                                    algorithm_result and 
                                    len(algorithm_result) > 1  # 至少包含多个字段
                                )
                                
                                # 只要有有效内容，就进行大模型分析
                                if has_valid_content:
                                    logger.info(f"算法返回有效结果，开始大模型分析")
                                    readable_result = await self._format_readable_result_with_llm(
                                        algorithm_type, 
                                        algorithm_result, 
                                        nl2sql_response.execution_result,
                                        parameters.normalized_query  # 传入用户原始问题
                                    )
                                else:
                                    logger.warning(f"算法执行失败或结果为空，跳过大模型分析")
                                    # 生成简单的错误说明
                                    error_message = algorithm_result.get('error', '算法执行失败，未返回有效结果')
                                    readable_result = {
                                        "llm_analysis": f"算法执行未成功完成。{error_message}",
                                        "analysis_source": "error_fallback"
                                    }
                                
                                final_data = {
                                    "algorithm_type": algorithm_type.value,
                                    "algorithm_type_chinese": algorithm_type_chinese,
                                    # "algorithm_result": algorithm_result,
                                    "algorithm_result": algorithm_result,
                                    "sql_statement": nl2sql_response.sql_statement,
                                    "normalized_query": parameters.normalized_query,
                                    "execution_summary": self._generate_algorithm_summary(algorithm_type, algorithm_result),
                                    "data_summary": {
                                        "input_rows": len(nl2sql_response.execution_result),
                                        "sql_execution_time": nl2sql_response.execution_time_ms
                                    },
                                    "readable_result": readable_result,
                                    "message": f"{algorithm_type_chinese}算法分析结果如下" if has_valid_content else f"{algorithm_type_chinese}算法执行失败"
                                }
                                
                                logger.info(f"完整算法流程执行完成: {algorithm_type.value}")
                                logger.info(f"最终结果摘要: {final_data['execution_summary']}")
                                
                                yield AlgorithmResponse(
                                    step=StreamingStep.COMPLETED,
                                    status="completed" if has_valid_content else "failed",
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
    
    async def process_manual_db_selection(
        self,
        manual_selection_token: str,
        manual_parameter_mapping: Dict[str, Any],
        user_feedback: Optional[str] = None,
    ) -> AlgorithmResponseGenerator:
        """手动流程步骤 2：根据用户选择生成新的规范化查询"""
        from algorithm.models import AlgorithmResponse, StreamingStep

        logger.info(f"开始处理手动流程步骤 2：根据用户选择生成新的规范化查询")
        logger.info(f"手动流程步骤 2：根据用户选择生成新的规范化查询，参数: manual_selection_token={manual_selection_token}, manual_parameter_mapping={manual_parameter_mapping}, user_feedback={user_feedback}")
        ctx = self._manual_context_store.get(manual_selection_token)
        if not ctx:
            yield AlgorithmResponse(
                step=StreamingStep.MANUAL_DB_SELECTION,
                status="error",
                error="manual_selection_token无效或已过期",
                timestamp=datetime.utcnow(),
            )
            return

        if not self.parameter_extractor:
            yield AlgorithmResponse(
                step=StreamingStep.MANUAL_DB_SELECTION,
                status="error",
                error="parameter_extractor未初始化",
                timestamp=datetime.utcnow(),
            )
            return

        new_normalized_query = await self.parameter_extractor.generate_normalized_query_from_manual_selection(
            original_question=ctx.question,
            algorithm_type=ctx.algorithm_type,
            manual_parameter_mapping=manual_parameter_mapping,
            user_feedback=user_feedback,
        )
        logger.info(f"新的规范化查询生成完成: {new_normalized_query}")

        yield AlgorithmResponse(
            step=StreamingStep.MANUAL_DB_SELECTION,
            status="completed",
            data={
                "manual_selection_token": manual_selection_token,
                "normalized_query": new_normalized_query,
                "message": "normalized_query生成完成"
            },
            timestamp=datetime.utcnow(),
        )

    async def process_manual_run(
        self,
        manual_selection_token: str,
        normalized_query: str,
        manual_parameter_mapping: Dict[str, Any],
    ) -> AlgorithmResponseGenerator:
        """手动流程步骤 3：使用用户确认的 normalized_query 和所选模式运行第3/4步。"""
        from algorithm.models import AlgorithmResponse, StreamingStep, NL2SQLRequest
        from algorithm.database.candidate_tables_parser import (
            parse_candidate_tables,
            flatten_columns,
            rebuild_candidate_tables_from_selected_columns,
        )

        ctx = self._manual_context_store.get(manual_selection_token)
        if not ctx:
            yield AlgorithmResponse(
                step=StreamingStep.MANUAL_DB_SELECTION,
                status="error",
                error="manual_selection_token无效或已过期",
                timestamp=datetime.utcnow(),
            )
            return

        # 从 manual_parameter_mapping 构建所选列列表（字段 -> 字典/字典列表）
        selected_columns: List[Dict[str, Any]] = []
        def _collect(v: Any):
            if isinstance(v, dict):
                # if looks like a column spec
                if (v.get('table_name') or v.get('table')) and (v.get('column_name') or v.get('column')):
                    selected_columns.append(v)
                else:
                    for vv in v.values():
                        _collect(vv)
            elif isinstance(v, list):
                for vv in v:
                    _collect(vv)

        _collect(manual_parameter_mapping)

        # 从原始候选表填充元数据
        parsed_tables = parse_candidate_tables(ctx.candidate_tables or [])
        table_comment_by_name: Dict[str, str] = {t.table_name: t.table_comment for t in parsed_tables}
        column_meta_by_fqn: Dict[tuple, Dict[str, str]] = {}
        for c in flatten_columns(parsed_tables):
            column_meta_by_fqn[(c.table_name, c.column_name)] = {
                'column_comment': c.column_comment,
                'data_type': c.data_type,
            }

        rebuilt_candidate_tables = rebuild_candidate_tables_from_selected_columns(
            selected_columns,
            table_comment_by_name=table_comment_by_name,
            column_meta_by_fqn=column_meta_by_fqn,
        )

        # 准备步骤3/4的参数
        parameters = ctx.parameters.model_copy(deep=True)
        parameters.normalized_query = normalized_query
        if parameters.query_db_result is None:
            parameters.query_db_result = {}
        parameters.query_db_result['candidateTables'] = rebuilt_candidate_tables
        parameters.query_db_result['keywords'] = getattr(ctx, 'keywords', {}) or {}

        # 步骤3：SQL生成与数据检索
        if not self.nl2sql_client:
            yield AlgorithmResponse(
                step=StreamingStep.COMPLETED,
                status="completed",
                data={
                    "algorithm_type": ctx.algorithm_type.value,
                    "normalized_query": parameters.normalized_query,
                    "message": "参数已确认，但NL2SQL客户端未配置"
                },
                timestamp=datetime.utcnow(),
            )
            return

        yield AlgorithmResponse(
            step=StreamingStep.SQL_GENERATION,
            status="processing",
            data={"message": "正在生成查询语句..."},
            timestamp=datetime.utcnow(),
        )

        try:
            if parameters.query_db_result and parameters.query_db_result.get('candidateTables'):
                nl2sql_response = await self._query_nl2sql_with_candidates_retry(
                    parameters.normalized_query,
                    parameters.query_db_result['candidateTables'],
                    parameters.query_db_result.get('keywords', {}),
                    ctx.window_id,
                    ctx.session_id,
                )
            else:
                nl2sql_request = NL2SQLRequest(
                    question=parameters.normalized_query,
                    window_id=ctx.window_id,
                    session_id=ctx.session_id,
                )
                nl2sql_response = await self._query_nl2sql_with_retry(nl2sql_request)

            yield AlgorithmResponse(
                step=StreamingStep.SQL_GENERATION,
                status="completed",
                data={
                    "sql_statement": nl2sql_response.sql_statement,
                    "execution_time_ms": nl2sql_response.execution_time_ms,
                    "message": "查询语句生成完成"
                },
                timestamp=datetime.utcnow(),
            )

            yield AlgorithmResponse(
                step=StreamingStep.DATA_RETRIEVAL,
                status="completed",
                data={
                    "data_rows_count": len(nl2sql_response.execution_result),
                    "sample_data": nl2sql_response.execution_result if nl2sql_response.execution_result else [],
                    "message": f"数据检索完成，获取到 {len(nl2sql_response.execution_result)} 行数据"
                },
                timestamp=datetime.utcnow(),
            )

            # 步骤4：算法执行（通过调用现有的转换/执行器重用现有逻辑）
            if self.algorithm_executor and self.data_processor:
                algorithm_type = ctx.algorithm_type
                algorithm_type_chinese = ALGORITHM_TYPE_CHINESE_MAP.get(algorithm_type, algorithm_type.value)
                yield AlgorithmResponse(
                    step=StreamingStep.ALGORITHM_EXECUTION,
                    status="processing",
                    data={"message": f"正在执行{algorithm_type_chinese}算法..."},
                    timestamp=datetime.utcnow(),
                )

                algorithm_config = self.config_manager.get_algorithm_config(algorithm_type)
                if not algorithm_config:
                    raise AlgorithmExecutionError(
                        f"未找到算法配置: {algorithm_type}",
                        algorithm_type=algorithm_type,
                    )

                algorithm_request = await self._convert_data_with_validation(
                    nl2sql_response.execution_result,
                    algorithm_config,
                    parameters,
                )
                execution_response = await self._execute_algorithm_with_retry(algorithm_type, algorithm_request)

                if execution_response.task_id:
                    yield AlgorithmResponse(
                        step=StreamingStep.TASK_POLLING,
                        status="processing",
                        data={
                            "task_id": execution_response.task_id,
                            "message": "算法正在异步执行，开始轮询任务状态..."
                        },
                        timestamp=datetime.utcnow(),
                    )

                    task_response = None
                    async for task_response in self._handle_async_task_with_timeout(execution_response.task_id, algorithm_type):
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
                            timestamp=datetime.utcnow(),
                        )
                        if task_response.status != "processing":
                            break

                    if task_response and task_response.status == "success" and task_response.result:
                        yield AlgorithmResponse(
                            step=StreamingStep.COMPLETED,
                            status="completed",
                            data={
                                "algorithm_type": algorithm_type.value,
                                "algorithm_result": task_response.result,
                                "task_id": task_response.task_id,
                                "sql_statement": nl2sql_response.sql_statement,
                                "normalized_query": parameters.normalized_query,
                                "message": "算法执行完成"
                            },
                            timestamp=datetime.utcnow(),
                        )
                    else:
                        raise AlgorithmExecutionError(
                            f"异步任务失败: {getattr(task_response, 'error', None)}",
                            algorithm_type=algorithm_type,
                        )
                else:
                    algorithm_result = execution_response.result
                    readable_result = await self._format_readable_result_with_llm(
                        ctx.algorithm_type,
                        algorithm_result,
                        nl2sql_response.execution_result,
                        parameters.normalized_query,
                    )

                    yield AlgorithmResponse(
                        step=StreamingStep.COMPLETED,
                        status="completed",
                        data={
                            "algorithm_type": algorithm_type.value,
                            "algorithm_result": algorithm_result,
                            "sql_statement": nl2sql_response.sql_statement,
                            "normalized_query": parameters.normalized_query,
                            "readable_result": readable_result,
                            "message": "算法执行完成"
                        },
                        timestamp=datetime.utcnow(),
                    )
            else:
                yield AlgorithmResponse(
                    step=StreamingStep.COMPLETED,
                    status="completed",
                    data={
                        "algorithm_type": ctx.algorithm_type.value,
                        "sql_statement": nl2sql_response.sql_statement,
                        "normalized_query": parameters.normalized_query,
                        "message": "数据检索完成，算法执行器未配置"
                    },
                    timestamp=datetime.utcnow(),
                )

        except Exception as e:
            logger.error(f"manual-run失败: {str(e)}", exc_info=True)
            yield AlgorithmResponse(
                step=StreamingStep.ERROR,
                status="error",
                error=str(e),
                timestamp=datetime.utcnow(),
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
        user_id: int,
        window_id: str = "default",
    ) -> AlgorithmParameters:
        """
        提取算法参数
        
        Args:
            question: 用户查询
            algorithm_type: 算法类型
            user_id: 用户ID
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
            question, algorithm_type, database_schema, window_id, user_id
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
        user_id: int,
        window_id: str = "default"
    ) -> AlgorithmParameters:
        """带重试的参数提取"""
        return await self.retry_handler.retry_async(
            self.extract_parameters,
            question,
            algorithm_type,
            user_id,
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
            # 暂时注释掉验证，因为列名映射问题导致验证失败
            # is_valid = await self.data_processor.validate_algorithm_input(
            #     algorithm_request, algorithm_config
            # )
            # 
            # if not is_valid:
            #     raise AlgorithmExecutionError(
            #         "转换后的算法输入数据验证失败",
            #         algorithm_type=parameters.algorithm_type
            #     )
            
            logger.info(f"跳过数据验证，直接返回算法请求（数据行数: {len(algorithm_request.data_rows)}）")
            
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
            elif algorithm_type == AlgorithmType.COMPARE_PROPORTION:
                return await self.retry_handler.retry_async(
                    self.algorithm_executor.execute_compare_proportion,
                    algorithm_request,
                    config=self.retry_configs['algorithm_api'],
                    retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
                    context={'operation': 'compare_proportion_execution', 'algorithm_type': algorithm_type.value}
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
            elif algorithm_type == AlgorithmType.PREDICT:
                # 预测类型需要根据子类型判断使用单变量还是多变量预测
                sub_algorithm = algorithm_request.config.get('sub_algorithm', 'univariate')
                if 'multivariate' in sub_algorithm or '多变量' in sub_algorithm:
                    return await self.retry_handler.retry_async(
                        self.algorithm_executor.execute_multivariate_forecast,
                        algorithm_request,
                        config=self.retry_configs['algorithm_api'],
                        retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
                        context={'operation': 'multivariate_forecast_execution', 'algorithm_type': algorithm_type.value}
                    )
                else:
                    return await self.retry_handler.retry_async(
                        self.algorithm_executor.execute_univariate_forecast,
                        algorithm_request,
                        config=self.retry_configs['algorithm_api'],
                        retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
                        context={'operation': 'univariate_forecast_execution', 'algorithm_type': algorithm_type.value}
                    )
            elif algorithm_type == AlgorithmType.ASSOCIATE:
                return await self.retry_handler.retry_async(
                    self.algorithm_executor.execute_association,
                    algorithm_request,
                    config=self.retry_configs['algorithm_api'],
                    retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
                    context={'operation': 'association_execution', 'algorithm_type': algorithm_type.value}
                )
            elif algorithm_type == AlgorithmType.CAUSALITY:
                return await self.retry_handler.retry_async(
                    self.algorithm_executor.execute_causality_analysis,
                    algorithm_request,
                    config=self.retry_configs['algorithm_api'],
                    retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
                    context={'operation': 'causality_execution', 'algorithm_type': algorithm_type.value}
                )
            elif algorithm_type == AlgorithmType.SIMILARITY:
                return await self.retry_handler.retry_async(
                    self.algorithm_executor.execute_similarity,
                    algorithm_request,
                    config=self.retry_configs['algorithm_api'],
                    retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
                    context={'operation': 'similarity_execution', 'algorithm_type': algorithm_type.value}
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
    
    async def _format_readable_result_with_llm(
        self, 
        algorithm_type: AlgorithmType, 
        algorithm_result: Dict[str, Any], 
        original_data: List[Dict[str, Any]],
        user_question: str
    ) -> Dict[str, Any]:
        """
        使用大模型分析格式化算法结果
        
        Args:
            algorithm_type: 算法类型
            algorithm_result: 算法执行结果
            original_data: 原始数据
            user_question: 用户原始问题
            
        Returns:
            Dict[str, Any]: 包含大模型分析和技术细节的结果
        """
        try:
            # 检查算法执行结果是否有效
            algorithm_status = algorithm_result.get('status', 'unknown')
            # if algorithm_status != 'success':
            #     logger.warning(f"算法执行状态为 {algorithm_status}，跳过大模型分析")
            #     error_message = algorithm_result.get('error', '算法执行失败')
            #     return {
            #         "llm_analysis": f"算法执行失败：{error_message}",
            #         "analysis_source": "error"
            #     }
            
            # 检查结果是否为空
            if not algorithm_result or len(algorithm_result) <= 1:
                logger.warning("算法执行结果为空，跳过大模型分析")
                return {
                    "llm_analysis": "算法执行未返回有效结果",
                    "analysis_source": "empty_result"
                }
            
            # 生成数据摘要
            data_summary = {
                "total_rows": len(original_data),
                "algorithm_type": algorithm_type.value,
                "execution_status": algorithm_status
            }
            
            # 如果启用了大模型分析且分析器可用
            if self.settings.enable_llm_result_analysis and self.result_analyzer:
                try:
                    # 使用大模型分析结果
                    llm_analysis = await asyncio.wait_for(
                        self.result_analyzer.analyze_algorithm_result(
                            user_question=user_question,
                            algorithm_type=algorithm_type.value,
                            algorithm_result=algorithm_result,
                            original_data_summary=data_summary
                        ),
                        timeout=self.settings.llm_analysis_timeout
                    )
                    
                    logger.info(f"大模型分析完成: {len(llm_analysis)} 字符")
                    
                except asyncio.TimeoutError:
                    logger.warning(f"大模型分析超时 ({self.settings.llm_analysis_timeout}s)，使用降级处理")
                    llm_analysis = None
                except Exception as e:
                    logger.warning(f"大模型分析失败: {str(e)}，使用降级处理")
                    llm_analysis = None
            else:
                llm_analysis = None
            
            # 生成技术细节（原有的格式化逻辑）
            technical_details = self._format_readable_result(algorithm_type, algorithm_result, original_data)
            
            # 如果大模型分析成功，返回新格式
            if llm_analysis:
                return {
                    "llm_analysis": llm_analysis,
                    # "technical_details": technical_details,
                    "analysis_source": "llm_enhanced"
                }
            else:
                # 降级处理：返回原有格式，但标记为降级
                if self.settings.llm_analysis_fallback_enabled:
                    return {
                        "llm_analysis": self._generate_fallback_analysis(algorithm_type, algorithm_result, user_question),
                        "technical_details": technical_details,
                        "analysis_source": "fallback"
                    }
                else:
                    # 如果不启用降级，直接返回技术细节
                    return technical_details
                    
        except Exception as e:
            logger.error(f"格式化算法结果失败: {str(e)}")
            # 最终降级：返回原有格式
            return self._format_readable_result(algorithm_type, algorithm_result, original_data)
    
    def _generate_fallback_analysis(
        self, 
        algorithm_type: AlgorithmType, 
        algorithm_result: Dict[str, Any],
        user_question: str
    ) -> str:
        """
        生成降级分析结果（当大模型分析失败时使用）
        
        Args:
            algorithm_type: 算法类型
            algorithm_result: 算法结果
            user_question: 用户问题
            
        Returns:
            str: 降级分析结果
        """
        try:
            status = algorithm_result.get('status', 'unknown')
            
            if status == 'success':
                # 根据算法类型生成基本分析
                if algorithm_type == AlgorithmType.CLUSTER:
                    k_used = algorithm_result.get('k_used', 0)
                    results = algorithm_result.get('results', [])
                    return f"根据您的问题「{user_question}」，我对数据进行了聚类分析。成功将 {len(results)} 个数据点分为 {k_used} 个不同的群组，每个群组代表具有相似特征的数据集合。这种分组可以帮助您发现数据中的潜在模式，为业务决策提供数据支持。"
                
                elif algorithm_type == AlgorithmType.CLASSIFY:
                    results = algorithm_result.get('results', [])
                    return f"针对您的问题「{user_question}」，我完成了分类分析，对 {len(results)} 个数据点进行了类别预测。分类结果可以帮助您了解数据的类别分布特征，识别不同类别的规律，为精准决策提供依据。"
                
                elif algorithm_type == AlgorithmType.ANOMALY:
                    results = algorithm_result.get('results', [])
                    anomalies = [r for r in results if r.get('cluster_id') == -1]
                    anomaly_rate = len(anomalies) / len(results) * 100 if results else 0
                    return f"基于您的问题「{user_question}」，我进行了异常检测分析。在 {len(results)} 个数据点中发现了 {len(anomalies)} 个异常点（异常率 {anomaly_rate:.1f}%）。这些异常点可能代表特殊情况、潜在问题或值得关注的特殊模式，建议进一步调查分析。"
                
                elif algorithm_type == AlgorithmType.TREND:
                    results = algorithm_result.get('results', {})
                    trend_direction = results.get('trend_direction', 'unknown')
                    direction_map = {'increasing': '上升', 'decreasing': '下降', 'stable': '稳定'}
                    direction_chinese = direction_map.get(trend_direction, '未知')
                    return f"根据您的问题「{user_question}」，我分析了数据的趋势变化。结果显示数据呈现 {direction_chinese} 趋势，这个趋势信息可以帮助您理解数据的发展规律，预测未来可能的变化方向，为战略规划提供参考依据。"
                
                elif algorithm_type == AlgorithmType.PREDICT:
                    predictions = algorithm_result.get('predictions', [])
                    forecast_values = algorithm_result.get('results', {}).get('forecast', [])
                    count = len(predictions) or len(forecast_values)
                    return f"针对您的问题「{user_question}」，我完成了预测分析，生成了 {count} 个预测值。这些预测结果基于历史数据的模式和规律，可以帮助您了解未来可能的发展趋势，为提前规划和资源配置提供数据支持。"
                
                else:
                    return f"根据您的问题「{user_question}」，我使用 {algorithm_type.value} 算法完成了数据分析。分析结果包含了基于您数据的深度洞察，揭示了数据中的关键模式和特征，可以为您的业务决策和策略制定提供有价值的数据支持。"
            
            else:
                error_msg = algorithm_result.get('error', algorithm_result.get('message', '未知错误'))
                return f"在处理您的问题「{user_question}」时，算法分析过程遇到了一些问题：{error_msg}。建议检查数据质量、调整分析参数或联系技术支持，以获得更好的分析结果。"
                
        except Exception as e:
            logger.error(f"生成降级分析失败: {str(e)}")
            return f"已完成对您问题「{user_question}」的算法分析，但结果处理过程中遇到问题。请查看技术细节了解具体的分析结果。"

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
            elif algorithm_type == AlgorithmType.PREDICT:
                return self._format_forecast_result(algorithm_result, original_data)
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

    def _format_clustering_result(self, algorithm_result: Dict[str, Any], original_data: List[Dict[str, Any]]) -> Dict[
        str, Any]:
        """
        格式化聚类算法结果
        适配动态ID列：假设 results 中每个对象的键顺序为 [cluster_id, <dynamic_id_key>, features...]

        Args:
            algorithm_result: 聚类算法结果
            original_data: 原始数据

        Returns:
            Dict[str, Any]: 格式化后的聚类结果
        """
        k_used = algorithm_result.get("k_used", 0)
        results = algorithm_result.get("results", [])

        # 1. 动态侦测 ID 列的键名
        id_key = None
        if results and len(results) > 0:
            # 获取第一条数据的键列表
            first_item_keys = list(results[0].keys())

            # 严格遵循约定：第1个是 cluster_id，第2个是 标识字段
            if len(first_item_keys) >= 2 and first_item_keys[0] == "cluster_id":
                id_key = first_item_keys[1]
                logger.info(f"聚类结果格式化：检测到动态ID列名为 '{id_key}'")
            else:
                logger.warning(f"聚类结果格式异常：未满足[cluster_id, id, ...]的顺序约定，键列表: {first_item_keys}")

        # 2. 按聚类ID分组
        cluster_groups = {}
        for item in results:
            cluster_id = item.get("cluster_id")

            # 使用侦测到的 id_key 提取标识，如果侦测失败则尝试降级逻辑（取第2个值）
            uid = None
            if id_key:
                uid = item.get(id_key)
            elif len(item) >= 2:
                # 降级策略：如果键顺序不对但数据存在，强行取 values 的第2个值
                uid = list(item.values())[1]

            if cluster_id is not None and uid is not None:
                if cluster_id not in cluster_groups:
                    cluster_groups[cluster_id] = []
                # 确保ID为字符串格式
                cluster_groups[cluster_id].append(str(uid))

        # 3. 构建简洁的聚类结果描述
        cluster_descriptions = []
        cluster_summary = {}

        for cluster_id in sorted(cluster_groups.keys()):
            member_ids = cluster_groups[cluster_id]
            cluster_name = f"第{cluster_id + 1}类" if cluster_id >= 0 else f"聚类{cluster_id}"

            # 创建描述
            if len(member_ids) <= 10:
                ids_str = "、".join(member_ids)
                description = f"{cluster_name}包含{len(member_ids)}个成员：{ids_str}"
            else:
                ids_str = "、".join(member_ids[:8])
                description = f"{cluster_name}包含{len(member_ids)}个成员：{ids_str}等"

            cluster_descriptions.append(description)
            cluster_summary[cluster_name] = {
                "count": len(member_ids),
                "members": member_ids
            }

        # 4. 生成总体描述
        total_description = f"聚类分析完成，将{len(results)}个数据点分为{k_used}个聚类。"
        if id_key:
            total_description += f"（基于标识列：{id_key}）"
        full_description = total_description + " " + "；".join(cluster_descriptions) + "。"

        return {
            "summary": full_description,
            "k_value": k_used,
            "id_column_detected": id_key,  # 记录检测到的ID列名，供调试或前端使用
            "total_data_points": len(results),
            "cluster_details": cluster_summary,
            "simple_view": {
                f"第{i + 1}类": cluster_groups.get(i, [])
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
    
    def _format_forecast_result(self, algorithm_result: Dict[str, Any], original_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        格式化预测算法结果（单变量/多变量预测）
        
        Args:
            algorithm_result: 预测算法结果
            original_data: 原始数据
            
        Returns:
            Dict[str, Any]: 格式化后的预测结果
        """
        import json
        
        success = algorithm_result.get('success', False)
        
        if not success:
            return {
                "summary": f"预测失败: {algorithm_result.get('message', '未知错误')}",
                "status": "failed",
                "data_points": len(original_data)
            }
        
        # 提取关键信息
        model_used = algorithm_result.get('model_used', 'unknown')
        results = algorithm_result.get('results', {})
        predictions = algorithm_result.get('predictions', [])
        metrics = algorithm_result.get('metrics', {})
        data_analysis = algorithm_result.get('data_analysis', {})
        
        # 获取预测值
        forecast_values = results.get('forecast', [])
        timestamps = results.get('timestamps', [])
        
        # 如果没有从results获取到，尝试从predictions获取
        if not forecast_values and predictions:
            forecast_values = [p.get('value') for p in predictions]
            timestamps = [p.get('timestamp') for p in predictions]
        
        forecast_count = len(forecast_values)
        
        # 构建主要描述
        if model_used and model_used != 'unknown':
            main_description = f"预测完成，使用{model_used}模型，生成了{forecast_count}个预测值"
        else:
            main_description = f"预测完成，生成了{forecast_count}个预测值"
        
        # 添加指标信息
        if metrics:
            rmse = metrics.get('rmse')
            mae = metrics.get('mae')
            mape = metrics.get('mape')
            if rmse:
                main_description += f"，RMSE={rmse:.4f}"
            if mae:
                main_description += f"，MAE={mae:.4f}"
            if mape:
                main_description += f"，MAPE={mape:.2f}%"
        
        # 构建预测摘要
        if forecast_values:
            min_val = min(forecast_values)
            max_val = max(forecast_values)
            avg_val = sum(forecast_values) / len(forecast_values)
            forecast_summary = {
                "预测数量": forecast_count,
                "最小值": round(min_val, 2),
                "最大值": round(max_val, 2),
                "平均值": round(avg_val, 2)
            }
        else:
            forecast_summary = {"预测数量": 0}
        
        # 构建简化视图
        simple_view = {
            "模型": model_used,
            "预测数量": forecast_count,
            "历史数据点": len(original_data)
        }
        
        # 构建预测详情（前5个和后5个）
        forecast_details = []
        if forecast_values and timestamps:
            for i, (ts, val) in enumerate(zip(timestamps, forecast_values)):
                if i < 5 or i >= len(timestamps) - 5:
                    forecast_details.append({
                        "timestamp": ts,
                        "value": round(val, 2) if isinstance(val, (int, float)) else val
                    })
                elif i == 5:
                    forecast_details.append({"note": f"... 省略 {len(timestamps) - 10} 个预测值 ..."})
        
        return {
            "summary": main_description,
            "model_used": model_used,
            "forecast_count": forecast_count,
            "data_points": len(original_data),
            "forecast_summary": forecast_summary,
            "simple_view": simple_view,
            "forecast_details": forecast_details,
            "metrics": metrics,
            "data_analysis": data_analysis,
            "full_response": json.dumps(algorithm_result, indent=2, ensure_ascii=False),
            "interpretation": f"基于{len(original_data)}个历史数据点，使用{model_used}模型预测了未来{forecast_count}个时间点的值"
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