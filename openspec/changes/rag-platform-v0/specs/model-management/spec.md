## ADDED Requirements

### Requirement: Provider configuration is tenant-scoped
系统 MUST 支持在企业空间维度管理模型 Provider 配置。Provider 配置 MUST 绑定当前企业空间，并且在任何读取/写入操作中 MUST 强制按企业空间隔离。

#### Scenario: Create provider config within a space
- **WHEN** 用户在企业空间 `acme` 上下文中创建一个 Provider 配置
- **THEN** 该配置仅归属 `acme` 且在 `default` 上下文不可见

#### Scenario: List provider configs is isolated
- **WHEN** 用户在企业空间 `default` 上下文请求 Provider 配置列表
- **THEN** 系统仅返回 `default` 下的配置

### Requirement: Provider types and minimal fields
系统 MUST 支持通过 `provider_type` 标识不同厂商/平台（例如 `bailian`、`deepseek`、`zhipu`、`kimi`、`openai-compatible`）。每个 Provider 配置 MUST 至少包含：`provider_type`、`display_name`，以及调用所需的连接信息（例如 `base_url`）与鉴权信息（例如 `api_key`）。

#### Scenario: Provider type is validated
- **WHEN** 用户提交不支持的 `provider_type`
- **THEN** 系统返回 `VALIDATION_ERROR`

#### Scenario: Required fields are enforced
- **WHEN** 用户创建 Provider 配置缺少必填字段
- **THEN** 系统返回 `VALIDATION_ERROR`

### Requirement: Secrets are write-only and never returned in plaintext
任何用于鉴权的敏感字段（例如 `api_key`、`access_token`、`secret`）MUST 仅允许写入/更新，且 MUST NOT 在任何响应中以明文返回。系统 MAY 返回“是否已配置”的布尔标记，但 MUST NOT 返回敏感值本身。

#### Scenario: Secret is accepted on create
- **WHEN** 用户创建 Provider 配置并提交 `api_key`
- **THEN** 系统保存该密钥并返回成功响应，但响应中不包含 `api_key` 明文字段

#### Scenario: Secret is not exposed on read
- **WHEN** 用户读取某个 Provider 配置详情
- **THEN** 响应中不包含敏感字段的明文

### Requirement: Model registry within a provider
系统 MUST 支持在企业空间内为某 Provider 管理可用模型条目（Model）。每个模型条目 MUST 关联一个 Provider，并包含：`model_name` 与 `capabilities`（至少区分 `chat`、`embedding`、`rerank`）。

#### Scenario: Create model under provider
- **WHEN** 用户在某 Provider 下创建一个模型条目并指定 `capabilities`
- **THEN** 系统保存模型条目且仅在当前企业空间可见

#### Scenario: Model cannot reference provider from another space
- **WHEN** 用户在企业空间 `acme` 上下文中创建模型条目但引用了企业空间 `default` 的 Provider
- **THEN** 系统拒绝并返回 `FORBIDDEN` 或 `SPACE_NOT_FOUND`

### Requirement: Connectivity test and error mapping
系统 MUST 支持对 Provider 配置进行连通性测试（最小请求或健康检查）。当厂商返回错误时，系统 MUST 映射为统一错误模型，并提供可排障的 `message`，但 MUST NOT 包含敏感信息。

#### Scenario: Provider test succeeds
- **WHEN** 用户对一个有效的 Provider 配置发起连通性测试
- **THEN** 系统返回成功结果并标识该 Provider 可用

#### Scenario: Provider error is mapped
- **WHEN** 厂商接口返回 401/429/5xx 等错误
- **THEN** 系统返回统一错误模型（例如 `FORBIDDEN`、`PROVIDER_UNAVAILABLE`、`INTEGRATION_ERROR`），并包含 `request_id`

### Requirement: Tenant context for all model operations
所有模型管理相关 API MUST 以企业空间为上下文（通过 `X-Enterprise-Space` 或等价机制），且 MUST 在审计记录中包含企业空间标识与 `request_id`。

#### Scenario: Missing context falls back to default
- **WHEN** 请求未提供企业空间上下文
- **THEN** 系统在 `default` 企业空间内执行该操作并强制隔离
