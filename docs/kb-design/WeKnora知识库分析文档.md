# WeKnora 知识库系统分析文档

## 一、项目概述

WeKnora 是一个基于 Go 语言的智能知识库系统，采用 Gin 框架提供 HTTP API，GORM 作为 ORM，PostgreSQL 作为主数据库，使用 Asynq 实现异步任务队列。系统支持文档型知识库和 FAQ 型知识库，具备完善的组织级权限管理和知识共享机制。

**技术栈**：Go + Gin + GORM + PostgreSQL + Asynq（异步任务）+ 向量数据库（Embedding检索）

---

## 二、数据模型

### 2.1 KnowledgeBase（知识库）

```go
type KnowledgeBase struct {
    ID                    string               // 唯一ID（UUID）
    Name                  string               // 知识库名称
    Type                  string               // 类型：document / faq
    IsTemporary           bool                 // 是否临时知识库
    Description           string               // 描述
    TenantID              uint64               // 租户ID
    ChunkingConfig        ChunkingConfig       // 分块配置（JSON）
    ImageProcessingConfig ImageProcessingConfig // 图片处理配置（JSON）
    EmbeddingModelID      string               // 嵌入模型ID
    SummaryModelID        string               // 摘要模型ID
    VLMConfig             VLMConfig            // VLM配置（JSON）
    StorageProviderConfig *StorageProviderConfig // 存储提供者配置（JSONB）
    ExtractConfig         *ExtractConfig       // 知识图谱抽取配置（JSONB）
    FAQConfig             *FAQConfig           // FAQ专用配置（JSONB）
    QuestionGenerationConfig *QuestionGenerationConfig // 问题生成配置（JSONB）
    IsPinned              bool                 // 是否置顶
    PinnedAt              *time.Time           // 置顶时间
    // 虚拟字段（不存储DB）：
    KnowledgeCount        int64                // 知识条目数量
    ChunkCount            int64                // 分块数量
    IsProcessing          bool                 // 是否有处理中的任务
    ProcessingCount       int64                // 处理中的数量
    ShareCount            int64                // 组织共享数量
}
```

### 2.2 Knowledge（知识条目）

```go
type Knowledge struct {
    ID                   string    // 唯一ID（UUID）
    TenantID             uint64    // 租户ID
    KnowledgeBaseID      string    // 所属知识库ID
    TagID                string    // 标签ID（用于FAQ分类）
    Type                 string    // 类型：manual / faq
    Title                string    // 标题
    Description          string    // 描述
    Source               string    // 来源（URL地址或 "manual"）
    Channel              string    // 来源渠道（web/api/browser_extension/wechat/wecom/feishu/dingtalk/slack/im）
    ParseStatus          string    // 解析状态：pending/processing/completed/failed/deleting
    SummaryStatus        string    // 摘要状态：none/pending/processing/completed/failed
    EnableStatus         string    // 启用状态
    EmbeddingModelID     string    // 嵌入模型ID
    FileName             string    // 文件名
    FileType             string    // 文件类型
    FileSize             int64     // 文件大小
    FileHash             string    // 文件哈希
    FilePath             string    // 文件路径
    StorageSize          int64     // 存储大小
    Metadata             JSON      // 元数据（JSON）
    LastFAQImportResult  JSON      // FAQ导入结果（JSON）
    ProcessedAt          *time.Time // 处理完成时间
    ErrorMessage         string    // 错误信息
    KnowledgeBaseName    string    // 知识库名称（虚拟字段）
}
```

**知识类型**：
- `manual`：手动创建的Markdown知识
- `faq`：FAQ问答对

**来源渠道**：web、api、browser_extension、wechat、wecom、feishu、dingtalk、slack、im

### 2.3 Chunk（分块）

```go
type Chunk struct {
    ID                    string    // 唯一ID（UUID）
    SeqID                 int64     // 自增序列ID（FAQ使用）
    TenantID              uint64    // 租户ID
    KnowledgeID           string    // 所属知识ID
    KnowledgeBaseID       string    // 所属知识库ID
    TagID                 string    // 标签ID
    Content               string    // 分块文本内容
    ChunkIndex            int       // 分块索引位置
    IsEnabled             bool      // 是否启用
    Flags                 ChunkFlags // 标志位（推荐等）
    Status                int       // 状态（0:默认 1:已存储 2:已索引）
    StartAt               int       // 起始字符位置
    EndAt                 int       // 结束字符位置
    PreChunkID            string    // 前一个分块ID
    NextChunkID           string    // 后一个分块ID
    ChunkType             ChunkType // 分块类型
    ParentChunkID         string    // 父分块ID（图片关联）
    RelationChunks        JSON      // 关系分块ID列表
    IndirectRelationChunks JSON     // 间接关系分块ID列表
    Metadata              JSON      // 分块元数据
    ContentHash           string    // 内容哈希（FAQ快速匹配）
    ImageInfo             string    // 图片信息（JSON）
}
```

**分块类型（ChunkType）**：
| 类型 | 说明 |
|------|------|
| text | 普通文本分块 |
| parent_text | 父子分块中的父文本（仅上下文，不参与向量索引） |
| image_ocr | 图片OCR文本 |
| image_caption | 图片描述 |
| summary | 摘要类型 |
| entity | 实体类型（知识图谱） |
| relationship | 关系类型（知识图谱） |
| faq | FAQ条目 |
| web_search | Web搜索结果 |
| table_summary | 数据表摘要 |
| table_column | 数据表列描述 |

### 2.4 ChunkingConfig（分块配置）

```go
type ChunkingConfig struct {
    ChunkSize        int      // 分块大小
    ChunkOverlap     int      // 分块重叠
    Separators       []string // 分隔符
    EnableMultimodal bool     // 启用多模态处理
}
```

### 2.5 ExtractConfig（知识图谱抽取配置）

```go
type ExtractConfig struct {
    Enabled   bool           // 是否启用
    Text      string         // 抽取提示文本
    Tags      []string       // 标签
    Nodes     []ExtractNode  // 节点定义
    Relations []ExtractRelation // 关系定义
}
```

### 2.6 SearchParams（搜索参数）

```go
type SearchParams struct {
    QueryText             string    // 查询文本
    QueryEmbedding        []float32 // 预计算查询向量
    VectorThreshold       float64   // 向量相似度阈值
    KeywordThreshold      float64   // 关键词匹配阈值
    MatchCount            int       // 匹配数量
    DisableKeywordsMatch  bool      // 禁用关键词匹配
    DisableVectorMatch    bool      // 禁用向量匹配
    KnowledgeIDs          []string  // 限定知识ID
    TagIDs                []string  // 标签过滤
    OnlyRecommended       bool      // 仅推荐分块
    KnowledgeBaseIDs      []string  // 跨知识库搜索
    SkipContextEnrichment bool      // 跳过上下文丰富
}
```

---

## 三、核心API接口

### 3.1 知识库管理接口（knowledgebase.go）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/knowledge-bases` | POST | 创建知识库（支持ExtractConfig知识图谱配置） |
| `/knowledge-bases` | GET | 获取知识库列表（支持agent_id共享智能体过滤） |
| `/knowledge-bases/{id}` | GET | 获取知识库详情 |
| `/knowledge-bases/{id}` | PUT | 更新知识库（名称、描述、配置） |
| `/knowledge-bases/{id}` | DELETE | 删除知识库（仅Owner可操作） |
| `/knowledge-bases/{id}/pin` | PUT | 置顶/取消置顶知识库 |
| `/knowledge-bases/{id}/hybrid-search` | GET | 混合搜索（向量+关键词） |
| `/knowledge-bases/copy` | POST | 复制知识库（异步任务） |
| `/knowledge-bases/copy/progress/{task_id}` | GET | 获取复制进度 |
| `/knowledge-bases/{id}/move-targets` | GET | 获取可移动目标知识库列表 |

### 3.2 知识管理接口（knowledge.go）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/knowledge-bases/{id}/knowledges` | POST | 从文件创建知识（支持多模态处理、元数据、URL类型） |
| `/knowledge-bases/{id}/knowledges` | GET | 获取知识列表 |
| `/knowledge-bases/{id}/knowledges/manual` | POST | 创建手动Markdown知识 |
| `/knowledge-bases/{id}/knowledges/{knowledge_id}` | GET | 获取知识详情 |
| `/knowledge-bases/{id}/knowledges/{knowledge_id}` | PUT | 更新知识 |
| `/knowledge-bases/{id}/knowledges/{knowledge_id}` | DELETE | 删除知识 |
| `/knowledge-bases/{id}/knowledges/manual/{knowledge_id}` | PUT | 更新手动知识 |
| `/knowledge-bases/{id}/knowledges/faq/import` | POST | FAQ批量导入 |

### 3.3 分块管理接口（chunk.go）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/chunks/by-id/{id}` | GET | 通过ID获取分块（支持共享KB） |
| `/chunks/{knowledge_id}` | GET | 获取知识下的分块列表（分页） |
| `/chunks/{knowledge_id}/{id}` | PUT | 更新分块（内容、启用状态等） |
| `/chunks/{knowledge_id}/{id}` | DELETE | 删除单个分块 |
| `/chunks/{knowledge_id}` | DELETE | 删除知识下所有分块 |
| `/chunks/by-id/{id}/questions` | DELETE | 删除分块中的生成问题 |

---

## 四、知识库创建与解析流程

### 4.1 文档型知识库流程

```
1. 创建知识库（POST /knowledge-bases）
   - 设置名称、类型(document)、描述
   - 配置 ChunkingConfig（chunk_size, chunk_overlap, separators）
   - 配置 EmbeddingModelID
   - 可选配置 ExtractConfig（知识图谱抽取）
   - 可选配置 QuestionGenerationConfig（问题生成）

2. 上传文件创建知识（POST /knowledge-bases/{id}/knowledges）
   - 上传文件（multipart/form-data）
   - 自动解析文件名、类型、大小、哈希
   - 重复检测（基于file_hash + file_name + file_size）
   - 创建 Knowledge 记录（ParseStatus=pending）

3. 后台异步处理：
   - 文件内容解析 → 文本分块（按ChunkingConfig）
   - 每个分块：
     a. Embedding 向量化
     b. 存储到向量数据库
     c. 存储到 PostgreSQL chunks 表
   - 更新 ParseStatus → completed
   - 可选：摘要生成（SummaryStatus）
   - 可选：问题生成（QuestionGeneration）
   - 可选：知识图谱抽取（ExtractConfig）
```

### 4.2 FAQ型知识库流程

```
1. 创建FAQ知识库（Type=faq）
   - 配置 FAQConfig（FAQIndexMode: question_only / question_answer）
   - 配置 QuestionGenerationConfig

2. FAQ导入（POST /knowledge-bases/{id}/knowledges/faq/import）
   - 批量导入问答对
   - FAQIndexMode.combined: 问题+相似问题合并索引
   - FAQIndexMode.separate: 问题和相似问题分开索引
   - ContentHash 用于快速去重匹配
```

### 4.3 手动知识创建流程

```
POST /knowledge-bases/{id}/knowledges/manual
- 直接输入Markdown内容
- 支持 draft（草稿）和 publish（发布）状态
- 发布后自动触发解析和索引
```

---

## 五、检索实现

### 5.1 混合搜索（HybridSearch）

```
POST /knowledge-bases/{id}/hybrid-search

检索参数（SearchParams）：
- QueryText: 查询文本
- QueryEmbedding: 预计算向量（可选）
- VectorThreshold: 向量阈值
- KeywordThreshold: 关键词阈值
- MatchCount: 返回数量
- DisableKeywordsMatch / DisableVectorMatch: 分别控制开关
- TagIDs: 标签过滤
- OnlyRecommended: 仅推荐内容
- KnowledgeBaseIDs: 跨知识库搜索

检索流程：
1. 向量检索：基于QueryEmbedding在向量数据库中检索
2. 关键词检索：BM25全文检索
3. 结果合并：按权重混合排序
4. 上下文丰富：获取父分块、邻近分块、关系分块
```

### 5.2 SearchResult（搜索结果）

```go
type SearchResult struct {
    ID                   string            // 分块ID
    Content              string            // 分块内容
    KnowledgeID          string            // 知识ID
    ChunkIndex           int               // 分块索引
    KnowledgeTitle       string            // 知识标题
    StartAt / EndAt      int               // 位置范围
    Score                float64           // 匹配分数
    MatchType            MatchType         // 匹配类型
    SubChunkID           []string          // 子分块ID
    Metadata             map[string]string  // 元数据
    ChunkType            string            // 分块类型
    ParentChunkID        string            // 父分块ID
    ImageInfo            string            // 图片信息
    KnowledgeFilename    string            // 知识文件名
    KnowledgeSource      string            // 知识来源
    KnowledgeChannel     string            // 来源渠道
    MatchedContent       string            // 实际匹配内容
    KnowledgeDescription string            // 知识描述
    KnowledgeBaseID      string            // 所属知识库ID
}
```

---

## 六、权限与共享机制

### 6.1 多级权限控制

WeKnora 实现了完善的多级权限体系：

1. **租户级别**：每个知识库属于一个租户（TenantID）
2. **组织共享**：通过 KBShareService 实现知识库跨租户共享
   - 权限级别：Admin（管理员）、Editor（编辑者）、Viewer（查看者）
3. **智能体关联共享**：通过 AgentShareService 实现
   - KBSelectionMode: none（不可用）/ all（全部可用）/ selected（选择特定知识库）

### 6.2 权限验证流程

```
validateAndGetKnowledgeBase:
1. 检查是否为Owner（TenantID匹配）→ Admin权限
2. 检查组织共享权限（KBShareService.CheckUserKBPermission）
3. 检查智能体关联权限（AgentShareService）
4. 无任何权限 → 返回403
```

---

## 七、异步任务系统

### 7.1 Asynq 任务队列

- 使用 Asynq 实现异步任务处理
- 任务类型包括：文档解析、知识图谱构建、知识库复制等
- 支持任务进度查询（Redis存储进度）

### 7.2 知识库复制

```
POST /knowledge-bases/copy
- 异步任务执行
- 校验Source和Target的TenantID（防跨租户克隆）
- 要求同类型、同Embedding模型
- 进度查询：GET /knowledge-bases/copy/progress/{task_id}
```

---

## 八、架构特点总结

1. **Go高并发架构**：Gin框架 + GORM + Asynq，适合高并发场景
2. **双类型知识库**：文档型 + FAQ型，各自独立的解析和检索策略
3. **多渠道来源**：支持web/api/微信/企业微信/飞书/钉钉/Slack等多种渠道
4. **完善的权限体系**：租户隔离 + 组织共享 + 智能体关联共享
5. **丰富的分块类型**：12种分块类型，支持知识图谱实体/关系分块
6. **父子分块策略**：parent_text类型分块用于上下文增强，不参与向量索引
7. **异步任务系统**：Asynq任务队列支持，可靠的进度追踪
8. **知识图谱抽取**：ExtractConfig支持自定义节点和关系的图谱构建
9. **内容安全**：分块内容输出前经过 SanitizeForDisplay 清理
