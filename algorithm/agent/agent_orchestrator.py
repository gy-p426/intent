"""
Agent编排器模块

实现ReAct（Reason-Act-Observe）循环，驱动LLM进行多步推理和工具调用。
替代传统的硬编码if-else流程编排，使分析流程更灵活、可扩展。
"""

import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from algorithm.models import AlgorithmResponse, StreamingStep, AlgorithmResponseGenerator
from algorithm.agent.tools import (
    ToolRegistry,
    CheckFollowUpTool,
    IdentifyAlgorithmTool,
    ExtractParametersTool,
    GenerateAndExecuteSQLTool,
    ExecuteAlgorithmTool,
    AnalyzeResultsTool,
    SaveQuestionTool,
)
from algorithm.agent.prompts import (
    AGENT_SYSTEM_PROMPT,
    AGENT_OBSERVATION_TEMPLATE,
    AGENT_INITIAL_PROMPT,
)

logger = logging.getLogger(__name__)

# Agent推理最大轮次（安全阈值）
MAX_AGENT_STEPS = 15


class AgentOrchestrator:
    """
    Agent编排器

    使用ReAct范式驱动LLM进行多步推理，根据用户问题动态规划
    和执行分析工具，替代固定的流水线流程。
    """

    def __init__(self, service):
        """
        初始化Agent编排器

        Args:
            service: AlgorithmIntegrationService实例，提供所有组件访问
        """
        self._service = service
        self._registry = ToolRegistry()
        self._llm_client = None
        self._initialize_tools()
        self._initialize_llm()

    def _initialize_llm(self):
        """初始化Agent推理用的LLM客户端"""
        from llm.llm_client import LLMClient

        try:
            settings = self._service.settings
            self._llm_client = LLMClient(
                model=getattr(settings, "agent_orchestration_model", None) or settings.ark_model,
                timeout=getattr(settings, "agent_orchestration_timeout", None) or settings.ark_timeout,
            )
            logger.info("Agent编排器LLM客户端初始化成功")
        except Exception as e:
            logger.error(f"Agent编排器LLM客户端初始化失败: {e}")
            raise

    def _initialize_tools(self):
        """注册所有可用工具"""
        svc = self._service

        # Tool 1: 追问判断
        if svc.nl2sql_client:
            self._registry.register(CheckFollowUpTool(svc.nl2sql_client))
            self._registry.register(SaveQuestionTool(svc.nl2sql_client))

        # Tool 2: 算法识别
        if svc.router:
            self._registry.register(IdentifyAlgorithmTool(svc.router))

        # Tool 3: 参数提取
        if svc.parameter_extractor:
            self._registry.register(
                ExtractParametersTool(svc.parameter_extractor, svc.schema_retriever)
            )

        # Tool 4: SQL生成与执行
        if svc.nl2sql_client:
            self._registry.register(
                GenerateAndExecuteSQLTool(
                    svc.nl2sql_client,
                    svc.retry_handler,
                    svc.retry_configs.get("nl2sql"),
                )
            )

        # Tool 5: 算法执行
        if svc.algorithm_executor and svc.data_processor:
            self._registry.register(
                ExecuteAlgorithmTool(
                    svc.algorithm_executor,
                    svc.data_processor,
                    svc.config_manager,
                    svc.retry_handler,
                    svc.retry_configs.get("algorithm_api"),
                )
            )

        # Tool 6: 结果分析
        self._registry.register(
            AnalyzeResultsTool(svc.result_analyzer, svc.settings)
        )

        logger.info(f"Agent编排器注册了 {len(self._registry.list_tools())} 个工具")

    async def process(
        self,
        question: str,
        window_id: str,
        session_id: str,
        user_id: Optional[int] = None,
        request_context: Optional[Dict[str, Any]] = None,
    ) -> AlgorithmResponseGenerator:
        """
        使用Agent编排执行算法分析流程

        Args:
            question: 用户问题
            window_id: 窗口ID
            session_id: 会话ID
            user_id: 用户ID
            request_context: 请求上下文

        Yields:
            AlgorithmResponse: 流式响应
        """
        trace_id = (request_context or {}).get("trace_id", "unknown")

        # 构建系统提示词（包含工具描述）
        tools_desc = self._registry.get_tools_description()
        system_prompt = AGENT_SYSTEM_PROMPT.format(tools_description=tools_desc)

        # 构建初始消息
        initial_prompt = AGENT_INITIAL_PROMPT.format(
            question=question,
            window_id=window_id,
            session_id=session_id,
            user_id=user_id or 0,
        )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": initial_prompt},
        ]

        # 通知客户端Agent编排开始
        yield AlgorithmResponse(
            step=StreamingStep.INTENT_ANALYSIS,
            status="processing",
            data={"message": "Agent正在分析问题意图并规划执行步骤..."},
            timestamp=datetime.utcnow(),
        )

        # 用于收集所有步骤的中间结果
        context_data: Dict[str, Any] = {
            "question": question,
            "window_id": window_id,
            "session_id": session_id,
            "user_id": user_id,
        }

        # ReAct 循环
        for step_num in range(1, MAX_AGENT_STEPS + 1):
            logger.info(f"Agent步骤 {step_num}/{MAX_AGENT_STEPS}", extra={"trace_id": trace_id})

            try:
                # 调用LLM获取下一步动作
                llm_response = await self._llm_client.chat_completion(messages)
                parsed = self._parse_llm_response(llm_response)
            except Exception as e:
                logger.error(f"Agent LLM调用失败: {e}", extra={"trace_id": trace_id})
                yield AlgorithmResponse(
                    step=StreamingStep.ERROR,
                    status="error",
                    error=f"Agent推理失败: {str(e)}",
                    timestamp=datetime.utcnow(),
                )
                return

            if parsed is None:
                logger.warning(f"Agent输出解析失败: {llm_response[:200]}", extra={"trace_id": trace_id})
                yield AlgorithmResponse(
                    step=StreamingStep.ERROR,
                    status="error",
                    error="Agent输出格式异常，无法继续",
                    timestamp=datetime.utcnow(),
                )
                return

            thought = parsed.get("thought", "")
            action = parsed.get("action", {})
            tool_name = action.get("tool", "")
            tool_params = action.get("parameters", {})

            logger.info(
                f"Agent思考: {thought[:100]}... → 行动: {tool_name}",
                extra={"trace_id": trace_id},
            )

            # 将LLM的输出追加到消息历史
            messages.append({"role": "assistant", "content": llm_response})

            # 检查是否完成
            if tool_name == "finish":
                # Agent认为任务完成
                summary = tool_params.get("summary", "分析完成")
                logger.info(f"Agent完成: {summary[:100]}", extra={"trace_id": trace_id})

                # 构建最终响应
                final_data = self._build_final_response(context_data, summary)
                yield AlgorithmResponse(
                    step=StreamingStep.COMPLETED,
                    status="completed",
                    data=final_data,
                    timestamp=datetime.utcnow(),
                )
                return

            # 查找并执行工具
            tool = self._registry.get(tool_name)
            if not tool:
                observation = f"错误：未找到工具 '{tool_name}'，可用工具: {[t.name for t in self._registry.list_tools()]}"
                logger.warning(observation, extra={"trace_id": trace_id})
            else:
                # 流式通知客户端当前正在执行的工具
                step_type = self._map_tool_to_streaming_step(tool_name)
                yield AlgorithmResponse(
                    step=step_type,
                    status="processing",
                    data={
                        "message": f"正在执行: {tool.description[:50]}...",
                        "agent_thought": thought,
                        "tool": tool_name,
                    },
                    timestamp=datetime.utcnow(),
                )

                # 注入上下文参数（工具可能未显式指定但上下文中存在的参数）
                enriched_params = self._enrich_params(tool_name, tool_params, context_data)

                # 执行工具
                try:
                    tool_result = await tool.execute(**enriched_params)
                except Exception as e:
                    tool_result = {"success": False, "error": str(e)}
                    logger.error(f"工具 {tool_name} 执行异常: {e}", extra={"trace_id": trace_id})

                # 更新上下文数据
                self._update_context(tool_name, tool_result, context_data)

                # 流式返回工具执行结果
                yield AlgorithmResponse(
                    step=step_type,
                    status="completed" if tool_result.get("success") else "error",
                    data=self._build_step_response(tool_name, tool_result, context_data),
                    timestamp=datetime.utcnow(),
                )

                observation = json.dumps(tool_result, ensure_ascii=False, default=str)

            # 将观察结果追加到消息中，触发下一轮推理
            obs_message = AGENT_OBSERVATION_TEMPLATE.format(
                tool_name=tool_name,
                observation=observation[:3000],  # 限制长度防止上下文溢出
            )
            messages.append({"role": "user", "content": obs_message})

        # 达到最大步骤数
        logger.warning(f"Agent达到最大步骤数 {MAX_AGENT_STEPS}", extra={"trace_id": trace_id})
        yield AlgorithmResponse(
            step=StreamingStep.COMPLETED,
            status="completed",
            data={
                "message": "Agent分析完成（达到最大步骤数）",
                **{k: v for k, v in context_data.items() if k not in ("question", "window_id", "session_id", "user_id")},
            },
            timestamp=datetime.utcnow(),
        )

    # -----------------------------------------------------------------------
    # 辅助方法
    # -----------------------------------------------------------------------

    def _parse_llm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        解析LLM的JSON响应

        支持处理Markdown代码块包裹的JSON。
        """
        text = response.strip()

        # 去除Markdown代码块标记
        if text.startswith("```"):
            lines = text.split("\n")
            # 去掉第一行和最后一行
            if lines[-1].strip() == "```":
                lines = lines[1:-1]
            else:
                lines = lines[1:]
            text = "\n".join(lines)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试从文本中提取JSON
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            logger.warning(f"无法解析LLM响应为JSON: {text[:200]}")
            return None

    def _map_tool_to_streaming_step(self, tool_name: str) -> StreamingStep:
        """将工具名称映射到流式响应步骤"""
        mapping = {
            "check_follow_up": StreamingStep.INTENT_ANALYSIS,
            "save_question": StreamingStep.INTENT_ANALYSIS,
            "identify_algorithm": StreamingStep.ALGORITHM_IDENTIFICATION,
            "extract_parameters": StreamingStep.PARAMETER_EXTRACTION,
            "generate_and_execute_sql": StreamingStep.SQL_GENERATION,
            "execute_algorithm": StreamingStep.ALGORITHM_EXECUTION,
            "analyze_results": StreamingStep.COMPLETED,
        }
        return mapping.get(tool_name, StreamingStep.ALGORITHM_EXECUTION)

    def _enrich_params(
        self, tool_name: str, params: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """根据上下文补充工具参数"""
        enriched = dict(params)

        # 通用上下文参数注入
        for key in ("question", "window_id", "session_id", "user_id"):
            if key not in enriched and key in context:
                enriched[key] = context[key]

        # 针对特定工具注入上下文中已有的数据
        if tool_name == "extract_parameters":
            # 使用合并后的问题
            if "merged_question" in context:
                enriched.setdefault("question", context["merged_question"])
            if "algorithm_type" in context:
                enriched.setdefault("algorithm_type", context["algorithm_type"])

        elif tool_name == "generate_and_execute_sql":
            if "normalized_query" in context:
                enriched.setdefault("normalized_query", context["normalized_query"])
            if "candidate_tables" in context:
                enriched.setdefault("candidate_tables", context["candidate_tables"])
            if "keywords" in context:
                enriched.setdefault("keywords", context["keywords"])

        elif tool_name == "execute_algorithm":
            if "algorithm_type" in context:
                enriched.setdefault("algorithm_type", context["algorithm_type"])
            if "execution_result" in context:
                enriched.setdefault("execution_result", context["execution_result"])
            if "normalized_query" in context:
                enriched.setdefault("normalized_query", context["normalized_query"])
            if "parameter_mapping" in context:
                enriched.setdefault("parameter_mapping", context["parameter_mapping"])
            if "required_columns" in context:
                enriched.setdefault("required_columns", context["required_columns"])
            if "query_db_result" in context:
                enriched.setdefault("query_db_result", context["query_db_result"])

        elif tool_name == "analyze_results":
            if "algorithm_type" in context:
                enriched.setdefault("algorithm_type", context["algorithm_type"])
            if "algorithm_result" in context:
                enriched.setdefault("algorithm_result", context["algorithm_result"])
            if "execution_result" in context:
                enriched.setdefault("original_data", context["execution_result"])
            enriched.setdefault("user_question", context.get("merged_question", context.get("question", "")))

        elif tool_name == "save_question":
            if "merged_question" in context:
                enriched.setdefault("question", context["merged_question"])

        return enriched

    def _update_context(
        self, tool_name: str, tool_result: Dict[str, Any], context: Dict[str, Any]
    ):
        """根据工具执行结果更新上下文"""
        if not tool_result.get("success"):
            return

        result = tool_result.get("result", {})

        if tool_name == "check_follow_up":
            merged = result.get("merged_question", context.get("question"))
            context["merged_question"] = merged
            context["is_continuous"] = result.get("is_continuous", False)
            # 更新当前使用的问题
            if result.get("is_continuous"):
                context["question"] = merged

        elif tool_name == "identify_algorithm":
            context["algorithm_type"] = result.get("algorithm_type")

        elif tool_name == "extract_parameters":
            context["normalized_query"] = result.get("normalized_query")
            context["required_columns"] = result.get("required_columns", [])
            context["parameter_mapping"] = result.get("parameter_mapping", {})
            context["query_db_result"] = result.get("query_db_result")
            # 提取候选表信息
            qdr = result.get("query_db_result") or {}
            context["candidate_tables"] = qdr.get("candidateTables")
            context["keywords"] = qdr.get("keywords", {})

        elif tool_name == "generate_and_execute_sql":
            context["sql_statement"] = result.get("sql_statement")
            context["execution_result"] = result.get("execution_result", [])
            context["execution_time_ms"] = result.get("execution_time_ms")
            context["data_rows_count"] = result.get("data_rows_count", 0)

        elif tool_name == "execute_algorithm":
            context["algorithm_result"] = result.get("algorithm_result", {})
            context["task_id"] = result.get("task_id")
            context["is_async"] = result.get("is_async", False)

        elif tool_name == "analyze_results":
            context["readable_result"] = result

    def _build_step_response(
        self, tool_name: str, tool_result: Dict[str, Any], context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建单步骤的流式响应数据"""
        result = tool_result.get("result", {})

        if tool_name == "check_follow_up":
            is_cont = result.get("is_continuous", False)
            merged = result.get("merged_question", context.get("question", ""))
            prev = result.get("previous_question", "")
            if is_cont:
                msg = f"用户追问之前的问题：{prev}，故新的问题为：{merged}"
            else:
                msg = f"用户之前的问题为：{prev or '无'}，不是对上一个问题的追问"
            return {
                "is_continuous": is_cont,
                "merged_question": merged,
                "previous_question": prev,
                "message": msg,
            }

        elif tool_name == "identify_algorithm":
            from algorithm.service import ALGORITHM_TYPE_CHINESE_MAP
            from algorithm.models import AlgorithmType

            at_str = result.get("algorithm_type", "")
            try:
                at = AlgorithmType(at_str)
                at_cn = ALGORITHM_TYPE_CHINESE_MAP.get(at, at_str)
            except ValueError:
                at_cn = at_str
            return {
                "algorithm_type": at_str,
                "algorithm_type_chinese": at_cn,
                "message": f"识别到算法类型: {at_cn}",
            }

        elif tool_name == "extract_parameters":
            return {
                "normalized_query": result.get("normalized_query", ""),
                "required_columns": result.get("required_columns", []),
                "parameter_mapping": result.get("parameter_mapping", {}),
                "message": "参数提取完成",
            }

        elif tool_name == "generate_and_execute_sql":
            return {
                "sql_statement": result.get("sql_statement", ""),
                "data_rows_count": result.get("data_rows_count", 0),
                "sample_data": (result.get("execution_result") or [])[:5],
                "execution_time_ms": result.get("execution_time_ms"),
                "message": f"数据检索完成，获取到 {result.get('data_rows_count', 0)} 行数据",
            }

        elif tool_name == "execute_algorithm":
            return {
                "algorithm_result": result.get("algorithm_result", {}),
                "is_async": result.get("is_async", False),
                "task_id": result.get("task_id"),
                "message": "算法执行完成",
            }

        elif tool_name == "analyze_results":
            return {
                "readable_result": result,
                "message": "结果分析完成",
            }

        elif tool_name == "save_question":
            return {
                "saved": result.get("saved", False),
                "session_id": result.get("session_id", ""),
                "message": "问题已保存" if result.get("saved") else "问题保存失败，不影响分析",
            }

        # 默认
        return {"message": f"工具 {tool_name} 执行完成", "result": result}

    def _build_final_response(
        self, context: Dict[str, Any], summary: str
    ) -> Dict[str, Any]:
        """构建最终完成响应"""
        from algorithm.service import ALGORITHM_TYPE_CHINESE_MAP
        from algorithm.models import AlgorithmType

        at_str = context.get("algorithm_type", "")
        try:
            at = AlgorithmType(at_str)
            at_cn = ALGORITHM_TYPE_CHINESE_MAP.get(at, at_str)
        except (ValueError, KeyError):
            at_cn = at_str

        data = {
            "message": summary,
            "algorithm_type": at_str,
            "algorithm_type_chinese": at_cn,
        }

        # 附加可用的上下文数据
        if "sql_statement" in context:
            data["sql_statement"] = context["sql_statement"]
        if "normalized_query" in context:
            data["normalized_query"] = context["normalized_query"]
        if "algorithm_result" in context:
            data["algorithm_result"] = context["algorithm_result"]
        if "readable_result" in context:
            data["readable_result"] = context["readable_result"]
        if "execution_result" in context:
            data["data_summary"] = {
                "input_rows": len(context["execution_result"]),
                "sql_execution_time": context.get("execution_time_ms"),
            }

        return data
