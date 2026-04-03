## ADDED Requirements

### Requirement: Tenant identity and default space
系统 MUST 以企业空间作为唯一租户标识。工程首次启动时 MUST 创建企业空间 `default`，并确保后续未显式指定企业空间上下文的操作默认基于 `default`。

#### Scenario: First boot creates default space
- **WHEN** 系统首次启动且数据库中不存在企业空间 `default`
- **THEN** 系统创建 `default` 企业空间并可被管理员访问

#### Scenario: Subsequent boot is idempotent
- **WHEN** 系统再次启动且企业空间 `default` 已存在
- **THEN** 系统不重复创建且不修改现有 `default` 的关键标识字段

### Requirement: Admin bootstrap initialization
工程首次启动时 MUST 初始化管理员账号。管理员初始化信息 MUST 由环境变量或启动参数提供。系统 MUST 保证初始化流程幂等且敏感信息不以明文写入日志。

#### Scenario: First boot creates admin
- **WHEN** 系统启动且数据库中不存在管理员账号
- **THEN** 系统读取初始化配置并创建管理员账号

#### Scenario: Secret values are not logged
- **WHEN** 初始化过程读取到管理员初始密码或一次性口令
- **THEN** 日志中不包含该敏感值的明文

### Requirement: Authentication required for management APIs
除健康检查与初始化引导所需的最小端点外，系统 MUST 要求对管理类 API 进行身份认证。未认证请求 MUST 返回统一错误模型且业务错误码为 `AUTH_REQUIRED`。

#### Scenario: Unauthorized request is rejected
- **WHEN** 客户端未携带有效认证信息请求任意管理类 API
- **THEN** 系统返回 401 且 `code` 为 `AUTH_REQUIRED`

### Requirement: Enterprise space context resolution
每个 API 请求 MUST 解析当前企业空间上下文。系统 MUST 支持通过请求头 `X-Enterprise-Space` 传递企业空间标识；若该请求头缺失，则 MUST 使用 `default` 作为企业空间上下文。

#### Scenario: Context resolved from header
- **WHEN** 请求包含 `X-Enterprise-Space: acme`
- **THEN** 系统将当前企业空间上下文解析为 `acme`

#### Scenario: Context falls back to default
- **WHEN** 请求不包含 `X-Enterprise-Space`
- **THEN** 系统将当前企业空间上下文解析为 `default`

### Requirement: Tenant isolation enforcement
系统 MUST 在服务层与数据访问层强制执行企业空间隔离：任何读取或写入与“模型配置/知识库元数据/外部连接配置”相关的资源 MUST 仅作用于当前企业空间上下文，并且 MUST 可审计（至少记录 request_id 与企业空间标识）。

#### Scenario: Cross-tenant read is prevented
- **WHEN** 用户在企业空间 `acme` 上下文中请求读取属于企业空间 `default` 的资源
- **THEN** 系统拒绝访问并返回统一错误模型（403 或 404），且不泄露资源是否存在的额外信息

#### Scenario: Cross-tenant write is prevented
- **WHEN** 用户在企业空间 `acme` 上下文中尝试写入/修改属于企业空间 `default` 的资源
- **THEN** 系统拒绝访问并返回统一错误模型

### Requirement: Unified error model
系统 MUST 对所有 API 返回统一的错误响应结构，包含：HTTP 状态码、业务错误码 `code`、人类可读的 `message`、以及 `request_id`。业务错误码 MUST 覆盖至少：`AUTH_REQUIRED`、`FORBIDDEN`、`SPACE_NOT_FOUND`、`VALIDATION_ERROR`、`INTERNAL_ERROR`。

#### Scenario: Error response shape
- **WHEN** 任意 API 发生错误
- **THEN** 响应 body 包含 `code`、`message`、`request_id` 字段且不包含敏感信息
