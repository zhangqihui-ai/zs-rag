## Why

现有 Neo4j 预留式「手写最小图写入」无法支撑实体关系抽取与图检索。采用 HKUDS LightRAG 作为独立图知识库引擎，与经典 Milvus 混合检索库并行。

## What Changes

- 新增 `kb_type=classic|lightrag`，图库走 LightRAG 入库与五模式检索
- 平台 Neo4j + Milvus + JsonKV，workspace `space_{sid}_kb_{kid}` 隔离
- 图谱可视化、graph-search API、对话按库类型路由
- 废弃 `graph_db_enabled` 作为主路径

## Capabilities

### New

- `graph-knowledge-base`: kb_type、LightRAG 入库、五模式检索、图谱可视化、对话分派

### Modified

- `knowledge-base-management`: 创建时选择库类型；经典库行为不变
