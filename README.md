# ZS-RAG 企业级 RAG 知识库管理平台

基于 OpenSpec 规格驱动开发的企业级 RAG（Retrieval-Augmented Generation）知识库管理平台 V0 版本。

## 功能特性

### V0 范围

1. **企业空间管理** - 多租户隔离，默认创建 `default` 企业空间
2. **模型管理** - 支持主流公有云/厂商模型服务（OpenAI 兼容、百炼、DeepSeek、智谱、Kimi）
3. **知识库管理** - 支持向量数据库（Milvus）和图数据库（Neo4j）

### 核心功能

- ✅ 多租户隔离（企业空间）
- ✅ JWT 认证
- ✅ 启动初始化（管理员账号 + default 企业空间）
- ✅ Provider 配置管理
- ✅ 知识库 CRUD
- ✅ Milvus/Neo4j 连接管理
- ✅ 统一错误模型

## 技术栈

**后端:**
- Python 3.12+
- FastAPI
- SQLAlchemy
- Pydantic
- PostgreSQL
- Alembic (数据库迁移)

**前端:**
- Vue 3 + Vite
- TypeScript
- Pinia (状态管理)
- Vue Router
- Axios

**基础设施:**
- PostgreSQL (业务数据)
- Milvus (向量数据库)
- Neo4j (图数据库)
- Docker Compose (开发环境编排)

## 快速开始

### 方式一：Docker Compose（推荐）

#### 开发环境

```bash
# 1. 复制环境变量文件
cp .env.template .env

# 2. 启动所有服务（包括前后端、数据库）
docker compose up -d

# 3. 运行数据库迁移
docker compose exec backend python -m alembic upgrade head

# 4. 查看日志
docker compose logs -f backend
docker compose logs -f frontend
```

#### 生产环境

```bash
# 1. 复制并修改环境变量（务必修改密码和密钥）
cp .env.template .env
# 编辑 .env 文件，设置生产环境的密码和密钥

# 2. 构建并启动生产环境
docker compose -f docker-compose.prod.yml up -d --build
```

#### 停启全部服务

`celery-worker`、`mineru-cpu`、`opendataloader-hybrid` 等可选组件使用了 Compose **profile**。直接执行 `docker compose stop` 只会停止默认服务（约 9 个容器），profile 服务仍会保持运行。

先定义与当前部署一致的 compose 命令（可按实际启用的 override 文件增减）：

```bash
# 开发环境（含 MinerU offline + ODL Hybrid，与常见全量部署一致）
COMPOSE="docker compose \
  -f docker-compose.yml \
  -f docker-compose.mineru-offline.yml \
  -f docker-compose.odl-hybrid.yml"

# 启用的可选 profile（按需增减；未启用 MinerU / Hybrid / Celery 时去掉对应项）
PROFILES="--profile celery --profile mineru --profile odl-hybrid"
```

**停止全部服务**（保留容器，可用 `start` 快速恢复）：

```bash
$COMPOSE $PROFILES stop
```

**停止并移除全部容器**：

```bash
$COMPOSE $PROFILES down
```

**启动全部服务**：

```bash
$COMPOSE $PROFILES up -d
```

**仅启动核心服务**（不含 Celery / MinerU / Hybrid）：

```bash
docker compose up -d
```

**确认是否已全部停止**：

```bash
docker compose ps -a
# 或
docker ps --filter "name=zs-rag-"
```

若仍有残留容器，可强制停止：

```bash
docker stop $(docker ps -q --filter "name=zs-rag-") 2>/dev/null || true
```

生产环境（含 registry 覆盖时，按 `.env` 中实际启用的 profile 调整）：

```bash
COMPOSE_PROD="docker compose \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.registry.yml"
PROFILES_PROD="--profile celery --profile mineru --profile odl-hybrid"

# 停止
$COMPOSE_PROD $PROFILES_PROD stop

# 启动
$COMPOSE_PROD $PROFILES_PROD up -d --no-build
```

#### 访问服务

- **前端**: http://localhost:80
- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/docs
- **Neo4j Browser**: http://localhost:7474
- **MinIO Console**: http://localhost:9001

#### 默认账号

- 用户名：`admin`
- 密码：`ChangeMe123!`

### 方式二：本地开发

#### 1. 启动基础设施

```bash
# 只启动数据库和中间件
docker compose up -d postgres milvus neo4j etcd minio
```

#### 2. 初始化后端

```bash
# 安装依赖
cd backend
pip install -r requirements.txt

# 运行数据库迁移
python -m alembic upgrade head

# 启动后端服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 3. 启动前端

```bash
# 安装依赖
cd web
npm install

# 启动开发服务器
npm run dev
```

## 项目结构

```
zs-rag/
├── backend/              # 后端工程
│   ├── app/
│   │   ├── api/         # API 路由
│   │   ├── core/        # 核心配置和工具
│   │   ├── db/          # 数据库配置
│   │   ├── models/      # SQLAlchemy 模型
│   │   └── schemas/     # Pydantic 模式
│   ├── alembic/         # 数据库迁移
│   ├── Dockerfile       # 后端 Docker 镜像
│   └── requirements.txt
├── web/                 # 前端工程
│   ├── src/
│   │   ├── components/  # Vue 组件
│   │   ├── stores/      # Pinia stores
│   │   ├── views/       # 页面视图
│   │   └── router/      # 路由配置
│   ├── Dockerfile       # 前端 Docker 镜像
│   ├── nginx.conf       # Nginx 配置（生产环境）
│   └── package.json
├── docker/              # Docker 配置
├── docker-compose.yml   # 开发环境编排
├── docker-compose.prod.yml  # 生产环境编排
├── Makefile            # 快捷命令
├── .env.template       # 环境变量模板
└── openspec/           # OpenSpec 规格文档
```

## 快捷命令

```bash
# 启动开发环境
make up

# 启动生产环境
make up-prod

# 停止服务
make down

# 查看日志
make logs service=backend

# 运行数据库迁移
make migrate

# 创建新迁移
make migration name="add_user_table"

# 构建镜像
make build        # 开发环境
make build-prod   # 生产环境

# 清理所有容器和卷
make clean
```

## API 端点

### 认证
- `POST /auth/login` - 用户登录

### 企业空间
- `GET /enterprise-spaces` - 列出企业空间
- `POST /enterprise-spaces` - 创建企业空间
- `GET /enterprise-spaces/{id}` - 获取详情
- `PATCH /enterprise-spaces/{id}` - 更新
- `DELETE /enterprise-spaces/{id}` - 删除

### 模型管理
- `GET /providers` - 列出 Provider
- `POST /providers` - 创建 Provider
- `GET /providers/{id}` - 获取详情
- `PATCH /providers/{id}` - 更新
- `DELETE /providers/{id}` - 删除
- `POST /providers/test` - 测试连接

### 知识库管理
- `GET /knowledge-bases` - 列出知识库
- `POST /knowledge-bases` - 创建知识库
- `GET /knowledge-bases/{id}` - 获取详情
- `PATCH /knowledge-bases/{id}` - 更新
- `DELETE /knowledge-bases/{id}` - 删除
- `POST /knowledge-bases/{id}/milvus-config` - 创建 Milvus 配置
- `GET /knowledge-bases/{id}/milvus-config` - 获取 Milvus 配置
- `PATCH /knowledge-bases/{id}/milvus-config` - 更新 Milvus 配置
- `DELETE /knowledge-bases/{id}/milvus-config` - 删除 Milvus 配置
- `POST /knowledge-bases/{id}/neo4j-connection` - 配置 Neo4j
- `POST /knowledge-bases/{id}/milvus-config/test` - 测试 Milvus
- `POST /knowledge-bases/{id}/neo4j-connection/test` - 测试 Neo4j

## 快捷命令

```bash
# 启动所有服务
make up

# 停止所有服务
make down

# 启动后端开发服务器
make backend-dev

# 启动前端开发服务器
make web-dev

# 查看日志
make logs
```

## 环境变量

复制 `.env.template` 到 `.env` 并修改配置：

```bash
cp .env.template .env
```

主要配置项：
- `DATABASE_URL` - PostgreSQL 连接字符串
- `JWT_SECRET` - JWT 密钥（生产环境务必修改）
- `ADMIN_USERNAME` - 管理员用户名
- `ADMIN_PASSWORD` - 管理员密码

### PDF 解析引擎

| 引擎 | 用途 | 依赖 |
|------|------|------|
| **OpenDataLoader**（默认） | 数字版 PDF，本地 CPU，无 HTTP | backend 镜像内 JRE 11+、`opendataloader-pdf` |
| **MinerU** | 图片 OCR、兼容模式 | `docker compose --profile mineru up -d mineru` |
| **Hybrid** | 扫描 PDF / 复杂表格 | `docker compose --profile odl-hybrid up -d opendataloader-hybrid` |

知识库「配置 → PDF 解析器」可 per-KB 选择；图片上传仍走 MinerU。

## 开发说明

### Docker 开发模式

开发环境下，前后端服务都会挂载源代码到容器中，实现热加载：

- **后端**: 使用 `uvicorn --reload` 监听代码变化
- **前端**: 使用 Vite 的热模块替换（HMR）

修改代码后服务会自动重新加载，无需重启容器。

### 数据库迁移

```bash
# 创建新迁移
make migration name="描述"

# 应用迁移
make migrate

# 或者手动执行
docker compose exec backend python -m alembic upgrade head
```

### 多租户隔离

所有 API 请求通过 `X-Enterprise-Space` 请求头传递企业空间标识，默认为 `default`。服务端在认证后解析并注入请求上下文，所有查询/写入都会按企业空间过滤。

### 认证流程

1. 用户登录获取 JWT Token
2. Token 存储在 localStorage
3. 后续请求自动添加 `Authorization: Bearer {token}` 头
4. Token 过期自动跳转到登录页

### 生产环境部署

生产环境使用多阶段构建优化镜像大小：

- **后端**: 使用非 root 用户运行，包含健康检查
- **前端**: 使用 Nginx 提供静态文件服务

```bash
# 构建并启动生产环境
docker compose -f docker-compose.prod.yml up -d --build
##离线构建
offline / 离线 Docker 构建说明
================================

conda create -n zs-rag python=3.12 -y
conda activate zs-rag
cd backend
./scripts/download_offline_wheels.sh
# 从仓库根目录离线构建（注意最后的 context 是 backend）：
docker build -f backend/Dockerfile.local --target development -t zs-rag-backend:dev backend
# 或使用 compose（context 已指向 ./backend）：
BACKEND_DOCKERFILE=Dockerfile.local docker compose up -d --build backend


# 查看日志
docker compose -f docker-compose.prod.yml logs -f
```


## 设计文档

- [RAGFlow 与 zs-rag 知识库构建对比与优化计划](docs/kb-design/RAGFlow与zs-rag知识库构建对比与优化计划.md)

## License

Internal Use Only
