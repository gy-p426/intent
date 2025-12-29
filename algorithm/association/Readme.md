# 关联分析 (Association Analysis)

### 1.算法简介

关联分析算法能够自动识别两列数据的类型（分类型或数值型），并根据数据类型自动选择最合适的统计分析方法来分析两个变量之间的关联关系。

#### 算法原理

- **数据类型检测**: 自动检测列数据是分类型还是数值型
- **方法自动选择**: 根据两列的数据类型组合，自动选择最合适的统计方法
- **统计分析**: 执行相应的统计检验，计算统计量、P 值和效应量
- **结果解释**: 提供易于理解的文字解释

#### 支持的分析方法

| 方法                         | 适用场景     | 统计量                         | 效应量        |
| ---------------------------- | ------------ | ------------------------------ | ------------- |
| **卡方检验** (Chi-Square)    | 分类 vs 分类 | Chi-Square, P-value            | Cramér's V    |
| **相关性分析** (Correlation) | 数值 vs 数值 | Pearson r, Spearman ρ, P-value | Pearson r, R² |
| **方差分析** (ANOVA)         | 分类 vs 数值 | F-statistic, P-value           | Eta²          |

#### 主要特点

- ✅ **智能类型检测**: 自动识别数据类型，无需人工指定
- ✅ **自动方法选择**: 根据数据类型自动选择最合适的分析方法
- ✅ **完整统计结果**: 提供统计量、P 值、效应量等完整指标
- ✅ **结果解释**: 提供易于理解的文字解释
- ✅ **详细报告**: 可选返回详细的统计信息

### 2.参数说明

#### （1）必需参数

- **column1_name** (string): 第一列数据的名称（数据库列名）
  - 示例: `"age"`, `"gender"`, `"education"`
- **column2_name** (string): 第二列数据的名称（数据库列名）
  - 示例: `"salary"`, `"product_preference"`, `"income"`

#### （2）可选参数

- **significance_level** (float): 显著性水平，默认值：`0.05`

  - 取值范围: `0.001` ~ `0.5`
  - 常用值: `0.01`, `0.05`, `0.1`
  - 说明: 用于判断结果是否统计显著

- **data_type_column1** (string): 第一列数据类型，默认值：`"auto"`

  - 选项:
    - `"auto"` - 自动检测（推荐）
    - `"categorical"` - 分类型
    - `"numerical"` - 数值型

- **data_type_column2** (string): 第二列数据类型，默认值：`"auto"`

  - 选项:
    - `"auto"` - 自动检测（推荐）
    - `"categorical"` - 分类型
    - `"numerical"` - 数值型

- **method** (string): 分析方法，默认值：`"auto"`

  - 选项:
    - `"auto"` - 自动选择（推荐）
    - `"chi_square"` - 卡方检验（分类 vs 分类）
    - `"correlation"` - 相关性分析（数值 vs 数值）
    - `"anova"` - 方差分析（分类 vs 数值）

- **return_details** (boolean): 是否返回详细统计信息，默认值：`true`
  - `true` - 返回完整的统计详情
  - `false` - 仅返回基本结果

#### （3）数据要求

- 每列至少需要 **2 个数据点**
- 两列数据长度必须 **完全相同**
- 数据可以包含缺失值（系统会自动处理）
- 清洗后有效数据点少于 2 个时将报错

### 使用场景

#### 场景 1: 数值相关性分析

**用户问题**: "员工年龄和薪资有什么关系？"

**分析类型**: 相关性分析（Correlation）

**预期结果**:

- Pearson 相关系数
- Spearman 等级相关系数
- R² 决定系数
- P 值
- 相关方向（正/负）
- 相关强度（弱/中等/强）

**示例解释**: "员工年龄 与 月薪 之间存在强正相关"

---

#### 场景 2: 分类关联分析

**用户问题**: "性别和产品偏好有关联吗？"

**分析类型**: 卡方检验（Chi-Square Test）

**预期结果**:

- 卡方统计量
- Cramér's V（效应量）
- P 值
- 列联表
- 关联强度（极弱/弱/中等/强）

**示例解释**: "性别 与 产品偏好 之间存在显著关联（关联强度: 中等）"

---

#### 场景 3: 混合类型分析

**用户问题**: "不同学历的收入有差异吗？"

**分析类型**: 方差分析（ANOVA）

**预期结果**:

- F 统计量
- Eta²（效应量）
- P 值
- 各组统计信息（均值、标准差等）
- 效应大小（极小/小/中等/大）

**示例解释**: "学历 对 年收入 有显著影响（效应: 大）"

---

### 参数示例

#### 示例 1: 基础用法（自动模式）

```json
{
  "parameter_mapping": {
    "column1_name": "age",
    "column2_name": "salary"
  }
}
```

#### 示例 2：指定数据类型

```
{
  "parameter_mapping": {
    "column1_name": "gender",
    "column2_name": "product_preference",
    "data_type_column1": "categorical",
    "data_type_column2": "categorical"
  }
}
```

#### 示例 3：完整参数配置

```
{
  "parameter_mapping": {
    "column1_name": "age",
    "column2_name": "salary",
    "significance_level": 0.05,
    "data_type_column1": "numerical",
    "data_type_column2": "numerical",
    "method": "correlation",
    "return_details": true
  }
}
```

### 返回结果示例

```
{
  "status": "success",
  "analysis": {
    "column1_type": "numerical",
    "column2_type": "numerical",
    "method_used": "correlation",
    "statistic_name": "Pearson r",
    "statistic_value": 0.9827,
    "p_value": 0.0005,
    "effect_size": 0.9827,
    "effect_size_name": "Pearson r",
    "significant": true,
    "interpretation": "年龄 与 月薪 之间存在强正相关",
    "details": {
      "pearson_r": 0.9827,
      "pearson_p": 0.0005,
      "spearman_r": 0.9429,
      "spearman_p": 0.0048,
      "r_squared": 0.9657,
      "sample_size": 50,
      "direction": "正",
      "strength": "强"
    }
  },
  "message": "分析完成"
}
```

## 开发指南

### 1. 复制模板

```bash
cp -r algorithm/template algorithm/your_algorithm_name
```

### 2. 修改文件名

- `extractor_template.py` → `extractor.py`
- `processor_template.py` → `processor.py`
- `config_template.py` → `config.py`
- `README_template.md` → `README.md`

### 3. 修改代码

1. **修改提取器** (`extractor.py`)：

   - 更新 `algorithm_type` 和 `algorithm_name`
   - 设计算法特定的提示词
   - 实现响应解析和参数验证逻辑

2. **修改处理器** (`processor.py`)：

   - 更新 `algorithm_type` 和 `algorithm_name`
   - 实现数据转换和清洗逻辑
   - 实现数据验证逻辑

3. **修改配置** (`config.py`)：

   - 更新算法信息和参数定义
   - 添加使用示例

4. **更新文档** (`README.md`)：
   - 完善算法说明和使用指南

### 4. 创建测试用例

在 `tests/` 目录下创建测试文件：

- `test_extractor.py`
- `test_processor.py`

### 5. 注册算法

在 `algorithm/base/registry.py` 中添加：

```python
from algorithm.your_algorithm_name.extractor import YourAlgorithmExtractor
from algorithm.your_algorithm_name.processor import YourAlgorithmProcessor
algorithm_registry.register_algorithm(YourAlgorithmExtractor(), YourAlgorithmProcessor())
```

## 开发规范

### 提示词设计规范

- 必须要求 LLM 使用数据库中实际存在的列名
- 提供完整的数据库 schema 信息
- 明确标记特殊类型的列（如数值型、分类型）
- 严格定义 JSON 输出格式
- 包含具体的使用示例

### 数据处理规范

- 使用 `_simple_data_fill` 方法进行数据填充
- 实现算法特定的数据清洗逻辑
- 严格验证输入数据的完整性和质量
- 提供详细的错误日志

### 测试规范

- 测试正常的参数提取流程
- 测试异常情况的处理
- 测试数据转换的正确性
- 测试数据验证的严格性

## 注意事项

1. 确保提取器和处理器的 `algorithm_type` 和 `algorithm_name` 完全一致
2. 提示词中要求 LLM 使用数据库中实际存在的列名
3. 数据处理时要进行适当的类型转换和清洗
4. 验证逻辑要严格检查数据质量和参数有效性
5. 添加充分的日志记录，便于调试

## 文件结构

```
algorithm/your_algorithm_name/
├── __init__.py          # 模块初始化
├── extractor.py         # 参数提取器
├── processor.py         # 数据处理器
├── config.py           # 算法配置
├── tests/              # 测试用例
│   ├── __init__.py
│   ├── test_extractor.py
│   └── test_processor.py
└── README.md           # 算法说明文档
```

## 测试

运行测试用例：

```bash
python -m pytest algorithm/your_algorithm_name/tests/
```

## 贡献

开发完成后，请：

1. 确保所有测试通过
2. 更新相关文档
3. 提交代码审查

## 今日剩余问题一览

### Q1：readme 中输入格式不正确

### Q2：代码未验证，例如可选参数是否发挥左右等

### Q3：kiro？

### Q4：未完待续
