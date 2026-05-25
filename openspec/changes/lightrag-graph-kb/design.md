# LightRAG 图知识库设计

## 架构

- **classic**：`knowledge_document` → chunk → Milvus/OpenSearch（不变）
- **lightrag**：解析文本 → `LightRAG.ainsert` → Neo4j 图谱 + Milvus 实体/关系/chunk 向量 + JsonKV

## Workspace

`space_{enterprise_space_id}_kb_{knowledge_base_id}` — Neo4j 节点 label、LightRAG 内部 Milvus collection 前缀。

## 配置

| 来源 | 说明 |
|------|------|
| `knowledge_base.kb_type` | `classic` / `lightrag` |
| `knowledge_base.config.lightrag` | `default_query_mode`、`extract_llm_id` 等 |
| 平台 env | `NEO4J_URI`、`MILVUS_HOST/PORT`、`LIGHTRAG_STORAGE_ROOT` |

## 文档状态（图库）

`graph_indexing` → `graph_indexed` / `graph_failed`；不写 `knowledge_chunk`。

## 检索

`POST /knowledge-bases/{id}/graph-search`，模式 `naive|local|global|hybrid|mix`。

## 对话

含 lightrag 库时调用 `lightrag_engine.query`；`ChatConfiguration.lightrag_query_mode` 默认 `mix`。
