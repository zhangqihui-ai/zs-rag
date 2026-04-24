## 1. 基础骨架

- [x] 1.1 创建工程目录骨架（backend/、web/、docker/、docs/ 以及根目录 docker-compose.yml、Makefile、.env.template）
- [x] 1.2 初始化 docker-compose 开发编排（PostgreSQL + Milvus + Neo4j）（验收：`docker compose up` 后三者均可健康运行）
- [x] 1.3 初始化后端工程（Python 3.12+、FastAPI、SQLAlchemy、Pydantic、Alembic）（验收：`/health` 可访问且能连通 PostgreSQL）
- [x] 1.4 实现统一错误模型与 request_id 注入（验收：制造校验错误时返回包含 `code`/`message`/`request_id` 的结构）
- [x] 1.5 初始化前端工程（Vue 3 + Vite + TypeScript + Router + Pinia + HTTP Client）（验收：页面可启动并能调用后端 `/health`）

## 2. 多租户与启动初始化

- [x] 2.1 设计并落库租户相关数据模型与迁移（enterprise_space、user、membership）（验收：唯一约束与索引生效）
- [x] 2.2 实现启动初始化（创建管理员账号 + 创建 `default` 企业空间 + 建立成员关系）（验收：首次启动创建；重复启动幂等）
- [x] 2.3 实现认证最小闭环（管理员登录签发 Bearer Token，密码安全散列）（验收：未认证访问管理 API 返回 401/`AUTH_REQUIRED`）
- [ ] 2.4 实现企业空间上下文解析（`X-Enterprise-Space`，缺省回落 `default`）与成员校验（验收：跨租户访问返回 403/404 且无信息泄露）
- [x] 2.5 实现企业空间管理 API（列出/创建/切换上下文所需的最小端点）（验收：可在 UI 中切换企业空间并影响后续请求）

## 3. 模型管理

- [x] 3.1 设计并落库模型管理数据模型与迁移（provider_config、model_ref，均带 `enterprise_space_id`）（验收：跨租户不可读写）
- [x] 3.2 实现 Provider CRUD API（验收：创建/更新/列表/删除可用；敏感字段仅写入不回显）
- [x] 3.3 实现同步模型查询与启停 API（模型由厂商同步获取，无需手工 CRUD；验收：模型条目只能引用同一企业空间下的 Provider）
- [x] 3.4 实现 Provider 连通性测试 API 与错误映射（验收：模拟 401/429/5xx 时返回统一错误结构且无敏感信息）
- [x] 3.5 实现 Provider 注册表与最小调用适配层（先落地 `openai-compatible`，其它 provider_type 预留扩展点）（验收：可通过配置切换 base_url/model_name 并完成一次最小请求）

## 4. 知识库管理（Milvus / Neo4j 最小闭环）

- [x] 4.1 设计并落库知识库元数据与连接配置模型与迁移（knowledge_base、milvus_connection、neo4j_connection）（验收：敏感字段仅写入不回显）
- [x] 4.2 实现知识库 CRUD API（验收：按企业空间隔离，列表/创建/更新/删除可用）
- [x] 4.3 实现 Milvus/Neo4j 连接健康检查 API（验收：不可用时返回统一错误结构与 `request_id`）
- [x] 4.4 集成 Milvus 最小闭环（collection 命名含企业空间与知识库标识；写入向量；topK 检索）（验收：写入后可检索到结果）
- [ ] 4.5 集成 Neo4j 最小闭环（按企业空间与知识库隔离写入最小图数据；最小查询）（验收：写入后查询可返回且不跨租户）

## 5. 前端联调

- [x] 5.1 实现登录页与 Token 持久化（验收：登录后可访问管理页面；退出后不可访问）
- [x] 5.2 实现企业空间选择器与请求头注入（`X-Enterprise-Space`）（验收：切换空间后数据视图随之变化）
- [x] 5.3 实现模型管理页面（Provider 列表/创建/编辑、Model 列表/启停、连通性测试）（验收：与后端 API 双向联调通过）
- [x] 5.4 实现知识库管理页面（知识库列表、创建/编辑、Milvus/Neo4j 连接配置与健康检查）（验收：与后端 API 双向联调通过）
- [x] 5.5 统一错误提示与基础表单校验（验收：后端返回错误码时前端可读提示且不泄露敏感信息）

## 6. 质量与可验证性

- [ ] 6.1 增加最小自动化验证（后端：租户隔离与启动初始化的单元/集成测试）（验收：CI/本地可一键运行并通过）
- [x] 6.2 配置并跑通 lint/typecheck（后端/前端）（验收：`make lint`/`make typecheck` 或等价命令通过）
