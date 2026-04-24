# RAGFlow 知识库系统分析文档

## 一、项目概述

RAGFlow 是一个基于 Python 的 RAG（Retrieval-Augmented Generation）知识库引擎，采用 Flask/Quart 框架提供 API 服务，使用 Peewee ORM 操作数据库，底层支持 Elasticsearch/Infinity 作为文档存储与检索引擎。

**技术栈**：Python + Quart + Peewee ORM + Elasticsearch/Infinity + Redis

---

## 二、数据库表结构

### 2.1 Knowledgebase（知识库表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | CharField(32), PK | 知识库唯一ID |
| avatar | TextField | 头像（Base64） |
| tenant_id | CharField(32), INDEX | 租户ID |
| name | CharField(128), INDEX | 知识库名称 |
| language | CharField(32) | 语言（Chinese/English） |
| description | TextField | 描述 |
| embd_id | CharField(128), INDEX | 默认嵌入模型ID |
| tenant_embd_id | IntegerField | 租户模型表中的嵌入模型记录ID |
| permission | CharField(16) | 权限（me/team） |
| created_by | CharField(32) | 创建者 |
| doc_num | IntegerField | 文档数量 |
| token_num | IntegerField | Token总量 |
| chunk_num | IntegerField | 分块数量 |
| similarity_threshold | FloatField(0.2) | 相似度阈值 |
| vector_similarity_weight | FloatField(0.3) | 向量相似度权重 |
| parser_id | CharField(32) | 默认解析器ID |
| pipeline_id | CharField(32) | Pipeline ID |
| parser_config | JSONField | 解析器配置（pages、table_context_size等） |
| pagerank | IntegerField | PageRank权重（用于GraphRAG） |
| graphrag_task_id | CharField(32) | GraphRAG任务ID |
| graphrag_task_finish_at | DateTimeField | GraphRAG任务完成时间 |
| raptor_task_id | CharField(32) | RAPTOR任务ID |
| raptor_task_finish_at | DateTimeField | RAPTOR任务完成时间 |
| mindmap_task_id | CharField(32) | 思维导图任务ID |
| mindmap_task_finish_at | DateTimeField | 思维导图任务完成时间 |
| status | CharField(1) | 状态（0:无效 1:有效） |

### 2.2 Document（文档表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | CharField(32), PK | 文档唯一ID |
| thumbnail | TextField | 缩略图（Base64） |
| kb_id | CharField(256), INDEX | 所属知识库ID |
| parser_id | CharField(32), INDEX | 解析器ID |
| pipeline_id | CharField(32) | Pipeline ID |
| parser_config | JSONField | 解析器配置 |
| source_type | CharField(128) | 来源类型（local等） |
| type | CharField(32) | 文件类型 |
| created_by | CharField(32) | 创建者 |
| name | CharField(255) | 文件名 |
| location | CharField(255) | 存储位置 |
| size | IntegerField | 文件大小 |
| token_num | IntegerField | Token数量 |
| chunk_num | IntegerField | 分块数量 |
| progress | FloatField | 处理进度 |
| progress_msg | TextField | 处理消息 |
| process_begin_at | DateTimeField | 处理开始时间 |
| process_duration | FloatField | 处理耗时 |
| suffix | CharField(32) | 文件后缀 |
| content_hash | CharField(32) | 内容哈希（xxhash128，用于变更检测） |
| run | CharField(1) | 运行状态（0:未运行 1:运行中 2:取消） |
| status | CharField(1) | 有效性（0:无效 1:有效） |

### 2.3 Task（任务表）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | CharField(32), PK | 任务ID |
| doc_id | CharField(32), INDEX | 关联文档ID |
| from_page | IntegerField | 起始页 |
| to_page | IntegerField | 结束页 |
| task_type | CharField(32) | 任务类型 |
| priority | IntegerField | 优先级 |
| begin_at | DateTimeField | 开始时间 |
| process_duration | FloatField | 处理耗时 |
| progress | FloatField | 进度 |
| progress_msg | TextField | 进度消息 |
| retry_count | IntegerField | 重试次数 |
| digest | TextField | 任务摘要 |
| chunk_ids | LongTextField | 分块ID列表 |

### 2.4 File / File2Document（文件管理表）

- **File**: 管理文件树（parent_id, tenant_id, name, location, size, type, source_type）
- **File2Document**: 文件与文档的映射关系（file_id, document_id）

---

## 三、核心API接口

### 3.1 知识库管理接口（kb_app.py）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/update_metadata_setting` | POST | 更新知识库元数据设置 |
| `/detail` | GET | 获取知识库详情（含size、connectors） |
| `/<kb_id>/tags` | GET | 获取知识库标签列表 |
| `/tags` | GET | 批量获取多个知识库标签 |
| `/<kb_id>/rm_tags` | POST | 删除标签 |
| `/<kb_id>/rename_tag` | POST | 重命名标签 |
| `/get_meta` | GET | 获取知识库元数据 |
| `/basic_info` | GET | 获取知识库基本信息 |
| `/list_pipeline_logs` | POST | 获取Pipeline操作日志 |
| `/delete_pipeline_logs` | POST | 删除Pipeline日志 |
| `/pipeline_log_detail` | GET | 获取Pipeline日志详情 |
| `/run_mindmap` | POST | 运行思维导图任务 |
| `/trace_mindmap` | GET | 追踪思维导图进度 |
| `/unbind_task` | DELETE | 解绑任务（GraphRAG/RAPTOR/Mindmap） |
| `/check_embedding` | POST | 检查Embedding模型切换兼容性 |

> 注：知识库的创建/更新/删除/列表接口已标记为 Deprecated（待删除），迁移至 RESTful API 或 SDK 方式。

### 3.2 文档管理接口（document_app.py）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/upload` | POST | 上传文件到知识库 |
| `/web_crawl` | POST | 网页抓取并添加到知识库（URL转PDF） |
| `/create` | POST | 创建虚拟文档记录 |
| `/list` | POST | 获取文档列表（支持分页、过滤、元数据搜索） |
| `/filter` | POST | 获取文档过滤选项 |
| `/infos` | POST | 批量获取文档信息 |
| `/metadata/summary` | POST | 获取文档元数据摘要 |
| `/metadata/update` | POST | 批量更新文档元数据 |
| `/update_metadata_setting` | POST | 更新文档元数据设置 |
| `/thumbnails` | GET | 获取文档缩略图 |
| `/change_status` | POST | 启用/禁用文档 |
| `/rm` | POST | 删除文档 |
| `/run` | POST | 运行/取消解析任务 |
| `/rename` | POST | 重命名文档 |
| `/get/<doc_id>` | GET | 下载文档文件 |
| `/change_parser` | POST | 更换解析器 |
| `/parse` | POST | 解析文件（URL或文件上传） |
| `/set_meta` | POST | 设置文档元数据 |
| `/upload_and_parse` | POST | 上传并解析文档（对话中使用） |
| `/upload_info` | POST | 获取上传文件信息 |
| `/artifact/<filename>` | GET | 获取Sandbox产物 |

### 3.3 分块管理接口（chunk_app.py）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/list` | POST | 获取文档的分块列表（支持关键词搜索） |
| `/get` | GET | 获取单个分块详情 |
| `/set` | POST | 更新分块内容（自动重新Embedding） |
| `/create` | POST | 手动创建分块（自动Embedding和索引） |
| `/switch` | POST | 启用/禁用分块 |
| `/rm` | POST | 删除分块（支持批量、全部删除） |
| `/retrieval_test` | POST | 检索测试（支持向量+关键词混合检索、Rerank、KG） |
| `/knowledge_graph` | GET | 获取知识图谱数据 |

---

## 四、文档解析流程

### 4.1 解析器类型（ParserType）

RAGFlow 支持多种文档解析器，通过 `rag/app/` 目录下的模块实现：

| 解析器 | 模块 | 适用场景 |
|--------|------|----------|
| **naive** (general) | `naive.py` | 通用文档 |
| **paper** | `paper.py` | 学术论文 |
| **book** | `book.py` | 书籍 |
| **presentation** | `presentation.py` | PPT/PPTX |
| **manual** | `manual.py` | 使用手册 |
| **laws** | `laws.py` | 法律文档 |
| **qa** | `qa.py` | 问答对 |
| **table** | `table.py` | 表格 |
| **resume** | `resume.py` | 简历 |
| **picture** | `picture.py` | 图片（OCR+多模态） |
| **one** | `one.py` | 单页文档 |
| **audio** | `audio.py` | 音频 |
| **email** | `email.py` | 邮件 |
| **tag** | `tag.py` | 标签分块 |
| **kg** | `naive.py` | 知识图谱（复用naive） |

### 4.2 解析执行流程

```
1. 用户调用 /run 接口 → 设置文档状态为 RUNNING
2. TaskExecutor（task_executor.py）消费任务：
   a. 根据 parser_id 从 FACTORY 获取解析器模块
   b. 读取文档文件（从 STORAGE_IMPL）
   c. 执行解析：文件 → 文本分段（Chunks）
   d. 对每个 Chunk：
      - 执行分词（rag_tokenizer.tokenize）
      - 调用 Embedding 模型生成向量
      - 生成关键词提取（keyword_extraction）
      - 生成问题建议（question_proposal）
      - 内容标签标注（content_tagging）
      - 元数据生成（gen_metadata）
   e. 写入 Elasticsearch/Infinity 索引（docStoreConn.insert）
   f. 更新文档进度（progress、chunk_num、token_num）
3. 可选后处理：
   - GraphRAG：构建知识图谱（实体/关系抽取）
   - RAPTOR：递归摘要树组织检索
   - Mindmap：生成思维导图
```

### 4.3 分块存储结构

分块数据存储在 Elasticsearch/Infinity 中，主要字段：

| 字段 | 说明 |
|------|------|
| id | Chunk ID（xxhash生成） |
| kb_id | 所属知识库ID |
| doc_id | 所属文档ID |
| docnm_kwd | 文档名称 |
| content_with_weight | 分块内容 |
| content_ltks / content_sm_ltks | 分词结果（粗粒度/细粒度） |
| important_kwd | 关键词 |
| important_tks | 关键词分词 |
| question_kwd | 生成的问题 |
| question_tks | 问题分词 |
| title_tks | 标题分词 |
| q_{dim}_vec | 向量（维度取决于Embedding模型） |
| available_int | 是否可用（0/1） |
| tag_kwd | 标签 |
| page_num_int | 页码 |
| position_int | 位置信息 |
| top_int | 层级信息 |
| knowledge_graph_kwd | 知识图谱类型（graph/subgraph/entity/relation） |
| img_id | 图片ID |
| pagerank_flt | PageRank权重 |
| create_time / create_timestamp_flt | 创建时间 |

---

## 五、检索实现

### 5.1 检索测试接口（retrieval_test）

位于 `chunk_app.py` 的 `/retrieval_test` 接口，完整检索流程：

```
1. 参数获取：
   - kb_ids: 知识库ID列表
   - question: 查询问题
   - similarity_threshold: 相似度阈值
   - vector_similarity_weight: 向量权重
   - rerank_id / tenant_rerank_id: Rerank模型
   - use_kg: 是否使用知识图谱
   - keyword: 是否使用LLM提取关键词
   - cross_languages: 跨语言检索
   - doc_ids: 限定文档范围
   - meta_data_filter: 元数据过滤

2. 预处理：
   a. 跨语言翻译（cross_languages）
   b. LLM关键词提取（keyword_extraction）
   c. 问题标签分类（label_question）

3. 检索执行（settings.retriever.retrieval）：
   - 向量检索（基于Embedding向量相似度）
   - 关键词检索（BM25）
   - 混合排序（vector_similarity_weight权重合并）
   - 可选Rerank重排序

4. 知识图谱检索（可选）：
   - settings.kg_retriever.retrieval
   - 图谱结果插入检索结果首位

5. 上下文扩展：
   - retrieval_by_children: 获取子分块补充上下文
```

### 5.2 检索配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| similarity_threshold | 0.2 | 相似度阈值 |
| vector_similarity_weight | 0.3 | 向量检索权重（0~1） |
| top_k | 1024 | 初始检索数量 |
| rerank_id | - | Rerank模型ID |
| use_kg | false | 是否启用知识图谱检索 |

---

## 六、高级功能

### 6.1 GraphRAG（知识图谱增强检索）
- 从文档中自动抽取实体和关系
- 构建 PageRank 加权知识图谱
- 支持子图检索和实体检索

### 6.2 RAPTOR（递归摘要树组织检索）
- 对文档分块进行递归摘要
- 构建层次化的摘要树
- 支持多粒度检索

### 6.3 Mindmap（思维导图生成）
- 自动从文档生成思维导图结构
- 节点和边数据存储在文档索引中

### 6.4 元数据过滤
- 支持文档级别的元数据管理
- 支持自动/半自动元数据过滤（auto/semi_auto模式）
- 支持手动条件过滤（and/or逻辑）

### 6.5 Embedding模型切换检查
- `/check_embedding` 接口通过余弦相似度比较新旧向量
- 平均相似度 > 0.9 才允许切换

---

## 七、架构特点总结

1. **Pipeline模式**：文档处理采用任务队列模式，支持进度追踪和取消
2. **多解析器支持**：14+种文档解析器，覆盖常见文件格式
3. **高级RAG能力**：GraphRAG + RAPTOR + 混合检索 + Rerank
4. **多租户隔离**：通过tenant_id实现数据隔离
5. **灵活的存储**：支持Elasticsearch和Infinity两种文档存储引擎
6. **标签系统**：支持分块级别的标签管理和过滤
7. **异步任务**：GraphRAG、RAPTOR、Mindmap均为异步后台任务
