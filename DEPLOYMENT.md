# ZS-RAG 部署说明

## 服务器部署配置

### 1. 修改服务器 IP

编辑 `.env` 文件，将所有 `localhost` 替换为你的服务器 IP 地址：

```bash
# 编辑环境变量文件
vi .env

# 修改以下内容：
VITE_API_BASE_URL=http://192.168.11.19:8000
CORS_ORIGINS=http://192.168.11.19,http://192.168.11.19:80,http://192.168.11.19:5173
```

### 2. 启动服务

```bash
# 启动所有服务
docker compose up -d

# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f
```

### 3. 访问地址

- **前端界面**: http://192.168.11.19:80
- **后端 API**: http://192.168.11.19:8000
- **API 文档**: http://192.168.11.19:8000/docs

### 4. 默认账号

- 用户名：`admin`
- 密码：`ChangeMe123!`

**⚠️ 重要：首次登录后请立即修改密码！**

## 防火墙配置

如果启用了防火墙，需要开放以下端口：

```bash
# 开放端口
sudo ufw allow 80/tcp      # 前端
sudo ufw allow 8000/tcp    # 后端 API
sudo ufw allow 5432/tcp    # PostgreSQL (可选)
sudo ufw allow 19530/tcp   # Milvus (可选)
sudo ufw allow 7474/tcp    # Neo4j Browser (可选)
```

## 常见问题排查

### Network Error

如果前端登录时报 "Network Error"：

1. 检查 `.env` 文件中的 `VITE_API_BASE_URL` 是否正确
2. 确保 CORS_ORIGINS 包含你的服务器 IP
3. 重启前端服务：`docker compose restart frontend`
4. 清除浏览器缓存后重试

### 服务无法访问

1. 检查服务状态：`docker compose ps`
2. 查看服务日志：`docker compose logs backend frontend`
3. 检查防火墙设置
4. 确认端口未被占用：`netstat -tlnp | grep :80`

### 后端启动失败

```bash
# 查看后端日志
docker compose logs backend

# 重启后端
docker compose restart backend

# 重新创建后端容器
docker compose up -d --force-recreate backend
```

### 前端页面空白

1. 打开浏览器开发者工具 (F12)
2. 查看 Console 中的错误信息
3. 检查 Network 标签中的 API 请求是否成功
4. 确认 `VITE_API_BASE_URL` 配置正确

## 生产环境部署

生产环境请使用专用配置文件：

```bash
# 使用生产配置启动
docker compose -f docker-compose.prod.yml up -d --build
```

生产环境必须修改以下环境变量：

```bash
# 安全密钥（务必修改！）
JWT_SECRET=your-super-secret-key-change-in-production

# 管理员密码（务必修改！）
ADMIN_PASSWORD=your-secure-password

# 数据库密码（务必修改！）
POSTGRES_PASSWORD=your-secure-postgres-password
NEO4J_PASSWORD=your-secure-neo4j-password
```

## 备份与恢复

### 数据备份

```bash
# 备份所有数据卷
docker compose down
tar -czvf zs-rag-backup.tar.gz /var/lib/docker/volumes/
```

### 数据恢复

```bash
# 恢复数据卷
tar -xzvf zs-rag-backup.tar.gz -C /var/lib/docker/volumes/
docker compose up -d
```

## 更新升级

```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker compose up -d --build

# 运行数据库迁移
docker compose exec backend python -m alembic upgrade head
```
