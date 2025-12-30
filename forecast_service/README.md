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

响应示例（v5.0 统一格式）：
```json
{
  "解释": "【趋势分解分析结果】\n\n📌 关键发现：\n1. 数据存在较为明显的趋势（强度：65%）\n2. 数据存在非常明显的周期性规律（强度：78%），每24个时间单位会重复类似的模式\n\n💡 分析说明：\n我们将您的数据分解成了三个部分：趋势成分、季节性成分和残差成分...\n\n📋 建议：\n• 趋势明显，建议关注长期变化方向\n• 周期性明显，建议在业务规划中考虑这种周期性波动",
  "算法结果": {
    "分析类型": "decomposition",
    "数据特征": {
      "数据点数": 168,
      "均值": 46.5,
      "标准差": 5.2
    },
    "分解结果": {
      "趋势分量": [{"时间戳": "2024-01-01 00:00", "数值": 46.5}, ...],
      "季节性分量": [{"时间戳": "2024-01-01 00:00", "数值": -1.5}, ...],
      "残差分量": [{"时间戳": "2024-01-01 00:00", "数值": 0.0}, ...],
      "分析指标": {
        "趋势强度": 0.65,
        "季节性强度": 0.78,
        "残差方差": 2.3
      }
    },
    "使用算法": "stl",
    "使用周期": 24,
    "数据点数": 168
  }
}
```

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

响应示例（v5.0 统一格式）：
```json
{
  "解释": "【趋势检测分析结果】\n\n📌 关键发现：\n1. 检测到数据呈现上升趋势，我们比较确定这个结论是可靠的（置信度：95%）\n2. 增长速度：平稳（每个时间单位平均变化 10.0）\n\n💡 分析说明：\n使用Mann-Kendall方法进行趋势检验，结果表明数据整体呈现上升趋势...\n\n📋 建议：\n• 数据呈上升趋势，建议关注增长的可持续性\n• 可以考虑利用这一趋势进行预测和规划",
  "算法结果": {
    "分析类型": "detection",
    "数据特征": {
      "数据点数": 30,
      "均值": 150.0,
      "标准差": 25.3
    },
    "检测结果": {
      "趋势方向": "increasing",
      "Sen斜率": 10.0,
      "p值": 0.001,
      "统计显著性": true,
      "置信水平": 0.95
    },
    "使用方法": "mann_kendall",
    "数据点数": 30
  }
}
```

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

响应示例（v5.0 统一格式）：
```json
{
  "解释": "【单变量预测分析结果】\n\n📌 关键发现：\n1. 系统自动选择了 Prophet（适合有季节性的数据）模型进行预测\n2. 预测了未来 24 个时间点的数据\n3. 预测期内整体呈上升趋势\n4. 数据存在周期性规律，预测已考虑这一特征\n\n💡 分析说明：\n我们使用 Prophet 对您的数据进行了分析和预测...\n\n📋 建议：\n• 预测值仅供参考，建议结合实际业务情况进行决策\n• 关注预测区间的上下限",
  "算法结果": {
    "是否成功": true,
    "预测结果": {
      "预测值": [115.0, 118.5, 122.0, ...],
      "时间点": ["2024-01-01 03:00", "2024-01-01 04:00", ...],
      "置信下限": [110.0, 113.0, 116.0, ...],
      "置信上限": [120.0, 124.0, 128.0, ...],
      "训练数据点数": 100,
      "预测步数": 24
    },
    "使用模型": "prophet",
    "数据分析": {
      "数据点数": 100,
      "均值": 107.5,
      "标准差": 8.2,
      "是否有季节性": true,
      "趋势方向": "increasing"
    },
    "预测步数": 24
  }
}
```

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

响应示例（v5.0 统一格式）：
```json
{
  "解释": "【多变量预测分析结果】\n\n📌 关键发现：\n1. 使用 Random Forest（随机森林）进行预测\n2. 综合了多个特征变量进行分析\n3. 模型准确度：非常高（R² = 92%）\n4. 预测期内（14个时间点）整体呈上升趋势\n\n💡 分析说明：\n我们使用随机森林算法，基于多个特征变量进行预测...\n\n📋 建议：\n• 模型准确度较高，预测结果可作为决策参考\n• 预测值会随时间推移而累积误差，建议定期更新模型",
  "算法结果": {
    "是否成功": true,
    "预测结果": {
      "时间点": ["2024-01-15 00:00", "2024-01-16 00:00", ...],
      "预测值": [1100.5, 1125.8, ...],
      "预测期数": 14
    },
    "使用模型": "random_forest",
    "模型ID": "mv_abc12345",
    "模型名称": "sales_forecast",
    "数据分析": {
      "数据点数": 100,
      "特征数量": 3,
      "目标变量统计": {
        "均值": 1050.0,
        "标准差": 85.2
      }
    },
    "评估指标": {
      "均方根误差": 45.2,
      "平均绝对误差": 32.1,
      "决定系数": 0.92
    },
    "是否复用模型": false
  }
}
```

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
