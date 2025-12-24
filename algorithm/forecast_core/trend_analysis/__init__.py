# forecast_modules/trend_analysis/__init__.py
"""
趋势分析模块

提供时间序列趋势分解和趋势检测功能。

使用示例:
    from forecast_modules.trend_analysis import router
    app.include_router(router, prefix="/api/v1")

    # 或直接使用服务
    from forecast_modules.trend_analysis import TrendService
    service = TrendService()
    result = service.decompose_trend_stl(series, period=24)
"""
from .router import router
from .schemas import (
    TimeSeriesPoint,
    TrendDecompositionRequest,
    TrendDecompositionResponse,
    TrendDetectionRequest,
    TrendDetectionResponse,
)
from .core import TrendService

__all__ = [
    "router",
    "TimeSeriesPoint",
    "TrendDecompositionRequest",
    "TrendDecompositionResponse",
    "TrendDetectionRequest",
    "TrendDetectionResponse",
    "TrendService",
]
__version__ = "1.0.0"
