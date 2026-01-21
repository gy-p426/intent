# 因果分析意图识别模块

因果分析意图识别模块负责从用户的自然语言问题中提取因果分析所需的参数，并将SQL查询结果转换为算法服务所需的输入格式。

## 🎯 功能特性

- ✅ **参数提取**：从自然语言问题中识别因变量和自变量
- ✅ **Schema集成**：调用NL2SQL服务获取数据库schema信息
- ✅ **数据处理**：将SQL查询结果转换为算法输入格式
- ✅ **数据清洗**：自动处理缺失值和数据类型转换
- ✅ **参数验证**：确保提取的参数满足算法要求
- ✅ **错误处理**：完善的数据验证和错误提示

## 📋 模块组成

### 1. CausalityExtractor（参数提取器）

负责从用户问题中提取因果分析所需的参数。

**核心功能：**
- 调用NL2SQL服务获取候选表和列信息
- 构建包含schema信息的参数提取提示词
- 解析LLM响应，提取因变量和自变量
- 验证参数的完整性和有效性
- 保存query_db结果供后续SQL生成使用

**关键方法：**
```python
class CausalityExtractor(BaseAlgorithmExtractor):
    @property
    def algorithm_type(self) -> AlgorithmType:
        """返回 AlgorithmType.CAUSALITY"""
    
    @property
    def algorithm_name(self) -> str:
        """返回 "causality" """
    
    async def build_extraction_prompt(
        self,
        question: str,
        database_schema: Optional[List[DatabaseColumn]] = None,
        window_id: str = "default"
    ) -> List[Dict[str, str]]:
        """构建参数提取提示词"""
    
    def parse_extraction_response(self, response: str) -> Dict[str, Any]:
        """解析LLM响应，提取参数"""
    
    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """验证参数完整性"""
    
    def get_last_query_db_result(self) -> Dict[str, Any]:
        """获取最后一次query_db的结果"""
```

### 2. CausalityProcessor（数据处理器）

负责将SQL查询结果转换为因果分析算法的输入格式。

**核心功能：**
- 验证SQL查询结果不为空
- 使用simple_data_fill方法填充数据
- 清洗数据：转换为数值类型，处理缺失值
- 构建符合算法服务要求的请求格式
- 验证数据列数和数据点数量

**关键方法：**
```python
class CausalityProcessor(BaseAlgorithmProcessor):
    @property
    def algorithm_type(self) -> AlgorithmType:
        """返回 AlgorithmType.CAUSALITY"""
    
    @property
    def algorithm_name(self) -> str:
        """返回 "causality" """
    
    async def convert_sql_result_to_algorithm_input(
        self,
        sql_result: List[Dict[str, Any]],
        algorithm_config: AlgorithmConfig,
        parameters: AlgorithmParameters
    ) -> AlgorithmExecutionRequest:
        """将SQL结果转换为算法输入格式"""
    
    async def validate_algorithm_input(
        self,
        request: AlgorithmExecutionRequest,
        algorithm_config: AlgorithmConfig
    ) -> bool:
        """验证算法输入"""
```

### 3. 配置文件（config.py）

定义因果分析算法的元数据和配置信息。

```python
CAUSALITY_CONFIG = {
    "name": "causality",
    "display_name": "因果分析",
    "description": "使用PC算法和贝叶斯网络发现变量之间的因果关系",
    "algorithm_type": "causality",
    "version": "1.0.0"
}
```

## 📁 文件结构

```
causality/
├── __init__.py          # 模块导出
├── config.py            # 算法配置
├── extractor.py         # 参数提取器
├── processor.py         # 数据处理器
└── README.md            # 本文件
```

## 🚀 使用方法

### 1. 算法注册

在系统启动时，因果分析算法会自动注册到算法注册表中：

```python
from algorithm.causality.extractor import CausalityExtractor
from algorithm.causality.processor import CausalityProcessor
from algorithm.base.registry import algorithm_registry

# 注册算法
algorithm_registry.register_algorithm(
    CausalityExtractor(nl2sql_client), 
    CausalityProcessor()
)
```

### 2. 参数提取流程

```python
# 1. 创建Extractor实例
extractor = CausalityExtractor(nl2sql_client)

# 2. 构建提取提示词
prompt = await extractor.build_extraction_prompt(
    question="分析销售额的影响因素有哪些？",
    window_id="default"
)

# 3. 调用LLM获取响应
llm_response = await llm_client.chat(prompt)

# 4. 解析响应
parameters = extractor.parse_extraction_response(llm_response)

# 5. 验证参数
validated_params = extractor.validate_parameters(parameters)
```

### 3. 数据处理流程

```python
# 1. 创建Processor实例
processor = CausalityProcessor()

# 2. 准备SQL查询结果
sql_result = [
    {"销售额": 1000, "广告投入": 500, "促销活动": 1, "季节": 1},
    {"销售额": 1200, "广告投入": 600, "促销活动": 0, "季节": 1},
    {"销售额": 800, "广告投入": 400, "促销活动": 0, "季节": 2}
]

# 3. 转换为算法输入格式
algorithm_request = await processor.convert_sql_result_to_algorithm_input(
    sql_result=sql_result,
    algorithm_config=algorithm_config,
    parameters=parameters
)

# 4. 验证算法输入
is_valid = await processor.validate_algorithm_input(
    request=algorithm_request,
    algorithm_config=algorithm_config
)
```

## 📝 数据格式

### 参数提取输出格式

```json
{
  "parameter_mapping": {
    "dependent_variable": "销售额",
    "independent_variables": ["广告投入", "促销活动", "季节"]
  },
  "required_columns": ["销售额", "广告投入", "促销活动", "季节"],
  "normalized_query": "获取销售数据的销售额、广告投入、促销活动、季节，返回4列数据"
}
```

**字段说明：**
- `parameter_mapping.dependent_variable`: 因变量（结果变量）
- `parameter_mapping.independent_variables`: 自变量列表（可能的原因变量）
- `required_columns`: 所有需要查询的列名
- `normalized_query`: 标准化的查询描述

### 算法输入格式

```json
{
  "data": [
    {"name": "销售额", "values": [1000, 1200, 800]},
    {"name": "广告投入", "values": [500, 600, 400]},
    {"name": "促销活动", "values": [1, 0, 0]},
    {"name": "季节", "values": [1, 1, 2]}
  ],
  "options": {
    "analysis_type": "causal"
  }
}
```

**字段说明：**
- `data`: 列数据数组，每个元素包含列名和数据值
- `options.analysis_type`: 分析类型，固定为 "causal"

## 💡 使用示例

### 示例1：分析销售额的影响因素

**用户问题：**
```
"分析销售额的影响因素有哪些？"
```

**提取的参数：**
```json
{
  "parameter_mapping": {
    "dependent_variable": "销售额",
    "independent_variables": ["广告投入", "促销活动", "价格", "季节"]
  },
  "required_columns": ["销售额", "广告投入", "促销活动", "价格", "季节"]
}
```

### 示例2：研究价格对需求的影响

**用户问题：**
```
"研究价格对需求的影响"
```

**提取的参数：**
```json
{
  "parameter_mapping": {
    "dependent_variable": "需求量",
    "independent_variables": ["价格"]
  },
  "required_columns": ["需求量", "价格"]
}
```

### 示例3：找出客户流失的原因

**用户问题：**
```
"找出客户流失的原因"
```

**提取的参数：**
```json
{
  "parameter_mapping": {
    "dependent_variable": "客户流失",
    "independent_variables": ["服务质量", "价格满意度", "使用频率", "客户年龄"]
  },
  "required_columns": ["客户流失", "服务质量", "价格满意度", "使用频率", "客户年龄"]
}
```

## 🔧 数据处理细节

### 数据填充

使用`_simple_data_fill`方法按照列名映射填充数据：

```python
# 从SQL结果中提取指定列的数据
for col_name in required_columns:
    values = [row.get(col_name) for row in sql_result]
    data_dict[col_name] = values
```

### 数据清洗

将所有数据转换为数值类型：

```python
def _clean_data(self, values: List[Any]) -> List[Union[float, None]]:
    """清洗数据，转换为数值类型"""
    cleaned = []
    for val in values:
        if val is None:
            cleaned.append(None)
        elif isinstance(val, (int, float)):
            cleaned.append(float(val))
        else:
            try:
                cleaned.append(float(val))
            except (ValueError, TypeError):
                cleaned.append(None)
    return cleaned
```

### 数据验证

验证数据满足算法要求：

```python
# 验证列数
if len(data_columns) < 2:
    raise ValueError("因果分析至少需要2列数据（1个因变量 + 1个自变量）")

# 验证每列的数据点数量
for col in data_columns:
    if len(col.values) < 2:
        raise ValueError(f"列{col.name}至少需要2个数据点")
```

## ⚠️ 注意事项

### 参数提取

1. **因变量识别**：确保LLM能够正确识别因变量（结果变量）
2. **自变量识别**：至少需要1个自变量（可能的原因变量）
3. **列名匹配**：提取的列名必须与数据库中的实际列名匹配
4. **Schema信息**：依赖NL2SQL服务提供准确的schema信息

### 数据处理

1. **数据类型**：所有数据必须能够转换为数值类型
2. **缺失值处理**：缺失值会被转换为None，但过多缺失值会影响分析结果
3. **数据量要求**：建议至少30个样本以获得可靠的因果关系
4. **数据质量**：确保数据质量良好，避免异常值和错误数据

### 错误处理

1. **空数据**：SQL查询结果为空时会抛出ValueError
2. **列数不足**：少于2列时会抛出ValueError
3. **数据点不足**：任意列少于2个数据点时会抛出ValueError
4. **类型转换失败**：无法转换为数值的数据会被设置为None

## 🧪 测试

### 单元测试

```python
import pytest
from algorithm.causality.extractor import CausalityExtractor
from algorithm.causality.processor import CausalityProcessor

def test_parameter_extraction():
    """测试参数提取"""
    extractor = CausalityExtractor(nl2sql_client=None)
    
    response = {
        "parameter_mapping": {
            "dependent_variable": "销售额",
            "independent_variables": ["广告投入", "促销活动"]
        },
        "required_columns": ["销售额", "广告投入", "促销活动"]
    }
    
    result = extractor.parse_extraction_response(json.dumps(response))
    
    assert "parameter_mapping" in result
    assert result["parameter_mapping"]["dependent_variable"] == "销售额"
    assert len(result["parameter_mapping"]["independent_variables"]) == 2

def test_data_processing():
    """测试数据处理"""
    processor = CausalityProcessor()
    
    sql_result = [
        {"销售额": 1000, "广告投入": 500},
        {"销售额": 1200, "广告投入": 600}
    ]
    
    # 测试数据转换
    # ... 测试代码 ...
```

### 属性测试

使用`hypothesis`库进行属性测试：

```python
from hypothesis import given, strategies as st

@given(st.lists(st.floats(min_value=-1000, max_value=1000), min_size=2))
def test_data_cleaning_preserves_length(values):
    """测试数据清洗保持长度不变"""
    processor = CausalityProcessor()
    cleaned = processor._clean_data(values)
    assert len(cleaned) == len(values)
```

## 🔗 相关模块

- **算法服务**：`algorithm/analysis-algorithm/causal-service/`
- **算法注册**：`algorithm/base/registry.py`
- **算法执行器**：`algorithm/executor/algorithm_executor.py`
- **API客户端**：`algorithm/clients/algorithm_api_client.py`
- **数据处理器基类**：`algorithm/processors/data_processor.py`

## 📚 参考文档

- [设计文档](../../.kiro/specs/causality-analysis/design.md)
- [需求文档](../../.kiro/specs/causality-analysis/requirements.md)
- [任务列表](../../.kiro/specs/causality-analysis/tasks.md)

## 🔄 更新日志

**v1.0.0** (2025-01-16)
- ✅ 初始版本发布
- ✅ 实现CausalityExtractor参数提取器
- ✅ 实现CausalityProcessor数据处理器
- ✅ 完整的数据验证和错误处理
- ✅ 集成到系统算法注册表

## 📄 许可证

本项目仅供内部使用。
