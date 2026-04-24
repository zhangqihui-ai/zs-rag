# AI模型管理系统数据库与接口设计

> 参考图片中的三块 UI：左侧“设置默认模型”、中间“已添加的模型”、右侧“可选模型”。
> 目标：设计一套简单、易落地、按企业空间隔离的模型管理方案，支持公有云/私有化接入、模型同步、按类型筛选、单模型启用/禁用、默认模型设置。

---

## 1. 设计原则

1. **按企业空间隔离**：所有模型配置、模型列表、默认模型都只属于当前企业空间。
2. **尽量少表**：只保留 3 张核心业务表，避免过度设计。
3. **Provider 与 Model 分离**：
   - `Provider` 表示“一个已接入的厂商/服务地址配置”；
   - `Model` 表示“该厂商地址返回的可用模型”。
4. **默认模型按类型设置**：更贴近图片 UI，可分别设置 `LLM / Embedding / VLM / ASR / Rerank / TTS / OCR / Moderation` 的默认模型。
   - 如果业务只需要“一个全局默认”，只使用 `LLM` 这一类默认模型即可。
5. **只允许启用模型被调用**：模型是否可调用，以 `is_enabled=1` 为准。
6. **厂商模板不建议落库**：像 OpenAI、Anthropic、Gemini 这类“可选厂商卡片”，建议后端写成内置配置，通过接口返回，避免额外维护模板表。

---

## 2. 核心对象说明

### 2.1 页面与数据对象映射

- **右侧“可选模型”区域**
  - 展示系统内置的厂商模板：如 `OpenAI`、`Anthropic`、`Gemini`、`DeepSeek`、`Qwen`。
  - 数据来源：后端内置配置接口，不强制落库。

- **中间“已添加的模型”区域**
  - 一行代表一个“已接入厂商配置”。
  - 展开后展示该厂商 URL 返回的模型列表。
  - 每个模型有单独启用/禁用开关。
  - 数据来源：`ai_model_provider` + `ai_model`。

- **左侧“设置默认模型”区域**
  - 从“已启用模型”中，按模型类型选择默认项。
  - 数据来源：`ai_model_default`。

---

## 3. 数据库 Schema 设计

> 以下以 **MySQL 8.0** 为例，若使用 PostgreSQL，可将 `JSON`、`TINYINT`、`DATETIME` 做等价替换。

### 3.1 企业空间表（复用现有企业表即可）

如果系统已有企业/租户表，直接复用；这里只给出最小字段示意。

```sql
CREATE TABLE enterprise_space (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '企业空间ID',
    name            VARCHAR(100) NOT NULL COMMENT '企业空间名称',
    status          TINYINT NOT NULL DEFAULT 1 COMMENT '状态: 1启用, 0停用',
    created_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) COMMENT='企业空间表';
```

---

### 3.2 已接入厂商配置表 `ai_model_provider`

一条记录代表“当前企业空间下接入的一个模型服务配置”。

例如：
- 企业 A 接入一个 OpenAI 公有云地址；
- 企业 A 再接入一个私有化 vLLM 地址；
- 这是两条 `provider` 记录。

```sql
CREATE TABLE ai_model_provider (
    id                  BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    enterprise_id       BIGINT NOT NULL COMMENT '企业空间ID',
    provider_code       VARCHAR(50) NOT NULL COMMENT '厂商编码，如 openai/deepseek/qwen/custom',
    provider_name       VARCHAR(100) NOT NULL COMMENT '厂商名称，如 OpenAI、DeepSeek、企业私有模型服务',
    deployment_type     VARCHAR(20) NOT NULL COMMENT '部署类型: public/private',
    base_url            VARCHAR(500) NOT NULL COMMENT '模型服务基础地址',
    auth_type           VARCHAR(30) NOT NULL COMMENT '认证类型: api_key/bearer/basic/custom',
    auth_config         JSON NOT NULL COMMENT '认证字段值，建议应用层加密后存储',
    supported_types     JSON NULL COMMENT '该厂商当前支持的模型类型列表，如 ["llm","embedding","rerank"]',
    remark              VARCHAR(255) NULL COMMENT '备注',
    sync_status         VARCHAR(20) NOT NULL DEFAULT 'pending' COMMENT '同步状态: pending/success/failed',
    last_sync_at        DATETIME NULL COMMENT '最近同步模型时间',
    last_sync_error     VARCHAR(500) NULL COMMENT '最近同步错误信息',
    created_by          BIGINT NULL COMMENT '创建人',
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT uk_enterprise_provider UNIQUE (enterprise_id, provider_name, base_url),
    INDEX idx_enterprise_id (enterprise_id),
    INDEX idx_provider_code (provider_code),
    INDEX idx_deployment_type (deployment_type),
    CONSTRAINT fk_provider_enterprise FOREIGN KEY (enterprise_id) REFERENCES enterprise_space(id)
) COMMENT='企业空间下已接入的模型厂商配置表';
```

#### 字段说明

| 字段 | 说明 |
|---|---|
| `enterprise_id` | 企业空间隔离主键，所有查询都必须带上当前登录企业空间 |
| `provider_code` | 系统识别码，便于前端显示图标、标签、默认认证方式 |
| `provider_name` | 页面展示名称 |
| `deployment_type` | `public` 表示公有云，`private` 表示私有化部署 |
| `base_url` | 模型服务访问地址，例如 `https://api.openai.com/v1` 或私有部署地址 |
| `auth_type` | 认证方式类型 |
| `auth_config` | 实际认证值，建议存加密后的 JSON |
| `supported_types` | 该地址返回的模型类型集合，供页面展示标签和筛选 |
| `sync_status` | 最近一次同步模型列表的结果 |
| `last_sync_at` | 最近同步时间 |
| `last_sync_error` | 同步失败原因 |

#### `auth_config` 示例

```json
{
  "api_key": "enc_xxx",
  "organization": "org_123",
  "api_version": "2024-10-01"
}
```

私有化部署示例：

```json
{
  "token": "enc_xxx",
  "tenant_header": "corp-a",
  "extra_headers": {
    "X-Channel": "internal"
  }
}
```

> 说明：认证字段定义本身建议由后端内置模板接口返回，不一定需要单独落表。

---

### 3.3 模型表 `ai_model`

一条记录代表“某个厂商地址下的一个具体模型”。

例如：
- `gpt-4o`
- `text-embedding-3-large`
- `qwen-max`
- `bge-reranker-v2`

```sql
CREATE TABLE ai_model (
    id                  BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    enterprise_id       BIGINT NOT NULL COMMENT '企业空间ID',
    provider_id         BIGINT NOT NULL COMMENT '所属厂商配置ID',
    model_code          VARCHAR(150) NOT NULL COMMENT '模型编码/唯一标识，如 gpt-4o',
    model_name          VARCHAR(150) NOT NULL COMMENT '模型名称，通常与 model_code 一致，可展示',
    model_type          VARCHAR(30) NOT NULL COMMENT '模型类型: llm/embedding/rerank/tts/asr/vlm/moderation/ocr',
    is_enabled          TINYINT NOT NULL DEFAULT 0 COMMENT '是否启用: 1启用, 0禁用',
    context_window      INT NULL COMMENT '上下文长度，可选',
    max_output_tokens   INT NULL COMMENT '最大输出token，可选',
    capabilities        JSON NULL COMMENT '能力标签，如 ["vision","function_call"]',
    raw_payload         JSON NULL COMMENT '厂商原始返回，便于排查和兼容扩展',
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT uk_provider_model UNIQUE (provider_id, model_code),
    INDEX idx_enterprise_type_enabled (enterprise_id, model_type, is_enabled),
    INDEX idx_provider_id (provider_id),
    CONSTRAINT fk_model_enterprise FOREIGN KEY (enterprise_id) REFERENCES enterprise_space(id),
    CONSTRAINT fk_model_provider FOREIGN KEY (provider_id) REFERENCES ai_model_provider(id) ON DELETE CASCADE
) COMMENT='企业空间下可用模型表';
```

#### 字段说明

| 字段 | 说明 |
|---|---|
| `provider_id` | 对应哪个已接入厂商配置 |
| `model_code` | 供应商返回的原始模型标识，建议作为业务唯一键 |
| `model_type` | 模型类型，供页面筛选与默认模型分类 |
| `is_enabled` | 是否启用；只有启用模型允许被调用 |
| `capabilities` | 能力标签，例如视觉、多模态、函数调用等 |
| `raw_payload` | 完整保留供应商返回字段，后续兼容更方便 |

---

### 3.4 默认模型表 `ai_model_default`

用于保存企业空间的默认模型设置。

> 为贴合图片 UI，设计为“**每种类型一个默认模型**”。
> 如果业务只想保留“一个全局默认”，只维护 `model_type='llm'` 一条即可。

```sql
CREATE TABLE ai_model_default (
    id                  BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '主键ID',
    enterprise_id       BIGINT NOT NULL COMMENT '企业空间ID',
    model_type          VARCHAR(30) NOT NULL COMMENT '模型类型: llm/embedding/rerank/tts/asr/vlm/moderation/ocr',
    model_id            BIGINT NOT NULL COMMENT '默认模型ID，必须是已启用模型',
    created_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT uk_enterprise_model_type UNIQUE (enterprise_id, model_type),
    INDEX idx_model_id (model_id),
    CONSTRAINT fk_default_enterprise FOREIGN KEY (enterprise_id) REFERENCES enterprise_space(id),
    CONSTRAINT fk_default_model FOREIGN KEY (model_id) REFERENCES ai_model(id)
) COMMENT='企业空间默认模型表';
```

#### 关键约束

- 同一企业空间、同一模型类型，只能有一个默认模型。
- `model_id` 对应的模型必须满足：
  1. 属于当前 `enterprise_id`
  2. `is_enabled = 1`
  3. `model_type` 与当前默认项一致

---

## 4. 为什么只需要这 3 张核心表

这个需求的核心其实只有三件事：

1. **接入哪个厂商地址 + 认证信息** → `ai_model_provider`
2. **该地址下有哪些模型 + 哪些模型启用** → `ai_model`
3. **每个类型默认用哪个模型** → `ai_model_default`

这样已经能完整支撑图片中的页面，不需要再拆：
- 厂商表
- 模型类型表
- 认证字段表
- 模型标签表
- 模型状态日志表

这些都可以先不做，保证方案简单、清晰、易实现。

---

## 5. 推荐的后端内置配置（不落库）

为了支持右侧“可选模型”区域，建议后端维护一个内置模板配置，例如：

```json
[
  {
    "provider_code": "openai",
    "provider_name": "OpenAI",
    "deployment_type": "public",
    "default_base_url": "https://api.openai.com/v1",
    "supported_types": ["llm", "embedding", "tts", "moderation"],
    "auth_fields": [
      {"key": "api_key", "label": "API Key", "type": "password", "required": true},
      {"key": "organization", "label": "Organization", "type": "text", "required": false}
    ]
  },
  {
    "provider_code": "custom",
    "provider_name": "自定义私有模型服务",
    "deployment_type": "private",
    "default_base_url": "",
    "supported_types": ["llm", "embedding", "rerank", "vlm", "asr", "tts"],
    "auth_fields": [
      {"key": "token", "label": "Token", "type": "password", "required": true}
    ]
  }
]
```

这样前端在点击“添加模型”时，可以动态生成认证表单，而不用额外设计数据库表去维护认证字段定义。

---

## 6. 关键业务规则

### 6.1 企业空间隔离

- 所有表都带 `enterprise_id`
- 所有接口都从登录态中获取 `enterprise_id`
- 请求体里不允许前端随意传企业空间 ID

### 6.2 添加厂商后自动同步模型

流程建议：
1. 创建 `ai_model_provider`
2. 后端根据 `base_url + auth_config` 调用厂商模型列表接口
3. 将返回模型 upsert 到 `ai_model`
4. 初始 `is_enabled = 0`
5. 返回同步结果

### 6.3 启用/禁用规则

- 只有启用模型可被调用。
- 如果某模型已被设置为默认模型，则禁用前应：
  - 要么拒绝禁用，并提示“该模型已被设为默认，请先取消默认”；
  - 要么自动清空对应默认项。

**建议采用第一种：拒绝禁用**，行为更明确。

### 6.4 删除厂商规则

删除 `provider` 时：
- 级联删除其下所有 `ai_model`
- 如果这些模型中存在默认模型引用，则先校验并拒绝删除，提示用户先调整默认模型

### 6.5 模型同步规则

再次同步时：
- 新模型：新增记录
- 已存在模型：更新 `raw_payload / capabilities / model_type`
- 已不存在模型：建议标记为不可用并自动禁用，或直接删除

**简单做法建议：自动禁用，不直接删除。**

---

## 7. API 接口定义

> 接口前缀建议：`/api/v1/ai-models`
>
> 所有接口默认基于当前登录企业空间执行，不需要前端传 `enterprise_id`。

### 7.1 通用响应结构

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

---

## 8. 厂商模板接口（右侧“可选模型”）

### 8.1 获取可选厂商模板列表

**GET** `/api/v1/ai-models/provider-templates`

#### 查询参数

| 参数 | 必填 | 说明 |
|---|---|---|
| `model_type` | 否 | 按模型类型过滤，如 `llm`、`embedding` |
| `keyword` | 否 | 按厂商名称搜索 |

#### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "provider_code": "openai",
      "provider_name": "OpenAI",
      "deployment_type": "public",
      "supported_types": ["llm", "embedding", "tts", "moderation"],
      "default_base_url": "https://api.openai.com/v1",
      "auth_fields": [
        {"key": "api_key", "label": "API Key", "type": "password", "required": true}
      ]
    }
  ]
}
```

---

## 9. 已接入厂商管理接口

### 9.1 新增厂商接入配置

**POST** `/api/v1/ai-models/providers`

#### 请求体

```json
{
  "provider_code": "openai",
  "provider_name": "OpenAI",
  "deployment_type": "public",
  "base_url": "https://api.openai.com/v1",
  "auth_type": "bearer",
  "auth_config": {
    "api_key": "sk-xxx"
  },
  "remark": "默认公有云接入",
  "auto_sync_models": true
}
```

#### 处理逻辑

- 创建 `ai_model_provider`
- 如果 `auto_sync_models=true`，立即调用对方接口同步模型列表
- 将返回的模型写入 `ai_model`

#### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "provider_id": 101,
    "provider_name": "OpenAI",
    "sync_status": "success",
    "model_count": 12
  }
}
```

---

### 9.2 查询已接入厂商列表

**GET** `/api/v1/ai-models/providers`

#### 查询参数

| 参数 | 必填 | 说明 |
|---|---|---|
| `keyword` | 否 | 按厂商名称搜索 |
| `deployment_type` | 否 | `public/private` |

#### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "id": 101,
      "provider_code": "openai",
      "provider_name": "OpenAI",
      "deployment_type": "public",
      "base_url": "https://api.openai.com/v1",
      "supported_types": ["llm", "embedding", "tts"],
      "sync_status": "success",
      "last_sync_at": "2026-04-02 15:30:00",
      "model_total": 12,
      "enabled_model_total": 4
    }
  ]
}
```

---

### 9.3 查看单个厂商详情

**GET** `/api/v1/ai-models/providers/{providerId}`

#### 响应说明

返回厂商基本信息、认证字段脱敏值、支持类型、同步状态。

---

### 9.4 更新厂商接入配置

**PUT** `/api/v1/ai-models/providers/{providerId}`

#### 请求体

```json
{
  "base_url": "https://new-api.example.com/v1",
  "auth_type": "bearer",
  "auth_config": {
    "api_key": "sk-new"
  },
  "remark": "更新后的接入地址",
  "auto_sync_models": true
}
```

#### 说明

- 更新地址或认证信息后，建议重新同步模型。
- 更新时如果 `auth_config` 未传，则保留原值。

---

### 9.5 删除厂商接入配置

**DELETE** `/api/v1/ai-models/providers/{providerId}`

#### 业务校验

- 若该厂商下仍有模型被设为默认模型，返回错误。
- 删除成功后，级联删除该厂商下模型记录。

#### 响应示例

```json
{
  "code": 0,
  "message": "deleted",
  "data": true
}
```

---

### 9.6 手动同步厂商模型列表

**POST** `/api/v1/ai-models/providers/{providerId}/sync`

#### 作用

调用厂商 `base_url`，重新拉取模型列表并更新 `ai_model`。

#### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "provider_id": 101,
    "added": 2,
    "updated": 8,
    "disabled": 1,
    "sync_status": "success"
  }
}
```

---

## 10. 模型列表与启用状态接口

### 10.1 查询模型列表

**GET** `/api/v1/ai-models/models`

#### 查询参数

| 参数 | 必填 | 说明 |
|---|---|---|
| `provider_id` | 否 | 按厂商筛选 |
| `model_type` | 否 | 按模型类型筛选 |
| `is_enabled` | 否 | `1/0` |
| `keyword` | 否 | 按模型名搜索 |
| `view` | 否 | `flat/grouped`，默认 `grouped`，方便贴合图片 UI |

#### `view=grouped` 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": [
    {
      "provider_id": 101,
      "provider_name": "OpenAI",
      "deployment_type": "public",
      "supported_types": ["llm", "embedding", "tts"],
      "models": [
        {
          "id": 1001,
          "model_code": "gpt-4o",
          "model_name": "gpt-4o",
          "model_type": "llm",
          "is_enabled": 1,
          "capabilities": ["vision", "function_call"]
        },
        {
          "id": 1002,
          "model_code": "text-embedding-3-large",
          "model_name": "text-embedding-3-large",
          "model_type": "embedding",
          "is_enabled": 0,
          "capabilities": []
        }
      ]
    }
  ]
}
```

---

### 10.2 查询单个模型详情

**GET** `/api/v1/ai-models/models/{modelId}`

#### 返回内容

- 模型基础信息
- 所属厂商
- 是否启用
- 是否是该类型默认模型
- `raw_payload`

---

### 10.3 启用/禁用单个模型

**PATCH** `/api/v1/ai-models/models/{modelId}/enabled`

#### 请求体

```json
{
  "is_enabled": 1
}
```

#### 业务规则

- `1`：启用模型，可用于后续调用和默认模型选择
- `0`：禁用模型，不可被调用
- 若模型已是默认模型，则禁用时返回错误：`该模型已被设为默认，请先修改默认模型`

#### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "id": 1001,
    "is_enabled": 1
  }
}
```

---

## 11. 默认模型接口（左侧“设置默认模型”）

### 11.1 查询当前企业空间默认模型

**GET** `/api/v1/ai-models/defaults`

#### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "llm": {
      "model_id": 1001,
      "model_name": "gpt-4o",
      "provider_name": "OpenAI"
    },
    "embedding": {
      "model_id": 1002,
      "model_name": "text-embedding-3-large",
      "provider_name": "OpenAI"
    },
    "rerank": null,
    "tts": null,
    "asr": null,
    "vlm": null,
    "moderation": null,
    "ocr": null
  }
}
```

---

### 11.2 批量保存默认模型

**PUT** `/api/v1/ai-models/defaults`

#### 请求体

```json
{
  "llm": 1001,
  "embedding": 1002,
  "rerank": 1003,
  "tts": null,
  "asr": null,
  "vlm": null,
  "moderation": null,
  "ocr": null
}
```

#### 业务校验

每个传入的 `model_id` 都必须满足：
- 属于当前企业空间
- `is_enabled = 1`
- `model_type` 与字段名一致

#### 响应示例

```json
{
  "code": 0,
  "message": "saved",
  "data": true
}
```

---

### 11.3 设置单个类型默认模型（更适合局部更新）

**PUT** `/api/v1/ai-models/defaults/{modelType}`

#### 路径参数

- `modelType`：`llm / embedding / rerank / tts / asr / vlm / moderation / ocr`

#### 请求体

```json
{
  "model_id": 1001
}
```

#### 响应示例

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "model_type": "llm",
    "model_id": 1001
  }
}
```

---

## 12. 推荐的页面加载顺序

为了和图片 UI 对齐，前端页面建议按以下顺序加载：

1. 调用 `GET /provider-templates` → 右侧可选厂商列表
2. 调用 `GET /providers` → 中间已添加厂商卡片
3. 调用 `GET /models?view=grouped` → 中间每个厂商下的模型
4. 调用 `GET /defaults` → 左侧默认模型下拉框

这样页面能一次性完成渲染。

---

## 13. 最简调用链路

### 13.1 新增一个厂商

1. 用户在右侧点击厂商卡片
2. 弹出配置框，填写 `base_url` 和认证信息
3. 调用 `POST /providers`
4. 后端自动同步模型写入 `ai_model`
5. 前端刷新 `providers/models/defaults`

### 13.2 启用某个模型

1. 用户在已添加厂商下打开某模型开关
2. 调用 `PATCH /models/{id}/enabled`
3. 模型状态更新成功后，该模型可用于默认模型设置

### 13.3 设置默认模型

1. 用户在左侧下拉框选择某个已启用模型
2. 调用 `PUT /defaults` 或 `PUT /defaults/{modelType}`
3. 后续业务调用模型时，优先读取该企业空间默认模型

---

## 14. 实现建议

### 14.1 鉴权与隔离

- `enterprise_id` 必须从登录态/JWT/Session 中解析
- 不接受前端显式传入 `enterprise_id`

### 14.2 敏感信息处理

- `auth_config` 建议应用层加密后再入库
- 查询厂商详情时，敏感字段只返回脱敏值，例如：
  - `sk-****abcd`
  - `token-****xyz`

### 14.3 调用默认模型

业务服务需要调用模型时，推荐流程：

1. 按 `enterprise_id + model_type` 查询 `ai_model_default`
2. 拿到 `model_id`
3. 关联查询 `ai_model` + `ai_model_provider`
4. 读取 `base_url + auth_config + model_code`
5. 发起模型调用

### 14.4 类型枚举建议

建议统一使用以下枚举值：

```text
llm
embedding
rerank
tts
asr
vlm
moderation
ocr
```

避免同时出现：
- `chat` / `llm`
- `image2text` / `vlm`
- `speech2text` / `asr`

前后端统一一套枚举即可。

---

## 15. 最终结论

这套方案最核心的优点是：

- **简单**：只需要 `厂商配置表 + 模型表 + 默认模型表`
- **够用**：完整覆盖添加厂商、同步模型、类型过滤、模型启停、默认模型设置
- **易扩展**：后续要增加模型能力标签、连通性检测、调用限流，也都能在现有结构上加字段或补接口
- **符合图片 UI**：
  - 右侧：厂商模板列表
  - 中间：已添加厂商及其模型
  - 左侧：按类型设置默认模型

如果后续你需要，我可以继续在这份设计基础上补一版：
1. **MySQL 完整建表 SQL**
2. **Swagger/OpenAPI 3.0 YAML**
3. **前端页面字段定义与交互说明**
4. **Java / Go / Python 任一后端的实体类与接口示例**
