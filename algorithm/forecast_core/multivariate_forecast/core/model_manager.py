# forecast_modules/multivariate_forecast/core/model_manager.py
"""模型管理器 - 使用文件系统存储"""
import logging
import os
import json
import pickle
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class ModelManager:
    """模型管理器 - 使用文件系统存储"""
    
    def __init__(self, storage_dir: str = None):
        if storage_dir is None:
            storage_dir = Path.cwd() / "models"
        
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.storage_dir / "model_index.json"
        self._load_index()
        logger.info(f"模型存储目录: {self.storage_dir}")
    
    def _load_index(self):
        if self.index_file.exists():
            try:
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    self.index = json.load(f)
            except Exception as e:
                logger.warning(f"加载索引失败: {e}")
                self.index = {"models": {}}
        else:
            self.index = {"models": {}}
    
    def _save_index(self):
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(self.index, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存索引失败: {e}")
    
    def _get_model_path(self, model_id: str) -> Path:
        return self.storage_dir / f"{model_id}.pkl"
    
    def save_model(self, model_id: str, model: Any, metadata: Dict, 
                   model_name: Optional[str] = None, description: Optional[str] = None) -> bool:
        try:
            version = 1
            if model_name:
                existing_versions = [m['version'] for m in self.index['models'].values() if m.get('model_name') == model_name]
                if existing_versions:
                    version = max(existing_versions) + 1
            
            model_path = self._get_model_path(model_id)
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
            
            self.index['models'][model_id] = {
                'model_id': model_id, 'model_name': model_name, 'version': version,
                'algorithm': metadata['algorithm'], 'target_column': metadata['target_column'],
                'feature_columns': metadata['feature_columns'], 'metrics': metadata.get('metrics'),
                'description': description, 'is_active': True,
                'created_at': datetime.now().isoformat(), 'file_path': str(model_path)
            }
            self._save_index()
            logger.info(f"模型已保存: {model_id}, 名称: {model_name}, 版本: {version}")
            return True
        except Exception as e:
            logger.error(f"保存模型失败: {e}")
            return False

    def load_model(self, model_id: str = None, model_name: str = None, version: int = None) -> Optional[Tuple[Any, Dict]]:
        try:
            model_info = None
            if model_id:
                model_info = self.index['models'].get(model_id)
            elif model_name:
                candidates = [m for m in self.index['models'].values() if m.get('model_name') == model_name]
                if version:
                    for m in candidates:
                        if m.get('version') == version:
                            model_info = m
                            break
                else:
                    active_candidates = [m for m in candidates if m.get('is_active', True)]
                    if active_candidates:
                        model_info = max(active_candidates, key=lambda x: x.get('version', 0))
                    elif candidates:
                        model_info = max(candidates, key=lambda x: x.get('version', 0))
            
            if not model_info:
                return None
            
            model_path = Path(model_info.get('file_path', self._get_model_path(model_info['model_id'])))
            if not model_path.exists():
                logger.error(f"模型文件不存在: {model_path}")
                return None
            
            with open(model_path, 'rb') as f:
                model = pickle.load(f)
            
            metadata = {
                'algorithm': model_info['algorithm'], 'target_column': model_info['target_column'],
                'feature_columns': model_info['feature_columns'], 'metrics': model_info.get('metrics'),
                'model_name': model_info.get('model_name'), 'version': model_info.get('version'),
                'description': model_info.get('description'), 'is_active': model_info.get('is_active', True)
            }
            return model, metadata
        except Exception as e:
            logger.error(f"加载模型失败: {e}")
            return None
    
    def list_models(self, model_name: str = None, include_inactive: bool = False) -> List[Dict]:
        try:
            models = []
            for model_info in self.index['models'].values():
                if model_name and model_info.get('model_name') != model_name:
                    continue
                if not include_inactive and not model_info.get('is_active', True):
                    continue
                models.append({
                    'model_id': model_info['model_id'], 'model_name': model_info.get('model_name'),
                    'version': model_info.get('version'), 'algorithm': model_info['algorithm'],
                    'target_column': model_info['target_column'], 'feature_columns': model_info['feature_columns'],
                    'metrics': model_info.get('metrics'), 'description': model_info.get('description'),
                    'is_active': model_info.get('is_active', True), 'created_at': model_info.get('created_at')
                })
            models.sort(key=lambda x: (x.get('model_name') or '', -x.get('version', 0)))
            return models
        except Exception as e:
            logger.error(f"列出模型失败: {e}")
            return []
    
    def get_model_versions(self, model_name: str) -> List[Dict]:
        return self.list_models(model_name=model_name, include_inactive=True)
    
    def set_active_version(self, model_name: str, version: int) -> bool:
        try:
            found = False
            for model_id, model_info in self.index['models'].items():
                if model_info.get('model_name') == model_name:
                    model_info['is_active'] = (model_info.get('version') == version)
                    if model_info['is_active']:
                        found = True
            if found:
                self._save_index()
                logger.info(f"已设置模型 {model_name} 的激活版本为 v{version}")
            return found
        except Exception as e:
            logger.error(f"设置激活版本失败: {e}")
            return False
    
    def delete_model(self, model_id: str = None, model_name: str = None, 
                     version: int = None, delete_all_versions: bool = False) -> bool:
        try:
            to_delete = []
            if model_id:
                if model_id in self.index['models']:
                    to_delete.append(model_id)
            elif model_name:
                for mid, model_info in self.index['models'].items():
                    if model_info.get('model_name') == model_name:
                        if delete_all_versions or (version and model_info.get('version') == version):
                            to_delete.append(mid)
            
            if not to_delete:
                return False
            
            for mid in to_delete:
                model_info = self.index['models'].get(mid)
                if model_info:
                    model_path = Path(model_info.get('file_path', self._get_model_path(mid)))
                    if model_path.exists():
                        model_path.unlink()
                    del self.index['models'][mid]
            
            self._save_index()
            logger.info(f"已删除 {len(to_delete)} 个模型")
            return True
        except Exception as e:
            logger.error(f"删除模型失败: {e}")
            return False
