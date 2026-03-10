"""
Agent工具定义模块

定义Agent可以调用的所有工具，每个工具封装一个现有服务方法。
工具遵循统一的接口规范，支持描述、参数定义和异步执行。
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentTool(ABC):
    """Agent工具基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称（英文标识符）"""

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述（供LLM理解用途）"""

    @property
    @abstractmethod
    def parameters_schema(self) -> Dict[str, Any]:
        """工具参数JSON Schema"""

    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行工具

        Returns:
            Dict 包含 success (bool) 和 result / error 字段
        """


# ---------------------------------------------------------------------------
# 具体工具实现
# ---------------------------------------------------------------------------


class CheckFollowUpTool(AgentTool):
    """追问判断工具 — 检测当前问题是否是对上一个问题的追问"""

    name = "check_follow_up"
    description = (
        "检测当前用户问题是否是对上一个问题的追问。"
        "如果是追问，返回合并后的完整问题；否则返回原始问题。"
        "应在流程最开始调用。"
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "用户问题"},
            "window_id": {"type": "string", "description": "窗口ID"},
            "session_id": {"type": "string", "description": "会话ID"},
            "user_id": {"type": "integer", "description": "用户ID"},
        },
        "required": ["question", "window_id"],
    }

    def __init__(self, nl2sql_client):
        self._nl2sql_client = nl2sql_client

    async def execute(self, **kwargs) -> Dict[str, Any]:
        question = kwargs["question"]
        window_id = kwargs["window_id"]
        session_id = kwargs.get("session_id", "")
        user_id = kwargs.get("user_id")

        try:
            result = await self._nl2sql_client.check_continuous_question(
                question=question,
                window_id=window_id,
                session_id=session_id,
                user_id=user_id,
            )
            is_continuous = result.get("isContinuous", False)
            merged = result.get("mergedQuestion", question)
            return {
                "success": True,
                "result": {
                    "is_continuous": is_continuous,
                    "merged_question": merged,
                    "previous_question": result.get("previousQuestion", ""),
                },
            }
        except Exception as e:
            logger.warning(f"追问判断失败 (window_id={window_id}): {e}")
            return {
                "success": True,
                "result": {
                    "is_continuous": False,
                    "merged_question": question,
                    "previous_question": "",
                },
            }


class IdentifyAlgorithmTool(AgentTool):
    """算法类型识别工具 — 根据用户问题判断应使用哪种算法"""

    name = "identify_algorithm"
    description = (
        "根据用户的自然语言问题识别最合适的算法类型。"
        "支持的类型包括：cluster(聚类)、classify(分类)、predict(预测)、"
        "anomaly(异常检测)、associate(关联分析)、similarity(相似度分析)、"
        "trend(趋势分析)、causality(因果分析)、nl2sql(数据查询)、"
        "compare_proportion(对比分析)。"
        "必须在参数提取之前调用。"
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "用户问题（可以是追问合并后的问题）"},
        },
        "required": ["question"],
    }

    def __init__(self, router):
        self._router = router

    async def execute(self, **kwargs) -> Dict[str, Any]:
        question = kwargs["question"]
        try:
            algorithm_type = await self._router.route_to_algorithm(question)
            return {
                "success": True,
                "result": {
                    "algorithm_type": algorithm_type.value,
                },
            }
        except Exception as e:
            logger.error(f"算法识别失败: {e}")
            return {"success": False, "error": str(e)}


class ExtractParametersTool(AgentTool):
    """参数提取工具 — 从用户问题中提取算法所需参数"""

    name = "extract_parameters"
    description = (
        "从用户的自然语言问题中提取所选算法需要的参数，"
        "包括规范化查询语句、所需数据列、参数映射等。"
        "必须在算法识别之后调用，需要提供 algorithm_type。"
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "用户问题"},
            "algorithm_type": {"type": "string", "description": "算法类型标识符"},
            "user_id": {"type": "integer", "description": "用户ID"},
            "window_id": {"type": "string", "description": "窗口ID"},
        },
        "required": ["question", "algorithm_type"],
    }

    def __init__(self, parameter_extractor, schema_retriever):
        self._extractor = parameter_extractor
        self._schema_retriever = schema_retriever

    async def execute(self, **kwargs) -> Dict[str, Any]:
        from algorithm.models import AlgorithmType

        question = kwargs["question"]
        algorithm_type = AlgorithmType(kwargs["algorithm_type"])
        user_id = kwargs.get("user_id", 0)
        window_id = kwargs.get("window_id", "default")

        try:
            # 获取数据库模式信息
            try:
                database_schema = await self._schema_retriever.get_database_schema()
            except Exception:
                database_schema = []

            parameters = await self._extractor.extract_parameters(
                question, algorithm_type, database_schema, window_id, user_id
            )
            return {
                "success": True,
                "result": {
                    "normalized_query": parameters.normalized_query,
                    "required_columns": parameters.required_columns,
                    "parameter_mapping": parameters.parameter_mapping,
                    "query_db_result": parameters.query_db_result,
                },
            }
        except Exception as e:
            logger.error(f"参数提取失败: {e}")
            return {"success": False, "error": str(e)}


class GenerateAndExecuteSQLTool(AgentTool):
    """SQL生成与执行工具 — 生成SQL并检索数据"""

    name = "generate_and_execute_sql"
    description = (
        "根据规范化查询和候选表信息生成SQL语句并执行，返回查询结果数据。"
        "必须在参数提取之后调用，需要 normalized_query。"
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "normalized_query": {"type": "string", "description": "规范化后的查询语句"},
            "window_id": {"type": "string", "description": "窗口ID"},
            "session_id": {"type": "string", "description": "会话ID"},
            "user_id": {"type": "integer", "description": "用户ID"},
            "candidate_tables": {"type": "array", "description": "候选表信息列表（可选）"},
            "keywords": {"type": "object", "description": "关键词信息（可选）"},
        },
        "required": ["normalized_query", "window_id"],
    }

    def __init__(self, nl2sql_client, retry_handler, retry_config):
        self._nl2sql_client = nl2sql_client
        self._retry_handler = retry_handler
        self._retry_config = retry_config

    async def execute(self, **kwargs) -> Dict[str, Any]:
        import asyncio
        from algorithm.models import NL2SQLRequest

        normalized_query = kwargs["normalized_query"]
        window_id = kwargs["window_id"]
        session_id = kwargs.get("session_id", "")
        user_id = kwargs.get("user_id", 0)
        candidate_tables = kwargs.get("candidate_tables")
        keywords_data = kwargs.get("keywords", {})

        try:
            if candidate_tables:
                nl2sql_response = await self._retry_handler.retry_async(
                    self._nl2sql_client.query_with_candidates,
                    normalized_query,
                    candidate_tables,
                    keywords_data,
                    window_id,
                    session_id,
                    config=self._retry_config,
                    retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
                    context={"operation": "nl2sql_query_with_candidates"},
                )
            else:
                nl2sql_request = NL2SQLRequest(
                    question=normalized_query,
                    window_id=window_id,
                    session_id=session_id,
                    user_id=user_id,
                )
                nl2sql_response = await self._retry_handler.retry_async(
                    self._nl2sql_client.query,
                    nl2sql_request,
                    config=self._retry_config,
                    retryable_exceptions=(ConnectionError, TimeoutError, asyncio.TimeoutError),
                    context={"operation": "nl2sql_query"},
                )

            return {
                "success": True,
                "result": {
                    "sql_statement": nl2sql_response.sql_statement,
                    "execution_result": nl2sql_response.execution_result,
                    "execution_time_ms": nl2sql_response.execution_time_ms,
                    "data_rows_count": len(nl2sql_response.execution_result),
                },
            }
        except Exception as e:
            logger.error(f"SQL生成或执行失败: {e}")
            return {"success": False, "error": str(e)}


class ExecuteAlgorithmTool(AgentTool):
    """算法执行工具 — 执行指定的算法"""

    name = "execute_algorithm"
    description = (
        "使用指定的算法类型对检索到的数据进行算法分析。"
        "支持同步和异步执行模式。需要先完成SQL数据检索。"
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "algorithm_type": {"type": "string", "description": "算法类型标识符"},
            "execution_result": {"type": "array", "description": "SQL查询返回的数据行"},
            "normalized_query": {"type": "string", "description": "规范化查询"},
            "parameter_mapping": {"type": "object", "description": "参数映射"},
            "required_columns": {"type": "array", "description": "所需列名"},
            "query_db_result": {"type": "object", "description": "query-db结果（可选）"},
        },
        "required": ["algorithm_type", "execution_result"],
    }

    def __init__(self, algorithm_executor, data_processor, config_manager, retry_handler, retry_config, async_task_timeout: int = 300):
        self._executor = algorithm_executor
        self._data_processor = data_processor
        self._config_manager = config_manager
        self._retry_handler = retry_handler
        self._retry_config = retry_config
        self._async_task_timeout = async_task_timeout

    async def execute(self, **kwargs) -> Dict[str, Any]:
        import asyncio
        from algorithm.models import AlgorithmType, AlgorithmParameters

        algorithm_type = AlgorithmType(kwargs["algorithm_type"])
        execution_result = kwargs["execution_result"]
        normalized_query = kwargs.get("normalized_query", "")
        parameter_mapping = kwargs.get("parameter_mapping", {})
        required_columns = kwargs.get("required_columns", [])
        query_db_result = kwargs.get("query_db_result")

        try:
            # 快速验证输入数据
            if not execution_result:
                return {"success": False, "error": "SQL查询结果为空，无法执行算法"}

            # 获取算法配置
            algorithm_config = self._config_manager.get_algorithm_config(algorithm_type)
            if not algorithm_config:
                return {"success": False, "error": f"未找到算法配置: {algorithm_type.value}"}

            # 构建参数对象
            parameters = AlgorithmParameters(
                algorithm_type=algorithm_type,
                normalized_query=normalized_query,
                parameter_mapping=parameter_mapping,
                required_columns=required_columns,
                query_db_result=query_db_result,
            )

            # 数据格式转换
            algorithm_request = await self._data_processor.convert_sql_result_to_algorithm_input(
                execution_result, algorithm_config, parameters
            )

            # 执行算法（根据类型分发）
            execution_response = await self._dispatch_algorithm(algorithm_type, algorithm_request)

            # 处理异步任务
            if execution_response.task_id:
                task_result = await self._poll_async_task(execution_response.task_id, algorithm_type)
                return {
                    "success": True,
                    "result": {
                        "algorithm_result": task_result,
                        "task_id": execution_response.task_id,
                        "is_async": True,
                    },
                }
            else:
                return {
                    "success": True,
                    "result": {
                        "algorithm_result": execution_response.result,
                        "is_async": False,
                    },
                }
        except Exception as e:
            logger.error(f"算法执行失败: {e}")
            return {"success": False, "error": str(e)}

    async def _dispatch_algorithm(self, algorithm_type, algorithm_request):
        """根据算法类型分发执行"""
        import asyncio
        from algorithm.models import AlgorithmType

        dispatch_map = {
            AlgorithmType.CLUSTER: self._executor.execute_clustering,
            AlgorithmType.CLASSIFY: self._executor.execute_classification,
            AlgorithmType.ANOMALY: self._executor.execute_anomaly_detection,
            AlgorithmType.COMPARE_PROPORTION: self._executor.execute_compare_proportion,
            AlgorithmType.TREND: self._executor.execute_trend_analysis,
            AlgorithmType.ASSOCIATE: self._executor.execute_association,
            AlgorithmType.CAUSALITY: self._executor.execute_causality_analysis,
            AlgorithmType.SIMILARITY: self._executor.execute_similarity,
        }

        # 特殊处理：PREDICT 需要根据子类型判断
        if algorithm_type == AlgorithmType.PREDICT:
            sub_algorithm = algorithm_request.config.get("sub_algorithm", "univariate")
            if "multivariate" in sub_algorithm or "多变量" in sub_algorithm:
                func = self._executor.execute_multivariate_forecast
            else:
                func = self._executor.execute_univariate_forecast
        else:
            func = dispatch_map.get(algorithm_type)

        if not func:
            from algorithm.error_handler import AlgorithmExecutionError
            raise AlgorithmExecutionError(
                f"暂不支持的算法类型: {algorithm_type.value}",
                algorithm_type=algorithm_type,
            )

        return await self._retry_handler.retry_async(
            func,
            algorithm_request,
            config=self._retry_config,
            retryable_exceptions=(ConnectionError, TimeoutError),
            context={"operation": f"{algorithm_type.value}_execution"},
        )

    async def _poll_async_task(self, task_id: str, algorithm_type) -> Dict[str, Any]:
        """轮询异步任务直到完成"""
        import asyncio

        start_time = datetime.utcnow()
        timeout_seconds = self._async_task_timeout

        poll_generator = self._executor.poll_async_task(task_id)
        if asyncio.iscoroutine(poll_generator):
            poll_generator = await poll_generator

        async for task_response in poll_generator:
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            if elapsed > timeout_seconds:
                return {"status": "timeout", "error": f"任务超时: {timeout_seconds}s"}

            if task_response.status == "success":
                return task_response.result or {}
            elif task_response.status == "failed":
                return {"status": "failed", "error": task_response.error or "任务失败"}
            # else: processing — continue polling

        return {"status": "unknown", "error": "轮询异常结束"}


class AnalyzeResultsTool(AgentTool):
    """结果分析工具 — 使用LLM将算法结果转换为自然语言分析"""

    name = "analyze_results"
    description = (
        "使用大模型将算法执行的结果转换为用户友好的自然语言分析报告。"
        "应在算法执行完成后调用。"
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "algorithm_type": {"type": "string", "description": "算法类型"},
            "algorithm_result": {"type": "object", "description": "算法执行结果"},
            "original_data": {"type": "array", "description": "原始数据"},
            "user_question": {"type": "string", "description": "用户原始问题"},
        },
        "required": ["algorithm_type", "algorithm_result", "user_question"],
    }

    def __init__(self, result_analyzer, settings):
        self._analyzer = result_analyzer
        self._settings = settings

    async def execute(self, **kwargs) -> Dict[str, Any]:
        import asyncio
        from algorithm.models import AlgorithmType

        algorithm_type = AlgorithmType(kwargs["algorithm_type"])
        algorithm_result = kwargs["algorithm_result"]
        original_data = kwargs.get("original_data", [])
        user_question = kwargs["user_question"]

        try:
            if not self._settings.enable_llm_result_analysis or not self._analyzer:
                return {
                    "success": True,
                    "result": {
                        "llm_analysis": "大模型结果分析未启用",
                        "analysis_source": "disabled",
                    },
                }

            data_summary = {
                "total_rows": len(original_data),
                "algorithm_type": algorithm_type.value,
                "execution_status": algorithm_result.get("status", "unknown"),
            }

            llm_analysis = await asyncio.wait_for(
                self._analyzer.analyze_algorithm_result(
                    user_question=user_question,
                    algorithm_type=algorithm_type.value,
                    algorithm_result=algorithm_result,
                    original_data_summary=data_summary,
                ),
                timeout=self._settings.llm_analysis_timeout,
            )

            return {
                "success": True,
                "result": {
                    "llm_analysis": llm_analysis,
                    "analysis_source": "llm_enhanced",
                },
            }
        except asyncio.TimeoutError:
            logger.warning("大模型分析超时")
            return {
                "success": True,
                "result": {
                    "llm_analysis": "分析超时，请查看算法原始结果",
                    "analysis_source": "timeout_fallback",
                },
            }
        except Exception as e:
            logger.error(f"结果分析失败: {e}")
            return {
                "success": True,
                "result": {
                    "llm_analysis": f"分析失败: {str(e)}",
                    "analysis_source": "error_fallback",
                },
            }


class SaveQuestionTool(AgentTool):
    """问题保存工具 — 将问题保存到会话历史记录"""

    name = "save_question"
    description = (
        "将用户问题保存到会话历史记录中。"
        "应在追问判断之后调用。"
    )
    parameters_schema = {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "要保存的问题"},
            "window_id": {"type": "string", "description": "窗口ID"},
            "user_id": {"type": "integer", "description": "用户ID"},
        },
        "required": ["question", "window_id"],
    }

    def __init__(self, nl2sql_client):
        self._nl2sql_client = nl2sql_client

    async def execute(self, **kwargs) -> Dict[str, Any]:
        question = kwargs["question"]
        window_id = kwargs["window_id"]
        user_id = kwargs.get("user_id")

        try:
            save_result = await self._nl2sql_client.save_question(
                question=question,
                window_id=window_id,
                user_id=user_id,
            )
            return {
                "success": save_result.get("success", False),
                "result": {
                    "saved": save_result.get("success", False),
                    "session_id": save_result.get("data", {}).get("sessionId", ""),
                },
            }
        except Exception as e:
            logger.warning(f"问题保存失败: {e}")
            return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 工具注册表
# ---------------------------------------------------------------------------


class ToolRegistry:
    """工具注册表 — 管理所有可用的Agent工具"""

    def __init__(self):
        self._tools: Dict[str, AgentTool] = {}

    def register(self, tool: AgentTool):
        """注册一个工具"""
        self._tools[tool.name] = tool
        logger.debug(f"注册Agent工具: {tool.name}")

    def get(self, name: str) -> Optional[AgentTool]:
        """获取指定名称的工具"""
        return self._tools.get(name)

    def list_tools(self) -> List[AgentTool]:
        """获取所有已注册的工具"""
        return list(self._tools.values())

    def get_tools_description(self) -> str:
        """获取所有工具的描述（供LLM提示词使用）"""
        descriptions = []
        for tool in self._tools.values():
            params_desc = []
            props = tool.parameters_schema.get("properties", {})
            required = tool.parameters_schema.get("required", [])
            for param_name, param_info in props.items():
                req_mark = "（必填）" if param_name in required else "（可选）"
                params_desc.append(
                    f"    - {param_name}: {param_info.get('description', '')} {req_mark}"
                )
            params_str = "\n".join(params_desc) if params_desc else "    （无参数）"
            descriptions.append(
                f"工具名称: {tool.name}\n"
                f"功能描述: {tool.description}\n"
                f"参数:\n{params_str}"
            )
        return "\n\n".join(descriptions)
