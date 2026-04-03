## Context

平台以“企业空间（enterprise space）”作为唯一租户边界，隔离模型配置与知识库资产。V0 需要先交付可运行的工程骨架与三大模块的最小闭环：

- 企业空间管理：启动初始化管理员账号并自动创建 `default` 企业空间；后续操作默认基于 `default`。
- 模型管理：用统一 Provider 抽象对接多家厂商模型服务。
- 知识库管理：PostgreSQL 保存元数据；Milvus/Neo4j 提供向量/图能力，V0 仅要求可连接与最小读写闭环。

约束：后端 Python 3.12+ / FastAPI / SQLAlchemy / Pydantic / PostgreSQL；前端 Vue 3 + Vite（主流生态）。

## Goals / Non-Goals

**Goals:**

- 定义企业空间（租户）数据模型与隔离落点，并贯穿 API 与数据访问层。
- 定义启动初始化流程（管理员账号 + `default` 企业空间）与幂等策略。
- 定义模型 Provider 抽象、配置方式、鉴权方式（密钥仅写入不回显）、超时/重试与错误映射原则。
- 定义 Milvus 与 Neo4j 的集成边界与 V0 最小能力（可连接、可写入、可检索/可查询的最小路径）。

**Non-Goals:**

- 不在 V0 定义复杂权限体系（如多角色、多级授权、细粒度资源权限）。
- 不在 V0 完整实现知识内容的全流程（采集、清洗、切分、评测、回溯、权限继承等），仅交付最小管理与连接/存储闭环。
- 不在 V0 承诺所有厂商模型的完整功能覆盖（仅提供统一的最小调用与管理能力）。

## Decisions

0) 认证与授权（V0 最小）

- 选择：提供管理员登录接口，签发 Bearer Token（例如 JWT）用于调用管理类 API；密码仅以安全散列存储（例如 bcrypt/argon2 其一）。
- 授权：V0 仅需要“已认证用户”与“管理员”两类能力边界；企业空间访问必须绑定用户与企业空间的成员关系（V0 可默认为管理员加入 `default` 并拥有 owner 权限）。
- 替代方案：HTTP Basic 或单一全局 API Key。为便于前端与后续演进，V0 优先 Token 方案。

1) 企业空间（租户）隔离策略

- 选择：以数据库字段/外键 `enterprise_space_id` 作为所有租户隔离的硬约束；所有与模型/知识库相关的核心表必须包含该字段，并建立索引（`(enterprise_space_id, id)`、`(enterprise_space_id, name)` 等）。
- API 上下文承载：使用请求头 `X-Enterprise-Space` 传递企业空间标识（默认 `default`）；服务端在认证后解析并注入请求上下文，所有查询/写入必须按该上下文过滤。
- 替代方案：URL 路径携带企业空间（`/spaces/{space}/...`）。保留为未来演进方向；V0 先以 header 方案减少路由膨胀与前端切换成本。

2) 启动初始化（Bootstrap）方式

- 选择：应用启动时执行幂等初始化逻辑：
  - 若不存在管理员账号，则从环境变量读取初始管理员信息并创建管理员。
  - 若不存在企业空间 `default`，则创建 `default`，并将管理员加入该空间（V0 可直接设为 owner）。
- 幂等策略：以唯一约束保证不重复创建（管理员唯一邮箱/用户名；企业空间唯一 slug/name）；初始化逻辑在事务内执行并吞掉“已存在”冲突，确保重复启动不破坏数据。
- 替代方案：提供一次性初始化 API/CLI。未来可引入；V0 以启动初始化为主，满足“开箱即用”。

3) 模型 Provider 抽象

- 选择：将“厂商/平台”抽象为 Provider，将“可调用模型”抽象为 Model，按企业空间配置 Provider 连接与模型列表：
  - ProviderConfig：`provider_type`（例如 bailian/deepseek/zhipu/kimi/openai-compatible）、`base_url`、`api_key` 等凭据、超时/重试参数。
  - ModelRef：`provider_id`、`model_name`、`capabilities`（chat/embedding/rerank 等）、可选默认参数（temperature、max_tokens 等）。
- 鉴权与密钥：密钥字段仅允许写入与更新，读取时永不回显明文；存储方式 V0 允许明文落库但必须具备迁移为加密存储的接口边界（推荐后续引入应用级加密或 KMS）。
- 错误映射：将厂商错误映射为统一错误模型（HTTP 状态码 + 业务错误码 + message + request_id），并保留可选 `details` 供排障但不得包含密钥。
- 超时/重试：在 Provider 层配置统一的默认超时与重试（仅对可重试错误码重试，如 429/5xx），并提供覆盖能力。

4) Milvus 与 Neo4j 集成边界（V0）

- 选择：知识库元数据（知识库、数据源、索引/集合配置、连接配置引用）存储在 PostgreSQL；Milvus/Neo4j 仅作为外部存储与检索系统。
- Milvus（向量）V0 最小能力：
  - 连接可用性检测（ping/health）。
  - 为某知识库创建或选择 collection（命名包含企业空间与知识库标识，避免跨租户冲突）。
  - 写入向量（带 payload 元数据，至少包含文档/片段标识与企业空间标识）。
  - 以向量查询返回 topK（最小检索闭环）。
- Neo4j（图）V0 最小能力：
  - 连接可用性检测。
  - 写入最小图实体（例如 Document/Chunk/Entity/Relation 中的最小子集）与按知识库维度的隔离标签/属性。
  - 按给定起点或条件执行最小查询（用于证明可读写闭环）。
- 替代方案：仅做 Milvus 或仅做 Neo4j。为了满足初始方向，V0 同时接入但严格限制能力范围，避免过度设计。

## Risks / Trade-offs

- 密钥存储未加密（若 V0 采用明文） → 通过“仅写入不回显”、最小权限、后续加密迁移预留字段/封装层降低风险。
- Header 作为企业空间上下文可能被伪造 → 必须与认证绑定：解析后校验用户对该企业空间的访问权限；服务端不可仅信任请求头。
- 多系统一致性（PostgreSQL + Milvus + Neo4j）存在写入不一致风险 → V0 仅保证“尽力写入”并记录外部写入状态；后续引入异步补偿与重试队列。
- 外部依赖引入复杂运维 → 用 docker-compose 提供开发环境编排，并在应用层提供健康检查与明确错误提示。

## Migration Plan

- V0 为新项目初始化，无存量迁移。
- 预留后续演进：密钥加密存储迁移、租户上下文从 header 迁移到 URL/Token claim、权限体系扩展。

## Open Questions

- 管理员初始化字段（邮箱/用户名/密码/一次性口令）最终采用哪组环境变量命名。
- Provider 类型枚举与最小统一调用接口（chat/embedding）在 V0 是否都需要，还是先只落地管理能力并在后续补齐调用链路。
- Milvus/Neo4j 的最小 schema（collection/labels/constraints）细节在规格阶段补充到可测试的程度。
