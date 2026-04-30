# P0 验收记录

## 验收目标

P0 目标是完成正式系统工程地基：独立 Git 仓库、前后端框架、后端虚拟环境、PostgreSQL Docker、数据库连接、Alembic 初始化，以及最小前后端联通。

## 本地服务

- Frontend: http://127.0.0.1:5173/
- Backend: http://127.0.0.1:8000
- OpenAPI: http://127.0.0.1:8000/docs
- PostgreSQL: localhost:5432

## 核心命令

启动 PostgreSQL:

```bash
docker compose -f deploy/docker-compose.dev.yml up -d
```

启动后端:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

启动前端:

```bash
cd frontend
npm run dev
```

验证后端:

```bash
cd backend
python -m pytest
python -m ruff check .
```

验证前端:

```bash
cd frontend
npm run lint
npm run build
```

验证数据库连接:

```bash
cd backend
python -c "from sqlalchemy import text; from app.core.database import engine; conn = engine.connect(); print(conn.execute(text('select 1')).scalar_one()); conn.close()"
```

验证 Alembic:

```bash
cd backend
alembic check
alembic current
```

## 验收清单

- [x] Git 仓库已在项目目录独立初始化。
- [x] Git remote 已配置到 `https://github.com/cafelemon/clinical-data-system.git`。
- [x] `frontend`、`backend`、`deploy`、`docs`、`scripts`、`data-dev` 目录已建立。
- [x] 后端 `requirements.txt` 和 `requirements-dev.txt` 已建立。
- [x] 后端 Python 虚拟环境 `backend/.venv` 可用。
- [x] FastAPI 最小服务可启动。
- [x] `/api/health` 和 `/api/version` 可访问。
- [x] PostgreSQL 已通过 Docker Compose 启动。
- [x] 后端 `.env` 可连接 Docker PostgreSQL。
- [x] Alembic 已初始化，并已绑定项目配置和 SQLAlchemy metadata。
- [x] 前端 React + Vite + TypeScript + Tailwind 可启动和构建。
- [x] 前端通过 Vite proxy 可访问后端健康检查接口。
- [x] 开发期边界已明确：前后端本地跑，数据库进 Docker；部署期再推进全服务 Docker Compose。
