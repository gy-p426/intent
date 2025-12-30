# 趋势分析与预测微服务

基于 FastAPI 构建的时间序列分析与预测微服务，提供趋势分解、趋势检测、单变量预测和多变量预测功能。

## 功能特性

- **趋势分解**: 支持 STL 和经典分解算法，提取趋势、季节性和残差成分
- **趋势检测**: 支持 Mann-Kendall 检验和线性回归方法
- **单变量预测**: 自动选择最佳模型（ARIMA、Prophet）
- **多变量预测**: 支持多种机器学习算法（Random Forest、LightGBM、XGBoost）
- **自动化**: 自动检测季节周期、自动选择算法

## 项目结构

```
forecast-microservice/
├── main.py                 # 服务入口
├── config.py               # 配置管理
├── requirements.txt        # 依赖列表
├── api/
│   ├── app.py              # FastAPI 应用
│   └── routes/
│       ├── trend.py        # 趋势分析路由
│       ├── univariate.py   # 单变量预测路由
│       ├── multivariate.py # 多变量预测路由
│       └── models.py       # 模型管理路由
├── core/
│   ├── trend_analysis/     # 趋势分析模块
│   ├── auto_univariate_forecast/  # 单变量预测模块
│   └── multivariate_forecast/     # 多变量预测模块
├── models/                 # 模型存储目录
└── tests/                  # 测试文件
```

## 快速开始

### 环境要求

- Python 3.10+
- pip

### 安装依赖

```bash
pip install -r requirements.txt
```

> **注意**: `prophet` 在 Windows 上安装可能需要 C++ 编译器，建议使用 conda：
> ```bash
> conda install -c conda-forge prophet
> ```

### 启动服务

```bash
python main.py
```

服务默认运行在 `http://0.0.0.0:8100`

### 访问文档

- Swagger UI: http://localhost:8100/docs
- ReDoc: http://localhost:8100/redoc

## API 接口

### 健康检查

```
GET /health
```

### 趋势分解

```
POST /api/v1/trend/decomposition
```

请求示例：
```json
{
  "data": [
    {"timestamp": "2024-01-01 00:00", "value": 45},
    {"timestamp": "2024-01-01 01:00", "value": 48}
  ],
  "period": 24,
  "decomposition_model": "additive",
  "algorithm": "auto"
}
```

参数说明：
- `data`: 时间序列数据点列表
- `period`: 季节周期（可选，自动检测）
- `decomposition_model`: 分解模型 (`additive` / `multiplicative`)
- `algorithm`: 算法 (`auto` / `stl` / `classical`)

### 趋势检测

```
POST /api/v1/trend/detection
```

请求示例：
```json
{
  "data": [
    {"timestamp": "2024-01-01", "value": 100},
    {"timestamp": "2024-01-02", "value": 110}
  ],
  "method": "auto",
  "confidence_level": 0.95,
  "include_seasonal_adjustment": true
}
```

参数说明：
- `method`: 检测方法 (`auto` / `mann_kendall` / `linear_regression`)
- `confidence_level`: 置信水平 (0.5-0.99)
- `include_seasonal_adjustment`: 是否进行季节性调整

### 单变量预测

```
POST /api/v1/forecast/univariate
```

请求示例：
```json
{
  "data": {
    "timestamp": ["2024-01-01 00:00", "2024-01-01 01:00", "2024-01-01 02:00"],
    "value": [100, 105, 110]
  },
  "config": {
    "forecast_horizon": 24,
    "include_confidence": true
  }
}
```

参数说明：
- `data`: 包含 `timestamp` 和 `value` 列表的字典
- `config.forecast_horizon`: 预测步数
- `config.include_confidence`: 是否包含置信区间

### 多变量预测

```
POST /api/v1/forecast/multivariate
```

请求示例：
```json
{
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
```

参数说明：
- `target_column`: 目标列名
- `algorithm`: 算法 (`random_forest` / `lightgbm` / `xgboost` / `linear_regression`)
- `forecast_horizon`: 预测步数
- `model_name`: 模型名称（用于保存和复用）

## 配置说明

支持通过环境变量或 `.env` 文件配置，环境变量前缀为 `FORECAST_`：

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| service_name | FORECAST_SERVICE_NAME | forecast-microservice | 服务名称 |
| service_port | FORECAST_SERVICE_PORT | 8100 | 服务端口 |
| debug | FORECAST_DEBUG | false | 调试模式 |
| log_level | FORECAST_LOG_LEVEL | INFO | 日志级别 |
| cors_origins | FORECAST_CORS_ORIGINS | * | CORS 来源 |

## 运行测试

```bash
pytest tests/ -v
```

## 技术栈

- **Web 框架**: FastAPI, Uvicorn
- **数据处理**: Pandas, NumPy
- **统计分析**: Statsmodels, SciPy
- **时序预测**: Prophet, pmdarima (ARIMA)
- **机器学习**: Scikit-learn
- **测试**: Pytest, Hypothesis

## License

MIT
