# Linux GPU 离线包刷新与服务器替换说明（3.3.1 + cu129）

本文只针对本次 `PaddlePaddle/PaddleOCR 3.3.1 + cu129` 的 GPU 离线包刷新。

## 1. 本地重新出包

在本地执行：

```bash
cd /Users/jiafei/workspace/clinical-data-system
bash scripts/package_linux_gpu_offline_bundle.sh
```

默认产物目录：

```text
backups/migration/offline-gpu
```

默认版本标识：

```text
YYYYMMDD-paddle331-cu129
```

默认会生成：

```text
clinical-data-gpu-images-<VERSION>.tar.gz
paddle-ocr-cache-<VERSION>/
paddle-ocr-model-cache-<VERSION>.tar.gz
SHA256SUMS-<VERSION>.txt
```

如果要改成 `cu130` 试验包，在本地改用：

```bash
cd /Users/jiafei/workspace/clinical-data-system
PADDLE_GPU_INDEX_URL=https://www.paddlepaddle.org.cn/packages/stable/cu130/ \
VERSION=$(date +%Y%m%d)-paddle331-cu130 \
bash scripts/package_linux_gpu_offline_bundle.sh
```

## 2. 上传到服务器

假设服务器根目录为：

```text
/data/jiafei
```

上传这三个文件到服务器，例如传到：

```text
/data/jiafei/offline-gpu-refresh
```

需要上传：

```text
clinical-data-gpu-images-<VERSION>.tar.gz
paddle-ocr-model-cache-<VERSION>.tar.gz
SHA256SUMS-<VERSION>.txt
```

## 3. 服务器替换旧离线包

在服务器执行：

```bash
mkdir -p /data/jiafei/offline-gpu-refresh
cd /data/jiafei/offline-gpu-refresh
sha256sum -c SHA256SUMS-<VERSION>.txt
```

删除旧的 OCR GPU 包与旧缓存解压目录：

```bash
rm -f /data/jiafei/offline-gpu-refresh/clinical-data-gpu-images-*.tar.gz
rm -f /data/jiafei/offline-gpu-refresh/paddle-ocr-model-cache-*.tar.gz
rm -f /data/jiafei/offline-gpu-refresh/SHA256SUMS-*.txt
rm -rf /data/jiafei/runtime/paddle-ocr/model_cache
```

注意：

- 上面删除命令只应用在确认新文件已经上传完成之后。
- 如果你把新文件传到了同一个目录，先不要执行这一组通配删除；改成只删旧版本的明确文件名。

更稳妥的推荐流程是：

```bash
mkdir -p /data/jiafei/offline-gpu-refresh/incoming
cd /data/jiafei/offline-gpu-refresh/incoming
sha256sum -c SHA256SUMS-<VERSION>.txt
```

然后只清运行缓存目录：

```bash
rm -rf /data/jiafei/runtime/paddle-ocr/model_cache
mkdir -p /data/jiafei/runtime/paddle-ocr
```

## 4. 解压新镜像包与模型缓存包

加载镜像：

```bash
cd /data/jiafei/offline-gpu-refresh/incoming
docker load -i clinical-data-gpu-images-<VERSION>.tar.gz
```

恢复模型缓存：

```bash
tar -xzf paddle-ocr-model-cache-<VERSION>.tar.gz -C /data/jiafei/runtime/paddle-ocr
```

如果看到类似下面这些信息：

```text
tar: 忽略未知的扩展头关键字‘LIBARCHIVE.xattr...’
```

这是 macOS 打包带来的扩展属性提示，通常可以忽略，不影响模型缓存内容解压。

恢复后目录应类似：

```text
/data/jiafei/runtime/paddle-ocr/model_cache/paddlex
/data/jiafei/runtime/paddle-ocr/model_cache/paddle
```

## 5. 重建 OCR 服务

进入部署目录：

```bash
cd /data/jiafei/clinical-data-system/deploy/linux
```

使用 GPU 覆盖 Compose 重建 OCR：

```bash
export PADDLE_OCR_IMAGE=paddle-ocr-api-gpu:latest
docker compose \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.gpu.yml \
  up -d --no-deps --force-recreate paddle-ocr-api
```

如果需要顺带重建 backend：

```bash
docker tag postgres:16 postgres:16 >/dev/null 2>&1 || true
docker compose \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.gpu.yml \
  up -d --no-deps --force-recreate backend paddle-ocr-api
```

说明：

- `docker-compose.prod.gpu.yml` 现在默认直接使用本地已加载的 `paddle-ocr-api-gpu:latest` 镜像，不在服务器上重新 build。
- 如果你当前 load 的还是旧标签镜像，可先手动补一个兼容标签：

```bash
docker tag paddle-ocr-api-gpu:<VERSION> paddle-ocr-api-gpu:latest
```

- 如果服务器本地 PostgreSQL 镜像标签不是 `postgres:16`，也先补齐：

```bash
docker tag clinical-postgres:16 postgres:16
```

## 6. 验证 GPU 与 OCR

先确认镜像与 GPU：

```bash
docker images | grep paddle-ocr-api-gpu
docker exec paddle-ocr-api python -c "import paddle; print(paddle.__version__); print('compiled_with_cuda=', paddle.device.is_compiled_with_cuda()); print('device=', paddle.device.get_device())"
docker exec paddle-ocr-api nvidia-smi
```

检查健康状态：

```bash
curl http://127.0.0.1:8048/health
docker logs --tail=200 paddle-ocr-api
```

对样本 PDF 做一次真实 OCR：

```bash
SAMPLE_PDF="$(find /data/jiafei/runtime/file-storage -iname '*.pdf' | head -1)"
test -n "$SAMPLE_PDF"
curl -sS -X POST \
  -F file=@"$SAMPLE_PDF" \
  "http://127.0.0.1:8048/ocr/pdf?max_pages=1&dpi=120&include_blocks=false"
```

成功标准：

- `paddle.__version__` 为 `3.3.1`
- `compiled_with_cuda= True`
- `device= gpu:0`
- `/ocr/pdf` 不再报 `Unsupported GPU architecture`

## 7. 如果 cu129 仍失败

如果仍然出现：

```text
RuntimeError: Unsupported GPU architecture
```

不要改服务器流程，只在本地重新出一个 `cu130` 版本包：

```bash
cd /Users/jiafei/workspace/clinical-data-system
PADDLE_GPU_INDEX_URL=https://www.paddlepaddle.org.cn/packages/stable/cu130/ \
VERSION=$(date +%Y%m%d)-paddle331-cu130 \
bash scripts/package_linux_gpu_offline_bundle.sh
```

然后重复本文第 2 到第 6 步。
