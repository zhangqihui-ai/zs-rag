# Yuxi 知识库系统分析文档

## 一、项目概述

Yuxi 是一个基于 Python/FastAPI 构建的 AI 知识库管理系统，采用**抽象基类 + 工厂模式 + 多实现**的架构设计。系统支持多种知识库后端（LightRAG、Milvus、Dify），通过统一的抽象接口屏蔽底层差异，提供灵活的知识库创建、文档解析、向量索引和智能检索能力。

### 核心技术栈
- **Web框架**: FastAPI（异步支持）
- **ORM**: SQLAlchemy + PostgreSQL
- **对象存储**: MinIO
- **向量数据库**: Milvus
- **图数据库**: Neo4j（LightRAG 知识图谱）
- **任务调度**: 自研 TaskService（asyncio 协程）
- **设计模式**: 抽象工厂模式（Abstract Factory）

---

## 二、数据库模型设计

### 2.1 KnowledgeBase（知识库表）

**表名**: `knowledge_bases`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer(PK) | 自增主键 |
| db_id | String(80, Unique) | 知识库唯一标识（格式: `kb_` 或 `kb_private_` + hash） |
| name | String(255) | 知识库名称（可重复） |
| description | Text | 知识库描述 |
| kb_type | String(32) | 知识库类型：`lightrag` / `milvus` / `dify` |
| embed_info | JSON | 嵌入模型配置（model_id/name, dimension, base_url, api_key） |
| llm_info | JSON | LLM 配置（model_spec, provider, model_name） |
| query_params | JSON | 查询参数配置（持久化的检索选项） |
| additional_params | JSON | 附加参数（chunk分块策略、auto_generate_questions等） |
| share_config | JSON | 分享配置 |
| mindmap | JSON | 思维导图数据 |
| sample_questions | JSON | AI 生成的示例测试问题 |
| created_at | DateTime(tz) | 创建时间 |
| updated_at | DateTime(tz) | 更新时间 |

### 2.2 KnowledgeFile（知识文件表）

**表名**: `knowledge_files`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer(PK) | 自增主键 |
| file_id | String(64, Unique) | 文件唯一标识（UUID或hash生成） |
| db_id | String(80, FK) | 所属知识库ID，关联 knowledge_bases.db_id（CASCADE删除） |
| parent_id | String(64, FK) | 父文件夹ID，支持树形结构（自引用，SET NULL） |
| filename | String(512) | 文件名 |
| original_filename | String(512) | 原始文件名（去掉后缀） |
| file_type | String(64) | 文件类型（file/url/folder） |
| path | String(1024) | 文件路径（本地路径或MinIO URL） |
| minio_url | String(1024) | MinIO 存储路径 |
| markdown_file | String(1024) | 解析后Markdown文件路径（MinIO URL） |
| status | String(32) | 文件状态：uploaded/parsing/parsed/indexing/indexed/error_parsing/error_indexing |
| content_hash | String(128) | 内容hash（用于去重） |
| file_size | BigInteger | 文件大小 |
| content_type | String(64) | 内容类型 |
| processing_params | JSON | 文档处理参数（chunk_size, chunk_overlap, chunk_preset_id等） |
| is_folder | Boolean | 是否为文件夹 |
| error_message | Text | 错误信息 |
| created_by | String(64) | 创建人 |
| updated_by | String(64) | 更新人 |
| created_at | DateTime(tz) | 创建时间 |
| updated_at | DateTime(tz) | 更新时间 |

### 2.3 评估相关表

- **EvaluationBenchmark** (`evaluation_benchmarks`): 评估基准，存储测试问题集
- **EvaluationResult** (`evaluation_results`): 评估结果，存储检索评测任务结果
- **EvaluationResultDetail** (`evaluation_result_details`): 评估详情，存储每条查询的检索结果和指标

---

## 三、核心架构：抽象基类 + 工厂模式

### 3.1 KnowledgeBase 抽象基类

**文件**: `backend/package/yuxi/knowledge/base.py`

定义了知识库的统一接口，所有具体实现必须继承此抽象类：

```python
class KnowledgeBase(ABC):
    """知识库抽象基类，定义统一接口"""
    
    @property
    @abstractmethod
    def kb_type(self) -> str: ...        # 知识库类型标识
    
    @abstractmethod
    async def _create_kb_instance(self, db_id, config): ...    # 创建底层实例
    @abstractmethod
    async def _initialize_kb_instance(self, instance): ...      # 初始化底层实例
    @abstractmethod
    async def index_file(self, db_id, file_id, operator_id): ... # 文档入库
    @abstractmethod
    async def aquery(self, query_text, db_id, **kwargs): ...    # 异步查询
    @abstractmethod
    async def delete_file(self, db_id, file_id): ...             # 删除文件
    @abstractmethod
    async def update_content(self, db_id, file_ids, params): ...  # 更新内容
    @abstractmethod
    async def get_file_basic_info(self, db_id, file_id): ...      # 获取文件基本信息
    @abstractmethod
    async def get_file_content(self, db_id, file_id): ...         # 获取文件内容
    @abstractmethod
    async def get_file_info(self, db_id, file_id): ...            # 获取文件完整信息
    @abstractmethod
    def get_query_params_config(self, db_id, **kwargs): ...       # 获取查询参数配置
```

**基类已实现的通用方法**（非抽象）：
- `create_database()` — 创建知识库记录
- `delete_database()` — 删除知识库（含MinIO文件清理）
- `add_file_record()` — 添加文件记录（状态: UPLOADED）
- `parse_file()` — 解析文件为Markdown（状态: PARSING -> PARSED）
- `update_file_params()` — 更新文件处理参数
- `create_folder()` / `delete_folder()` / `move_file()` — 文件夹管理
- `get_database_info()` / `get_databases()` — 获取知识库信息
- `update_database()` — 更新知识库配置
- `get_retrievers()` — 获取所有检索器（供Agent使用）
- `_save_metadata()` / `_load_metadata()` — 元数据持久化

### 3.2 KnowledgeBaseFactory 工厂类

**文件**: `backend/package/yuxi/knowledge/factory.py`

```python
class KnowledgeBaseFactory:
    _kb_types: dict[str, type[KnowledgeBase]] = {}     # {kb_type: kb_class}
    _default_configs: dict[str, dict] = {}              # {kb_type: default_config}
    
    @classmethod
    def register(cls, kb_type, kb_class, default_config): ...
    
    @classmethod
    def create(cls, kb_type, work_dir, **kwargs) -> KnowledgeBase: ...
    
    @classmethod
    def get_available_types(cls) -> dict[str, dict]: ...
```

### 3.3 三种具体实现

| 实现类 | kb_type | 底层存储 | 特点 |
|--------|---------|----------|------|
| `LightRagKB` | `lightrag` | Milvus + Neo4j + JSON | 知识图谱 + 向量检索，实体关系抽取 |
| `MilvusKB` | `milvus` | Milvus | 纯向量检索，支持Rerank |
| `DifyKB` | `dify` | 外部Dify API | 只读检索，代理第三方知识库 |

---

## 四、API 接口设计

### 4.1 知识库管理

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/knowledge/databases` | 获取所有知识库（按用户权限过滤） | admin |
| POST | `/knowledge/databases` | 创建知识库 | admin |
| GET | `/knowledge/databases/accessible` | 获取可访问的知识库列表（用于Agent配置） | user |
| GET | `/knowledge/databases/{db_id}` | 获取知识库详情 | admin |
| PUT | `/knowledge/databases/{db_id}` | 更新知识库信息 | admin |
| DELETE | `/knowledge/databases/{db_id}` | 删除知识库 | admin |
| GET | `/knowledge/databases/{db_id}/export` | 导出知识库数据（csv/xlsx/md/txt） | admin |
| GET | `/knowledge/types` | 获取支持的知识库类型 | admin |
| GET | `/knowledge/stats` | 获取知识库统计信息 | admin |

**创建知识库参数**：
```json
{
  "database_name": "string",
  "description": "string",
  "kb_type": "lightrag",
  "embed_model_name": "text-embedding-3-small",
  "additional_params": {
    "chunk_size": 1000,
    "chunk_overlap": 200,
    "language": "Chinese"
  },
  "llm_info": {"model_spec": "openai/gpt-4o"},
  "share_config": {}
}
```

### 4.2 文档管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/knowledge/databases/{db_id}/documents` | 添加文档（上传→解析→可选入库） |
| POST | `/knowledge/databases/{db_id}/documents/parse` | 手动触发文档解析 |
| POST | `/knowledge/databases/{db_id}/documents/index` | 手动触发文档入库 |
| GET | `/knowledge/databases/{db_id}/documents/{doc_id}` | 获取文档详情（基本信息+内容） |
| GET | `/knowledge/databases/{db_id}/documents/{doc_id}/basic` | 获取文档基本信息 |
| GET | `/knowledge/databases/{db_id}/documents/{doc_id}/content` | 获取文档内容（chunks和lines） |
| DELETE | `/knowledge/databases/{db_id}/documents/{doc_id}` | 删除文档 |
| DELETE | `/knowledge/databases/{db_id}/documents/batch` | 批量删除文档 |
| GET | `/knowledge/databases/{db_id}/documents/{doc_id}/download` | 下载原始文件 |
| PUT | `/knowledge/databases/{db_id}/documents/{doc_id}/move` | 移动文件/文件夹 |
| POST | `/knowledge/databases/{db_id}/folders` | 创建文件夹 |

### 4.3 查询与检索

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/knowledge/databases/{db_id}/query` | 查询知识库 |
| POST | `/knowledge/databases/{db_id}/query-test` | 测试查询 |
| GET | `/knowledge/databases/{db_id}/query-params` | 获取查询参数配置 |
| PUT | `/knowledge/databases/{db_id}/query-params` | 更新查询参数配置 |

### 4.4 文件上传与解析

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/knowledge/files/upload` | 上传文件到MinIO |
| POST | `/knowledge/files/fetch-url` | 抓取URL内容并上传到MinIO |
| GET | `/knowledge/files/supported-types` | 获取支持的文件类型 |
| POST | `/knowledge/files/markdown` | 文件解析预览（返回Markdown） |

**支持的上传文件格式**：pdf, docx, txt, md, json, csv, xlsx, xls, pptx, ppt, jpg/jpeg, png, gif, bmp, svg, zip, html, xml, py, java, cpp 等

### 4.5 AI 辅助功能

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/knowledge/databases/{db_id}/sample-questions` | AI生成测试问题 |
| GET | `/knowledge/databases/{db_id}/sample-questions` | 获取已保存的测试问题 |
| POST | `/knowledge/generate-description` | AI生成知识库描述 |
| GET | `/knowledge/embedding-models/status` | 获取所有embedding模型状态 |
| GET | `/knowledge/embedding-models/{model_id}/status` | 获取指定embedding模型状态 |

---

## 五、文档处理流程

### 5.1 完整流程：上传 → 解析 → 入库

```
用户上传文件 → MinIO存储 → 添加文件记录(UPLOADED) 
    → 调用Parser解析为Markdown(PARSING → PARSED) → 存储Markdown到MinIO
    → [可选] 自动入库: chunk分块(INDEXING) → embedding向量化 → 写入向量库(INDEXED)
```

### 5.2 文件上传流程

1. **前端上传**: `POST /knowledge/files/upload` → 文件上传到 MinIO（bucket: `kb-documents`）
2. **内容去重**: 计算 `content_hash`，检查同一知识库内是否已存在相同内容
3. **返回信息**: 返回 MinIO URL、content_hash、同名文件检测等

### 5.3 文档添加流程（三阶段任务）

文档添加通过 `POST /knowledge/databases/{db_id}/documents` 触发，内部通过 `TaskService` 异步执行：

**第一阶段：添加文件记录（5% ~ 30%）**
- 调用 `knowledge_base.add_file_record()` → 生成 file_id，状态设为 `UPLOADED`
- 记录文件路径、类型、处理参数等元数据

**第二阶段：批量解析（30% ~ 55%）**
- 调用 `knowledge_base.parse_file()` → 状态 `PARSING`
- 使用统一 Parser (`yuxi.plugins.parser.unified.Parser`) 将文件解析为 Markdown
- 支持 PDF、Word、Excel、PPT、HTML 等多种格式
- 解析结果存储到 MinIO（bucket: `kb-parsed`，路径: `{db_id}/parsed/{file_id}.md`）
- 成功后状态更新为 `PARSED`

**第三阶段：自动入库（55% ~ 95%，可选）**
- 参数 `auto_index=true` 时触发
- 调用 `knowledge_base.update_file_params()` 更新分块参数
- 调用 `knowledge_base.index_file()` 执行入库
- 状态 `INDEXING` → `INDEXED`

### 5.4 文件状态机

```
UPLOADED → PARSING → PARSED → INDEXING → INDEXED
              ↓          ↓         ↓
     ERROR_PARSING  ERROR_PARSING  ERROR_INDEXING
                      ↓
              (可重试解析)
                      ↓
                  INDEXING → INDEXED
```

**状态修复机制**: 系统会自动检测异常状态——如果文件状态为 `PARSING` 或 `INDEXING` 但不在处理队列中，会自动标记为对应的错误状态。

### 5.5 URL 抓取流程

1. `POST /knowledge/files/fetch-url` → 白名单验证 + 大小限制 + 类型检查
2. 下载 URL 内容 → 计算 content_hash → 上传到 MinIO
3. 返回 MinIO URL 供后续添加文档使用

---

## 六、分块与索引策略

### 6.1 分块配置

分块参数支持多层优先级合并：
1. **知识库级别** (`additional_params`): 默认分块配置
2. **文件级别** (`processing_params`): 文件特定配置
3. **请求级别**: API 调用时传入的临时参数

通过 `resolve_chunk_processing_params()` 函数按优先级合并：

```python
# 核心参数
{
    "chunk_size": 1000,        # 分块大小
    "chunk_overlap": 200,      # 分块重叠
    "chunk_preset_id": "...",  # 预设模板ID
    "chunk_parser_config": {}, # 解析器配置
    "qa_separator": "",        # QA分隔符
}
```

### 6.2 LightRAG 知识库入库流程

1. 获取/创建 LightRAG 实例（缓存机制 + 双重检查锁）
2. 从 MinIO 读取 Markdown 内容
3. 使用 `chunk_markdown()` 进行分块
4. 通过 `YUXI_CHUNK_DELIM` 分隔符拼接 chunks
5. 调用 `rag.ainsert()` 执行入库（异步）
6. LightRAG 自动进行：实体抽取 → 关系抽取 → 知识图谱构建 → 向量化存储
7. 验证文档处理状态（确保 processed/preprocessed）

**底层存储**：
- **向量存储**: Milvus（集合: `{db_id}_chunks`, `{db_id}_relationships`, `{db_id}_entities`）
- **图存储**: Neo4j（带 `db_id` 标签的节点）
- **KV存储**: JSON 文件

### 6.3 Milvus 知识库入库流程

1. 获取/创建 Milvus Collection
2. 从 MinIO 读取 Markdown
3. `chunk_markdown()` 分块
4. 批量向量化（`abatch_encode`）
5. 清理已有 chunks（支持重索引）
6. 批量插入 Milvus（id, content, source, chunk_id, file_id, chunk_index, embedding）

**Milvus Collection Schema**：
```
id            VARCHAR(100)   PK
content       VARCHAR(65535)
source        VARCHAR(500)
chunk_id      VARCHAR(100)
file_id       VARCHAR(100)
chunk_index   INT64
embedding     FLOAT_VECTOR(dim)
```

**索引**: COSINE + IVF_FLAT (nlist=1024)

---

## 七、检索流程

### 7.1 Milvus 向量检索

```python
async def aquery(self, query_text, db_id, **kwargs):
```

**支持的检索模式**：
- `vector`: 纯向量检索（默认）
- `keyword`: 关键词检索（BM25）
- `hybrid`: 混合检索（向量 + 关键词）

**检索参数**：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| final_top_k | 10 | 最终返回数量 |
| recall_top_k | 50 | Rerank前的召回数量 |
| similarity_threshold | 0.2 | 相似度阈值 |
| search_mode | vector | 检索模式 |
| use_reranker | false | 是否启用Rerank |
| metric_type | COSINE | 距离度量方式 |
| file_name | - | 按文件名过滤 |

**Rerank流程**：当 `use_reranker=true` 时，先召回 `recall_top_k` 条结果，再通过 Reranker 模型重排序，取 `final_top_k` 条。

### 7.2 LightRAG 知识图谱检索

```python
async def aquery(self, query_text, db_id, **kwargs):
```

**检索特点**：
- 使用 LightRAG 的 `QueryParam` 配置查询
- 默认模式为 `mix`（混合模式）
- 支持 `local`、`global`、`hybrid`、`naive`、`mix` 多种查询模式

**查询模式**：
| 模式 | 说明 |
|------|------|
| naive | 原始chunk检索 |
| local | 实体中心局部检索 |
| global | 全局关系检索 |
| hybrid | 实体 + 关系 |
| mix | 综合所有模式 |

**检索内容范围**（`retrieval_content_scope`）：
- `chunks`: 仅返回chunk文本
- `graph`: 返回实体和关系
- `all`: chunks + graph

### 7.3 Dify 只读检索

```python
async def aquery(self, query_text, db_id, **kwargs):
```

- 通过 HTTP 调用 Dify Dataset Retrieve API
- 支持 `semantic_search` / `keyword_search` / `hybrid_search`
- 配置降级机制：首次请求失败时自动降级为 query-only 请求
- 所有写入操作均抛出 `ValueError("Dify 知识库为只读检索类型")`

---

## 八、元数据管理

### 8.1 内存 + 数据库双层持久化

Yuxi 采用**内存字典 + PostgreSQL 数据库**双层架构管理元数据：

**内存层**（`databases_meta` / `files_meta` / `benchmarks_meta`）：
- 提供快速读写
- 支持延迟加载（由 `KnowledgeBaseManager` 统一管理）

**数据库层**（PostgreSQL）：
- `KnowledgeBaseRepository` / `KnowledgeFileRepository`
- `_save_metadata()`: 全量保存
- `_persist_kb()`: 单个知识库保存
- `_persist_file()`: 单个文件保存（增量更新，避免全量遍历）

### 8.2 时间戳标准化

所有时间戳自动转换为 UTC ISO 格式，确保跨时区一致性。

---

## 九、任务调度系统

文档处理使用自研 `TaskService`（`yuxi.services.task_service`）：

```python
# 任务入队
task = await tasker.enqueue(
    name="知识库文档处理 (知识库名)",
    task_type="knowledge_ingest",
    payload={"db_id": db_id, "items": items, "params": params},
    coroutine=run_ingest,
)
# 返回: {"message": "任务已提交", "status": "queued", "task_id": "xxx"}
```

**特性**：
- 基于 asyncio 协程
- 支持进度上报（`context.set_progress()`）
- 支持任务取消（`context.raise_if_cancelled()`）
- 支持消息更新（`context.set_message()`）
- 支持结果设置（`context.set_result()`）

---

## 十、安全与权限

1. **用户认证**: 基于 `get_admin_user` / `get_required_user` 中间件
2. **文件路径验证**: `validate_file_path()` 防止路径遍历攻击
3. **URL 白名单**: `fetch_url_content()` 内置域名白名单校验
4. **内容去重**: `content_hash` 防止重复上传
5. **同名文件检测**: 上传时自动检测同名文件并返回警告
6. **文件大小限制**: URL 抓取和文件上传均有大小限制
7. **知识库类型校验**: Dify 知识库禁止文档操作（只允许检索）
8. **私有知识库**: `is_private` 参数生成 `kb_private_` 前缀的 ID

---

## 十一、存储架构

```
MinIO:
├── kb-documents/          # 原始文件
│   └── {db_id}/upload/    # 上传的文件
├── kb-parsed/             # 解析后的Markdown
│   └── {db_id}/parsed/{file_id}.md
└── kb-images/             # 图片资源
    └── {db_id}/kb-images/

Milvus:
├── yuxi_know/             # Milvus数据库
│   └── {db_id}/           # 每个知识库一个Collection（向量检索）
└── {db_id}_chunks/        # LightRAG chunks集合
    {db_id}_relationships/ # LightRAG 关系集合
    {db_id}_entities/      # LightRAG 实体集合

Neo4j:
└── 标签={db_id}           # 每个知识库的实体关系图

PostgreSQL:
├── knowledge_bases        # 知识库元数据
├── knowledge_files        # 文件元数据
├── evaluation_benchmarks  # 评估基准
├── evaluation_results     # 评估结果
└── evaluation_result_details # 评估详情
```

---

## 十二、特色功能

### 12.1 AI 辅助功能
- **AI 生成测试问题**: 根据知识库文件列表自动生成检索测试问题
- **AI 生成知识库描述**: 使用 LLM 为知识库生成适合作为 Agent 工具描述的文本

### 12.2 评估体系
- 完整的 RAG 评估基准管理
- 支持黄金 chunks 和黄金答案
- 评估任务执行与结果详情追踪

### 12.3 知识库导出
- 支持导出为 CSV、XLSX、Markdown、TXT 格式
- 可选是否包含向量数据

### 12.4 文件夹管理
- 支持树形文件夹结构（parent_id 自引用）
- 文件夹的递归删除
- 文件移动（含循环检测）

### 12.5 Dify 集成
- 支持将外部 Dify 知识库作为只读数据源接入
- 请求降级机制增强兼容性
