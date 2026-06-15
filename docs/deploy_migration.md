# 开发到生产迁移说明

本文用于 `clinical-data-system` 从开发环境迁移到生产环境时使用。文档分两部分：

- 第一部分给 Codex：说明迁移时应该做什么、不能做什么。
- 第二部分给用户：提供可以照着执行的命令。

本迁移文档只覆盖应用程序发布，即 backend/frontend 程序和镜像。生产环境 OCR GPU 模式已经冻结，不在本流程中重建、不替换、不重启。

## 1. 固定端口口径

### 1.1 开发环境端口

| 服务 | 地址/端口 | 说明 |
| --- | --- | --- |
| 前端开发服务 | `http://127.0.0.1:5173` | Vite dev server |
| 后端开发服务 | `http://127.0.0.1:8000` | FastAPI |
| Mac 本地 OCR | `http://127.0.0.1:8048` | Apple Vision OCR，仅开发调试 |
| PostgreSQL 开发库 | `127.0.0.1:5432` | Docker PostgreSQL |

开发环境允许使用 Mac Apple Vision OCR，但它不能迁移成生产 OCR 方案。

### 1.2 生产环境端口

| 服务 | 生产端口 | Compose 口径 | 说明 |
| --- | --- | --- | --- |
| 前端生产入口 | `http://<服务器IP>:18080` | `18080:80` | 用户访问入口 |
| 后端生产 API | `127.0.0.1:8000` | `127.0.0.1:8000:8000` | 只给本机/Nginx/前端代理使用 |
| 生产 OCR API | `127.0.0.1:8048` | `127.0.0.1:8048:8000` | PaddleOCR GPU，已冻结 |
| PostgreSQL | `127.0.0.1:5432` | `127.0.0.1:5432:5432` | 只给本机容器/维护使用 |

生产后端容器内访问 OCR 的地址固定为：

```text
PDF_PACKET_OCR_API_URL=http://paddle-ocr-api:8000
```

不要在生产命令中把 OCR 改成 Mac 的 `127.0.0.1:8048`。

## 2. 给 Codex 的迁移规则

### 2.1 Codex 要做的事情

每次从开发环境准备生产迁移时，Codex 负责：

1. 检查当前分支、未提交改动和目标版本说明。
2. 明确本次版本号，格式建议为 `YYYYMMDD-版本-范围`，例如 `20260609-v355-colon-upload-field-normalize`。
3. 运行必要验证：
   - 后端测试和 ruff。
   - 前端 build。
   - 如涉及资料包识别，补跑 `tests/test_pdf_packets.py`。
4. 只构建 backend/frontend 的 linux/amd64 镜像。
5. 打包 backend/frontend 镜像为离线包。
6. 生成 `SHA256SUMS`。
7. 提供生产替换命令。
8. 说明本次是否涉及数据库 migration。
9. 说明本次是否需要备份文件存储。
10. 明确提醒用户：本次不触碰生产 OCR GPU 服务。

### 2.2 Codex 不能做的事情

除非用户明确要求 OCR 生产基线升级，否则 Codex 不得执行：

```bash
scripts/package_linux_gpu_offline_bundle.sh
```

不得修改或替换：

- `deploy/linux/docker-compose.prod.gpu.yml`
- `PADDLE_OCR_IMAGE`
- `paddle-ocr-api-gpu:latest`
- `/data/jiafei/runtime/paddle-ocr`
- 生产 OCR 模型缓存
- 生产 OCR GPU 容器运行模式

不得在生产环境执行会连带重建 OCR 的命令，例如：

```bash
docker compose up -d
docker compose build
docker compose up -d --build
```

生产应用替换只能面向：

```text
backend frontend
```

并且必须使用：

```text
--no-build --no-deps
```

### 2.3 Codex 打包产物要求

应用发布包至少包含：

```text
clinical-data-app-images-<RELEASE_VERSION>.tar.gz
SHA256SUMS-<RELEASE_VERSION>.txt
docker-compose.app-release.yml
```

其中：

- `clinical-data-app-images-*.tar.gz` 只包含 backend/frontend 镜像。
- `docker-compose.app-release.yml` 只覆盖 backend/frontend 镜像，OCR 保持现有 GPU 镜像。
- `SHA256SUMS` 用于生产服务器校验包完整性。

## 3. 给 Codex 的开发机打包命令

以下命令在开发机项目根目录执行。

设置版本号：

```bash
export RELEASE_VERSION=20260609-v355-colon-upload-field-normalize
export RELEASE_DIR=backups/migration/app-release-${RELEASE_VERSION}
mkdir -p "${RELEASE_DIR}"
```

运行验证：

```bash
cd backend
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
cd ../frontend
npm run build
cd ..
```

构建 linux/amd64 应用镜像：

```bash
docker buildx build --platform linux/amd64 --provenance=false --load -t clinical-backend:${RELEASE_VERSION} backend
docker buildx build --platform linux/amd64 --provenance=false --load -t clinical-frontend:${RELEASE_VERSION} frontend
```

打包应用镜像：

```bash
docker save clinical-backend:${RELEASE_VERSION} clinical-frontend:${RELEASE_VERSION} -o "${RELEASE_DIR}/clinical-data-app-images-${RELEASE_VERSION}.tar"
gzip -9 "${RELEASE_DIR}/clinical-data-app-images-${RELEASE_VERSION}.tar"
cp deploy/linux/docker-compose.app-release.yml "${RELEASE_DIR}/docker-compose.app-release.yml"
```

生成校验文件：

```bash
cd "${RELEASE_DIR}"
shasum -a 256 "clinical-data-app-images-${RELEASE_VERSION}.tar.gz" "docker-compose.app-release.yml" > "SHA256SUMS-${RELEASE_VERSION}.txt"
cd -
```

最终交付目录：

```text
backups/migration/app-release-<RELEASE_VERSION>/
```

## 4. 给用户的生产替换命令

以下命令在生产服务器执行。生产项目目录为：

```text
/data/jiafei/clinical-data-system
```

运行前请把开发机生成的发布包上传到生产服务器，例如：

```text
/data/jiafei/clinical-data-system/backups/migration/app-release-<RELEASE_VERSION>/
```

### 4.1 设置版本号

```bash
export RELEASE_VERSION=20260609-v355-colon-upload-field-normalize
export PROJECT_DIR=/data/jiafei/clinical-data-system
export RELEASE_DIR=${PROJECT_DIR}/backups/migration/app-release-${RELEASE_VERSION}
cd ${PROJECT_DIR}
```

### 4.2 校验发布包

```bash
cd ${RELEASE_DIR}
shasum -a 256 -c SHA256SUMS-${RELEASE_VERSION}.txt
cd ${PROJECT_DIR}
```

### 4.3 记录当前镜像，方便回滚

```bash
docker inspect --format='{{.Config.Image}}' clinical-backend
docker inspect --format='{{.Config.Image}}' clinical-frontend
docker inspect --format='{{.Config.Image}}' paddle-ocr-api
```

第三行只用于确认 OCR 当前镜像，不用于替换。

### 4.4 备份数据库和文件存储

```bash
mkdir -p ${PROJECT_DIR}/backups/pre-release/${RELEASE_VERSION}
docker exec clinical-postgres-prod sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/clinical_data_pre_release.dump'
docker cp clinical-postgres-prod:/tmp/clinical_data_pre_release.dump ${PROJECT_DIR}/backups/pre-release/${RELEASE_VERSION}/clinical_data.dump
tar -czf ${PROJECT_DIR}/backups/pre-release/${RELEASE_VERSION}/file-storage.tar.gz -C /data/jiafei/runtime file-storage
```

### 4.5 加载 backend/frontend 镜像

```bash
docker load -i ${RELEASE_DIR}/clinical-data-app-images-${RELEASE_VERSION}.tar.gz
cp ${RELEASE_DIR}/docker-compose.app-release.yml ${PROJECT_DIR}/deploy/linux/docker-compose.app-release.yml
```

### 4.6 只替换 backend/frontend

```bash
cd ${PROJECT_DIR}/deploy/linux
CLINICAL_BACKEND_IMAGE=clinical-backend:${RELEASE_VERSION} CLINICAL_FRONTEND_IMAGE=clinical-frontend:${RELEASE_VERSION} docker compose -f docker-compose.prod.yml -f docker-compose.prod.gpu.yml -f docker-compose.app-release.yml up -d --no-build --no-deps backend frontend
```

这条命令只更新：

```text
backend
frontend
```

不会重建或重启：

```text
paddle-ocr-api
postgres
```

### 4.7 验证服务

```bash
curl -sS http://127.0.0.1:8000/api/health
curl -sS http://127.0.0.1:18080
curl -sS http://127.0.0.1:8048/health
docker compose -f docker-compose.prod.yml -f docker-compose.prod.gpu.yml -f docker-compose.app-release.yml ps
```

验证口径：

- `8000/api/health` 返回后端正常。
- `18080` 返回前端页面。
- `8048/health` 返回 OCR 正常。
- OCR 正常只是健康确认，不代表本次替换触碰了 OCR。

## 5. 回滚命令

如果替换后 backend/frontend 有问题，使用 4.3 记录的旧镜像回滚。

```bash
export PROJECT_DIR=/data/jiafei/clinical-data-system
cd ${PROJECT_DIR}/deploy/linux
CLINICAL_BACKEND_IMAGE=<旧backend镜像> CLINICAL_FRONTEND_IMAGE=<旧frontend镜像> docker compose -f docker-compose.prod.yml -f docker-compose.prod.gpu.yml -f docker-compose.app-release.yml up -d --no-build --no-deps backend frontend
```

回滚后验证：

```bash
curl -sS http://127.0.0.1:8000/api/health
curl -sS http://127.0.0.1:18080
curl -sS http://127.0.0.1:8048/health
```

## 6. 验证成功后的清理

如果用户完成业务验证，并确认不需要回滚，可以清理本次发布留下的旧镜像和回滚备份。

建议先保留一段观察期，例如 1 到 3 天；如果系统稳定，再执行清理。不要在刚替换完成、还没有业务验证时清理。

### 6.1 清理前确认

确认当前运行镜像：

```bash
docker inspect --format='{{.Config.Image}}' clinical-backend
docker inspect --format='{{.Config.Image}}' clinical-frontend
docker inspect --format='{{.Config.Image}}' paddle-ocr-api
```

确认服务健康：

```bash
curl -sS http://127.0.0.1:8000/api/health
curl -sS http://127.0.0.1:18080
curl -sS http://127.0.0.1:8048/health
```

确认后端和前端运行镜像已经是本次新版本。第三行 OCR 镜像只用于确认，不要清理生产正在使用的 OCR 镜像。

### 6.2 清理旧 backend/frontend 镜像

先查看应用镜像：

```bash
docker images 'clinical-backend'
docker images 'clinical-frontend'
```

删除已经确认不再需要回滚的旧 backend/frontend 镜像：

```bash
docker rmi <旧backend镜像ID或tag>
docker rmi <旧frontend镜像ID或tag>
```

不要删除：

```text
paddle-ocr-api-gpu:latest
paddle-ocr-api
postgres:16
```

### 6.3 清理发布包和回滚备份

如果确认本次版本稳定，并且不再需要回滚到上一版，可以清理本次临时发布包和回滚备份。

查看目录：

```bash
export RELEASE_VERSION=20260609-v355-colon-upload-field-normalize
export PROJECT_DIR=/data/jiafei/clinical-data-system
ls -lh ${PROJECT_DIR}/backups/migration/app-release-${RELEASE_VERSION}
ls -lh ${PROJECT_DIR}/backups/pre-release/${RELEASE_VERSION}
```

清理目录：

```bash
rm -rf ${PROJECT_DIR}/backups/migration/app-release-${RELEASE_VERSION}
rm -rf ${PROJECT_DIR}/backups/pre-release/${RELEASE_VERSION}
```

清理后保留：

- 当前运行的 backend/frontend 镜像。
- 当前生产数据库。
- 当前生产文件存储。
- 当前 OCR GPU 镜像和模型缓存。
- 最近一个仍有价值的稳定版本备份，如果磁盘空间允许。

### 6.4 Codex 清理规则

Codex 在清理阶段必须先向用户确认：

```text
本次版本已经验证成功，并且不再需要回滚到上一版。
```

确认后只能清理：

- 旧 backend/frontend 镜像。
- 本次迁移临时发布包。
- 用户确认不再需要的 pre-release 回滚备份。

不得清理：

- OCR GPU 镜像。
- OCR 模型缓存。
- PostgreSQL 镜像。
- 当前生产数据库目录。
- 当前生产文件存储目录。

## 7. 禁止事项清单

生产应用发布时不要执行：

```bash
docker compose up -d
docker compose up -d --build
docker compose build
scripts/package_linux_gpu_offline_bundle.sh
```

不要改：

```text
deploy/linux/docker-compose.prod.gpu.yml
PADDLE_OCR_IMAGE
PDF_PACKET_OCR_API_URL=http://paddle-ocr-api:8000
127.0.0.1:8048:8000
PADDLE_OCR_DEVICE=gpu:0
```

不要把开发端口写进生产命令：

```text
5173
```

不要把生产入口临时改成：

```text
18081
```

生产入口固定使用：

```text
18080
```
