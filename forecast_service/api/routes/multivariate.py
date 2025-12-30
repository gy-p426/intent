# forecast_service/api/routes/multivariate.py
"""
多变量预测API路由
实现 /api/v1/forecast/multivariate 端点
返回统一输出格式：{"解释": str, "算法结果": dict}
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict, field_validator
import logging
import time
import sys
import os

# 添加父目录到路径以便导入core模块
forecast_service_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, forecast_service_root)

# 导入核心服务
from core.multivariate_forecast.core import MultivariatePredictor
# 导入统一输出格式化器
from core.unified_output_formatter import UnifiedOutputFormatter

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/forecast", tags=["多变量预测"])

# 初始化预测器
predictor = MultivariatePredictor()

# 初始化统一输出格式化器
unified_formatter = UnifiedOutputFormatter()


# ============ 请求/响应模型 ============

class MultivariateForecastRequest(BaseModel):
    """多变量预测请求"""
    model_config = ConfigDict(
        protected_namespaces=(),
        json_schema_extra={
            "example": {
                "data": [
                    {"timestamp": "2024-01-01 00:00", "target": 1000, "price": 99, "promotion": 1},
                    {"timestamp": "2024-01-01 01:00", "target": 1050, "price": 95, "promotion": 1}
                ],
                "config": {
                    "target_column": "target",
                    "algorithm": "random_forest",
                    "forecast_horizon": 14
                }
            }
        }
    )
    
    data: List[Dict[str, Any]] = Field(..., description="多变量时序数据")
    config: Optional[Dict[str, Any]] = Field(default=None, description="配置参数")

    @field_validator('data')
    @classmethod
    def validate_data(cls, data):
        if len(data) < 10:
            raise ValueError("数据点太少，至少需要10个数据点")
        if not all('timestamp' in d for d in data):
            raise ValueError("每个数据点必须包含 timestamp 字段")
        return data


class MultivariateForecastResponse(BaseModel):
    """多变量预测响应 - 统一输出格式"""
    解释: str = Field(..., description="面向用户的通俗分析结论")
    算法结果: Dict[str, Any] = Field(..., description="算法特定的详细数据")
    
    model_config = ConfigDict(populate_by_name=True)


# ============ API端点 ============

@router.post(
    "/multivariate",
    response_model=MultivariateForecastResponse,
    summary="多变量时序预测",
    description="对多变量时间序列数据进行预测，支持多种机器学习算法，返回统一输出格式"
)
async def multivariate_forecast(request: MultivariateForecastRequest) -> Dict[str, Any]:
    """
    多变量预测端点
    
    - **data**: 多变量时序数据列表
    - **config**: 配置参数
        - target_column: 目标列名（默认"target"）
        - feature_columns: 特征列名列表（可选，自动推断）
        - algorithm: 算法（lightgbm/xgboost/random_forest/linear_regression）
        - forecast_horizon: 预测步数（默认14）
        - model_name: 模型名称（用于保存和复用）
        - use_model_id: 复用指定ID的模型
        - use_model_name: 复用指定名称的模型
    
    返回统一输出格式：{"解释": str, "算法结果": dict}
    """
    try:
        logger.info("收到多变量预测请求")
        start_time = time.time()
        
        # 构造请求数据
        request_data = {
            'data': request.data,
            'config': request.config or {}
        }
        
        # 执行预测（返回原始结果）
        result = predictor.forecast(request_data)
        
        processing_time = time.time() - start_time
        logger.info(f"多变量预测完成，耗时: {processing_time:.3f}秒")
        
        # 使用统一格式化器转换输出
        unified_output = unified_formatter.format_multivariate_forecast(result)
        
        # 返回统一格式的响应
        return unified_output
            
    except ValueError as e:
        logger.warning(f"多变量预测参数错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"多变量预测失败: {e}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")
