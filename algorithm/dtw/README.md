# DTW 动态时间规整算法

## 算法简介

DTW（Dynamic Time Warping，动态时间规整）是一种用于测量两个时间序列之间相似度的算法，通过动态规划找到两个序列的最优对齐路径。

**适用场景**：
- 时间序列相似度分析
- 传感器数据匹配（温度、湿度、功率等）
- 实际值与预测值对比
- 设备性能对比分析
- 金融时间序列对比

**主要特点**：
1. 能够处理长度不同的时间序列
2. 对时间轴上的非线性扭曲具有鲁棒性
3. 相比欧氏距离更适合衡量时间序列的相似性
4. 支持多种距离度量和步进模式

## 架构说明

DTW算法采用**独立FastAPI服务**的架构：

```
┌─────────────────────────────────────────────────────────────┐
│                    Intent服务                                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ DTWExtractor │→ │ DTWProcessor │→ │ API Client   │      │
│  │ (参数提取)    │  │ (数据处理)    │  │ (调用服务)    │      │
│  └──────────────┘  └──────────────┘  └──────┬───────┘      │
└────────────────────────────────────────────┼────────────────┘
                                              │ HTTP
                                              ↓
┌─────────────────────────────────────────────────────────────┐
│              DTW相似度分析服务 (端口8025)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   FastAPI    │→ │ DTWAnalyzer  │→ │   响应格式    │      │
│  │   路由       │  │ (算法实现)    │  │   (中文)      │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

**服务位置**：
- Intent模块：`Intelligent_retrieval_and_analysis/intent/algorithm/dtw/`
- 独立服务：`algorithm/analysis-algorithm/similarity-service/`

## 参数说明

### 必需参数

- **time_series1**: 第一个时间序列数据所在的列名，该列应为数值型数据
- **time_series2**: 第二个时间序列数据所在的列名，该列应为数值型数据

### 可选参数

- **normalize**: 是否对序列进行归一化处理（缩放到 0-1 范围），默认值：`true`
  - 建议：数值范围差异大时使用归一化
  
- **distance_metric**: 距离度量方式，默认值：`"euclidean"`
  - `"euclidean"`：欧氏距离（推荐，适合大多数情况）
  - `"manhattan"`：曼哈顿距离（对极端值不敏感）
  - `"cosine"`：余弦距离（只关心趋势方向）
  
- **step_pattern**: 步进模式，默认值：`"symmetric2"`
  - `"symmetric2"`：改进对称模式（推荐，鼓励一对一匹配）
  - `"symmetric1"`：标准对称模式（路径灵活）
  - `"asymmetric"`：非对称模式（限制严格）
  
- **window_size**: Sakoe-Chiba窗口大小，用于限制路径搜索范围，默认值：`None`（不限制）
  - 建议：序列长度相近时可设置窗口约束以提高性能

## 数据要求

1. **最小数据量**：每个序列至少需要 2 个数据点
2. **数据类型**：time_series1 和 time_series2 必须是数值型
3. **列的唯一性**：time_series1 和 time_series2 不能是同一列
4. **数据完整性**：缺失值会被自动跳过，但建议预先处理
5. **数据顺序**：数据将按查询返回的原始顺序处理，请确保数据库查询已正确排序

## 使用示例

### 示例 1：温度与湿度相似度分析

```json
{
  "parameter_mapping": {
    "time_series1": "temperature",
    "time_series2": "humidity",
    "normalize": true,
    "distance_metric": "euclidean",
    "step_pattern": "symmetric2",
    "window_size": null
  },
  "required_columns": ["temperature", "humidity"],
  "normalized_query": "获取温度、湿度，共2列数据"
}
```

### 示例 2：实际销量与预测销量对比

```json
{
  "parameter_mapping": {
    "time_series1": "actual_sales",
    "time_series2": "predicted_sales",
    "normalize": false,
    "distance_metric": "euclidean",
    "step_pattern": "symmetric2",
    "window_size": 5
  },
  "required_columns": ["actual_sales", "predicted_sales"],
  "normalized_query": "获取实际销量、预测销量，共2列数据"
}
```

## 输出格式

### 响应结构

```json
{
  "解释": "两个序列的相似度为95.2%，相似度很高，序列变化趋势基本一致...",
  "算法结果": {
    "DTW距离": 0.48,
    "归一化距离": 0.048,
    "相似度得分": 0.952,
    "对齐路径长度": 100,
    "距离度量": "欧氏距离",
    "步进模式": "改进对称模式",
    "是否归一化": "是",
    "窗口约束": "无",
    "详细信息": {
      "序列1长度": 100,
      "序列2长度": 100,
      "路径长度": 100,
      "平均距离": 0.096,
      "最小距离": 0.0,
      "最大距离": 0.2,
      "参数说明": {
        "距离度量": "使用欧氏距离计算两点差异...",
        "步进模式": "改进对称模式：鼓励斜着走...",
        "归一化": "已将两个序列都缩放到0-1之间...",
        "窗口约束": "没有限制对齐路径..."
      }
    }
  }
}
```

### 相似度解释

- **100%**：完全相同的趋势
- **50%**：完全相反的趋势（在中间点相遇）
- **0%**：完全随机/不相关

## 配置管理

### 环境变量配置

在 `.env` 文件中添加：

```properties
# DTW相似度分析服务
SIMILARITY_SERVICE_NAME=similarity-service
SIMILARITY_API_URL=http://localhost:8025
```

### 服务启动

```bash
# 启动DTW相似度分析服务
cd algorithm/analysis-algorithm/similarity-service
python app/main.py

# 或使用uvicorn
uvicorn app.main:app --host 0.0.0.0 --port 8025
```

## 开发指南

### 1. 算法注册

在 `algorithm/base/registry.py` 中注册：

```python
from algorithm.dtw.extractor import DTWExtractor
from algorithm.dtw.processor import DTWProcessor

algorithm_registry.register_algorithm(
    DTWExtractor(nl2sql_client), 
    DTWProcessor()
)
```

### 2. API客户端配置

在 `algorithm/clients/algorithm_api_client.py` 中添加：

```python
# 服务映射
self.service_mapping = {
    'similarity': self.settings.similarity_service_name,
}

# API调用方法
async def call_similarity_api(self, data_rows, config):
    payload = {
        "time_series1": config.get('time_series1'),
        "time_series2": config.get('time_series2'),
        "normalize": config.get('normalize', True),
        "distance_metric": config.get('distance_metric', 'euclidean'),
        "step_pattern": config.get('step_pattern', 'symmetric2'),
        "window_size": config.get('window_size')
    }
    return await self.call_algorithm_api(
        "similarity", 
        "/api/v1/similarity/dtw", 
        "POST", 
        payload
    )
```

### 3. 测试

运行测试用例：

```bash
# 单元测试
python -m pytest algorithm/dtw/tests/

# 集成测试
python test_dtw_integration.py
```

## 关键实现细节

### 1. 参数提取器 (extractor.py)

- 从用户自然语言中提取算法参数
- 要求LLM使用数据库中实际存在的列名
- 处理参数默认值和类型转换
- 验证参数的有效性

### 2. 数据处理器 (processor.py)

- 将SQL查询结果转换为算法输入格式
- 数据清洗：处理缺失值、类型转换
- 可选的归一化处理
- 提取两个数值序列数组

### 3. 独立服务 (similarity-service)

- FastAPI实现的RESTful API
- 完整的DTW算法实现（动态规划）
- 支持多种距离度量和步进模式
- 用户友好的中文输出格式

## 常见问题

### Q: 为什么相反趋势的相似度是50%而不是0%？

A: 这是合理的设计。完全相反的趋势在中间点会相遇，因此相似度约为50%。这样的设计更符合直觉：
- 完全相同 = 100%
- 完全相反 = 50%
- 完全随机 = 0%

### Q: 什么时候应该使用归一化？

A: 当两个序列的数值范围差异很大时（如温度20-30度 vs 湿度50-90%），建议使用归一化以确保公平比较。

### Q: 如何选择距离度量方法？

A: 
- **欧氏距离**：适合大多数情况（推荐）
- **曼哈顿距离**：对极端值不敏感，适合有噪声的数据
- **余弦距离**：只关心趋势方向，不在意数值大小

### Q: 窗口约束有什么作用？

A: 窗口约束可以限制对齐路径不能偏离太远，可以加快计算速度，适合长度相近的序列。

## 注意事项

1. 确保提取器和处理器的 `algorithm_type` 和 `algorithm_name` 完全一致
2. 提示词中要求 LLM 使用数据库中实际存在的列名
3. 数据处理时要进行适当的类型转换和清洗
4. 验证逻辑要严格检查数据质量和参数有效性
5. 添加充分的日志记录，便于调试
6. 独立服务需要单独部署和维护

## 文件结构

```
algorithm/dtw/                                    # Intent模块
├── __init__.py                                   # 模块初始化
├── extractor.py                                  # 参数提取器
├── processor.py                                  # 数据处理器
├── config.py                                     # 算法配置
├── README.md                                     # 本文档
├── STANDARD_INPUT.json                           # 标准输入示例
└── tests/                                        # 测试用例
    ├── __init__.py
    ├── test_extractor.py
    └── test_processor.py

algorithm/analysis-algorithm/similarity-service/  # 独立服务
├── app/
│   ├── main.py                                   # FastAPI主应用
│   ├── api/routes.py                            # API路由
│   ├── schemas/request_response.py              # 请求响应模型
│   └── services/dtw_analyzer.py                 # DTW算法实现
├── test_service.py                               # 服务测试
├── test_data_*.json                              # 测试数据
└── requirements.txt                              # 依赖
```

## 参考文档

- **算法接入指南**: `Intelligent_retrieval_and_analysis/intent/算法接入(1).md`
- **DTW接入案例**: 见算法接入指南末尾的"DTW相似度分析接入完整案例"章节
- **独立服务实现**: `algorithm/analysis-algorithm/similarity-service/`

## 贡献

开发完成后，请：

1. 确保所有测试通过
2. 更新相关文档
3. 提交代码审查
4. 验证独立服务正常运行
