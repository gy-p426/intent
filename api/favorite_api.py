"""
用户收藏API路由

提供收藏管理和执行的HTTP接口
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel, Field

from services.favorite_service import FavoriteService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/favorites", tags=["favorites"])


# ==================== 请求/响应模型 ====================

class CreateFavoriteRequest(BaseModel):
    """创建收藏请求"""
    favorite_name: str = Field(..., description="收藏名称")
    original_question: str = Field(..., description="用户原始问题")
    algorithm_type: str = Field(..., description="算法类型")
    window_id: Optional[str] = Field(None, description="窗口ID")
    session_id: Optional[str] = Field(None, description="会话ID")
    algorithm_params: dict = Field(..., description="算法参数")
    original_sql: str = Field(..., description="原始SQL")
    tags: Optional[str] = Field(None, description="标签")
    description: Optional[str] = Field(None, description="描述")


class UpdateFavoriteRequest(BaseModel):
    """更新收藏请求"""
    favorite_id: int = Field(..., description="收藏ID")
    favorite_name: Optional[str] = Field(None, description="收藏名称")
    description: Optional[str] = Field(None, description="描述")
    tags: Optional[str] = Field(None, description="标签")


class DeleteFavoritesRequest(BaseModel):
    """删除收藏请求"""
    favorite_ids: List[int] = Field(..., description="收藏ID列表")


class ExecuteFavoriteRequest(BaseModel):
    """执行收藏请求"""
    favorite_id: int = Field(..., description="收藏ID")
    use_original_params: bool = Field(True, description="是否使用原参数")
    modified_where_params: Optional[dict] = Field(None, description="修改的WHERE参数")


class ApiResponse(BaseModel):
    """统一API响应"""
    success: bool
    message: str = ""
    data: Optional[dict] = None


# ==================== API路由 ====================

@router.post("", response_model=ApiResponse)
async def create_favorite(request: CreateFavoriteRequest, user_id: int = Query(..., description="用户ID")):
    """
    创建收藏
    
    Args:
        request: 创建收藏请求
        user_id: 用户ID
    
    Returns:
        ApiResponse: 包含favorite_id的响应
    """
    try:
        service = FavoriteService()
        favorite_id = service.create_favorite(user_id, request.dict())
        
        return ApiResponse(
            success=True,
            message="收藏创建成功",
            data={
                "favorite_id": favorite_id,
                "favorite_name": request.favorite_name
            }
        )
    except Exception as e:
        logger.error(f"创建收藏失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"创建收藏失败: {str(e)}")


@router.get("", response_model=ApiResponse)
async def get_favorites_list(
    user_id: int = Query(..., description="用户ID"),
    algorithm_type: Optional[str] = Query(None, description="算法类型"),
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(20, ge=1, le=100, description="每页数量")
):
    """
    获取收藏列表
    
    Args:
        user_id: 用户ID
        algorithm_type: 算法类型（可选）
        page: 页码
        pageSize: 每页数量
    
    Returns:
        ApiResponse: 包含收藏列表的响应
    """
    try:
        service = FavoriteService()
        result = service.get_favorites_list(user_id, algorithm_type, page, pageSize)
        
        return ApiResponse(
            success=True,
            data=result
        )
    except Exception as e:
        logger.error(f"获取收藏列表失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取收藏列表失败: {str(e)}")


@router.get("/{favorite_id}", response_model=ApiResponse)
async def get_favorite_detail(
    favorite_id: int,
    user_id: int = Query(..., description="用户ID")
):
    """
    获取收藏详情
    
    Args:
        favorite_id: 收藏ID
        user_id: 用户ID
    
    Returns:
        ApiResponse: 包含收藏详情的响应
    """
    try:
        service = FavoriteService()
        favorite = service.get_favorite(favorite_id, user_id)
        
        if not favorite:
            raise HTTPException(status_code=404, detail="收藏不存在")
        
        return ApiResponse(
            success=True,
            data=favorite
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取收藏详情失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取收藏详情失败: {str(e)}")


@router.put("", response_model=ApiResponse)
async def update_favorite(
    request: UpdateFavoriteRequest,
    user_id: int = Query(..., description="用户ID")
):
    """
    更新收藏（仅更新名称、描述、标签）
    
    Args:
        request: 更新收藏请求
        user_id: 用户ID
    
    Returns:
        ApiResponse: 更新结果
    """
    try:
        service = FavoriteService()
        success = service.update_favorite(request.favorite_id, user_id, request.dict(exclude={'favorite_id'}))
        
        if not success:
            raise HTTPException(status_code=404, detail="收藏不存在或更新失败")
        
        return ApiResponse(
            success=True,
            message="收藏更新成功"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新收藏失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"更新收藏失败: {str(e)}")


@router.delete("", response_model=ApiResponse)
async def delete_favorites(
    request: DeleteFavoritesRequest,
    user_id: int = Query(..., description="用户ID")
):
    """
    批量删除收藏
    
    Args:
        request: 删除收藏请求
        user_id: 用户ID
    
    Returns:
        ApiResponse: 删除结果
    """
    try:
        service = FavoriteService()
        result = service.delete_favorites(request.favorite_ids, user_id)
        
        return ApiResponse(
            success=True,
            message=f"成功删除{result['deleted_count']}个收藏",
            data=result
        )
    except Exception as e:
        logger.error(f"删除收藏失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"删除收藏失败: {str(e)}")


@router.get("/{favorite_id}/where-params", response_model=ApiResponse)
async def get_where_params(
    favorite_id: int,
    user_id: int = Query(..., description="用户ID")
):
    """
    获取可修改的WHERE参数（含实时options）
    
    Args:
        favorite_id: 收藏ID
        user_id: 用户ID
    
    Returns:
        ApiResponse: 包含where_template和where_params（含options）的响应
    """
    try:
        service = FavoriteService()
        result = service.get_where_params_with_options(favorite_id, user_id)
        
        result['note'] = "只能修改WHERE条件参数，算法参数不可修改"
        
        return ApiResponse(
            success=True,
            data=result
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取WHERE参数失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取WHERE参数失败: {str(e)}")


@router.post("/execute", response_model=ApiResponse)
async def execute_favorite(
    request: ExecuteFavoriteRequest,
    user_id: int = Query(..., description="用户ID")
):
    """
    执行收藏
    
    支持两种模式：
    1. use_original_params=true: 使用原参数直接执行
    2. use_original_params=false: 修改WHERE条件后执行
    
    Args:
        request: 执行收藏请求
        user_id: 用户ID
    
    Returns:
        ApiResponse: 执行结果
    """
    try:
        service = FavoriteService()
        result = await service.execute_favorite(
            favorite_id=request.favorite_id,
            user_id=user_id,
            use_original_params=request.use_original_params,
            modified_where_params=request.modified_where_params
        )
        
        return ApiResponse(
            success=True,
            message="执行成功",
            data=result
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"执行收藏失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"执行收藏失败: {str(e)}")


@router.get("/{favorite_id}/history", response_model=ApiResponse)
async def get_execution_history(
    favorite_id: int,
    user_id: int = Query(..., description="用户ID"),
    page: int = Query(1, ge=1, description="页码"),
    pageSize: int = Query(20, ge=1, le=100, description="每页数量")
):
    """
    获取执行历史
    
    Args:
        favorite_id: 收藏ID
        user_id: 用户ID
        page: 页码
        pageSize: 每页数量
    
    Returns:
        ApiResponse: 包含执行历史列表的响应
    """
    try:
        service = FavoriteService()
        result = service.get_execution_history(favorite_id, user_id, page, pageSize)
        
        return ApiResponse(
            success=True,
            data=result
        )
    except Exception as e:
        logger.error(f"获取执行历史失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取执行历史失败: {str(e)}")
