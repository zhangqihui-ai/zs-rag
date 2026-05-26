# Frontend Dockerfile
# Supports both development and production modes

ARG NODE_IMAGE=node:20-alpine
ARG NGINX_IMAGE=nginx:alpine

# Development stage
FROM ${NODE_IMAGE} as development

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies（与 lockfile 一致，避免漏装 pdfjs-dist 等）
RUN npm ci

# Copy source code
COPY . .

# Expose port
EXPOSE 5173

# Command for development with hot reload
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]


# Build stage
FROM ${NODE_IMAGE} as builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# 构建时注入 API 地址（离线 prod 部署在 push 脚本里按目标机 IP 传入）
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Build for production
RUN npm run build


# Production stage
FROM ${NGINX_IMAGE} as production

# Copy custom nginx config
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1

# Nginx runs in foreground by default
CMD ["nginx", "-g", "daemon off;"]
