# forecast_modules/config.py
"""
模块配置管理
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings


class ModelStorageSettings(BaseSettings):
    """模型存储配置"""
    storage_dir: str = ""
    
    class Config:
        env_prefix = "MODEL_"


class ModuleSettings(BaseSettings):
    """模块配置"""
    debug: bool = False
    log_level: str = "INFO"
    model_storage: ModelStorageSettings = ModelStorageSettings()
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = ModuleSettings()


def get_model_storage_dir() -> str:
    """获取模型存储目录"""
    if settings.model_storage.storage_dir:
        return settings.model_storage.storage_dir
    
    # 默认存储在当前工作目录的 models 文件夹
    return str(Path.cwd() / "models")
