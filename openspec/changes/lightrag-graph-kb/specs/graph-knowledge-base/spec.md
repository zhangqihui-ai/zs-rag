# Graph Knowledge Base

## Requirements

### KB-TYPE-001
系统 SHALL 支持 `knowledge_base.kb_type` 为 `classic`（默认）或 `lightrag`。

### KB-TYPE-002
创建 `lightrag` 库时 SHALL 自动 `graph_db_enabled=true` 并写入 `config.lightrag.default_query_mode=mix`。

### INGEST-001
图库文档入库 SHALL：解析 → `graph_indexing` → LightRAG `ainsert` → `graph_indexed`；失败为 `graph_failed`。

### INGEST-002
图库 SHALL NOT 写入 `knowledge_chunk` 经典分块表。

### SEARCH-001
`POST /knowledge-bases/{kb_id}/graph-search` SHALL 支持模式 naive/local/global/hybrid/mix 与 Top K。

### SEARCH-002
响应 SHALL 含 `answer_context`、`entities`、`relationships`、`citations`。

### VIZ-001
`GET .../graph/stats|subgraph|nodes/{id}|export` SHALL 按 workspace 隔离查询 Neo4j。

### CHAT-001
对话检索含 lightrag 库时 SHALL 使用 `lightrag_query_mode`（默认 mix）调用 LightRAG。

### DEPRECATE-001
`graph_db_enabled` 与 per-KB Neo4j CRUD UI 标记为废弃；新图库使用平台 Neo4j + LightRAG。
