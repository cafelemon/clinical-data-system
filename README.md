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
