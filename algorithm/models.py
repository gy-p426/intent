"""
Algorithm Integration Data Models

Defines all data models and interfaces for the algorithm integration service,
including request/response models, configuration models, and internal data structures.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union, AsyncGenerator
from enum import Enum
from pydantic import BaseModel, Field


class AlgorithmType(str, Enum):
    """支持的算法类型枚举"""
    CLUSTER = "cluster"
    CLASSIFY = "classify"
    PREDICT = "predict"
    ANOMALY = "anomaly"         # 异常检测统一类型
    # DBSCAN = "dbscan"          # 注释掉，统一使用ANOMALY
    # IFOREST = "iforest"        # 注释掉，统一使用ANOMALY
    ASSOCIATE = "associate"
    COMPARE = "compare"
    SIMILARITY = "similarity"
    TREND = "trend"
    PROFILE = "profile"
    CAUSALITY = "causality"
    ALERT = "alert"
    RECOMMEND = "recommend"
    COMPARE_PROPORTION = "compare_proportion"
    MULTI_ANALYSIS = "multi_analysis"  # 统一多算法分析（周期性、环比、同比、定基比）


class ResponseFormat(str, Enum):
    """响应格式类型"""
    SYNC = "sync"
    ASYNC = "async"
    SYNC_OR_ASYNC = "sync_or_async"


class StreamingStep(str, Enum):
    """流式响应步骤"""
    ALGORITHM_IDENTIFICATION = "algorithm_identification"
    PARAMETER_EXTRACTION = "parameter_extraction"
    # 手动模式：用户选择数据库/列信息的交互步骤
    MANUAL_DB_SELECTION = "manual_db_selection"
    SQL_GENERATION = "sql_generation"
    DATA_RETRIEVAL = "data_retrieval"
    ALGORITHM_EXECUTION = "algorithm_execution"
    TASK_POLLING = "task_polling"
    AGENT_ALGORITHM_ANALYSIS = "agent_algorithm_analysis"  # Agent算法分析步骤
    COMPLETED = "completed"
    ERROR = "error"


class AlgorithmField(BaseModel):
    """算法字段定义"""
    field: str = Field(..., description="字段名称")
    type: str = Field(..., description="字段类型")
    description: str = Field(..., description="字段描述")
    default: Optional[Any] = Field(None, description="默认值")
    options: Optional[List[str]] = Field(None, description="可选值列表")


class AlgorithmConfig(BaseModel):
    """算法配置模型"""
    name: str = Field(..., description="算法名称")
    description: str = Field(..., description="算法描述")
    api_endpoint: str = Field(..., description="API端点")
    method: str = Field(default="POST", description="HTTP方法")
    required_fields: List[AlgorithmField] = Field(..., description="必需字段")
    optional_fields: List[AlgorithmField] = Field(default_factory=list, description="可选字段")
    data_format: str = Field(..., description="数据格式")
    sql_template: Optional[str] = Field(None, description="SQL模板")
    response_format: ResponseFormat = Field(default=ResponseFormat.SYNC, description="响应格式")
    examples: List[str] = Field(default_factory=list, description="示例查询")
    intent_keywords: Optional[List[str]] = Field(None, description="意图关键词")


class DatabaseColumn(BaseModel):
    """数据库列信息"""
    table_name: str = Field(..., description="表名")
    column_name: str = Field(..., description="列名")
    column_comment: str = Field(..., description="列注释")
    data_type: str = Field(..., description="数据类型")
    is_nullable: bool = Field(..., description="是否可为空")
    column_default: Optional[str] = Field(None, description="默认值")


class AlgorithmRequest(BaseModel):
    """算法请求模型"""
    question: str = Field(..., min_length=1, max_length=1000, description="用户自然语言查询")
    window_id: str = Field(default="default", description="窗口ID")
    session_id: str = Field(..., description="会话ID")
    # None/True: 走现有自动分析；False: 手动选择数据库信息（新增交互步骤2.1）
    auto_analysis: Optional[bool] = Field(default=None, description="是否自动分析；None/true=自动；false=手动选择数据库信息")
    stream: bool = Field(default=True, description="是否流式返回")
    agent_algorithm: bool = Field(default=False, description="是否使用Agent算法分析")  # 新增


class AlgorithmParameters(BaseModel):
    """算法参数模型"""
    algorithm_type: AlgorithmType = Field(..., description="算法类型")
    normalized_query: str = Field(..., description="规范化查询语句")
    parameter_mapping: Dict[str, Any] = Field(..., description="参数映射")
    required_columns: List[str] = Field(..., description="所需数据库列")
    sql_queries: Dict[str, str] = Field(default_factory=dict, description="生成的SQL查询")
    query_db_result: Optional[Dict[str, Any]] = Field(None, description="query-db接口的结果，包含候选表和关键词")


class NL2SQLRequest(BaseModel):
    """NL2SQL请求模型"""
    question: str = Field(..., description="查询问题")
    window_id: str = Field(..., description="窗口ID")
    session_id: str = Field(..., description="会话ID")


class NL2SQLResponse(BaseModel):
    """NL2SQL响应模型"""
    sql_statement: str = Field(..., description="生成的SQL语句")
    execution_result: List[Dict[str, Any]] = Field(..., description="执行结果")
    execution_time_ms: int = Field(..., description="执行时间(毫秒)")
    error: Optional[str] = Field(None, description="错误信息")


class ManualDBSelectionRequest(BaseModel):
    """手动模式第二段：用户已选择列 -> 生成新的 normalized_query"""
    manual_selection_token: str = Field(..., description="手动选择流程 token（第一次 /execute 返回）")
    manual_parameter_mapping: Dict[str, Any] = Field(..., description="算法字段 -> 选中的 table/column 等信息（字段直映射）")
    user_feedback: Optional[str] = Field(None, description="用户补充说明/反馈（可选）")
    stream: bool = Field(default=True, description="是否流式返回")


class ManualRunRequest(BaseModel):
    """手动模式第三段：用户确认 normalized_query 后执行 Step3/4 全流程"""
    manual_selection_token: str = Field(..., description="手动选择流程 token（第一次 /execute 返回）")
    normalized_query: str = Field(..., min_length=1, description="用户确认后的 normalized_query")
    manual_parameter_mapping: Dict[str, Any] = Field(..., description="算法字段 -> 选中的 table/column 等信息（字段直映射）")
    stream: bool = Field(default=True, description="是否流式返回")


class AlgorithmExecutionRequest(BaseModel):
    """算法执行请求模型"""
    data_rows: List[Dict[str, Any]] = Field(..., description="数据行")
    config: Dict[str, Any] = Field(..., description="算法配置")
    data_sets: Optional[List[Dict[str, Any]]] = Field(None, description="训练数据集(分类算法)")


class AlgorithmExecutionResponse(BaseModel):
    """算法执行响应模型"""
    result: Optional[Dict[str, Any]] = Field(None, description="同步执行结果")
    task_id: Optional[str] = Field(None, description="异步任务ID")
    status: str = Field(..., description="执行状态")
    message: str = Field(..., description="状态消息")
    readable_result: Optional[Union[str, Dict[str, Any]]] = Field(None, description="可读性格式化结果，支持字符串或结构化格式")


class LLMAnalysisResult(BaseModel):
    """大模型分析结果模型"""
    llm_analysis: str = Field(..., description="大模型生成的自然语言分析")
    technical_details: Dict[str, Any] = Field(..., description="技术细节和原始结果")
    analysis_source: str = Field(..., description="分析来源：llm_enhanced, fallback, technical_only")
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow, description="分析时间戳")


class TaskStatus(str, Enum):
    """任务状态枚举"""
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"


class AsyncTaskResponse(BaseModel):
    """异步任务响应模型"""
    task_id: str = Field(..., description="任务ID")
    status: TaskStatus = Field(..., description="任务状态")
    progress: Optional[Dict[str, Any]] = Field(None, description="进度信息")
    result: Optional[Dict[str, Any]] = Field(None, description="最终结果")
    error: Optional[str] = Field(None, description="错误信息")
    logs: Optional[List[str]] = Field(None, description="训练日志")
    metrics: Optional[Dict[str, Any]] = Field(None, description="任务指标")


class AlgorithmResponse(BaseModel):
    """算法流式响应模型"""
    step: StreamingStep = Field(..., description="当前执行步骤")
    status: str = Field(..., description="状态: processing/completed/error")
    data: Optional[Dict[str, Any]] = Field(None, description="步骤数据")
    error: Optional[str] = Field(None, description="错误信息")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="时间戳")


class AlgorithmResult(BaseModel):
    """最终算法结果模型"""
    algorithm_type: AlgorithmType = Field(..., description="算法类型")
    normalized_query: str = Field(..., description="规范化查询")
    sql_statement: str = Field(..., description="SQL语句")
    algorithm_input: Dict[str, Any] = Field(..., description="算法输入")
    algorithm_output: Dict[str, Any] = Field(..., description="算法输出")
    execution_time_ms: int = Field(..., description="执行时间(毫秒)")
    task_id: Optional[str] = Field(None, description="异步任务ID")


class ErrorResponse(BaseModel):
    """错误响应模型"""
    step: StreamingStep = Field(default=StreamingStep.ERROR, description="错误步骤")
    status: str = Field(default="error", description="状态")
    error_code: str = Field(..., description="错误代码")
    error_message: str = Field(..., description="错误消息")
    error_details: Optional[Dict[str, Any]] = Field(None, description="错误详情")
    suggestions: Optional[List[str]] = Field(None, description="建议")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="时间戳")


# Type aliases for better code readability
AlgorithmResponseGenerator = AsyncGenerator[AlgorithmResponse, None]
StreamingResponseData = Union[AlgorithmResponse, ErrorResponse]