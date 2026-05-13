# V2 PDF 审阅浏览器兼容离线替换包

适用场景：服务器上的后端和 GPU OCR 已经 healthy，但 Chrome / Edge / 豆包 / 夸克等 Chromium 浏览器在线审阅 PDF 显示 `PDF文件加载失败`，Safari 可以打开，文件下载也正常。

根因是生产 Nginx 对 Vite 打包出的 PDF.js `.mjs` worker 文件返回了 `application/octet-stream`，Chromium 会拒绝加载 module worker。本包显式修正 `.mjs` 的 JavaScript MIME；PDF.js 仍先使用主版本加载，失败或超时后再动态切到 legacy 构建兜底，同时关闭 PDF.js 的 ImageDecoder / OffscreenCanvas 路径以避开浏览器兼容差异。

另外，本包保留后端 PDF preview MIME 修正：如果历史扫描上传的 PDF 被记录成 `application/octet-stream`，后端会按 `.pdf` 文件名回推 `application/pdf`，避免预览接口误判为不支持。

不要再部署上一版 `clinical-data-pdfjs-legacy-20260513.tar.gz`，那版强制使用 legacy 构建，实测会让 Safari 也无法正常审阅。

本次包使用的镜像标签：

```text
clinical-backend:20260513-pdf-preview-fix
clinical-frontend:20260513-pdfjs-mjs-fix
paddle-ocr-api-gpu:latest
```

本包包含后端 Docker 镜像、前端 Docker 镜像、compose 覆盖文件和这份命令文档。数据库、文件存储和 OCR 镜像不在这个包里，不会替换 OCR 容器。

本地最终实测：

- Safari：`http://127.0.0.1:18081/pdf-review/files/2?version=1` 可渲染 `010001-知情同意书.pdf`，显示 `1/1` 和批注框。
- Chrome：同地址可渲染，Console 只剩 PDF 内部字典 warning，没有 MIME / worker 加载错误。
- 夸克：同地址可渲染，显示 `1/1`、`120%` 和批注框。

## 1. 上传离线包

本机生成完成后，包路径会是：

```text
/Users/jiafei/workspace/clinical-data-system/backups/migration/v2-replace/clinical-data-pdfjs-mjs-fix-20260513.tar.gz
```

上传到服务器：

```bash
scp /Users/jiafei/workspace/clinical-data-system/backups/migration/v2-replace/clinical-data-pdfjs-mjs-fix-20260513.tar.gz root@生产服务器IP:/data/jiafei/
```

## 2. 解压并加载镜像

```bash
cd /data/jiafei
tar -xzf clinical-data-pdfjs-mjs-fix-20260513.tar.gz
cd clinical-data-pdfjs-mjs-fix-20260513
shasum -a 256 -c SHA256SUMS
docker load -i clinical-data-pdfjs-mjs-fix-20260513.docker.tar.gz
```

如果服务器没有 `shasum`，用：

```bash
sha256sum -c SHA256SUMS
```

## 3. 安装 compose 覆盖文件

```bash
cp docker-compose.v2-replace-images.yml /data/jiafei/clinical-data-system/deploy/linux/
```

## 4. 替换后端和前端

这里故意使用 `--no-build --no-deps`：不在服务器重新构建镜像，也不重建/重启已经 healthy 的 PostgreSQL 和 OCR 容器。

```bash
cd /data/jiafei/clinical-data-system/deploy/linux
sed -i 's/"8080:80"/"18080:80"/' docker-compose.prod.yml
sed -i 's/:8080/:18080/g' backend.env

docker compose \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.gpu.yml \
  -f docker-compose.v2-replace-images.yml \
  up -d --no-build --no-deps backend frontend
```

确认 compose 已经指向新镜像：

```bash
docker compose \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.gpu.yml \
  -f docker-compose.v2-replace-images.yml \
  ps
```

## 5. 验证

```bash
curl -fsS http://127.0.0.1:8000/api/health
curl -fsS http://127.0.0.1:8048/health
```

浏览器打开：

```text
http://生产服务器IP:18080
```

重点看：

- 能正常登录。
- 临床数据集和受试者详情正常。
- PDF 审阅和整改任务入口正常。
- PDF 资料包/OCR 调用仍正常。

日志命令：

```bash
docker compose \
  -f docker-compose.prod.yml \
  -f docker-compose.prod.gpu.yml \
  -f docker-compose.v2-replace-images.yml \
  logs --tail=100 backend frontend
```
