# forecast_service/api/routes/univariate.py
"""
单变量预测API路由
实现 /api/v1/forecast/univariate 端点
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
from core.auto_univariate_forecast.core import AutoUnivariatePredictor
# 导入统一输出格式化器
from core.unified_output_formatter import UnifiedOutputFormatter

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/forecast", tags=["单变量预测"])

# 初始化预测器
predictor = AutoUnivariatePredictor()

# 初始化统一输出格式化器
unified_formatter = UnifiedOutputFormatter()


# ============ 请求/响应模型 ============

class UnivariateForecastRequest(BaseModel):
    """单变量预测请求"""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": {
                    "timestamp": ["2024-01-01 00:00", "2024-01-01 01:00", "2024-01-01 02:00"],
                    "value": [100, 105, 110]
                },
                "config": {
                    "forecast_horizon": 24,
                    "include_confidence": True
                }
            }
        }
    )
    
    data: Dict[str, Any] = Field(..., description="时序数据，包含timestamp和value列表")
    config: Optional[Dict[str, Any]] = Field(
        default_factory=lambda: {"forecast_horizon": 24, "include_confidence": True},
        description="配置参数"
    )
    
    @field_validator('data')
    @classmethod
    def validate_data_structure(cls, data):
        # 格式1: {"timestamp": [...], "value": [...]}
        if 'timestamp' in data and 'value' in data:
            if len(data['timestamp']) != len(data['value']):
                raise ValueError("timestamp和value长度必须一致")
            if len(data['timestamp']) < 10:
                raise ValueError("数据点太少，至少需要10个数据点")
            return data
        
        # 格式2: {"sample_data": [...]}
        if 'sample_data' in data:
            if len(data['sample_data']) < 10:
                raise ValueError("数据点太少，至少需要10个数据点")
            return data
        
        # 格式3: 直接是对象数组（这种情况在这里不会触发，因为data已经是dict）
        raise ValueError("数据必须包含'timestamp'和'value'字段，或'sample_data'字段")
        return data


class UnivariateForecastResponse(BaseModel):
    """单变量预测响应 - 统一输出格式"""
    解释: str = Field(..., description="面向用户的通俗分析结论")
    算法结果: Dict[str, Any] = Field(..., description="算法特定的详细数据")
    
    model_config = ConfigDict(populate_by_name=True)


# ============ API端点 ============

@router.post(
    "/univariate",
    response_model=UnivariateForecastResponse,
    summary="单变量时序预测",
    description="对单变量时间序列数据进行自动预测，自动选择最佳模型，返回统一输出格式"
)
async def univariate_forecast(request: UnivariateForecastRequest) -> Dict[str, Any]:
    """
    单变量预测端点
    
    - **data**: 时序数据，包含timestamp和value两个列表
    - **config**: 配置参数
        - forecast_horizon: 预测步数（默认24）
        - include_confidence: 是否包含置信区间
    
    返回统一输出格式：{"解释": str, "算法结果": dict}
    """
    try:
        logger.info("收到单变量预测请求")
        start_time = time.time()
        
        # 构造请求数据
        request_data = {
            'data': request.data,
            'config': request.config or {"forecast_horizon": 24, "include_confidence": True}
        }
        
        # 执行预测（返回原始结果）
        result = predictor.forecast(request_data)
        
        processing_time = time.time() - start_time
        logger.info(f"单变量预测完成，耗时: {processing_time:.3f}秒")
        
        # 使用统一格式化器转换输出
        unified_output = unified_formatter.format_univariate_forecast(result)
        
        # 返回统一格式的响应
        return unified_output
            
    except ValueError as e:
        logger.warning(f"单变量预测参数错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"单变量预测失败: {e}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")
