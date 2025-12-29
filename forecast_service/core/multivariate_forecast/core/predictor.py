# forecast_service/core/multivariate_forecast/core/predictor.py
"""多变量预测器核心实现"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)


class MultivariatePredictor:
    """多变量时序预测器"""
    
    SUPPORTED_ALGORITHMS = ['lightgbm', 'xgboost', 'random_forest', 'linear_regression']
    
    def __init__(self):
        self.models = {}
        self._model_manager = None
    
    @property
    def model_manager(self):
        if self._model_manager is None:
            from .model_manager import ModelManager
            self._model_manager = ModelManager()
        return self._model_manager
    
    def forecast(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """执行预测"""
        try:
            config = request.get('config') or {}
            use_model_id = config.get('use_model_id')
            use_model_name = config.get('use_model_name')
            use_model_version = config.get('use_model_version')
            
            if use_model_id or use_model_name:
                return self._predict_with_existing_model(request, use_model_id, use_model_name, use_model_version)
            return self._train_and_predict(request)
        except Exception as e:
            logger.error(f"预测失败: {e}")
            return {'success': False, 'message': str(e)}
    
    def _predict_with_existing_model(self, request: Dict[str, Any], 
                                      model_id: str = None, model_name: str = None,
                                      version: int = None) -> Dict[str, Any]:
        """使用已有模型进行预测"""
        try:
            if model_id and model_id in self.models:
                model_info = self.models[model_id]
                model = model_info['model']
                metadata = model_info
            else:
                result = self.model_manager.load_model(model_id=model_id, model_name=model_name, version=version)
                if not result:
                    return {'success': False, 'message': f'模型不存在: {model_id or model_name}'}
                model, metadata = result
                cache_id = model_id or f"{model_name}_v{metadata['version']}"
                self.models[cache_id] = {'model': model, **metadata}
            
            config = request.get('config') or {}
            data = request.get('data')
            horizon = config.get('forecast_horizon', 14)
            
            if not data:
                return {'success': False, 'message': '重用模型时需要提供预测数据'}
            
            df = pd.DataFrame(data)
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df = df.sort_values('timestamp')
            
            feature_columns = metadata['feature_columns']
            target_column = metadata['target_column']
            
            missing_cols = [c for c in feature_columns if c not in df.columns]
            if missing_cols:
                return {'success': False, 'message': f'数据缺少特征列: {missing_cols}'}
            
            predictions = self._generate_forecast(model, df, target_column, feature_columns, horizon)
            
            return {
                'success': True, 'results': predictions, 'model_used': metadata['algorithm'],
                'model_id': model_id, 'model_name': metadata.get('model_name'),
                'model_version': metadata.get('version'), 'reused_model': True
            }
        except Exception as e:
            logger.error(f"使用已有模型预测失败: {e}")
            return {'success': False, 'message': str(e)}
    
    def _train_and_predict(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """训练新模型并预测"""
        config = request.get('config') or {}
        data = request['data']
        target_column = config.get('target_column', 'target')
        feature_columns = config.get('feature_columns')
        algorithm = config.get('algorithm', 'lightgbm')
        horizon = config.get('forecast_horizon', 14)
        model_name = config.get('model_name')
        
        df = pd.DataFrame(data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp')

        if not feature_columns:
            feature_columns = [c for c in df.columns if c not in ['timestamp', target_column]]
        
        if target_column not in df.columns:
            return {'success': False, 'message': f'目标列 {target_column} 不存在'}
        
        missing_cols = [c for c in feature_columns if c not in df.columns]
        if missing_cols:
            return {'success': False, 'message': f'特征列不存在: {missing_cols}'}
        
        analysis = self._analyze_data(df, target_column, feature_columns)
        X, y = self._prepare_features(df, target_column, feature_columns)
        model, metrics = self._train_model(X, y, algorithm)
        predictions = self._generate_forecast(model, df, target_column, feature_columns, horizon)
        
        model_id = f"mv_{uuid.uuid4().hex[:8]}"
        self.models[model_id] = {
            'model': model, 'algorithm': algorithm, 'target_column': target_column,
            'feature_columns': feature_columns, 'model_name': model_name, 'created_at': datetime.now()
        }
        
        return {
            'success': True, 'results': predictions, 'model_used': algorithm,
            'model_id': model_id, 'model_name': model_name, 'data_analysis': analysis,
            'metrics': metrics, 'reused_model': False
        }

    def _analyze_data(self, df: pd.DataFrame, target: str, features: List[str]) -> Dict[str, Any]:
        return {
            'data_points': len(df),
            'target_stats': {
                'mean': float(df[target].mean()), 'std': float(df[target].std()),
                'min': float(df[target].min()), 'max': float(df[target].max())
            },
            'feature_count': len(features),
            'missing_values': int(df[features + [target]].isnull().sum().sum())
        }
    
    def _prepare_features(self, df: pd.DataFrame, target: str, features: List[str]) -> tuple:
        df_feat = df.copy()
        df_feat['hour'] = df_feat['timestamp'].dt.hour
        df_feat['dayofweek'] = df_feat['timestamp'].dt.dayofweek
        df_feat['month'] = df_feat['timestamp'].dt.month
        
        for lag in [1, 2, 3]:
            df_feat[f'{target}_lag{lag}'] = df_feat[target].shift(lag)
        
        df_feat = df_feat.dropna()
        all_features = features + ['hour', 'dayofweek', 'month', f'{target}_lag1', f'{target}_lag2', f'{target}_lag3']
        return df_feat[all_features].values, df_feat[target].values

    def _train_model(self, X: np.ndarray, y: np.ndarray, algorithm: str) -> tuple:
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
        
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
        
        if algorithm == 'lightgbm':
            import lightgbm as lgb
            model = lgb.LGBMRegressor(n_estimators=100, random_state=42, verbose=-1)
        elif algorithm == 'xgboost':
            import xgboost as xgb
            model = xgb.XGBRegressor(n_estimators=100, random_state=42, verbosity=0)
        elif algorithm == 'random_forest':
            from sklearn.ensemble import RandomForestRegressor
            model = RandomForestRegressor(n_estimators=100, random_state=42)
        else:
            from sklearn.linear_model import LinearRegression
            model = LinearRegression()
        
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        metrics = {
            'rmse': float(np.sqrt(mean_squared_error(y_test, y_pred))),
            'mae': float(mean_absolute_error(y_test, y_pred)),
            'r2': float(r2_score(y_test, y_pred))
        }
        logger.info(f"模型训练完成: {algorithm}, R2={metrics['r2']:.4f}")
        return model, metrics

    def _generate_forecast(self, model, df: pd.DataFrame, target: str, features: List[str], horizon: int) -> Dict[str, Any]:
        last_row = df.iloc[-1].copy()
        last_timestamp = pd.to_datetime(last_row['timestamp'])
        recent_values = df[target].tail(3).tolist()
        
        forecasts, timestamps = [], []
        freq = pd.to_datetime(df['timestamp']).diff().median() if len(df) > 1 else pd.Timedelta(hours=1)
        
        for i in range(horizon):
            next_ts = last_timestamp + freq * (i + 1)
            timestamps.append(next_ts.strftime('%Y-%m-%d %H:%M'))
            
            feat_values = [last_row[f] for f in features]
            feat_values.extend([next_ts.hour, next_ts.dayofweek, next_ts.month])
            feat_values.extend(recent_values[-3:])
            
            pred = model.predict([feat_values])[0]
            forecasts.append(float(pred))
            recent_values.append(pred)
            recent_values = recent_values[-3:]
        
        return {'timestamps': timestamps, 'forecast': forecasts, 'horizon': horizon}
