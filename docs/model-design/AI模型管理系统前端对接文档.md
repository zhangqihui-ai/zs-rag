# AI模型管理系统前端对接文档

> 本文档面向前端开发，基于以下两份设计产出整理：
>
> - `AI模型管理系统OpenAPI.yaml`
> - `AI模型管理系统设计3.md`
>
> 目标：让前端能快速完成页面联调、接口封装、状态管理与异常处理。

---

## 1. 文档使用说明

前端开发时建议这样配合使用：

- **主文档**：`AI模型管理系统前端对接文档.md`
  - 用于理解页面该怎么调接口、字段怎么展示、交互怎么处理。
- **接口契约**：`AI模型管理系统OpenAPI.yaml`
  - 用于看精确路径、方法、请求参数、响应结构。
- **后端/数据库设计说明**：`AI模型管理系统设计3.md`
  - 用于理解业务背景和数据结构来源。

如果只是前端联调，优先看本文件和 `OpenAPI.yaml` 即可。

---

## 2. 业务范围

本系统只处理**当前企业空间下**的 AI 模型管理，企业空间之间完全隔离。

页面大致对应图片中的 3 个区域：

1. **左侧：设置默认模型**
   - 按模型类型设置默认模型
   - 只能从“已启用模型”里选

2. **中间：已添加的模型**
   - 展示当前企业空间已接入的厂商配置
   - 每个厂商下展示已同步回来的模型列表
   - 支持单个模型启用/禁用

3. **右侧：可选模型 / 可选厂商**
   - 展示系统内置支持接入的厂商模板
   - 点击后可填写 URL、认证信息并新增接入

---

## 3. 接口基础信息

### 3.1 Base URL

建议统一前缀：

```text
/api/v1/ai-models
```

### 3.2 鉴权方式

采用 `Bearer Token`。

请求头示例：

```http
Authorization: Bearer <token>
```

### 3.3 企业空间隔离约定

- 前端**不要传** `enterprise_id`
- 后端从登录态中解析当前企业空间
- 前端只需要确保带上登录凭证

### 3.4 通用响应结构

```json
{
  "code": 0,
  "message": "ok",
  "data": {}
}
```

字段说明：

| 字段 | 说明 |
|---|---|
| `code` | 业务状态码，`0` 表示成功 |
| `message` | 提示信息 |
| `data` | 实际响应数据 |

前端建议：

- `code === 0` 视为成功
- 其他情况统一走错误提示逻辑

---

## 4. 页面与接口映射

---

### 4.1 右侧：可选厂商列表

#### 接口

- `GET /provider-templates`

#### 作用

获取系统内置厂商模板，用于展示右侧厂商卡片，例如：

- OpenAI
- Anthropic
- Gemini
- DeepSeek
- Qwen
- 自定义私有模型服务

#### 前端展示建议

每个厂商卡片展示：

- `provider_name`
- `supported_types`
- `deployment_type`
- 可选厂商 Logo/图标（前端本地维护映射即可）

#### 点击卡片后的行为

打开“新增厂商接入”弹窗，根据 `auth_fields` 动态渲染表单。

---

### 4.2 中间：已添加厂商 + 模型列表

#### 接口

- `GET /providers`
- `GET /models?view=grouped`
- `PATCH /models/{modelId}/enabled`
- `POST /providers/{providerId}/sync`
- `DELETE /providers/{providerId}`
- `PUT /providers/{providerId}`

#### 作用

用于展示当前企业空间已接入的厂商配置及其模型列表。

#### 页面结构建议

一个厂商卡片包含：

- 厂商名称
- 部署类型
- 支持模型类型标签
- 同步状态
- 操作按钮：编辑 / 同步 / 删除
- 下方展开模型列表

模型列表每一行展示：

- `model_name`
- `model_type`
- `capabilities`
- `is_enabled` 开关

---

### 4.3 左侧：默认模型设置

#### 接口

- `GET /defaults`
- `PUT /defaults`
- `PUT /defaults/{modelType}`
- 辅助查询：`GET /models?is_enabled=true&view=flat`

#### 作用

用于展示并设置每个模型类型的默认模型。

#### 页面结构建议

左侧表单可固定展示以下类型：

- LLM
- Embedding
- VLM
- ASR
- Rerank
- TTS
- Moderation
- OCR

每一项下拉框的数据来源应为：

- 当前企业空间下
- `is_enabled = true`
- `model_type = 当前类型`

---

## 5. 页面初始化调用顺序

建议前端页面初始化按以下顺序调用：

### 5.1 首页初始加载

1. `GET /provider-templates`
2. `GET /providers`
3. `GET /models?view=grouped`
4. `GET /defaults`

这样可以一次性渲染：

- 右侧可选厂商
- 中间已添加厂商及模型
- 左侧默认模型

### 5.2 如果默认模型下拉框需要独立数据源

可以额外调用：

- `GET /models?view=flat&is_enabled=true`

然后前端按 `model_type` 分组，构建各下拉框选项。

---

## 6. 推荐的前端接口封装

建议按模块拆分：

### 6.1 `providerApi`

- `getProviderTemplates(params)`
- `getProviders(params)`
- `createProvider(data)`
- `getProviderDetail(id)`
- `updateProvider(id, data)`
- `deleteProvider(id)`
- `syncProviderModels(id)`

### 6.2 `modelApi`

- `getModels(params)`
- `getModelDetail(id)`
- `toggleModelEnabled(id, data)`

### 6.3 `defaultModelApi`

- `getDefaults()`
- `saveDefaults(data)`
- `saveSingleDefault(modelType, data)`

---

## 7. 关键枚举说明

### 7.1 `model_type`

后端统一使用以下枚举值：

| 值 | 前端显示建议 |
|---|---|
| `llm` | LLM |
| `embedding` | Embedding |
| `rerank` | Rerank |
| `tts` | TTS |
| `asr` | ASR |
| `vlm` | VLM |
| `moderation` | Moderation |
| `ocr` | OCR |

前端建议维护一个映射：

```ts
const MODEL_TYPE_LABEL_MAP = {
  llm: 'LLM',
  embedding: 'Embedding',
  rerank: 'Rerank',
  tts: 'TTS',
  asr: 'ASR',
  vlm: 'VLM',
  moderation: 'Moderation',
  ocr: 'OCR',
}
```

### 7.2 `deployment_type`

| 值 | 含义 |
|---|---|
| `public` | 公有云 |
| `private` | 私有化部署 |

### 7.3 `auth_type`

| 值 | 含义 |
|---|---|
| `api_key` | 通过 API Key 认证 |
| `bearer` | Bearer Token |
| `basic` | Basic Auth |
| `custom` | 自定义认证方式 |

### 7.4 `sync_status`

| 值 | 含义 | 前端展示建议 |
|---|---|---|
| `pending` | 待同步 | 灰色 |
| `success` | 同步成功 | 绿色 |
| `failed` | 同步失败 | 红色 |

---

## 8. 主要接口说明

---

### 8.1 获取可选厂商模板

**GET** `/api/v1/ai-models/provider-templates`

#### 常用场景

- 页面右侧厂商卡片加载
- 按 `model_type` 过滤厂商
- 搜索厂商

#### 常用查询参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `model_type` | string | 否 | 按模型类型过滤 |
| `keyword` | string | 否 | 厂商名称关键字 |

#### 响应字段重点

| 字段 | 用途 |
|---|---|
| `provider_code` | 前端图标映射、逻辑识别 |
| `provider_name` | 卡片标题 |
| `deployment_type` | 标签展示 |
| `supported_types` | 类型标签展示 |
| `default_base_url` | 新增弹窗默认填充值 |
| `auth_fields` | 动态渲染认证表单 |

---

### 8.2 新增厂商接入

**POST** `/api/v1/ai-models/providers`

#### 使用场景

用户点击右侧厂商卡片后，在弹窗中填写接入信息并保存。

#### 请求体示例

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

#### 前端处理建议

创建成功后依次刷新：

1. `GET /providers`
2. `GET /models?view=grouped`
3. `GET /defaults`

如果后端返回了 `model_count`，也可以直接提示：

- “新增成功，已同步 12 个模型”

---

### 8.3 获取已接入厂商列表

**GET** `/api/v1/ai-models/providers`

#### 用途

渲染中间区域厂商卡片头部信息。

#### 前端展示字段

| 字段 | 展示位置 |
|---|---|
| `provider_name` | 卡片标题 |
| `deployment_type` | 部署类型标签 |
| `supported_types` | 类型标签 |
| `sync_status` | 同步状态展示 |
| `last_sync_at` | 最近同步时间 |
| `model_total` | 总模型数 |
| `enabled_model_total` | 已启用模型数 |

---

### 8.4 查询模型列表

**GET** `/api/v1/ai-models/models`

#### 推荐用法 1：中间区域按厂商分组展示

```text
GET /models?view=grouped
```

#### 推荐用法 2：默认模型下拉数据源

```text
GET /models?view=flat&is_enabled=true
```

#### 常用查询参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `provider_id` | number | 否 | 按厂商筛选 |
| `model_type` | string | 否 | 按模型类型筛选 |
| `is_enabled` | boolean | 否 | 按启用状态筛选 |
| `keyword` | string | 否 | 模型名称关键字 |
| `view` | string | 否 | `grouped` 或 `flat` |

#### `grouped` 响应适合的场景

- 厂商卡片下展开模型列表
- 一个厂商下面显示多个模型

#### `flat` 响应适合的场景

- 默认模型下拉框
- 搜索型选择器
- 表格模式的后台页

---

### 8.5 启用 / 禁用模型

**PATCH** `/api/v1/ai-models/models/{modelId}/enabled`

#### 请求体

```json
{
  "is_enabled": true
}
```

#### 前端交互建议

- 开关切换时可直接调用接口
- 成功后刷新：
  - 当前模型列表
  - 默认模型可选项
- 如果是禁用操作失败，提示：
  - “该模型已被设为默认模型，请先调整默认模型”

#### 建议交互

- 开关切换时做按钮 loading
- 成功后 toast：
  - “已启用”
  - “已禁用”

---

### 8.6 查询默认模型

**GET** `/api/v1/ai-models/defaults`

#### 用途

用于左侧默认模型区域初始化。

#### 响应结构说明

返回一个对象，每个模型类型对应一个默认模型：

```json
{
  "llm": {
    "model_id": 1001,
    "model_name": "gpt-4o",
    "provider_name": "OpenAI"
  },
  "embedding": null,
  "rerank": null
}
```

#### 前端处理建议

- 若值为 `null`，下拉框展示“未设置”
- 若有值，回填对应模型

---

### 8.7 批量保存默认模型

**PUT** `/api/v1/ai-models/defaults`

#### 请求体示例

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

#### 用途

适合左侧整块表单统一保存。

#### 前端交互建议

- 用户修改多个类型后点击“保存”
- 保存成功后刷新 `GET /defaults`

---

### 8.8 设置单个类型默认模型

**PUT** `/api/v1/ai-models/defaults/{modelType}`

#### 请求体示例

```json
{
  "model_id": 1001
}
```

#### 用途

适合用户每改一个下拉框就立即保存。

#### 两种实现方式建议

1. **整表单保存模式**
   - 统一使用 `PUT /defaults`
   - 更适合带“保存”按钮的页面

2. **即时保存模式**
   - 使用 `PUT /defaults/{modelType}`
   - 更适合改完即生效的页面

建议优先选一种，不要混用。

---

## 9. 前端字段使用建议

---

### 9.1 厂商卡片字段

建议使用：

| 字段 | 说明 |
|---|---|
| `provider_name` | 卡片标题 |
| `provider_code` | 图标映射 key |
| `deployment_type` | 展示“公有云/私有化”标签 |
| `supported_types` | 展示模型类型标签 |
| `sync_status` | 展示同步状态 |
| `model_total` | 展示模型总数 |
| `enabled_model_total` | 展示已启用数 |
| `last_sync_at` | 展示最近同步时间 |

---

### 9.2 模型列表字段

建议使用：

| 字段 | 说明 |
|---|---|
| `id` | 操作开关 / 默认设置时的主键值 |
| `model_name` | 列表主展示名称 |
| `model_code` | 次要展示信息，可选 |
| `model_type` | 类型标签 |
| `is_enabled` | 开关状态 |
| `capabilities` | 能力标签 |
| `context_window` | 可选展示 |
| `max_output_tokens` | 可选展示 |

---

### 9.3 默认模型下拉框字段

下拉框建议：

- `label = model_name + ' / ' + provider_name`
- `value = id`

示例：

```ts
{
  label: 'gpt-4o / OpenAI',
  value: 1001
}
```

---

## 10. 认证字段动态表单建议

右侧厂商模板接口会返回 `auth_fields`，前端可以动态渲染新增厂商表单。

### 10.1 示例

```json
[
  {
    "key": "api_key",
    "label": "API Key",
    "type": "password",
    "required": true
  },
  {
    "key": "organization",
    "label": "Organization",
    "type": "text",
    "required": false
  }
]
```

### 10.2 前端处理方式

- `key` → 表单字段名
- `label` → 表单标签
- `type` → 输入框类型
- `required` → 是否必填

生成提交对象时，组装到：

```json
{
  "auth_config": {
    "api_key": "xxx",
    "organization": "org_123"
  }
}
```

---

## 11. 推荐的前端状态结构

可按以下结构维护页面状态：

```ts
interface ModelManagePageState {
  providerTemplates: ProviderTemplate[]
  providers: ProviderSummary[]
  groupedModels: ProviderModelsGroup[]
  defaults: DefaultsData
  enabledModelOptionsMap: Record<string, Array<{ label: string; value: number }>>
  loading: boolean
}
```

### 11.1 `enabledModelOptionsMap` 结构建议

```ts
{
  llm: [{ label: 'gpt-4o / OpenAI', value: 1001 }],
  embedding: [{ label: 'text-embedding-3-large / OpenAI', value: 1002 }],
  rerank: []
}
```

这样左侧每种类型的下拉框可以直接读取对应数组。

---

## 12. 推荐的前端交互流程

---

### 12.1 新增厂商

1. 用户点击右侧厂商卡片
2. 打开弹窗
3. 根据 `auth_fields` 渲染认证字段
4. 提交 `POST /providers`
5. 成功后刷新：
   - `providers`
   - `models(grouped)`
   - `defaults`

---

### 12.2 手动同步模型

1. 用户点击厂商卡片上的“同步模型”按钮
2. 调用 `POST /providers/{providerId}/sync`
3. 成功后刷新：
   - `providers`
   - `models(grouped)`
   - `defaults`

---

### 12.3 启用模型

1. 用户切换模型开关为开
2. 调用 `PATCH /models/{modelId}/enabled`
3. 成功后刷新：
   - 当前模型列表
   - 默认模型候选列表

---

### 12.4 禁用模型

1. 用户切换模型开关为关
2. 调用 `PATCH /models/{modelId}/enabled`
3. 若失败且提示“已被设为默认模型”
4. 前端提示用户先修改默认模型

---

### 12.5 设置默认模型

1. 用户在左侧选择某类型默认模型
2. 调用：
   - `PUT /defaults/{modelType}`，或
   - `PUT /defaults`
3. 成功后刷新 `GET /defaults`

---

## 13. 错误处理约定

前端至少要重点处理以下场景：

### 13.1 模型已是默认模型，不能禁用

后端可能返回：

- `409 Conflict`
- `message = 该模型已被设为默认模型，请先调整默认模型后再禁用`

前端建议提示：

```text
当前模型已被设为默认模型，请先修改默认模型后再禁用。
```

### 13.2 删除厂商时，该厂商下有默认模型引用

后端可能返回：

- `409 Conflict`
- `message = 该厂商下有模型已被设为默认模型，无法删除`

前端建议提示：

```text
该厂商下仍有模型被设为默认模型，请先修改默认模型。
```

### 13.3 同步失败

后端可能返回：

- `sync_status = failed`
- `last_sync_error` 包含失败原因

前端建议：

- 卡片顶部显示红色失败状态
- 支持 hover 或展开查看错误信息

### 13.4 参数错误 / 认证失败

后端可能返回：

- `400` 参数错误
- `401` 登录失效
- `409` 业务冲突

前端建议统一错误处理：

| 状态 | 建议处理 |
|---|---|
| `400` | toast 提示 message |
| `401` | 跳登录或刷新登录态 |
| `404` | 提示资源不存在并刷新列表 |
| `409` | 业务提示，保留用户当前页状态 |
| `500` | 统一异常提示 |

---

## 14. 前端展示建议

### 14.1 厂商标签颜色建议

- `public`：蓝色标签，显示“公有云”
- `private`：紫色/灰色标签，显示“私有化”

### 14.2 模型类型标签建议

使用浅灰/浅蓝标签展示，例如：

- `LLM`
- `Embedding`
- `Rerank`
- `TTS`
- `ASR`
- `VLM`
- `Moderation`
- `OCR`

### 14.3 同步状态展示建议

- `pending`：待同步
- `success`：同步成功
- `failed`：同步失败

### 14.4 默认模型未设置展示

下拉框 placeholder 建议：

```text
请选择模型
```

或：

```text
未设置默认模型
```

---

## 15. 推荐的请求封装示例（字段层面）

> 这里只给字段建议，不绑定具体框架。

### 15.1 新增厂商请求体字段

```ts
interface CreateProviderPayload {
  provider_code: string
  provider_name: string
  deployment_type: 'public' | 'private'
  base_url: string
  auth_type: 'api_key' | 'bearer' | 'basic' | 'custom'
  auth_config: Record<string, any>
  remark?: string
  auto_sync_models?: boolean
}
```

### 15.2 模型开关请求体字段

```ts
interface ToggleModelEnabledPayload {
  is_enabled: boolean
}
```

### 15.3 默认模型保存字段

```ts
interface BatchDefaultsPayload {
  llm?: number | null
  embedding?: number | null
  rerank?: number | null
  tts?: number | null
  asr?: number | null
  vlm?: number | null
  moderation?: number | null
  ocr?: number | null
}
```

---

## 16. 最小联调清单

前端至少完成以下接口联调即可支持基础页面：

### 16.1 右侧可选厂商

- [ ] `GET /provider-templates`

### 16.2 中间已添加厂商与模型

- [ ] `GET /providers`
- [ ] `GET /models?view=grouped`
- [ ] `PATCH /models/{modelId}/enabled`
- [ ] `POST /providers/{providerId}/sync`
- [ ] `POST /providers`
- [ ] `PUT /providers/{providerId}`
- [ ] `DELETE /providers/{providerId}`

### 16.3 左侧默认模型

- [ ] `GET /defaults`
- [ ] `PUT /defaults` 或 `PUT /defaults/{modelType}`
- [ ] `GET /models?view=flat&is_enabled=true`

---

## 17. 推荐联调顺序

建议前端按这个顺序开发：

1. 先完成右侧厂商模板展示
2. 再完成中间已添加厂商 + 模型分组列表
3. 再接入模型启用/禁用
4. 最后接入左侧默认模型设置

原因：

- 默认模型依赖“已启用模型”
- 已启用模型又依赖厂商接入和模型同步

也就是：

```text
厂商模板 -> 新增厂商 -> 同步模型 -> 启用模型 -> 设置默认模型
```

---

## 18. 结论

对于前端来说，最重要的是两个文件：

1. `AI模型管理系统前端对接文档.md`
2. `AI模型管理系统OpenAPI.yaml`

其中：

- 本文档负责讲“页面怎么接、字段怎么用、交互怎么走”
- `OpenAPI.yaml` 负责讲“接口精确定义是什么”

二者一起使用，基本就可以直接进入开发和联调。
