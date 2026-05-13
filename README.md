# 临床数据收集系统

本项目是公司内部临床研究资料、受试者过程数据、原始文件、研发图像视频数据和数据治理要求的统一管理系统。

## 技术栈

- Frontend: React + TypeScript + Vite + Tailwind CSS + shadcn/ui 风格组件 + Recharts
- Backend: FastAPI + SQLAlchemy 2.x ORM + Pydantic + Alembic
- Database: PostgreSQL
- Deploy: Docker Compose + Nginx

## 本地开发方式

后端：

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

前端：

```bash
cd frontend
npm run dev
```

默认访问地址：

- 前端: http://localhost:5173
- 后端健康检查: http://localhost:8000/api/health
- 后端 OpenAPI: http://localhost:8000/docs

本地开发 OCR：

- 当前 Mac 本机研发环境不再使用 Docker 内的 PaddleOCR CPU 容器。
- 本地 OCR 服务改为 macOS 原生 Apple Vision OCR API，继续占用原来的 `8048` 端口，因此后端默认配置 `PDF_PACKET_OCR_API_URL=http://127.0.0.1:8048` 不需要修改。
- 启动方式：在项目根目录运行 `MAC_VISION_OCR_PORT=8048 backend/.venv/bin/python scripts/mac_vision_ocr_api.py`。
- 健康检查：`http://127.0.0.1:8048/health` 返回的 `service` 应为 `mac-vision-ocr-api`。
- 后端调用本地 OCR 时已在 `backend/app/services/ocr_client.py` 中关闭代理环境继承，避免 `127.0.0.1:8048` 被系统代理转发后出现 `502 Bad Gateway`。

本地验证记录：

- `010005.pdf` 全 27 页 OCR 已跑通，耗时约 12.6 秒。
- 资料包重新分析成功后状态为 `ready`，生成 `9 segments` 和 `27 text/OCR pages`。

生产 OCR：

- Linux 生产环境仍沿用既有 GPU OCR 方案，即 PaddleOCR GPU 服务和 `paddle-ocr-api-gpu` 镜像。
- macOS Apple Vision OCR 只用于本机开发和样本调试，不替代生产环境的 Linux GPU PaddleOCR 基线。

环境端口说明：

- 本地开发环境：前端 `5173`，后端 `8000`
- 本地生产验证环境：前端 `18081`
- 服务器测试/生产环境：前端 `18080`

说明：

- `5173` 是日常开发调试默认前端端口
- `18081` 仅用于本机贴近生产构建的验证，不作为默认开发端口
- `18080` 是服务器侧测试/生产访问口径，避免与 `18081` 混用

局域网访问：

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

cd frontend
npm run dev
```

同一局域网设备访问 `http://<本机局域网IP>:5173`。

开发默认管理员：

- 用户名：`admin`
- 密码：`Admin@123456`

开发期推荐前后端在 Mac 本地运行，PostgreSQL 使用 Docker 容器，文件存储使用 `data-dev/file-storage` 模拟。正式部署前再补齐 frontend、backend、postgres、nginx 的完整 Docker Compose 编排。
