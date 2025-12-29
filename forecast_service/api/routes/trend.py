# forecast_service/api/routes/trend.py
"""
趋势分析API路由
实现 /api/v1/trend/decomposition 和 /api/v1/trend/detection 端点
"""
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict
import uuid
import logging
import sys
import os

# 添加父目录到路径以便导入core模块
forecast_service_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, forecast_service_root)

# 导入核心服务
from core.trend_analysis.core import TrendService

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/trend", tags=["趋势分析"])

# 初始化趋势分析服务
trend_service = TrendService()


# ============ 请求/响应模型 ============

class TimeSeriesPoint(BaseModel):
    """时间序列数据点"""
    timestamp: Union[str, datetime]
    value: float


class TrendDecompositionRequest(BaseModel):
    """趋势分解请求"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {"timestamp": "2024-01-01 00:00", "value": 45},
                    {"timestamp": "2024-01-01 01:00", "value": 48}
                ],
                "period": 24,
                "decomposition_model": "additive",
                "algorithm": "auto"
            }
        }
    )
    
    data: List[TimeSeriesPoint] = Field(..., description="时间序列数据")
    period: Optional[int] = Field(default=None, ge=2, description="季节周期，None时自动检测")
    decomposition_model: str = Field(default="additive", description="分解模型：additive 或 multiplicative")
    algorithm: str = Field(default="auto", description="算法：auto/stl/classical")


class TrendDetectionRequest(BaseModel):
    """趋势检测请求"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {"timestamp": "2024-01-01", "value": 100},
                    {"timestamp": "2024-01-02", "value": 110}
                ],
                "method": "auto",
                "confidence_level": 0.95,
                "include_seasonal_adjustment": True
            }
        }
    )
    
    data: List[TimeSeriesPoint] = Field(..., description="时间序列数据")
    method: str = Field(default="auto", description="检测方法：auto/mann_kendall/linear_regression")
    confidence_level: float = Field(default=0.95, ge=0.5, le=0.99, description="置信水平")
    include_seasonal_adjustment: bool = Field(default=True, description="是否先去除季节性")


class TrendDecompositionResponse(BaseModel):
    """趋势分解响应"""
    success: bool = Field(..., description="请求是否成功")
    task_id: str = Field(..., description="任务ID")
    message: Optional[str] = Field(default=None, description="响应消息")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="响应时间戳")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    results: Dict[str, Any] = Field(default_factory=dict, description="分解结果")


class TrendDetectionResponse(BaseModel):
    """趋势检测响应"""
    success: bool = Field(..., description="请求是否成功")
    task_id: str = Field(..., description="任务ID")
    message: Optional[str] = Field(default=None, description="响应消息")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="响应时间戳")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    results: Dict[str, Any] = Field(default_factory=dict, description="检测结果")


# ============ 辅助函数 ============

def generate_task_id() -> str:
    """生成任务ID"""
    return f"trend_{uuid.uuid4().hex[:8]}"


# ============ API端点 ============

@router.post(
    "/decomposition",
    response_model=TrendDecompositionResponse,
    summary="趋势分解",
    description="对时间序列数据进行趋势分解，提取趋势、季节性和残差成分"
)
async def trend_decomposition(request: TrendDecompositionRequest) -> TrendDecompositionResponse:
    """
    趋势分解端点
    
    - **data**: 时间序列数据点列表
    - **period**: 季节周期（可选，自动检测）
    - **decomposition_model**: 分解模型类型（additive/multiplicative）
    - **algorithm**: 分解算法（auto/stl/classical）
    """
    try:
        logger.info(f"收到趋势分解请求，数据点数量: {len(request.data)}")
        task_id = generate_task_id()
        
        # 检查最小数据量
        if len(request.data) < 4:
            raise ValueError(f"数据点数量不足，至少需要4个数据点，当前只有{len(request.data)}个")
        
        # 准备数据
        data_points = [point.model_dump() for point in request.data]
        series = trend_service.prepare_data(data_points)
        
        # 确定周期
        period = request.period
        if period is None:
            period = trend_service.detect_seasonal_period(series)
            logger.info(f"自动检测到季节周期: {period}")
        
        # 如果周期仍为 None 或数据量不足，使用默认周期
        if period is None:
            period = min(len(series) // 2, 7)  # 默认周期，最大为7
            logger.info(f"无法检测周期，使用默认周期: {period}")
        
        # 根据数据量自动调整算法
        algorithm = request.algorithm
        min_data_for_classical = 2 * period
        
        if algorithm == "auto":
            # 自动选择：数据量足够用 classical，否则用 stl
            if len(series) >= min_data_for_classical:
                algorithm = trend_service.auto_select_decomposition_algorithm(series, period)
            else:
                algorithm = "stl"
                logger.info(f"数据量({len(series)})不足以使用经典分解(需要{min_data_for_classical})，自动切换到STL算法")
        elif algorithm == "classical" and len(series) < min_data_for_classical:
            # 用户指定 classical 但数据量不足，自动降级到 stl
            logger.warning(f"数据量({len(series)})不足以使用经典分解(需要{min_data_for_classical})，自动切换到STL算法")
            algorithm = "stl"
        
        logger.info(f"使用算法: {algorithm}, 周期: {period}, 数据点: {len(series)}")
        
        # 执行分解
        if algorithm == "stl":
            results = trend_service.decompose_trend_stl(series, period, robust=True)
        elif algorithm == "classical":
            results = trend_service.decompose_trend_classical(
                series, period, model=request.decomposition_model
            )
        else:
            raise ValueError(f"不支持的算法: {algorithm}")
        
        # 生成通俗易懂的摘要
        readable_summary = trend_service.generate_readable_summary(results, "decomposition")
        results["readable_summary"] = readable_summary
        
        return TrendDecompositionResponse(
            success=True,
            task_id=task_id,
            message=readable_summary.get("title", f"趋势分解完成，使用{algorithm.upper()}算法"),
            timestamp=datetime.utcnow().isoformat(),
            metadata={
                "period_detected": period,
                "algorithm_selected": algorithm,
                "data_points": len(series),
                "decomposition_model": request.decomposition_model,
                "algorithm_auto_adjusted": algorithm != request.algorithm
            },
            results=results
        )
        
    except ValueError as e:
        logger.warning(f"趋势分解参数错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"趋势分解失败: {e}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")


@router.post(
    "/detection",
    response_model=TrendDetectionResponse,
    summary="趋势检测",
    description="检测时间序列数据中的趋势方向和统计显著性"
)
async def trend_detection(request: TrendDetectionRequest) -> TrendDetectionResponse:
    """
    趋势检测端点
    
    - **data**: 时间序列数据点列表
    - **method**: 检测方法（auto/mann_kendall/linear_regression）
    - **confidence_level**: 置信水平
    - **include_seasonal_adjustment**: 是否进行季节性调整
    """
    try:
        logger.info("收到趋势检测请求")
        task_id = generate_task_id()
        
        # 准备数据
        data_points = [point.model_dump() for point in request.data]
        series = trend_service.prepare_data(data_points)
        
        # 选择方法
        method = request.method
        if method == "auto":
            method = trend_service.auto_select_trend_method(series)
            logger.info(f"自动选择检测方法: {method}")
        
        # 季节性调整
        import pandas as pd
        if request.include_seasonal_adjustment:
            try:
                period = trend_service.detect_seasonal_period(series)
                if period and len(series) >= 2 * period:
                    decomposed = trend_service.decompose_trend_classical(
                        series, period, model="additive"
                    )
                    adjusted_series = pd.Series(
                        {pd.Timestamp(item['timestamp']): item['value'] 
                         for item in decomposed['trend']},
                        dtype=float
                    )
                    series = adjusted_series.dropna()
                    logger.info(f"已进行季节性调整，使用周期: {period}")
            except Exception as e:
                logger.warning(f"季节性调整失败，使用原始数据: {e}")
        
        # 执行检测
        if method == "mann_kendall":
            results = trend_service.detect_trend_mann_kendall(
                series, alpha=1 - request.confidence_level
            )
        elif method == "linear_regression":
            results = trend_service.detect_trend_linear_regression(
                series, confidence_level=request.confidence_level
            )
        else:
            raise ValueError(f"不支持的检测方法: {method}")
        
        # 生成通俗易懂的摘要
        readable_summary = trend_service.generate_readable_summary(results, "detection")
        results["readable_summary"] = readable_summary
        
        return TrendDetectionResponse(
            success=True,
            task_id=task_id,
            message=readable_summary.get("title", "趋势检测完成"),
            timestamp=datetime.utcnow().isoformat(),
            metadata={
                "method_used": results.get("method", method),
                "data_points": len(series),
                "confidence_level": request.confidence_level,
                "seasonal_adjustment": request.include_seasonal_adjustment
            },
            results=results
        )
        
    except ValueError as e:
        logger.warning(f"趋势检测参数错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"趋势检测失败: {e}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")
