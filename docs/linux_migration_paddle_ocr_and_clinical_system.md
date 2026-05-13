# Linux 服务器迁移指南：临床数据系统 + PaddleOCR

本文用于把当前本机的临床数据系统、PaddleOCR 服务、已有数据库数据和已上传文件迁移到公司 Linux 服务器。

## 1. 迁移内容

迁移包包含：

- `clinical-data-system/`：临床数据系统源码、后端/前端 Dockerfile、生产 Compose 配置。
- `paddle-ocr-api/`：PaddleOCR 本地 API 服务源码。
- `database/clinical_data.sql`：当前 PostgreSQL 逻辑备份。
- `runtime/file-storage/`：当前已上传文件、拆分 PDF、资料包相关文件。
- `runtime/paddle-ocr/`：OCR 服务运行目录，含模型缓存与 OCR 输出目录占位。

数据库和文件存储必须一起迁移。只迁数据库会导致系统里有文件记录，但实际 PDF/附件不存在。

## 2. 在本机生成迁移包

在当前项目目录执行：

```bash
cd /Users/jiafei/workspace/clinical-data-system
bash scripts/package_linux_migration.sh
```

默认会从本机 Docker 容器 `clinical-postgres-dev` 导出数据库：

```text
POSTGRES_CONTAINER=clinical-postgres-dev
POSTGRES_USER=clinical_user
POSTGRES_DB=clinical_data
```

如果本机容器名或路径不同，可覆盖环境变量：

```bash
POSTGRES_CONTAINER=clinical-postgres-dev \
POSTGRES_USER=clinical_user \
POSTGRES_DB=clinical_data \
FILE_STORAGE_DIR=/Users/jiafei/workspace/clinical-data-system/data-dev/file-storage \
PADDLE_OCR_DIR=/Users/jiafei/workspace/paddle-ocr-api \
bash scripts/package_linux_migration.sh
```

生成结果位于：

```text
backups/migration/clinical-data-linux-migration-YYYYMMDD_HHMMSS.tar.gz
```

默认会额外尝试打包本机已有的 OCR 运行缓存目录：

```text
/Users/jiafei/workspace/clinical-data-system/runtime/paddle-ocr
```

如果你的模型缓存实际在别处，打包前请显式指定：

```bash
PADDLE_OCR_RUNTIME_DIR=/实际的/runtime/paddle-ocr \
bash scripts/package_linux_migration.sh
```

## 3. 上传并解压到服务器

建议服务器目录：

```text
/data/clinical-data-stack
```

上传后在服务器执行：

```bash
sudo mkdir -p /data/clinical-data-stack
sudo tar -xzf clinical-data-linux-migration-YYYYMMDD_HHMMSS.tar.gz -C /data/clinical-data-stack --strip-components=1
cd /data/clinical-data-stack
```

检查包完整性：

```bash
sha256sum -c SHA256SUMS
```

如果服务器是 macOS 生成的 `shasum` 格式，Linux 的 `sha256sum -c` 可正常识别。

## 4. 准备环境配置

进入 Compose 目录：

```bash
cd /data/clinical-data-stack/clinical-data-system/deploy/linux
cp postgres.env.example postgres.env
cp backend.env.example backend.env
```

编辑 `postgres.env`，设置强密码：

```dotenv
POSTGRES_DB=clinical_data
POSTGRES_USER=clinical_user
POSTGRES_PASSWORD=替换为强密码
```

编辑 `backend.env`，至少修改：

```dotenv
DATABASE_URL=postgresql+psycopg://clinical_user:同一个强密码@postgres:5432/clinical_data
JWT_SECRET_KEY=替换为足够长的随机密钥
INITIAL_ADMIN_PASSWORD=临时初始密码
BACKEND_CORS_ORIGINS=["http://服务器IP:18080"]
```

OCR 服务在 Compose 网络中使用：

```dotenv
PDF_PACKET_OCR_API_URL=http://paddle-ocr-api:8000
PDF_PACKET_OCR_DPI=120
PDF_PACKET_OCR_TIMEOUT_SECONDS=1800
```

## 5. 启动服务

服务器需要已经安装 Docker 和 Docker Compose v2。

如果要启用 GPU，还需要：

- 宿主机 `nvidia-smi` 正常。
- Docker 已安装并配置 `nvidia-container-toolkit`。
- `docker run --rm --gpus all nvidia/cuda:11.8.0-runtime-ubuntu22.04 nvidia-smi` 能正常输出显卡信息。
- 如果显卡是 `RTX 5090 / 5080 / 5070` 这类 Blackwell `sm_120`，请不要继续使用旧的 `paddlepaddle-gpu 3.2.0 + cu118` 组合。按飞桨当前官方支持表，应切到 `PaddlePaddle 3.3.1`，优先 `CUDA 12.9`，其次 `CUDA 13.0`。

```bash
cd /data/clinical-data-stack/clinical-data-system/deploy/linux
docker compose -f docker-compose.prod.yml up -d --build postgres paddle-ocr-api
docker compose -f docker-compose.prod.yml ps
```

如果服务器要跑 GPU 版 OCR，改用：

```bash
cd /data/clinical-data-stack/clinical-data-system/deploy/linux
docker compose \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.gpu.yml \
  up -d --build postgres paddle-ocr-api
docker compose \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.gpu.yml \
  ps
```

当前仓库中的 GPU Dockerfile 已默认切到：

```text
PaddlePaddle 3.3.1
CUDA 12.9 wheel
```

如果之后要切到 CUDA 13.0，可在构建时覆盖：

```bash
docker build \
  --build-arg PADDLE_VERSION=3.3.1 \
  --build-arg PADDLE_GPU_INDEX_URL=https://www.paddlepaddle.org.cn/packages/stable/cu130/ \
  -f /data/clinical-data-stack/clinical-data-system/deploy/offline/paddle-ocr-api-gpu.Dockerfile \
  /data/clinical-data-stack/paddle-ocr-api
```

如果你采用的是本仓库的离线 GPU 打包脚本：

```bash
cd /Users/jiafei/workspace/clinical-data-system
bash scripts/package_linux_gpu_offline_bundle.sh
```

它会默认产出带版本后缀的离线包，例如：

```text
clinical-data-gpu-images-20260509-paddle331-cu129.tar.gz
paddle-ocr-model-cache-20260509-paddle331-cu129.tar.gz
SHA256SUMS-20260509-paddle331-cu129.txt
```

等待 PostgreSQL 健康后，恢复数据库：

```bash
docker exec -i clinical-postgres-prod \
  psql -U clinical_user -d clinical_data \
  < /data/clinical-data-stack/database/clinical_data.sql
```

再启动后端和前端：

```bash
docker compose -f docker-compose.prod.yml up -d --build backend frontend
```

如果 OCR 已启用 GPU 覆盖文件，后端和前端也继续沿用同样的 `-f` 组合：

```bash
docker compose \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.gpu.yml \
  up -d --build backend frontend
```

验证：

```bash
curl -fsS http://127.0.0.1:8000/api/health
curl -fsS http://127.0.0.1:8048/health
```

如果你怀疑 OCR 模型没有加载成功，先看缓存目录是否真的带上来了：

```bash
find /data/clinical-data-stack/runtime/paddle-ocr/model_cache -maxdepth 3 -type f | head
du -sh /data/clinical-data-stack/runtime/paddle-ocr/model_cache
```

浏览器访问：

```text
http://服务器IP:18080
```

## 6. PaddleOCR 模型预热

PaddleOCR 第一次真实 OCR 会下载并加载模型，耗时较长。建议部署后先预热一次：

```bash
cd /data/clinical-data-stack
SAMPLE_PDF="$(find runtime/file-storage -iname '*.pdf' | head -1)"
test -n "$SAMPLE_PDF"
curl -fsS -X POST \
  -F file=@"$SAMPLE_PDF" \
  "http://127.0.0.1:8048/ocr/pdf?max_pages=1&dpi=120&include_blocks=false"
```

也可以换成任意一页扫描 PDF。模型会缓存到：

```text
/data/clinical-data-stack/runtime/paddle-ocr/model_cache
```

后续容器重启不会重复下载。

如果服务器没有外网，而这里第一次预热就失败，通常就说明模型缓存并没有随迁移包一起到位。

## 6.1 GPU 生效检查

先确认容器拿到了 GPU：

```bash
docker exec paddle-ocr-api nvidia-smi
```

再确认 Paddle 在容器内识别到 CUDA：

```bash
docker exec paddle-ocr-api python -c "import paddle; print('compiled_with_cuda=', paddle.device.is_compiled_with_cuda()); print('device=', paddle.device.get_device())"
```

理想输出应接近：

```text
compiled_with_cuda= True
device= gpu:0
```

如果这里显示 `False` 或 `cpu`，说明当前容器并没有真正跑在 GPU 版镜像/运行时上。

如果这里显示 `gpu:0`，但首个 OCR 请求又报：

```text
RuntimeError: Unsupported GPU architecture
```

通常就说明当前安装包虽然启用了 CUDA，但 wheel 不是为当前显卡架构编译的。对 `RTX 5090`，优先排查是否仍在使用旧的 `cu118 / 3.2.0` 组合，或没有升级到 `3.3.1 + cu129/cu130`。

## 7. 端口与反向代理

默认端口：

- 前端：`18080`
- 后端：仅本机 `127.0.0.1:8000`
- PaddleOCR：仅本机 `127.0.0.1:8048`
- PostgreSQL：仅本机 `127.0.0.1:5432`

如果要使用正式域名，建议公司网关或 Nginx 只暴露前端，并反代到：

```text
http://127.0.0.1:18080
```

后端、OCR、数据库不要直接暴露到公网或普通办公网段。

## 8. 日常运维

查看服务：

```bash
docker compose -f /data/clinical-data-stack/clinical-data-system/deploy/linux/docker-compose.prod.yml ps
```

查看日志：

```bash
docker logs -f clinical-backend
docker logs -f clinical-frontend
docker logs -f paddle-ocr-api
docker logs -f clinical-postgres-prod
```

排查 OCR 500 时，优先看这几个点：

```bash
docker logs --tail=200 paddle-ocr-api
docker inspect paddle-ocr-api --format '{{json .HostConfig.DeviceRequests}}'
docker exec paddle-ocr-api sh -c 'ls -lah /root/.paddlex && ls -lah /root/.cache/paddle'
curl -v -X POST -F file=@/data/clinical-data-stack/runtime/file-storage/某个样本.pdf "http://127.0.0.1:8048/ocr/pdf?max_pages=1&dpi=120&include_blocks=false"
```

常见判定方式：

- 日志里出现模型下载失败、连接超时、404/403，基本就是模型缓存没带上且服务器外网不可用。
- `DeviceRequests` 为空，或者容器里 `paddle.device.get_device()` 返回 `cpu`，就是没有启用 GPU。
- `/root/.paddlex`、`/root/.cache/paddle` 基本为空，则说明挂载目录或迁移包内容不对。

备份数据库：

```bash
mkdir -p /data/clinical-data-stack/backups
docker exec clinical-postgres-prod pg_dump -U clinical_user clinical_data \
  > /data/clinical-data-stack/backups/clinical_data_$(date +%Y%m%d_%H%M%S).sql
```

备份文件存储：

```bash
tar -czf /data/clinical-data-stack/backups/file-storage_$(date +%Y%m%d_%H%M%S).tar.gz \
  -C /data/clinical-data-stack/runtime file-storage
```

## 9. 升级流程

新版本代码包上传后：

```bash
cd /data/clinical-data-stack/clinical-data-system/deploy/linux
docker compose -f docker-compose.prod.yml build backend frontend paddle-ocr-api
docker compose -f docker-compose.prod.yml up -d
```

后端容器启动时会自动执行：

```bash
alembic upgrade head
```

因此升级前必须先做数据库备份。

## 10. 回滚原则

如果升级后异常：

1. 停止服务。
2. 恢复上一版代码包。
3. 恢复升级前的数据库 SQL 备份。
4. 恢复对应时间点的 `runtime/file-storage` 备份。
5. 重新 `docker compose up -d --build`。

数据库结构迁移一旦执行，不建议只回滚代码，不回滚数据库。
