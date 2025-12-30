# forecast_service/api/routes/univariate.py
"""
单变量预测API路由
实现 /api/v1/forecast/univariate 端点
返回数据使用中文字段名
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

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/forecast", tags=["单变量预测"])

# 初始化预测器
predictor = AutoUnivariatePredictor()


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
        if 'timestamp' not in data or 'value' not in data:
            raise ValueError("数据必须包含'timestamp'和'value'字段")
        if len(data['timestamp']) != len(data['value']):
            raise ValueError("timestamp和value长度必须一致")
        if len(data['timestamp']) < 10:
            raise ValueError("数据点太少，至少需要10个数据点")
        return data


class UnivariateForecastResponse(BaseModel):
    """单变量预测响应（中文字段名）"""
    是否成功: bool = Field(..., alias="是否成功", description="请求是否成功")
    消息: Optional[str] = Field(default=None, alias="消息", description="响应消息")
    时间戳: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), alias="时间戳", description="响应时间戳")
    使用模型: Optional[str] = Field(default=None, alias="使用模型", description="使用的模型")
    预测列表: Optional[List[Dict[str, Any]]] = Field(default=None, alias="预测列表", description="预测结果列表")
    评估指标: Optional[Dict[str, float]] = Field(default=None, alias="评估指标", description="模型指标")
    处理时间: Optional[float] = Field(default=None, alias="处理时间", description="处理时间(秒)")
    预测结果: Optional[Dict[str, Any]] = Field(default=None, alias="预测结果", description="完整结果")
    数据分析: Optional[Dict[str, Any]] = Field(default=None, alias="数据分析", description="数据分析结果")
    
    model_config = ConfigDict(populate_by_name=True)


# ============ API端点 ============

@router.post(
    "/univariate",
    summary="单变量时序预测",
    description="对单变量时间序列数据进行自动预测，自动选择最佳模型，返回中文字段名"
)
async def univariate_forecast(request: UnivariateForecastRequest) -> Dict[str, Any]:
    """
    单变量预测端点
    
    - **data**: 时序数据，包含timestamp和value两个列表
    - **config**: 配置参数
        - forecast_horizon: 预测步数（默认24）
        - include_confidence: 是否包含置信区间
    
    返回数据使用中文字段名
    """
    try:
        logger.info("收到单变量预测请求")
        start_time = time.time()
        
        # 构造请求数据
        request_data = {
            'data': request.data,
            'config': request.config or {"forecast_horizon": 24, "include_confidence": True}
        }
        
        # 执行预测（返回中文字段名）
        result = predictor.forecast(request_data)
        
        processing_time = time.time() - start_time
        
        # 结果已经是中文字段名，直接使用
        if result.get('是否成功'):
            # 格式化预测结果列表
            predictions = None
            results_data = result.get('预测结果', {})
            if results_data:
                forecast_values = results_data.get('预测值', [])
                timestamps = results_data.get('时间点', [])
                lower_bounds = results_data.get('置信下限', [])
                upper_bounds = results_data.get('置信上限', [])
                
                if forecast_values:
                    predictions = []
                    for i, value in enumerate(forecast_values):
                        pred_item = {
                            '时间戳': timestamps[i] if i < len(timestamps) else None,
                            '数值': value
                        }
                        if i < len(lower_bounds):
                            pred_item['置信下限'] = lower_bounds[i]
                        if i < len(upper_bounds):
                            pred_item['置信上限'] = upper_bounds[i]
                        predictions.append(pred_item)
            
            return {
                "是否成功": True,
                "消息": "预测完成",
                "时间戳": datetime.utcnow().isoformat(),
                "使用模型": result.get('使用模型'),
                "预测列表": predictions,
                "评估指标": results_data.get('评估指标'),
                "处理时间": round(processing_time, 3),
                "预测结果": results_data,
                "数据分析": result.get('数据分析')
            }
        else:
            return {
                "是否成功": False,
                "消息": result.get('消息', '预测失败'),
                "时间戳": datetime.utcnow().isoformat(),
                "使用模型": result.get('使用模型'),
                "处理时间": round(processing_time, 3)
            }
            
    except ValueError as e:
        logger.warning(f"单变量预测参数错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"单变量预测失败: {e}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")
