# forecast_modules/trend_analysis/router.py
"""趋势分析模块路由"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import uuid
import logging
import time
import pandas as pd

from .schemas import (
    TrendDecompositionRequest, TrendDecompositionResponse,
    TrendDetectionRequest, TrendDetectionResponse
)
from .core import TrendService

router = APIRouter(prefix="/trend", tags=["趋势分析"])
trend_service = TrendService()
logger = logging.getLogger(__name__)
tasks_store: Dict[str, Any] = {}


def generate_task_id() -> str:
    return f"task_{uuid.uuid4().hex[:8]}"


@router.post("/decomposition", response_model=TrendDecompositionResponse)
async def trend_decomposition(request: TrendDecompositionRequest):
    """趋势分解分析"""
    try:
        logger.info("收到趋势分解请求")
        task_id = generate_task_id()
        series = trend_service.prepare_data([point.dict() for point in request.data])

        period = request.period
        if period is None:
            period = trend_service.detect_seasonal_period(series)

        algorithm = request.algorithm
        if algorithm == "auto":
            algorithm = trend_service.auto_select_decomposition_algorithm(series, period)

        if algorithm == "stl":
            results = trend_service.decompose_trend_stl(series, period, robust=True)
        elif algorithm == "classical":
            results = trend_service.decompose_trend_classical(series, period, model=request.decomposition_model)
        else:
            raise ValueError(f"不支持的算法: {algorithm}")

        return TrendDecompositionResponse(
            success=True, task_id=task_id,
            message=f"趋势分解完成，使用{algorithm.upper()}算法",
            metadata={"period_detected": period, "algorithm_selected": algorithm, "data_points": len(series)},
            results=results
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"趋势分解失败: {e}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")


@router.post("/detection", response_model=TrendDetectionResponse)
async def trend_detection(request: TrendDetectionRequest):
    """趋势检测"""
    try:
        logger.info("收到趋势检测请求")
        series = trend_service.prepare_data([point.dict() for point in request.data])

        method = request.method
        if method == "auto":
            method = trend_service.auto_select_trend_method(series)

        if request.include_seasonal_adjustment:
            try:
                period = trend_service.detect_seasonal_period(series)
                if period and len(series) >= 2 * period:
                    decomposed = trend_service.decompose_trend_classical(series, period, model="additive")
                    adjusted_series = pd.Series(
                        {pd.Timestamp(item['timestamp']): item['value'] for item in decomposed['trend']},
                        dtype=float
                    )
                    series = adjusted_series.dropna()
                    logger.info(f"已进行季节性调整，使用周期: {period}")
            except Exception as e:
                logger.warning(f"季节性调整失败: {e}")

        if method == "mann_kendall":
            results = trend_service.detect_trend_mann_kendall(series, alpha=1 - request.confidence_level)
        elif method == "linear_regression":
            results = trend_service.detect_trend_linear_regression(series, confidence_level=request.confidence_level)
        else:
            raise ValueError(f"不支持的检测方法: {method}")

        task_id = generate_task_id()
        return TrendDetectionResponse(
            success=True, task_id=task_id, results=results, message="趋势检测完成",
            metadata={"method_used": results.get("method", method), "data_points": len(series)}
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"趋势检测失败: {e}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")


@router.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """查询任务状态"""
    task_info = tasks_store.get(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
    return {"task_id": task_id, "status": task_info.get("status", "unknown")}
