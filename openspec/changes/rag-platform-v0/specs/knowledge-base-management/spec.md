## ADDED Requirements

### Requirement: Knowledge base metadata is tenant-scoped
系统 MUST 在企业空间维度管理知识库（Knowledge Base）元数据。知识库元数据 MUST 存储在 PostgreSQL 中，并且 MUST 强制按企业空间隔离。

#### Scenario: Create knowledge base within a space
- **WHEN** 用户在企业空间 `acme` 上下文创建一个知识库
- **THEN** 该知识库仅归属 `acme` 且在 `default` 上下文不可见

#### Scenario: List knowledge bases is isolated
- **WHEN** 用户在企业空间 `default` 上下文请求知识库列表
- **THEN** 系统仅返回 `default` 下的知识库

### Requirement: External storage connections are configurable per tenant
系统 MUST 支持在企业空间维度配置外部存储连接信息，至少包括 Milvus 与 Neo4j。连接配置中的敏感字段（如密码、Token）MUST 仅写入不回显。

#### Scenario: Create Milvus connection config
- **WHEN** 用户创建一个 Milvus 连接配置并提交必要的连接参数
- **THEN** 系统保存配置并在读取时不返回敏感字段明文

#### Scenario: Create Neo4j connection config
- **WHEN** 用户创建一个 Neo4j 连接配置并提交必要的连接参数
- **THEN** 系统保存配置并在读取时不返回敏感字段明文

### Requirement: Connection health checks
系统 MUST 提供对 Milvus 与 Neo4j 连接配置的健康检查能力，用于验证“可连接”。健康检查失败时 MUST 返回统一错误模型并包含 `request_id`。

#### Scenario: Milvus health check succeeds
- **WHEN** 用户对一个可用的 Milvus 连接配置发起健康检查
- **THEN** 系统返回成功结果并标识连接可用

#### Scenario: Neo4j health check fails
- **WHEN** 用户对一个不可用的 Neo4j 连接配置发起健康检查
- **THEN** 系统返回统一错误模型（例如 `INTEGRATION_ERROR` 或 `PROVIDER_UNAVAILABLE`）并包含 `request_id`

### Requirement: Milvus minimal write and search loop
系统 MUST 支持对接 Milvus 完成最小闭环：在知识库维度选择或创建 collection，写入向量，并执行 topK 向量检索。Milvus 中的向量记录 MUST 可追溯到企业空间与知识库（通过命名或元数据字段之一实现）。

#### Scenario: Write embedding vectors to Milvus
- **WHEN** 用户向某知识库提交一批向量与最小元数据（文档/片段标识）
- **THEN** 系统将向量写入该知识库对应的 Milvus collection

#### Scenario: Search topK from Milvus
- **WHEN** 用户以查询向量对某知识库执行 topK 检索
- **THEN** 系统返回匹配结果列表并可关联回知识库元数据

### Requirement: Neo4j minimal write and query loop
系统 MUST 支持对接 Neo4j 完成最小闭环：在知识库维度写入最小图数据，并执行最小图查询以验证可读写。Neo4j 中的数据 MUST 以企业空间与知识库维度隔离（通过标签或属性之一实现）。

#### Scenario: Write minimal graph nodes and relations
- **WHEN** 用户向某知识库写入最小图实体（例如 Document/Chunk/Entity/Relation 的最小子集）
- **THEN** 系统将数据写入 Neo4j 且可按知识库维度隔离

#### Scenario: Query minimal graph view
- **WHEN** 用户对某知识库执行最小图查询（例如按文档标识查关联实体）
- **THEN** 系统返回查询结果且结果不包含其它企业空间的数据

### Requirement: Tenant context for all knowledge base operations
所有知识库管理相关 API MUST 以企业空间为上下文（通过 `X-Enterprise-Space` 或等价机制），并 MUST 强制执行隔离与审计记录。

#### Scenario: Cross-tenant access is rejected
- **WHEN** 用户在企业空间 `acme` 上下文访问 `default` 的知识库资源
- **THEN** 系统拒绝并返回统一错误模型
