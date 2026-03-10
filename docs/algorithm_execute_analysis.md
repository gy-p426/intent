# /api/v1/algorithm/execute 接口流程分析与Agent化改造潜力评估

## 一、接口概述

`POST /api/v1/algorithm/execute` 是算法集成服务的核心接口，负责接收用户的自然语言查询，经过完整的算法分析流程后以流式响应返回实时处理进度和最终结果。

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `question` | string | 是 | 用户自然语言查询（1-1000字符） |
| `window_id` | string | 否 | 窗口ID，默认 "default" |
| `session_id` | string | 是 | 会话ID |
| `user_id` | int | 是 | 用户ID |
| `auto_analysis` | bool | 否 | 是否自动分析；`None`/`true`=自动；`false`=手动选择数据库信息 |
| `stream` | bool | 否 | 是否流式返回，默认 `true` |
| `agent_algorithm` | bool | 否 | 是否使用Agent算法分析，默认 `false` |
| `fileIds` | string/list | 否 | 文件ID列表（支持逗号分隔字符串或整数数组） |

### 响应格式

流式响应（`StreamingResponse`），每条消息为 `AlgorithmResponse` 结构：

```json
{
  "step": "algorithm_identification | parameter_extraction | sql_generation | ...",
  "status": "processing | completed | error",
  "data": { ... },
  "error": null,
  "timestamp": "2025-01-01T00:00:00Z"
}
```

---

## 二、当前完整执行流程

接口的执行流程根据请求参数的不同，分为**三条主分支**：

1. **文件上传流程**（`fileIds` 非空）
2. **Agent算法分析流程**（`agent_algorithm=true`）
3. **传统算法分析流程**（默认路径）

以下按照代码执行顺序逐步说明。

### 2.1 API层入口处理（`api/algorithm_api.py`）

```
POST /api/v1/algorithm/execute
    ↓
execute_algorithm() 方法
```

**步骤说明：**

1. **服务可用性检查**：验证 `algorithm_service` 是否已初始化，未初始化返回 503 错误。
2. **请求日志记录**：记录请求参数（question, window_id, session_id, agent_algorithm, user_id, fileIds）。
3. **fileIds处理**：如果 `fileIds` 是数组，转换为逗号分隔的字符串格式。
4. **创建响应生成器**：调用 `algorithm_service.process_algorithm_request()` 创建异步生成器。
5. **响应分发**：
   - `stream=true`：通过 `StreamingResponseHandler` 创建流式响应，支持客户端断连检测。
   - `stream=false`：收集所有响应，返回最终结果。
6. **异常处理**：`ValueError` → 400，其他异常 → 500。

### 2.2 服务层核心逻辑（`algorithm/service.py`）

入口方法：`AlgorithmIntegrationService.process_algorithm_request()`

#### 2.2.0 公共前置步骤

| 步骤 | 操作 | 说明 |
|------|------|------|
| 生成追踪ID | `uuid.uuid4()` | 用于全链路日志追踪 |
| 构建请求上下文 | 组装 `request_context` | 包含所有请求参数和追踪信息 |
| 参数验证 | `_validate_request_parameters()` | 验证 question（非空、长度≤1000）和 window_id（非空） |
| 组件验证 | `_validate_components()` | 确认 router、parameter_extractor、config_manager 已初始化 |
| 结构化日志 | `structured_logger.log_algorithm_request()` | 记录算法请求开始 |

#### 2.2.1 分支判断：文件上传流程

```python
if fileIds:  # fileIds 非空 → 文件上传流程
    → _process_file_upload_to_agent()
    → return  # 文件处理完成后直接返回
```

**文件上传流程详情（`_process_file_upload_to_agent`）：**

| 子步骤 | 操作 | 说明 |
|--------|------|------|
| F1 | 获取文件详情 | 调用NL2SQL服务的 `/api/file/manage/detail/{fileIds}` 接口 |
| F2 | 解析文件数据 | 支持单文件（dict）和多文件（list）格式 |
| F3 | 读取文件内容 | 根据文件路径读取文件二进制内容 |
| F4 | 构建multipart请求 | 组装 files + request_data（query） |
| F5 | 调用Agent服务 | POST `{agent_base_url}/query_agents_stream`，流式接收SSE事件 |
| F6 | 透传SSE事件 | 解析 `data: {...}` 格式事件，直接包装为 `AlgorithmResponse` 透传 |

#### 2.2.2 追问判断（公共步骤，适用于非文件上传路径）

| 子步骤 | 操作 | 说明 |
|--------|------|------|
| C1 | 流式返回"正在分析意图" | `StreamingStep.INTENT_ANALYSIS` processing |
| C2 | 调用追问判断接口 | `nl2sql_client.check_continuous_question()` |
| C3 | 处理追问结果 | 如果是追问（`isContinuous=true`），将问题替换为合并后的问题（`mergedQuestion`） |
| C4 | 流式返回追问结果 | 包含 `is_continuous`、`merged_question`、`message` |
| C5 | 保存问题到Session | `nl2sql_client.save_question()` 保存到历史记录 |

**注意：** 追问判断和问题保存均为非阻塞性操作，失败不影响主流程。

#### 2.2.3 分支判断：Agent流程 vs 传统流程

```python
if agent_algorithm:
    → _process_agent_algorithm()     # Agent算法分析
else:
    → _process_with_error_handling() # 传统算法分析
```

---

### 2.3 Agent算法分析流程（`_process_agent_algorithm`）

```
用户问题 → 候选表获取 → 问题标准化 → SQL生成与执行 → CSV转换 → Agent服务调用 → 结果透传
```

| 步骤 | 操作 | 依赖组件 | 流式步骤标识 |
|------|------|----------|-------------|
| A0 | 获取候选表信息 | `get_candidate_tables_from_nl2sql()` → `nl2sql_client.query_db()` | `ALGORITHM_IDENTIFICATION` |
| A1 | 问题标准化 | `normalize_question_for_agent()` → LLM调用 | `ALGORITHM_IDENTIFICATION` |
| A2 | SQL生成与执行 | `_query_nl2sql_with_candidates_retry()` 或 `_query_nl2sql_with_retry()` | `SQL_GENERATION` / `DATA_RETRIEVAL` |
| A3 | CSV数据转换 | `CSVConverter.convert_to_csv()` | （无独立步骤） |
| A4 | 调用Agent服务 | `AgentAlgorithmClient.analyze_streaming()` | `AGENT_ALGORITHM_ANALYSIS` |
| A5 | 透传Agent事件 | 逐事件yield `AlgorithmResponse` | `AGENT_ALGORITHM_ANALYSIS` |

**关键特征：**
- Agent流程使用外部Agent服务（`agent_algorithm_analysis_url`配置）进行分析
- 数据以CSV格式传递给Agent服务
- Agent服务返回SSE流，本服务原封不动透传

---

### 2.4 传统算法分析流程（`_process_with_error_handling`）

```
用户问题 → 算法类型识别 → [NL2SQL分支/参数提取] → SQL生成 → 数据检索 → 算法执行 → 结果分析
```

#### 步骤1：算法类型识别

| 操作 | 说明 |
|------|------|
| 调用 `_identify_algorithm_type_with_retry()` | 通过算法路由器（LLM或RAG+关键词）识别算法类型 |
| 支持的算法类型 | cluster, classify, predict, anomaly, associate, similarity, trend, causality, nl2sql, compare_proportion 等 |
| 流式返回 | `StreamingStep.ALGORITHM_IDENTIFICATION` → 返回 `algorithm_type` 和中文名称 |

#### NL2SQL数据查询分支

如果识别为 `AlgorithmType.NL2SQL`（智能检索），直接调用NL2SQL流式接口：

```python
if algorithm_type == AlgorithmType.NL2SQL:
    → nl2sql_client.query_stream()  # 流式返回查询结果
    → return  # NL2SQL流程结束，不执行后续算法
```

#### 步骤2：参数提取

| 操作 | 说明 |
|------|------|
| 调用 `_extract_parameters_with_retry()` | 通过LLM从用户问题中提取算法所需参数 |
| 返回内容 | `normalized_query`（规范化查询）、`required_columns`（所需列）、`parameter_mapping`（参数映射）、`query_db_result`（候选表信息） |
| 流式返回 | `StreamingStep.PARAMETER_EXTRACTION` → 返回参数提取结果 |

**手动模式分支**（`auto_analysis=false`时）：

```python
if auto_analysis is False:
    → 构建 required_columns 映射
    → 解析候选表信息 → 返回 db_schema_options
    → 保存上下文到 ManualContextStore
    → 返回 StreamingStep.MANUAL_DB_SELECTION
    → return  # 等待用户通过 manual-db-selection / manual-run 接口继续
```

#### 步骤3：SQL生成与数据检索

| 操作 | 说明 |
|------|------|
| 判断是否有预获取的候选表 | 优化：使用参数提取阶段已获取的候选表信息避免重复调用 `/query-db` |
| 调用NL2SQL服务 | `_query_nl2sql_with_candidates_retry()` 或 `_query_nl2sql_with_retry()` |
| 流式返回SQL生成结果 | `StreamingStep.SQL_GENERATION` → 返回 `sql_statement`、`execution_time_ms` |
| 流式返回数据检索结果 | `StreamingStep.DATA_RETRIEVAL` → 返回 `data_rows_count`、`sample_data` |

#### 步骤4：算法执行

| 子步骤 | 操作 | 说明 |
|--------|------|------|
| 4.1 | 获取算法配置 | `config_manager.get_algorithm_config(algorithm_type)` |
| 4.2 | 数据格式转换 | `_convert_data_with_validation()` → `data_processor.convert_sql_result_to_algorithm_input()` |
| 4.3 | 执行算法 | `_execute_algorithm_with_retry()` → 根据算法类型分发至对应执行器 |
| 4.4a | 同步结果处理 | 直接获取 `execution_response.result` |
| 4.4b | 异步任务处理 | 通过 `_handle_async_task_with_timeout()` 轮询任务状态 |

**支持的算法执行器分发：**

| 算法类型 | 执行方法 |
|---------|---------|
| `CLUSTER` | `execute_clustering()` |
| `CLASSIFY` | `execute_classification()` |
| `ANOMALY` | `execute_anomaly_detection()` |
| `COMPARE_PROPORTION` | `execute_compare_proportion()` |
| `TREND` | `execute_trend_analysis()` |
| `PREDICT` | `execute_univariate_forecast()` / `execute_multivariate_forecast()` |
| `ASSOCIATE` | `execute_association()` |
| `CAUSALITY` | `execute_causality_analysis()` |
| `SIMILARITY` | `execute_similarity()` |

#### 步骤5：结果分析与格式化

| 操作 | 说明 |
|------|------|
| 结果有效性检查 | 判断算法结果是否包含有效内容 |
| 大模型结果分析 | `_format_readable_result_with_llm()` → 通过LLM将算法结果转换为自然语言分析 |
| 降级处理 | LLM分析失败时使用 `_generate_fallback_analysis()` 生成基础分析文本 |
| 构建最终响应 | 组装 `algorithm_result`、`sql_statement`、`readable_result` 等完整结果 |
| 流式返回 | `StreamingStep.COMPLETED` → 返回完整分析结果 |

---

## 三、完整流程图

```
                    ┌─────────────────────────────────────────┐
                    │  POST /api/v1/algorithm/execute          │
                    │  (API层: algorithm_api.py)               │
                    └──────────────┬──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────┐
                    │  服务可用性检查 + fileIds格式转换          │
                    └──────────────┬──────────────────────────┘
                                   │
                    ┌──────────────▼──────────────────────────┐
                    │  process_algorithm_request()              │
                    │  参数验证 + 组件验证 + 生成trace_id       │
                    └──────────────┬──────────────────────────┘
                                   │
                         ┌─────────┴─────────┐
                    fileIds非空?              fileIds空
                         │                       │
                    ┌────▼────┐          ┌───────▼────────┐
                    │文件上传  │          │ 追问判断(C1-C5) │
                    │流程(F1-F6)│         │ + 问题保存      │
                    └────┬────┘          └───────┬────────┘
                         │                       │
                    return              ┌────────┴────────┐
                                   agent_algorithm?     否
                                        │                │
                                   ┌────▼────┐   ┌──────▼──────┐
                                   │Agent流程 │   │ 传统流程     │
                                   │(A0-A5)  │   │              │
                                   └────┬────┘   │ 步骤1:算法识别│
                                        │        │      │       │
                                   return        │  NL2SQL? ────→ query_stream → return
                                                 │      │       │
                                                 │ 步骤2:参数提取│
                                                 │      │       │
                                                 │ 手动模式? ───→ 返回schema → return
                                                 │      │       │
                                                 │ 步骤3:SQL生成 │
                                                 │ + 数据检索    │
                                                 │      │       │
                                                 │ 步骤4:算法执行│
                                                 │ (同步/异步)   │
                                                 │      │       │
                                                 │ 步骤5:LLM分析│
                                                 │ + 结果返回    │
                                                 └──────┴──────┘
```

---

## 四、关键依赖组件清单

| 组件 | 接口 | 实现类/模块 | 职责 |
|------|------|------------|------|
| 算法路由器 | `IAlgorithmRouter` | `pure_llm_selector.py` | 通过LLM识别算法类型 |
| 参数提取器 | `IParameterExtractor` | 各算法目录下的 `extractor.py` | 从自然语言中提取算法参数 |
| NL2SQL客户端 | `INL2SQLClient` | `algorithm/clients/` | 自然语言转SQL、数据检索 |
| 算法执行器 | `IAlgorithmExecutor` | `algorithm/executor/` | 调用外部算法服务API |
| 数据处理器 | `IDataProcessor` | `algorithm/processors/` | SQL结果转算法输入格式 |
| 流式响应处理器 | `IStreamingResponseHandler` | `algorithm/streaming/` | 创建SSE/chunked流式响应 |
| 配置管理器 | `IAlgorithmConfigManager` | `algorithm/config_manager.py` | 算法配置加载和管理 |
| 任务管理器 | `ITaskManager` | `algorithm/tasks/` | 异步任务生命周期管理 |
| 结果分析器 | `AlgorithmResultAnalyzer` | `llm/algorithm_result_analyzer.py` | LLM分析算法结果 |
| 问题标准化 | `normalize_question_for_agent` | `algorithm/agent/` | 问题规范化处理 |
| 重试处理器 | `RetryHandler` | `algorithm/error_handler.py` | 失败重试策略 |
| 错误处理器 | `ErrorHandler` | `algorithm/error_handler.py` | 统一错误处理 |

---

## 五、Agent化改造潜力分析

基于上述流程分析，以下识别出具有Agent化改造潜力的步骤，并给出初步改造理由。

### 5.1 可改造步骤总览

| 编号 | 步骤 | 当前实现 | Agent化潜力 | 优先级 |
|------|------|---------|------------|--------|
| S1 | 追问判断 | 调用NL2SQL外部接口 | ⭐⭐⭐ 高 | P1 |
| S2 | 算法类型识别 | LLM单次调用 | ⭐⭐⭐⭐ 很高 | P0 |
| S3 | 参数提取 | LLM单次调用 | ⭐⭐⭐⭐ 很高 | P0 |
| S4 | SQL生成与数据检索 | 调用NL2SQL外部服务 | ⭐⭐ 中 | P2 |
| S5 | 数据格式转换 | 规则引擎处理 | ⭐ 低 | P3 |
| S6 | 算法执行 | 调用外部算法API | ⭐ 低 | P3 |
| S7 | 结果分析与格式化 | LLM单次调用 | ⭐⭐⭐ 高 | P1 |
| S8 | 全流程编排 | 硬编码if-else分支 | ⭐⭐⭐⭐⭐ 极高 | P0 |

### 5.2 各步骤详细分析

#### S1: 追问判断 — Agent化潜力：高

**当前实现：**
- 调用 `nl2sql_client.check_continuous_question()` 外部接口
- 获取 `isContinuous`、`mergedQuestion`、`previousQuestion`
- 如果是追问，合并问题后继续处理

**改造理由：**
- 追问判断本质上是一个**对话上下文理解**任务，非常适合Agent的记忆和推理能力
- Agent可以维护完整的对话历史，不仅判断是否追问，还能理解对话意图演变
- 当前实现依赖外部接口，Agent化后可内聚为Agent的内置能力
- Agent可以更智能地处理多轮对话中的隐含条件和指代消解

**改造方式建议：**
将追问判断内化为Agent的对话管理能力，Agent维护对话上下文，自动决定是否合并、如何合并问题。

---

#### S2: 算法类型识别 — Agent化潜力：很高

**当前实现：**
- 通过 `IAlgorithmRouter`（`pure_llm_selector.py`）调用LLM单次推理
- LLM根据预定义的算法描述和关键词匹配，返回算法类型
- 支持的算法类型有约12种，使用硬编码的提示词模板

**改造理由：**
- 算法选择是一个**决策推理**任务，适合Agent的规划和推理能力
- Agent可以结合用户历史偏好、数据特征等多维信息做出更准确的算法选择
- 当前单次LLM调用可能因问题模糊导致误判，Agent可以通过**多步推理**或**向用户追问**来消除歧义
- Agent可以动态访问算法知识库（Tool），了解各算法的适用场景和限制条件
- 支持新算法时，Agent只需更新Tool描述，无需修改硬编码的提示词

**改造方式建议：**
将算法选择建模为Agent的Tool选择过程，每种算法作为一个Tool注册到Agent，Agent根据问题分析自主选择最合适的Tool（算法）。

---

#### S3: 参数提取 — Agent化潜力：很高

**当前实现：**
- 通过 `IParameterExtractor` 调用LLM提取参数
- 结合数据库Schema信息，从自然语言中提取算法所需参数
- 返回规范化查询、所需列、参数映射等

**改造理由：**
- 参数提取涉及**自然语言理解 + 数据库Schema理解 + 业务规则**的综合推理
- Agent可以在参数提取不确定时**主动向用户确认**，而非直接推测
- Agent可以结合Tool（如数据库Schema查询工具）动态获取信息，而非一次性传入全部Schema
- 当前参数提取和算法选择是割裂的两步，Agent化后可以**将二者统一为一个连贯的推理过程**
- Agent可以验证提取的参数是否合理（如列名是否存在、数据类型是否匹配），并在不合理时自动修正

**改造方式建议：**
参数提取作为Agent的一个推理步骤，Agent通过Tool调用数据库Schema查询、数据采样等工具来辅助参数提取和验证。

---

#### S4: SQL生成与数据检索 — Agent化潜力：中

**当前实现：**
- 调用NL2SQL外部服务（两阶段：`query-db` 获取候选表 → `generate-sql`/`execute` 生成和执行SQL）
- 支持使用预获取的候选表信息避免重复调用
- 带重试机制的网络调用

**改造理由：**
- SQL生成可作为Agent的一个Tool，Agent可以在SQL执行失败时**自主调试和修正SQL**
- Agent可以在数据量过大或无数据时做出智能判断（如调整查询条件、扩大/缩小范围）
- 但NL2SQL本身是一个复杂的独立服务，完全内化成本较高

**改造方式建议：**
将NL2SQL封装为Agent的Tool，保持外部服务调用，但Agent掌握SQL生成和修正的决策权。Agent可以在SQL执行失败时分析错误原因，自动修改查询条件重试。

---

#### S5: 数据格式转换 — Agent化潜力：低

**当前实现：**
- 规则引擎：`data_processor.convert_sql_result_to_algorithm_input()`
- 将SQL查询结果按照算法配置转换为算法输入格式

**改造理由：**
- 数据格式转换是确定性的规则操作，不需要推理或决策
- Agent化不会带来显著价值提升

**改造方式建议：**
保持现有实现，作为Agent调用的一个内部工具函数。

---

#### S6: 算法执行 — Agent化潜力：低

**当前实现：**
- 调用外部算法服务API（HTTP请求）
- 支持同步和异步（轮询）两种模式
- 按算法类型分发至对应执行器

**改造理由：**
- 算法执行是具体的计算任务，需要专业算法服务完成
- Agent化改造主要在**调度和编排层面**，而非执行层面
- 但Agent可以在算法执行失败时自主选择备选算法或调整参数

**改造方式建议：**
将各算法执行器封装为Agent的Tool，Agent负责调度和错误恢复决策。

---

#### S7: 结果分析与格式化 — Agent化潜力：高

**当前实现：**
- `_format_readable_result_with_llm()`：通过LLM将算法结果转换为自然语言分析
- `AlgorithmResultAnalyzer.analyze_algorithm_result()`：专用结果分析器
- 降级处理：LLM失败时使用模板生成基础分析

**改造理由：**
- 结果分析是Agent的**核心能力之一**——将技术结果翻译为用户可理解的语言
- Agent可以结合对话上下文，生成与用户问题更相关的分析结论
- Agent可以在分析过程中**主动补充洞察**，如数据异常值的可能原因、趋势变化的业务含义
- Agent可以根据用户角色（如管理层/技术人员）调整分析的详细程度和专业性
- 当前实现是独立的LLM调用，Agent化后可与前序步骤形成连贯的分析链

**改造方式建议：**
作为Agent最终输出环节的核心能力，Agent综合所有步骤收集到的信息（问题意图、算法选择理由、数据特征、算法结果）生成连贯完整的分析报告。

---

#### S8: 全流程编排 — Agent化潜力：极高

**当前实现：**
- 硬编码的 if-else 分支逻辑：
  - `if fileIds` → 文件上传流程
  - `if agent_algorithm` → Agent流程
  - `if algorithm_type == NL2SQL` → NL2SQL流程
  - `if auto_analysis is False` → 手动模式
- 各步骤严格顺序执行，无法动态调整
- 步骤间通过变量传递状态

**改造理由：**
- 当前的硬编码编排方式**灵活性差**，每增加一个新分支都需修改核心代码
- Agent的**规划（Planning）能力**天然适合流程编排——Agent可以根据问题和中间结果动态规划后续步骤
- Agent可以实现**自适应流程**：如数据量太少时跳过复杂算法、SQL结果异常时自动回退重试
- Agent可以在流程中任意步骤**与用户交互**（如确认参数、选择算法），而非仅在特定的手动模式分支
- 将所有步骤建模为Agent的Tool后，Agent可以灵活组合这些Tool完成不同类型的分析任务
- 便于后续扩展新的分析流程，无需修改编排逻辑

**改造方式建议：**
将当前固定的流程编排改为Agent驱动的动态编排。所有步骤（追问判断、算法选择、参数提取、SQL生成、算法执行、结果分析）都注册为Agent的Tool，Agent根据用户问题自主规划执行计划并按需调用Tool。

---

### 5.3 改造优先级建议

```
P0（核心改造）：
  ├── S8: 全流程编排 → Agent规划与编排
  ├── S2: 算法类型识别 → Agent Tool选择
  └── S3: 参数提取 → Agent推理+Tool辅助

P1（高价值改造）：
  ├── S1: 追问判断 → Agent对话管理
  └── S7: 结果分析 → Agent综合分析输出

P2（中等价值改造）：
  └── S4: SQL生成 → Agent Tool（保持外部服务）

P3（低优先级/保持现状）：
  ├── S5: 数据格式转换 → 保持为内部工具函数
  └── S6: 算法执行 → 保持为外部服务调用
```

---

### 5.4 改造后的目标架构愿景

```
用户问题 → Agent（大模型驱动的智能中枢）
                │
                ├── Tool 1: 对话上下文管理（追问判断 + 历史记忆）
                ├── Tool 2: 数据库Schema查询（获取表/列信息）
                ├── Tool 3: 数据采样与预览（快速了解数据特征）
                ├── Tool 4: NL2SQL生成与执行（SQL查询数据）
                ├── Tool 5: 数据格式转换（SQL结果 → 算法输入）
                ├── Tool 6-N: 各类算法执行器（聚类/分类/预测/异常检测/...）
                └── Tool N+1: 用户交互（向用户确认参数/展示中间结果）
                │
                └── Agent自主完成：规划执行步骤、选择合适算法、
                    处理异常恢复、生成分析报告
```

**核心变化：从"固定流水线"到"Agent自主规划与执行"**

---

## 六、待确认事项

请确认以上流程总结和Agent化改造潜力分析是否准确完整，确认后将进行：

1. **详细的Agent化改造技术方案设计**
2. **Tool定义和Agent Prompt设计**
3. **改造实施计划和分阶段里程碑**
4. **兼容性方案**（确保改造期间现有接口正常工作）
