# forecast_service/core/multivariate_forecast/router.py
"""多变量预测路由"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import time
import logging

from .schemas import MultivariateForecastRequest, MultivariateForecastResponse
from .core.predictor import MultivariatePredictor
from .core.model_manager import ModelManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/forecast", tags=["多变量预测"], responses={404: {"description": "未找到"}})

_predictor = None
_model_manager = None


def get_predictor():
    global _predictor
    if _predictor is None:
        _predictor = MultivariatePredictor()
    return _predictor


def get_model_manager():
    global _model_manager
    if _model_manager is None:
        _model_manager = ModelManager()
    return _model_manager


@router.post("/multivariate", response_model=MultivariateForecastResponse)
async def multivariate_forecast(request: MultivariateForecastRequest):
    """多变量时序预测"""
    try:
        start_time = time.time()
        predictor = get_predictor()
        result = predictor.forecast(request.model_dump())
        
        if not result.get('success'):
            raise HTTPException(400, detail=result.get('message', '预测失败'))
        
        if not result.get('reused_model') and result.get('model_id'):
            try:
                manager = get_model_manager()
                model_info = predictor.models.get(result['model_id'])
                if model_info:
                    config = request.config or {}
                    manager.save_model(
                        result['model_id'], model_info['model'],
                        {'algorithm': result['model_used'], 'target_column': model_info['target_column'],
                         'feature_columns': model_info['feature_columns'], 'metrics': result.get('metrics')},
                        model_name=config.get('model_name'), description=config.get('model_description')
                    )
            except Exception as e:
                logger.warning(f"保存模型失败: {e}")
        
        result['processing_time'] = time.time() - start_time
        return MultivariateForecastResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"预测失败: {e}")
        raise HTTPException(500, detail=f"服务错误: {str(e)}")


@router.get("/models")
async def list_models(model_name: Optional[str] = Query(None), include_inactive: bool = Query(False)):
    """列出所有已保存的模型"""
    try:
        manager = get_model_manager()
        models = manager.list_models(model_name=model_name, include_inactive=include_inactive)
        return {"success": True, "models": models, "count": len(models)}
    except Exception as e:
        raise HTTPException(500, detail=str(e))


@router.get("/models/{model_id}")
async def get_model(model_id: str):
    """获取模型详情"""
    manager = get_model_manager()
    result = manager.load_model(model_id=model_id)
    if not result:
        raise HTTPException(404, detail=f"模型不存在: {model_id}")
    _, metadata = result
    return {"success": True, "model_id": model_id, **metadata}


@router.get("/models/name/{model_name}/versions")
async def get_model_versions(model_name: str):
    """获取指定模型的所有版本"""
    manager = get_model_manager()
    versions = manager.get_model_versions(model_name)
    if not versions:
        raise HTTPException(404, detail=f"模型不存在: {model_name}")
    return {"success": True, "model_name": model_name, "versions": versions, "count": len(versions)}


@router.put("/models/name/{model_name}/active/{version}")
async def set_active_version(model_name: str, version: int):
    """设置模型的激活版本"""
    manager = get_model_manager()
    if manager.set_active_version(model_name, version):
        return {"success": True, "message": f"已设置 {model_name} 的激活版本为 v{version}"}
    raise HTTPException(404, detail=f"模型或版本不存在: {model_name} v{version}")


@router.delete("/models/{model_id}")
async def delete_model(model_id: str):
    """删除模型"""
    manager = get_model_manager()
    if manager.delete_model(model_id=model_id):
        return {"success": True, "message": f"模型 {model_id} 已删除"}
    raise HTTPException(404, detail=f"模型不存在: {model_id}")


@router.delete("/models/name/{model_name}")
async def delete_model_by_name(model_name: str, version: Optional[int] = Query(None), delete_all: bool = Query(False)):
    """删除模型（按名称）"""
    manager = get_model_manager()
    if delete_all:
        if manager.delete_model(model_name=model_name, delete_all_versions=True):
            return {"success": True, "message": f"模型 {model_name} 的所有版本已删除"}
    elif version:
        if manager.delete_model(model_name=model_name, version=version):
            return {"success": True, "message": f"模型 {model_name} v{version} 已删除"}
    else:
        raise HTTPException(400, detail="请指定版本号或设置 delete_all=true")
    raise HTTPException(404, detail=f"模型不存在: {model_name}")


@router.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "multivariate_forecast", "timestamp": time.time()}
