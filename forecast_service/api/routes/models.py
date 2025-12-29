# forecast_service/api/routes/models.py
"""
模型管理API路由
实现 /api/v1/models 端点
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
import logging
import sys
import os

# 添加父目录到路径以便导入core模块
forecast_service_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, forecast_service_root)

# 导入模型管理器
from core.multivariate_forecast.core import ModelManager

logger = logging.getLogger(__name__)

# 创建路由器
router = APIRouter(prefix="/api/v1/models", tags=["模型管理"])

# 初始化模型管理器
model_manager = ModelManager()


# ============ 响应模型 ============

class ModelInfo(BaseModel):
    """模型信息"""
    model_config = ConfigDict(protected_namespaces=())
    
    model_id: str = Field(..., description="模型ID")
    model_name: Optional[str] = Field(default=None, description="模型名称")
    version: Optional[int] = Field(default=None, description="版本号")
    algorithm: str = Field(..., description="算法类型")
    target_column: str = Field(..., description="目标列")
    feature_columns: List[str] = Field(..., description="特征列")
    description: Optional[str] = Field(default=None, description="模型描述")
    is_active: bool = Field(default=True, description="是否激活")
    created_at: Optional[str] = Field(default=None, description="创建时间")
    metrics: Optional[Dict[str, float]] = Field(default=None, description="模型指标")


class ModelListResponse(BaseModel):
    """模型列表响应"""
    success: bool = Field(..., description="请求是否成功")
    message: Optional[str] = Field(default=None, description="响应消息")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="响应时间戳")
    models: List[ModelInfo] = Field(default_factory=list, description="模型列表")
    total: int = Field(default=0, description="模型总数")


class ModelDetailResponse(BaseModel):
    """模型详情响应"""
    success: bool = Field(..., description="请求是否成功")
    message: Optional[str] = Field(default=None, description="响应消息")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="响应时间戳")
    model: Optional[ModelInfo] = Field(default=None, description="模型信息")


class ModelVersionsResponse(BaseModel):
    """模型版本列表响应"""
    success: bool = Field(..., description="请求是否成功")
    message: Optional[str] = Field(default=None, description="响应消息")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="响应时间戳")
    model_name: str = Field(..., description="模型名称")
    versions: List[ModelInfo] = Field(default_factory=list, description="版本列表")


class OperationResponse(BaseModel):
    """操作响应"""
    success: bool = Field(..., description="操作是否成功")
    message: Optional[str] = Field(default=None, description="响应消息")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat(), description="响应时间戳")


# ============ API端点 ============

@router.get(
    "",
    response_model=ModelListResponse,
    summary="列出所有模型",
    description="获取所有已保存的模型列表"
)
async def list_models(
    model_name: Optional[str] = Query(default=None, description="按模型名称筛选"),
    include_inactive: bool = Query(default=False, description="是否包含非激活模型")
) -> ModelListResponse:
    """列出所有模型"""
    try:
        logger.info(f"列出模型，筛选条件: model_name={model_name}, include_inactive={include_inactive}")
        
        models = model_manager.list_models(
            model_name=model_name,
            include_inactive=include_inactive
        )
        
        model_infos = [
            ModelInfo(
                model_id=m['model_id'],
                model_name=m.get('model_name'),
                version=m.get('version'),
                algorithm=m['algorithm'],
                target_column=m['target_column'],
                feature_columns=m['feature_columns'],
                description=m.get('description'),
                is_active=m.get('is_active', True),
                created_at=m.get('created_at'),
                metrics=m.get('metrics')
            )
            for m in models
        ]
        
        return ModelListResponse(
            success=True,
            message=f"找到 {len(model_infos)} 个模型",
            timestamp=datetime.utcnow().isoformat(),
            models=model_infos,
            total=len(model_infos)
        )
        
    except Exception as e:
        logger.error(f"列出模型失败: {e}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")


@router.get(
    "/{model_id}",
    response_model=ModelDetailResponse,
    summary="获取模型详情",
    description="根据模型ID获取模型详细信息"
)
async def get_model(model_id: str) -> ModelDetailResponse:
    """获取模型详情"""
    try:
        logger.info(f"获取模型详情: {model_id}")
        
        result = model_manager.load_model(model_id=model_id)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"模型不存在: {model_id}")
        
        _, metadata = result
        
        model_info = ModelInfo(
            model_id=model_id,
            model_name=metadata.get('model_name'),
            version=metadata.get('version'),
            algorithm=metadata['algorithm'],
            target_column=metadata['target_column'],
            feature_columns=metadata['feature_columns'],
            description=metadata.get('description'),
            is_active=metadata.get('is_active', True),
            metrics=metadata.get('metrics')
        )
        
        return ModelDetailResponse(
            success=True,
            message="获取模型成功",
            timestamp=datetime.utcnow().isoformat(),
            model=model_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取模型详情失败: {e}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")


@router.get(
    "/name/{name}/versions",
    response_model=ModelVersionsResponse,
    summary="获取模型版本列表",
    description="根据模型名称获取所有版本"
)
async def get_model_versions(name: str) -> ModelVersionsResponse:
    """获取模型版本列表"""
    try:
        logger.info(f"获取模型版本: {name}")
        
        versions = model_manager.get_model_versions(name)
        
        version_infos = [
            ModelInfo(
                model_id=v['model_id'],
                model_name=v.get('model_name'),
                version=v.get('version'),
                algorithm=v['algorithm'],
                target_column=v['target_column'],
                feature_columns=v['feature_columns'],
                description=v.get('description'),
                is_active=v.get('is_active', True),
                created_at=v.get('created_at'),
                metrics=v.get('metrics')
            )
            for v in versions
        ]
        
        return ModelVersionsResponse(
            success=True,
            message=f"找到 {len(version_infos)} 个版本",
            timestamp=datetime.utcnow().isoformat(),
            model_name=name,
            versions=version_infos
        )
        
    except Exception as e:
        logger.error(f"获取模型版本失败: {e}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")


@router.put(
    "/name/{name}/active/{version}",
    response_model=OperationResponse,
    summary="设置激活版本",
    description="设置指定模型名称的激活版本"
)
async def set_active_version(name: str, version: int) -> OperationResponse:
    """设置激活版本"""
    try:
        logger.info(f"设置激活版本: {name} v{version}")
        
        success = model_manager.set_active_version(name, version)
        
        if success:
            return OperationResponse(
                success=True,
                message=f"已将模型 {name} 的激活版本设置为 v{version}",
                timestamp=datetime.utcnow().isoformat()
            )
        else:
            raise HTTPException(
                status_code=404,
                detail=f"模型 {name} 版本 {version} 不存在"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"设置激活版本失败: {e}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")


@router.delete(
    "/{model_id}",
    response_model=OperationResponse,
    summary="删除模型",
    description="根据模型ID删除模型"
)
async def delete_model(model_id: str) -> OperationResponse:
    """删除模型"""
    try:
        logger.info(f"删除模型: {model_id}")
        
        success = model_manager.delete_model(model_id=model_id)
        
        if success:
            return OperationResponse(
                success=True,
                message=f"模型 {model_id} 已删除",
                timestamp=datetime.utcnow().isoformat()
            )
        else:
            raise HTTPException(status_code=404, detail=f"模型不存在: {model_id}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除模型失败: {e}")
        raise HTTPException(status_code=500, detail=f"内部错误: {str(e)}")
