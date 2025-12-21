"""
API数据模型定义

定义了意图识别服务和算法集成服务的所有API请求和响应模型，包括：
- IntentEntry: 知识库条目
- IntentCandidate: 检索候选结果
- IntentRecognitionRequest: API请求模型
- IntentRecognitionResponse: API响应模型
- IntentResult: 意图识别结果
- HealthCheckResponse: 健康检查响应模型
- AlgorithmRequest: 算法请求模型
- AlgorithmStreamResponse: 算法流式响应模型
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from services.intent_recognition_service import IntentResult


class IntentEntry(BaseModel):
    """知识库条目"""
    text: str  # 用户问题示例
    intent: str  # 对应的微服务名称


class IntentCandidate(BaseModel):
    """检索候选结果"""
    intent: str  # 微服务名称
    text: str  # 匹配的问题文本
    score: float  # 相似度分数


class IntentRecognitionRequest(BaseModel):
    """API请求模型"""
    question: str = Field(..., min_length=1, max_length=500, description="用户问题文本")
    top_k: int = Field(default=20, ge=1, le=100, description="返回的候选微服务数量")


# IntentResult is imported from services.intent_recognition_service
# to avoid duplication and maintain consistency


class IntentRecognitionResponse(BaseModel):
    """API响应模型"""
    code: int  # 响应状态码
    message: str  # 响应消息
    data: Optional[IntentResult] = None  # 响应数据


class HealthCheckResponse(BaseModel):
    """健康检查响应模型"""
    status: str  # 服务状态
    service: str  # 服务名称
    timestamp: str  # 时间戳
    checks: Dict[str, str]  # 各组件检查状态


class ErrorResponse(BaseModel):
    """错误响应模型"""
    code: int  # 错误状态码
    message: str  # 错误消息
    data: Optional[Any] = None  # 错误详情


# Algorithm Integration API Models
class AlgorithmRequest(BaseModel):
    """算法请求模型"""
    question: str = Field(..., min_length=1, max_length=1000, description="用户自然语言查询")
    window_id: str = Field(default="default", description="窗口ID")
    session_id: str = Field(..., description="会话ID")
    stream: bool = Field(default=True, description="是否流式返回")


class AlgorithmStreamResponse(BaseModel):
    """算法流式响应模型"""
    step: str = Field(..., description="当前执行步骤")
    status: str = Field(..., description="状态: processing/completed/error")
    data: Optional[Dict[str, Any]] = Field(None, description="步骤数据")
    error: Optional[str] = Field(None, description="错误信息")
    timestamp: str = Field(..., description="时间戳")