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
# 导入字段映射工具
from core.field_mapper import FieldMapper
# 导入统一输出格式化器
from core.unified_output_formatter import UnifiedOutputFormatter

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/trend", tags=["趋势分析"])

# 初始化趋势分析服务
trend_service = TrendService()

# 初始化统一输出格式化器
unified_formatter = UnifiedOutputFormatter()


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
    """趋势分解响应 - 统一输出格式"""
    解释: str = Field(..., description="面向用户的通俗分析结论")
    算法结果: Dict[str, Any] = Field(..., description="算法特定的详细数据")
    
    model_config = ConfigDict(populate_by_name=True)


class TrendDetectionResponse(BaseModel):
    """趋势检测响应 - 统一输出格式"""
    解释: str = Field(..., description="面向用户的通俗分析结论")
    算法结果: Dict[str, Any] = Field(..., description="算法特定的详细数据")
    
    model_config = ConfigDict(populate_by_name=True)


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
async def trend_decomposition(request: TrendDecompositionRequest) -> Dict[str, Any]:
    """
    趋势分解端点
    
    - **data**: 时间序列数据点列表
    - **period**: 季节周期（可选，自动检测）
    - **decomposition_model**: 分解模型类型（additive/multiplicative）
    - **algorithm**: 分解算法（auto/stl/classical）
    """
    try:
        logger.info(f"收到趋势分解请求，数据点数量: {len(request.data)}")
        
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
        
        # STL 算法也需要至少 2 个完整周期，自动调整周期
        min_data_for_stl = 2 * period
        if algorithm == "stl" and len(series) < min_data_for_stl:
            # 自动调整周期，确保数据量足够
            max_period = len(series) // 2
            if max_period >= 2:
                old_period = period
                period = max_period
                logger.info(f"数据量({len(series)})不足以使用周期{old_period}进行STL分解，自动调整周期为{period}")
            else:
                raise ValueError(f"数据点数量({len(series)})太少，无法进行趋势分解，至少需要4个数据点")
        
        logger.info(f"使用算法: {algorithm}, 周期: {period}, 数据点: {len(series)}")
        
        # 执行分解
        if algorithm == "stl":
            decomposition_results = trend_service.decompose_trend_stl(series, period, robust=True)
        elif algorithm == "classical":
            decomposition_results = trend_service.decompose_trend_classical(
                series, period, model=request.decomposition_model
            )
        else:
            raise ValueError(f"不支持的算法: {algorithm}")
        
        # 分析数据特征
        data_characteristics = trend_service.analyze_data_characteristics(series)
        
        # 生成通俗易懂的摘要
        readable_summary = trend_service.generate_readable_summary(decomposition_results, "decomposition")
        
        # 构建原始结果（用于格式化器）
        raw_result = {
            "数据特征": data_characteristics,
            "分解结果": decomposition_results,
            "通俗摘要": readable_summary,
            "分析类型": "decomposition",
            "使用算法": algorithm.upper(),
            "使用周期": period
        }
        
        # 使用统一格式化器转换输出
        unified_output = unified_formatter.format_trend_decomposition(raw_result)
        
        # 返回统一格式的响应
        return unified_output
        
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
async def trend_detection(request: TrendDetectionRequest) -> Dict[str, Any]:
    """
    趋势检测端点
    
    - **data**: 时间序列数据点列表
    - **method**: 检测方法（auto/mann_kendall/linear_regression）
    - **confidence_level**: 置信水平
    - **include_seasonal_adjustment**: 是否进行季节性调整
    """
    try:
        logger.info("收到趋势检测请求")
        
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
                    # 适配中文字段名
                    trend_data = decomposed.get('趋势分量', decomposed.get('trend', []))
                    adjusted_series = pd.Series(
                        {pd.Timestamp(item['时间戳'] if '时间戳' in item else item['timestamp']): 
                         item['数值'] if '数值' in item else item['value'] 
                         for item in trend_data},
                        dtype=float
                    )
                    series = adjusted_series.dropna()
                    logger.info(f"已进行季节性调整，使用周期: {period}")
            except Exception as e:
                logger.warning(f"季节性调整失败，使用原始数据: {e}")
        
        # 执行检测
        if method == "mann_kendall":
            detection_results = trend_service.detect_trend_mann_kendall(
                series, alpha=1 - request.confidence_level
            )
        elif method == "linear_regression":
            detection_results = trend_service.detect_trend_linear_regression(
                series, confidence_level=request.confidence_level
            )
        else:
            raise ValueError(f"不支持的检测方法: {method}")
        
        # 分析数据特征
        data_characteristics = trend_service.analyze_data_characteristics(series)
        
        # 生成通俗易懂的摘要
        readable_summary = trend_service.generate_readable_summary(detection_results, "detection")
        
        # 构建原始结果（用于格式化器）
        raw_result = {
            "数据特征": data_characteristics,
            "检测结果": detection_results,
            "通俗摘要": readable_summary,
            "分析类型": "detection",
            "使用方法": detection_results.get("检测方法", method)
        }
        
        # 使用统一格式化器转换输出
        unified_output = unified_formatter.format_trend_detection(raw_result)
        
        # 返回统一格式的响应
        return unified_output
        
    except ValueError as e:
        logger.warning(f"趋势检测参数错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"趋势检测失败: {e}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")
