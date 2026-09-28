# data-agent
Is AI Agent

架构：

这是一个自然语言转 SQL 的数据查询 Agent。它用 LangGraph 编排查询流程，用元数据和检索结果帮助模型生成 SQL，再通过 MySQL 执行查询。

```BASH
  用户
   │
   ▼
  FastAPI 查询接口 ── SSE 流式返回进度和结果
   │
   ▼
  LangGraph 工作流
   提取关键词
      ├── 召回字段 ── BGE Embedding + Qdrant
      ├── 召回指标 ── BGE Embedding + Qdrant
      └── 召回字段取值 ── Elasticsearch
              │
              ▼
         合并并筛选元数据
              │
              ▼
         生成 SQL（大语言模型）
              │
              ▼
         EXPLAIN 校验
          ├── 失败 → 尝试修正 SQL
          └── 通过 ───────┐
                          ▼
                   执行 SQL → 返回结果

运行时依赖由 FastAPI 的生命周期初始化，并通过运行上下文传给 Agent 节点：

   组件                      职责
  ━━━━━━━━━━━━━━━━━━━━━━━━  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   FastAPI                   提供 /api/query 查询接口，以 SSE 发送执行阶段和结果
  ────────────────────────  ─────────────────────────────────────────────────────
   LangGraph                 管理节点、共享状态、并行检索分支及校验后的条件分支
  ────────────────────────  ─────────────────────────────────────────────────────
   大语言模型                扩展检索关键词、生成 SQL，以及根据校验错误修正 SQL
  ────────────────────────  ─────────────────────────────────────────────────────
   BGE Embedding + Qdrant    将问题或关键词转为向量，召回相关字段和指标
  ────────────────────────  ─────────────────────────────────────────────────────
   Elasticsearch             按关键词检索字段取值，例如地区名称
  ────────────────────────  ─────────────────────────────────────────────────────
   MySQL dw                  保存示例业务数据，校验并执行生成的 SQL
  ────────────────────────  ─────────────────────────────────────────────────────
   MySQL meta                保存表、字段、指标等业务元数据

```

  项目分为两个阶段：

  1. 离线构建知识库：build_meta_knowledge.py 从 conf/meta_config.yaml 读取表、字段和指标定义，读取 dw 的表结构，然后写入 meta、Qdrant
     和 Elasticsearch。

  2. 在线问数：用户提交问题，Agent 检索相关上下文，生成并校验 SQL，执行后通过 SSE 返回结果。

  主要代码入口：

  - app/agent/graph.py：定义工作流和节点连接。
  - app/agent/state.py：定义节点间共享的查询状态。
  - app/api/routers/query_router.py：提供查询 API。
  - app/services/meta_knowledge_service.py：构建元数据和检索索引。
  - docker/docker-compose.yaml：启动 MySQL、Elasticsearch、Qdrant、Embedding 和可选的 Kibana。

  你可以把一次查询的核心过程记成：检索业务上下文 → 生成 SQL → 校验并执行。目前 SQL 校验失败后会尝试修正；这个工作流里的模型调用和查询
  步骤由预先定义的图控制。


```bash
 代码请求流程: 从 HTTP 路由、依赖注入、LangGraph 节点，到数据库执行和 SSE 返回串起来，并标出关键文件。

• Explored
  └ Read query_router.py, dependencies.py, query_service.py, graph.py, state.py, context.py, execute_sql.py, query_schema.py,
  lifespan.py

• 请求从 POST /api/query 进入，经过 FastAPI 校验和依赖注入后交给 LangGraph，最终查询结果以 SSE 事件流返回。

  POST /api/query
      │
      ▼
  QuerySchema 校验请求体
      │
      ▼
  依赖注入 QueryService、数据库 Repository 和 Embedding 客户端
      │
      ▼
  QueryService 创建查询状态与运行上下文
      │
      ▼
  LangGraph 编排检索、生成和执行
      │
      ▼
  SSE 返回阶段进度、结果或错误

```

  以请求体 {"query":"统计各地区销售总额"} 为例，完整流程如下：

  1. 路由接收请求：app/api/routers/query_router.py 中的 POST /api/query 用 QuerySchema 校验 query 字段，并返回 StreamingResponse。
  2. 组装服务依赖：app/api/dependencies.py 将应用启动时创建的 TEI、Qdrant、Elasticsearch 客户端，以及当前请求使用的 MySQL Session 封
     装成 Repository，注入 QueryService。

  3. 创建图的输入：app/services/query_service.py 创建初始状态 state，其中包含用户问题；再创建 runtime context，放入 Embedding 客户端
     和各数据仓库 Repository。

  4. 执行 LangGraph：app/agent/graph.py 调用 graph.astream(..., stream_mode="custom")。图的状态结构定义在 app/agent/state.py，运行时
     依赖结构定义在 app/agent/context.py。

  5. 检索并整理上下文：提取关键词后，并行执行字段、指标、字段取值三路召回；字段和指标通过本地 TEI 计算向量，再查 Qdrant，字段取值查
     Elasticsearch。三路结果汇合后，再并行筛选表和指标，最后补充生成 SQL 所需的上下文。

  6. 生成、校验并执行 SQL：模型根据问题和检索上下文生成 SQL。MySQL Repository 使用 EXPLAIN 校验；校验通过就执行，失败则进入 SQL 修正
     节点，然后执行修正结果。

  7. 流式返回：节点通过 runtime.stream_writer 发送进度或查询结果，QueryService 将每条事件编码成 SSE 格式：

  data: {"stage": "生成sql"}

  data: {"result": [...]}

  API 启动和关闭时，客户端由 app/core/lifespan.py 管理。

  有一个值得注意的流程细节：修正后的 SQL 会直接执行，当前图没有再次调用 EXPLAIN 校验。 因此面试或项目说明中，应描述为“校验失败后尝试
  修正并执行”，不要称为“修正后再次校验”。




```bash
这个项目涉及的知识点可以按一条问数链路来理解：用户请求 → Agent 编排 → 检索业务知识 → 生成 SQL → 数据库执行 → 流式返回。

  1. Python 服务与异步编程

  - FastAPI 路由、Pydantic 请求校验、依赖注入。
  - async/await、异步生成器、异步数据库访问。
  - 应用生命周期管理：启动时创建客户端，关闭时释放连接。
  - 分层设计：Router、Service、Repository 如何划分职责。

  对应代码：app/api/、app/services/、app/repositories/、app/core/lifespan.py。

  2. Agent 工作流与 LangGraph

  - 节点：每个节点负责一项工作，例如提取关键词、召回字段、生成 SQL。
  - State：节点之间传递的问题、关键词、检索结果、SQL 和错误信息。
  - Context：提供数据库、向量库和 Embedding 等运行依赖。
  - 并行分支与汇合：字段、指标、字段取值三路召回并行运行，之后合并结果。
  - 条件路由：SQL 校验通过则执行，失败则进入修正节点。
  - 流式事件：节点通过 stream_writer 输出阶段和结果。

  重点文件：app/agent/graph.py、state.py、context.py。

  这个项目的流程由代码预先编排，适合称为 NL2SQL Agent 工作流。理解图的状态和分支，比只熟悉 LangGraph 的 API 更重要。

  3. 检索增强与业务元数据

  - Embedding：把文本转换成向量，用语义相似度找字段和指标。
  - 向量检索：项目使用 BGE 模型和 Qdrant 召回候选字段、指标。
  - 关键词检索：Elasticsearch 用于查找字段的具体取值，例如地区名。
  - 元数据建模：表、字段、别名、业务描述、指标口径及字段关系。
  - 候选合并和上下文裁剪：从召回结果中组织模型生成 SQL 所需的信息。

  可以重点学习：向量召回和关键词召回的适用差异、召回结果排序、如何判断召回是否正确，以及哪些元数据最影响 SQL 生成质量。

  4. NL2SQL 与数据库

  - 将业务问题映射到指标、表、字段和过滤条件。
  - JOIN 关系推断、聚合、时间过滤、排序和分组。
  - Schema linking：把用户说法关联到真实数据库字段。
  - SQL 校验与错误修正。
  - 异步 SQLAlchemy、MySQL Session 和 Repository 封装。

  关键点是：SQL 能执行，不代表答案符合业务口径。例如 JOIN 重复可能导致销售金额被重复累计。理解指标定义并人工核对查询结果，是评估系统
  是否正确的必要部分。

  5. 模型调用与提示词

  - 用 LangChain 组装 Prompt、模型和输出解析器。
  - 提示词外置管理，便于调整关键词扩展、筛选、SQL 生成和修正策略。
  - 结构化输出与 JSON 解析。
  - 模型配置、超时、失败处理和成本控制。

  6. 服务化与本地基础设施

  - Docker Compose 编排 MySQL、Elasticsearch、Qdrant、Embedding 和 Kibana。
  - BGE 模型由 TEI 提供本地 HTTP 推理接口。
  - 知识库初始化脚本负责将表字段、指标及字段取值写入对应存储。
  - FastAPI 通过 SSE 向调用方流式返回进度和查询结果。

  建议的学习顺序

  1. 先从 query_router.py 跟到 QueryService.query()，弄懂一次请求怎么进入系统。
  2. 读 graph.py 和 state.py，画出节点、并行分支、条件路由以及状态变化。
  3. 追踪一个实际问题的召回结果，理解字段、指标和字段取值如何补足模型上下文。
  4. 看 generate_sql.py、SQL 校验和执行逻辑，手工对照 SQL 与真实业务口径。
  5. 最后读知识库构建和 Docker 配置，弄清数据如何进入 MySQL、Qdrant 和 Elasticsearch。

  结合你的 iOS 和跨端经验，还可以关注 SSE 事件设计、任务状态展示、取消查询、错误呈现和结果解释：这些能把 Agent 后端流程和端到端产品体
  验连接起来。
```






脚本仅使用 Python 标准库，无需额外安装 Python 依赖。需要先安装
Docker Desktop（macOS）或 Docker Engine 和 Compose（Linux），并将
BGE 模型文件放在 `docker/embedding/bge-large-zh-v1.5/`。
脚本在 macOS 上会尝试打开 Docker Desktop，自动拉取镜像、构建带 IK 插件的
Elasticsearch、启动 MySQL / Elasticsearch / Qdrant / Embedding，并等待服务就绪。
首次拉取镜像需要网络访问镜像仓库。

```bash
# 可选：同时启动 Kibana
python3 scripts/start_deps.py --with-kibana

# 模型加载较慢时，延长就绪等待时间（不包含镜像拉取和构建时间）
python3 scripts/start_deps.py --timeout 600
```

脚本保留已有数据卷。MySQL 仅在空数据卷首次初始化时自动执行
`docker/mysql/dw.sql` 和 `docker/mysql/meta.sql`，创建数据库、表和示例业务数据。
现有 SQL 包含删除重建表的语句，不要将手动重跑 SQL 当作普通重启操作。
就绪检查使用 Compose 文件中当前的本机映射端口；修改端口时也需要同步调整脚本。

依赖就绪后，初始化知识库并启动 API：

```bash
source .venv/bin/activate
python -m app.scripts.build_meta_knowledge -c conf/meta_config.yaml
python -m uvicorn main:app --reload
```

知识库构建和 API 启动不包含在依赖启动脚本中。查询前需在
`conf/app_config.yaml` 中配置有效的模型密钥。

项目架构:


```yaml
data-agent 根目录
├── app 代码目录
│   ├── agent 智能体
│   ├── api 接口
│   ├── clients 数据库客户端
│   ├── conf 配置类
│   ├── core 基础设施
│   ├── models 数据库实体类
│   ├── prompt 提示词工具
│   ├── repositories Repo层——负责数据库底层查询
│   ├── scripts 脚本
│   └── services Service层——负责具体的业务逻辑
├── conf 配置文件
├── docker 开发环境
│   ├── elasticsearch
│   ├── embedding
│   └── mysql
├── logs 日志目录
└── prompts 提示词目录
```



问数智能体的核心代码主要位于 data-agent/app/agent 目录下。

在智能体执行过程中，部分节点需要访问元数据或向量/检索系统以获取辅助信息，相关的查询与访问逻辑统一封装在 data-agent/app/repositories 目录中，供各个 Agent 节点按需调用。

除代码逻辑外，智能体运行还高度依赖提示词（Prompt）。所有提示词均集中管理在data-agent/prompts目录下。
具体组织规划如下：

```
data-agent/
├─ app/
│  ├─ agent/
│  │  ├─ graph.py # 负责定义langgraph图
│  │  ├─ state.py # 负责定义langgraph状态
│  │  ├─ context.py # 负责定义langgraph运行上下文
│  │  ├─ llm.py # 负责定义llm
│  │  └─ nodes/
│  │     ├─ extract_keywords.py # 负责定义关键词抽取的节点
│  │     ├─ recall_column.py # 负责定义召回字段信息的节点
│  │     ├─ recall_metric.py # 负责定义召回指标信息的节点
│  │     ├─ recall_value.py  # 负责定义召回字段取值的节点
│  │     ├─ merge_retrieved_info.py # 负责定义合并召回信息的节点
│  │     ├─ filter_metric.py # 负责定义过滤指标信息的节点
│  │     ├─ filter_table.py # 负责定义过滤表格信息的节点
│  │     ├─ add_extra_context.py # 负责定义添加额外上下文信息的节点
│  │     ├─ generate_sql.py # 负责定义生成SQL的节点
│  │     ├─ validate_sql.py # 负责定义校验SQL的节点
│  │     ├─ correct_sql.py # 负责定义校正SQL的节点
│  │     └─ execute_sql.py # 负责定义执行SQL的节点
│  │
│  └─ repositories/
│     ├─ mysql/
│     │  ├─ meta/
│     │  │  ├─ meta_mysql_repository.py
│     │  │  └─ models/
│     │  │     ├─ table_info_mysql.py
│     │  │     ├─ column_info_mysql.py
│     │  │     ├─ metric_info_mysql.py
│     │  │     └─ column_metric_mysql.py
│     │  └─ dw/
│     │     └─ dw_mysql_repository.py
│     │
│     ├─ qdrant/
│     │  ├─ column_qdrant_repository.py
│     │  └─ metric_qdrant_repository.py
│     │
│     └─ es/
│        └─ value_qdrant_repository.py
│
├─ prompts/
│  ├─ extend_keywords_for_column_recall.prompt # 为召回字段信息扩展关键词 的提示词
│  ├─ extend_keywords_for_metric_recall.prompt # 为召回指标信息扩展关键词 的提示词
│  ├─ extend_keywords_for_value_recall.prompt # 为召回字段取值扩展关键词 的提示词 
│  ├─ filter_metric_info.prompt # 过滤指标信息 的提示词
│  ├─ filter_table_info.prompt # 过滤表格信息 的提示词
│  ├─ generate_sql.prompt # 生成SQL 的提示词
│  └─ correct_sql.prompt # 校正SQL 的提示词
│
└─ prompt/
   └─ prompt_loader.py

```


智能体的结构构建以langgraph为基础框架，完成结构清晰的项目构建.

面试题：为什么选择langgraph作为基础框架？

NL2SQL 不是 “一次调用 LLM 生成 SQL”，而是一套包含理解→检索→生成→校验→安全→执行→反思→修复→多轮交互的完整工作流；
LangGraph 用 “状态机 + 图 + 循环 + 分支 + 人在环 + 可观测”，正好把这套复杂流程变成可控、可靠、可生产的智能体。




节点

在 LangGraph 中，节点是 Python 函数（可以是同步函数也可以是异步函数），它们接受以下参数：

1、state–图的状态
2、config–RunnableConfig包含配置信息（例如）thread_id和跟踪信息（例如）的对象tags
3、runtime– 一个Runtime包含运行时context和其他信息的对象，store例如stream_writer
（1）Runtime中的重要参数:

如下展示的是源码中的重要参数：




```
data-agent/
├─ main.py # FastAPI入口脚本
└─ app/
   ├─ api/
   │  ├─ routers/
   │  │  └─ query_router.py # 负责定义查询接口
   │  ├─ schemas/ # 请求参数和返回值结果
   │  │  └─ query_schema.py # 负责定义查询接口请求体结构
   │  └─ dependencies.py # 负责定义查询接口依赖项
   │
   ├─ services/
   │  └─ query_service.py # 负责定义查询接口核心业务逻辑
   │
   └─ core/
      ├─ lifespan.py # 负责定义FastAPI生命周期事件
      ├─ context.py # 负责定义异步任务上下文变量
      └─ log.py # 重新定义日志的输出格式
 
```

