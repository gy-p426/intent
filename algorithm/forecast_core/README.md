# 时间序列预测模块包

独立可迁移的时间序列预测模块，可集成到任何 FastAPI 项目中。

## 模块说明

| 模块 | 功能 | API 版本 |
|------|------|----------|
| `trend_analysis` | 趋势分解和检测 | v1 |
| `auto_univariate_forecast` | 自动单变量预测（ARIMA/Prophet） | v2 |
| `multivariate_forecast` | 多变量预测（机器学习算法） | v3 |

## 安装

```bash
# 复制 forecast_modules 目录到目标项目
cp -r forecast_modules /path/to/your/project/

# 安装依赖
pip install -r forecast_modules/requirements.txt

# 可选：安装增强算法
pip install lightgbm xgboost
```

## 快速开始

### 方式一：作为 FastAPI 路由集成

```python
from fastapi import FastAPI
from forecast_modules.trend_analysis import router as trend_router
from forecast_modules.auto_univariate_forecast import router as forecast_router
from forecast_modules.multivariate_forecast import router as multivariate_router

app = FastAPI(title="我的预测服务")

# 注册路由
app.include_router(trend_router, prefix="/api/v1")
app.include_router(forecast_router, prefix="/api/v2")
app.include_router(multivariate_router, prefix="/api/v3")
```

### 方式二：直接调用核心类

```python
# 趋势分析
from forecast_modules.trend_analysis import TrendService

service = TrendService()
data = [{"timestamp": "2024-01-01 00:00", "value": 100}, ...]
series = service.prepare_data(data)
result = service.decompose_trend_stl(series, period=24)
detection = service.detect_trend_mann_kendall(series)

# 单变量预测
from forecast_modules.auto_univariate_forecast import AutoUnivariatePredictor

predictor = AutoUnivariatePredictor()
request_data = {
    'data': {
        'timestamp': ["2024-01-01 00:00", "2024-01-01 01:00", ...],
        'value': [100, 105, ...]
    },
    'config': {'forecast_horizon': 24}
}
result = predictor.forecast(request_data)

# 多变量预测
from forecast_modules.multivariate_forecast import MultivariatePredictor

predictor = MultivariatePredictor()
request = {
    'data': [
        {"timestamp": "2024-01-01 00:00", "target": 1000, "feature1": 10, "feature2": 0.5},
        ...
    ],
    'config': {
        'target_column': 'target',
        'feature_columns': ['feature1', 'feature2'],
        'algorithm': 'random_forest',
        'forecast_horizon': 14
    }
}
result = predictor.forecast(request)
```

## API 端点

### 趋势分析 (v1)
- `POST /api/v1/trend/decomposition` - 趋势分解
- `POST /api/v1/trend/detection` - 趋势检测
- `GET /api/v1/trend/tasks/{task_id}` - 查询任务状态

### 单变量预测 (v2)
- `POST /api/v2/forecast/auto` - 自动预测
- `GET /api/v2/forecast/health` - 健康检查

### 多变量预测 (v3)
- `POST /api/v3/forecast/multivariate` - 多变量预测
- `GET /api/v3/forecast/models` - 列出模型
- `GET /api/v3/forecast/models/{model_id}` - 获取模型详情
- `DELETE /api/v3/forecast/models/{model_id}` - 删除模型
- `GET /api/v3/forecast/health` - 健康检查

## 支持的算法

| 功能 | 算法 | 依赖 |
|------|------|------|
| 趋势分解 | STL、经典分解 | statsmodels |
| 趋势检测 | Mann-Kendall、线性回归 | scipy |
| 单变量预测 | ARIMA | pmdarima |
| 单变量预测 | Prophet | prophet |
| 多变量预测 | 随机森林 | scikit-learn |
| 多变量预测 | 线性回归 | scikit-learn |
| 多变量预测 | LightGBM | lightgbm（可选） |
| 多变量预测 | XGBoost | xgboost（可选） |

## 模型存储

多变量预测模块支持模型持久化：
- 模型以 pickle 格式保存在 `models/` 目录
- 索引文件 `models/model_index.json` 记录模型元数据
- 支持版本管理和模型重用

## 配置

可通过环境变量或 `config.py` 配置：

```python
from forecast_modules.config import Settings

settings = Settings(
    model_storage_dir="./my_models",  # 自定义模型存储目录
    log_level="INFO"
)
```

## 目录结构

```
forecast_modules/
├── __init__.py              # 包入口
├── config.py                # 配置管理
├── requirements.txt         # 依赖列表
├── README.md                # 使用说明
├── trend_analysis/          # 趋势分析模块
│   ├── router.py            # API 路由
│   ├── schemas.py           # 数据模型
│   └── core/
│       └── trend_service.py # 核心服务
├── auto_univariate_forecast/ # 单变量预测模块
│   ├── router.py            # API 路由
│   ├── schemas.py           # 数据模型
│   ├── core/
│   │   ├── predictor.py     # 预测器
│   │   ├── data_processor.py # 数据处理
│   │   └── model_selector.py # 模型选择
│   └── models/
│       ├── arima_model.py   # ARIMA 实现
│       └── prophet_model.py # Prophet 实现
└── multivariate_forecast/   # 多变量预测模块
    ├── router.py            # API 路由
    ├── schemas.py           # 数据模型
    └── core/
        ├── predictor.py     # 预测器
        └── model_manager.py # 模型管理
```

## 注意事项

1. Prophet 首次运行可能需要编译 Stan 模型，耗时较长
2. LightGBM 和 XGBoost 为可选依赖，不安装时使用随机森林作为默认算法
3. 模型存储目录需要有写入权限
4. 建议在生产环境中配置适当的日志级别
