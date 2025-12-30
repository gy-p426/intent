# forecast_service/api/routes/multivariate.py
"""
多变量预测API路由
实现 /api/v1/forecast/multivariate 端点
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
from core.multivariate_forecast.core import MultivariatePredictor

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/forecast", tags=["多变量预测"])

# 初始化预测器
predictor = MultivariatePredictor()


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
    """多变量预测响应（中文字段名）"""
    model_config = ConfigDict(protected_namespaces=(), populate_by_name=True)
    
    是否成功: bool = Field(..., alias="是否成功", description="请求是否成功")
    消息: Optional[str] = Field(default=None, alias="消息", description="响应消息")
    时间戳: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), alias="时间戳", description="响应时间戳")
    模型ID: Optional[str] = Field(default=None, alias="模型ID", description="模型ID")
    模型名称: Optional[str] = Field(default=None, alias="模型名称", description="模型名称")
    使用模型: Optional[str] = Field(default=None, alias="使用模型", description="使用的算法")
    预测列表: Optional[List[Dict[str, Any]]] = Field(default=None, alias="预测列表", description="预测结果")
    评估指标: Optional[Dict[str, float]] = Field(default=None, alias="评估指标", description="模型指标")
    是否复用模型: bool = Field(default=False, alias="是否复用模型", description="是否复用已有模型")
    处理时间: Optional[float] = Field(default=None, alias="处理时间", description="处理时间(秒)")
    预测结果: Optional[Dict[str, Any]] = Field(default=None, alias="预测结果", description="完整结果")
    数据分析: Optional[Dict[str, Any]] = Field(default=None, alias="数据分析", description="数据分析结果")


# ============ API端点 ============

@router.post(
    "/multivariate",
    summary="多变量时序预测",
    description="对多变量时间序列数据进行预测，支持多种机器学习算法，返回中文字段名"
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
    
    返回数据使用中文字段名
    """
    try:
        logger.info("收到多变量预测请求")
        start_time = time.time()
        
        # 构造请求数据
        request_data = {
            'data': request.data,
            'config': request.config or {}
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
                
                if forecast_values and timestamps:
                    predictions = [
                        {'时间戳': ts, '数值': val}
                        for ts, val in zip(timestamps, forecast_values)
                    ]
            
            return {
                "是否成功": True,
                "消息": "预测完成",
                "时间戳": datetime.utcnow().isoformat(),
                "模型ID": result.get('模型ID'),
                "模型名称": result.get('模型名称'),
                "使用模型": result.get('使用模型'),
                "预测列表": predictions,
                "评估指标": result.get('评估指标'),
                "是否复用模型": result.get('是否复用模型', False),
                "处理时间": round(processing_time, 3),
                "预测结果": results_data,
                "数据分析": result.get('数据分析')
            }
        else:
            return {
                "是否成功": False,
                "消息": result.get('消息', '预测失败'),
                "时间戳": datetime.utcnow().isoformat(),
                "处理时间": round(processing_time, 3)
            }
            
    except ValueError as e:
        logger.warning(f"多变量预测参数错误: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"多变量预测失败: {e}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")
