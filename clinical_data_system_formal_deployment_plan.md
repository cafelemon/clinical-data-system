# 临床数据收集系统正式部署落地方案（从零到一细粒度版本）

## 0. 方案定位

系统目标是建设一个面向公司内部临床研究资料、受试者过程数据、原始文件、研发图像视频数据和数据治理要求的统一管理系统。它不是简单文件夹，也不是完整 EDC，而是公司临床数据收集、文件追踪、研发数据资产化和后续高质量数据集建设的底座。

开发阶段先在 Mac 电脑上完成本地开发、联调和测试；后续正式部署到公司内网服务器，以 Docker Compose 方式容器化运行。

---

## 1. 正式技术栈选择

### 1.1 前端技术栈

| 模块    | 技术选型             | 说明                         |
| ----- | ---------------- | -------------------------- |
| 前端框架  | React            | 适合后台管理系统、表格、状态页、看板和复杂交互    |
| 开发语言  | TypeScript       | 降低字段、接口、状态类型错误             |
| 构建工具  | Vite             | 轻量、启动快，适合 Mac 本地开发         |
| UI 样式 | Tailwind CSS     | 快速搭建统一风格页面                 |
| 组件库   | shadcn/ui        | 表格、弹窗、按钮、下拉、卡片、标签等组件适合后台系统 |
| 图表    | Recharts         | 用于项目看板、中心完成率、趋势图、状态分布      |
| 请求层   | Axios / Fetch 封装 | 统一接口请求、错误处理、Token 注入       |
| 状态管理  | Zustand          | 轻量维护用户信息、项目中心选择、权限状态       |
| 路由    | React Router     | 支持登录页、看板页、数据集页、详情页、设置页     |

### 1.2 后端技术栈

| 模块         | 技术选型                      | 说明                       |
| ---------- | ------------------------- | ------------------------ |
| 后端框架       | FastAPI                   | 接口开发快，自动生成 OpenAPI 文档    |
| 数据校验       | Pydantic                  | 统一入参、出参、字段结构             |
| ORM        | SQLAlchemy 2.x ORM        | 正式系统数据关系复杂，建议用 ORM 提升维护性 |
| 数据迁移       | Alembic                   | 管理数据库表结构版本升级             |
| 认证鉴权       | JWT + RBAC                | 支持账号登录、角色权限、接口权限控制       |
| 文件处理       | Python pathlib / aiofiles | 处理文件上传、下载、路径、哈希          |
| Excel 导入导出 | openpyxl                  | 支持批量导入、导出台账和统计报表         |
| 日志         | loguru / logging          | 操作日志、错误日志、服务日志分离         |
| 测试         | pytest                    | 后端接口和业务逻辑测试              |

### 1.3 数据库与存储

| 模块    | 技术选型                     | 说明                          |
| ----- | ------------------------ | --------------------------- |
| 主数据库  | PostgreSQL               | 正式部署优先，适合 JSON 字段、统计分析和复杂关系 |
| 缓存/队列 | Redis，后续引入               | 一期可不启用，后续用于任务队列、异步处理、通知     |
| 文件存储  | NAS 挂载目录 / MinIO 二选一     | 一期建议先用服务器挂载目录，后续可切 MinIO    |
| 文件访问  | 后端受控下载接口                 | 不直接暴露真实文件路径                 |
| 备份    | PostgreSQL dump + 文件目录备份 | 正式部署必须纳入运维规范                |

### 1.4 部署技术栈

| 模块    | 技术选型           | 说明                    |
| ----- | -------------- | --------------------- |
| 容器化   | Docker         | 前端、后端、数据库、Nginx 分容器   |
| 编排    | Docker Compose | 适合公司内网中小型系统部署         |
| 反向代理  | Nginx          | 统一入口、静态资源、后端代理、文件下载代理 |
| 配置管理  | .env           | 区分开发、测试、生产配置          |
| 部署环境  | Ubuntu Server  | 公司内网服务器运行             |
| 域名/访问 | 内网 IP 或内部域名    | 先内网访问，后续再接统一入口        |

---

## 2. 总体架构

```text
用户浏览器
  ↓
Nginx 统一入口
  ├─ 前端 React 静态资源
  └─ /api 反向代理
        ↓
     FastAPI 后端服务
        ↓
  PostgreSQL 主数据库
        ↓
  文件存储目录 / NAS / MinIO
```

后续扩展：

```text
飞书 / 企微 / 内部门户
  ↓
统一网关 / Bridge
  ↓
临床数据收集系统 API
  ↓
数据库 + 文件存储 + JSON 字典 + 权限系统
```

---

## 3. 开发与部署环境分层

### 3.1 Mac 本地开发环境

Mac 电脑负责：

1. 前端页面开发。
2. 后端接口开发。
3. PostgreSQL 本地容器调试。
4. 文件上传目录模拟。
5. 接口联调。
6. 测试数据构造。
7. Docker Compose 本地预演。

推荐本地目录：

```text
clinical-data-system/
  frontend/
  backend/
  deploy/
  docs/
  scripts/
  data-dev/
```

### 3.2 正式服务器环境

正式服务器负责：

1. Docker Compose 运行所有服务。
2. PostgreSQL 持久化存储。
3. 文件目录挂载。
4. Nginx 对外提供内网访问。
5. 日志和备份。
6. 后续接入 NAS / MinIO / 统一认证。

正式部署目录建议：

```text
/opt/clinical-data-system/
  docker-compose.yml
  .env
  nginx/
  backend/
  frontend/
  postgres-data/
  file-storage/
  logs/
  backups/
```

---

## 4. 分期落地路线总览

| 阶段  | 名称              | 核心目标                 | 结果         |
| --- | --------------- | -------------------- | ---------- |
| P0  | 项目初始化与正式架构搭建    | 建仓库、建技术骨架、跑通前后端和数据库  | 系统地基完成     |
| P1  | 基础主数据模块         | 项目、中心、阶段、资料模板、状态字典   | 有统一数据口径    |
| P2  | 用户认证与权限体系       | 登录、用户、角色、RBAC        | 正式系统安全边界成型 |
| P3  | 临床数据集核心链路       | 项目中心切换、阶段资料、受试者列表、详情 | 业务主链路打通    |
| P4  | 文件上传与原文件绑定      | 文件上传、下载、预览、版本、哈希、绑定  | 从台账进入文件闭环  |
| P5  | 审核流与资料完整性       | 提交、审核、驳回、重新上传、完整性计算  | 临床资料流转闭环   |
| P6  | 数据看板与统计分析       | 项目看板、中心对比、趋势、状态分布    | 管理层可看进度    |
| P7  | Excel 导入导出与批量维护 | 批量导入主数据、导出报表         | 降低人工录入成本   |
| P8  | 操作日志、审计与备份      | 操作留痕、日志查询、备份脚本       | 满足治理要求     |
| P9  | 研发图像视频数据资产模块    | 图像视频目录、JSON 字典、权限矩阵  | 研发需求正式并入   |
| P10 | 数据质量检查与缺失项提醒    | 缺失项、异常时间、重复编号检查      | 提升数据治理质量   |
| P11 | 通知与协同入口         | 飞书/企微提醒、待办通知         | 形成协作闭环     |
| P12 | OCR/结构化提取预研模块   | 固定模板 OCR、人工校对台       | 智能化能力试点    |
| P13 | AI 辅助质控与报告摘要    | AI 检查、摘要、辅助报告        | 智能增强能力     |

---

# P0 项目初始化、开发环境与正式架构搭建

## P0.1 目标

P0 不是“建完仓库就直接写业务”，而是先把正式系统的工程地基、依赖管理、虚拟环境、Docker 边界、数据库连接和最小服务链路全部搭好。

这一阶段要解决四个问题：

1. 代码放在哪里。
2. Python / Node 依赖怎么管理。
3. 哪些服务在 Mac 本地直接跑，哪些先进入 Docker。
4. 后续如何平滑迁移到 Docker Compose 正式部署。

## P0.2 开发阶段与 Docker 边界

### P0.2.1 Mac 开发阶段推荐运行方式

开发阶段不要一开始就把所有东西都塞进 Docker。推荐采用：

| 模块         | 开发阶段运行方式                 | 是否进入 Docker | 原因                |
| ---------- | ------------------------ | ----------- | ----------------- |
| 前端 React   | Mac 本地 Node.js / Vite 运行 | 暂不进入        | 热更新快，调试方便         |
| 后端 FastAPI | Mac 本地 Python 虚拟环境运行     | 暂不进入        | 接口调试快，报错直观        |
| PostgreSQL | Docker 容器运行              | 进入 Docker   | 数据库环境最容易不一致，优先容器化 |
| Nginx      | 前期不启用                    | 暂不进入        | 本地开发阶段不需要反向代理     |
| 文件存储       | Mac 本地目录模拟               | 暂不进入        | 用目录模拟上传文件即可       |
| Redis      | 前期不启用                    | 后续进入        | 一期不是必须            |
| MinIO      | 前期不启用                    | 后续进入        | 一期可先用挂载目录或 NAS    |

因此，P0-P3 阶段推荐开发组合是：

```text
React 前端：Mac 本地 npm run dev
FastAPI 后端：Mac 本地 .venv + uvicorn --reload
PostgreSQL 数据库：Docker 容器
文件目录：Mac 本地 data-dev/file-storage
```

到正式部署前，再演进为：

```text
frontend 容器
backend 容器
postgres 容器
nginx 容器
file-storage 挂载目录 / NAS
```

## P0.3 仓库骨架搭建

### P0.3.1 创建项目目录

```bash
mkdir -p ~/workspace/clinical-data-system
cd ~/workspace/clinical-data-system
```

### P0.3.2 初始化 Git 仓库
https://github.com/cafelemon/clinical-data-system 这是仓库地址
```bash
git init
```

### P0.3.3 创建标准目录结构

```bash
mkdir -p frontend backend deploy docs scripts data-dev/file-storage data-dev/postgres
```

推荐结构：

```text
clinical-data-system/
  frontend/                 # React 前端项目
  backend/                  # FastAPI 后端项目
  deploy/                   # Docker Compose、Nginx、部署配置
  docs/                     # 需求文档、接口文档、数据库设计、部署说明
  scripts/                  # 初始化脚本、备份脚本、导入导出脚本
  data-dev/                 # Mac 本地开发数据，不提交 Git
    postgres/               # PostgreSQL 容器本地挂载目录
    file-storage/           # 本地模拟文件上传目录
  README.md
  .gitignore
```

### P0.3.4 创建 .gitignore

```bash
cat > .gitignore <<'EOF'
# Python
__pycache__/
*.py[cod]
.venv/
.env
.env.*
!.env.example

# Node
node_modules/
dist/
build/

# IDE
.DS_Store
.vscode/
.idea/

# Local data
data-dev/
postgres-data/
file-storage/
logs/
backups/

# Docker temporary
*.pid
EOF
```

### P0.3.5 创建 README.md

```bash
cat > README.md <<'EOF'
# 临床数据收集系统

本项目为公司内部临床数据收集、原始文件管理、受试者资料追踪、审核流、统计看板和研发图像视频数据资产化的正式业务系统。

## 技术栈

- Frontend: React + TypeScript + Vite + Tailwind CSS + shadcn/ui + Recharts
- Backend: FastAPI + SQLAlchemy ORM + Pydantic + Alembic
- Database: PostgreSQL
- Deploy: Docker Compose + Nginx

## 开发阶段运行方式

- 前端：Mac 本地 npm run dev
- 后端：Mac 本地 Python .venv + uvicorn --reload
- 数据库：Docker PostgreSQL
- 文件目录：Mac 本地 data-dev/file-storage
EOF
```

## P0.4 后端 requirements 与 Python 虚拟环境

仓库骨架建好后，第二步不是直接写接口，而是先明确后端依赖，创建虚拟环境，并把依赖固化到 requirements 文件。

### P0.4.1 创建后端目录结构

```bash
cd ~/workspace/clinical-data-system
mkdir -p backend/app/{api/v1,core,models,schemas,services,repositories,utils,tests}
touch backend/app/__init__.py
```

推荐结构：

```text
backend/
  app/
    main.py
    core/
      config.py
      database.py
      security.py
    api/
      v1/
    models/
    schemas/
    services/
    repositories/
    utils/
    tests/
  requirements.txt
  requirements-dev.txt
  .env.example
```

### P0.4.2 创建 requirements.txt

```bash
cat > backend/requirements.txt <<'EOF'
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
psycopg2-binary==2.9.9
pydantic==2.9.2
pydantic-settings==2.5.2
alembic==1.13.2
python-multipart==0.0.9
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
openpyxl==3.1.5
loguru==0.7.2
aiofiles==24.1.0
EOF
```

### P0.4.3 创建 requirements-dev.txt

```bash
cat > backend/requirements-dev.txt <<'EOF'
-r requirements.txt
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2
ruff==0.6.8
black==24.8.0
mypy==1.11.2
EOF
```

### P0.4.4 创建 Python 虚拟环境

```bash
cd ~/workspace/clinical-data-system/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

检查：

```bash
python --version
pip list
```

### P0.4.5 什么时候使用虚拟环境

| 场景                 | 是否使用 .venv                     |
| ------------------ | ------------------------------ |
| Mac 本地开发 FastAPI   | 使用                             |
| Mac 本地跑 Alembic 迁移 | 使用                             |
| Mac 本地跑 pytest 测试  | 使用                             |
| Docker 容器内运行后端     | 不使用本机 .venv，容器内安装 requirements |
| Ubuntu 正式部署        | 不使用本机 .venv，全部由 Docker 镜像管理    |

一句话：

```text
开发期：.venv 负责后端开发效率。
部署期：Docker 镜像负责后端运行环境一致性。
```

## P0.5 后端基础配置

### P0.5.1 创建 .env.example

```bash
cat > backend/.env.example <<'EOF'
APP_NAME=clinical-data-system
APP_ENV=development
APP_DEBUG=true

DATABASE_URL=postgresql+psycopg2://clinical_user:clinical_pass@localhost:5432/clinical_data

JWT_SECRET_KEY=change-this-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

FILE_STORAGE_ROOT=../data-dev/file-storage
MAX_UPLOAD_SIZE_MB=200
EOF
```

本地开发时复制：

```bash
cp backend/.env.example backend/.env
```

### P0.5.2 创建 FastAPI 最小入口

```bash
cat > backend/app/main.py <<'EOF'
from fastapi import FastAPI

app = FastAPI(title="临床数据收集系统", version="0.1.0")


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "clinical-data-system"}


@app.get("/api/version")
def version():
    return {"version": "0.1.0"}
EOF
```

### P0.5.3 本地启动后端
先查看端口，找个空闲的端口，下面的端口算是参考
```bash
cd ~/workspace/clinical-data-system/backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

浏览器访问：

```text
http://localhost:8000/api/health
http://localhost:8000/docs
```

## P0.6 Docker 先接管 PostgreSQL

### P0.6.1 创建 deploy/docker-compose.dev.yml

```bash
cd ~/workspace/clinical-data-system
cat > deploy/docker-compose.dev.yml <<'EOF'
services:
  postgres:
    image: postgres:16
    container_name: clinical-postgres-dev
    restart: unless-stopped
    environment:
      POSTGRES_DB: clinical_data
      POSTGRES_USER: clinical_user
      POSTGRES_PASSWORD: clinical_pass
    ports:
      - "5432:5432"
    volumes:
      - ../data-dev/postgres:/var/lib/postgresql/data
EOF
```

### P0.6.2 启动 PostgreSQL 容器

```bash
cd ~/workspace/clinical-data-system/deploy
docker compose -f docker-compose.dev.yml up -d
```

检查容器：

```bash
docker ps
docker logs -f clinical-postgres-dev
```

进入数据库：

```bash
docker exec -it clinical-postgres-dev psql -U clinical_user -d clinical_data
```

测试：

```sql
SELECT version();
-- 退出 psql 时输入反斜杠 q
```

### P0.6.3 本地后端连接 Docker 数据库

后端 `.env` 中使用：

```text
DATABASE_URL=postgresql+psycopg2://clinical_user:clinical_pass@localhost:5432/clinical_data
```

因为 PostgreSQL 容器已经把容器内 5432 映射到了 Mac 本机 5432。

## P0.7 数据库连接与 Alembic 初始化

### P0.7.1 创建 database.py

```bash
cat > backend/app/core/database.py <<'EOF'
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
EOF
```

### P0.7.2 创建 config.py

```bash
cat > backend/app/core/config.py <<'EOF'
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "clinical-data-system"
    app_env: str = "development"
    app_debug: bool = True
    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440
    file_storage_root: str = "../data-dev/file-storage"
    max_upload_size_mb: int = 200

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
EOF
```

### P0.7.3 初始化 Alembic

```bash
cd ~/workspace/clinical-data-system/backend
source .venv/bin/activate
alembic init alembic
```

后续 P1 开始建模型后，再正式生成迁移文件。

## P0.8 前端工程初始化

### P0.8.1 创建 React + TypeScript 项目

```bash
cd ~/workspace/clinical-data-system
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

### P0.8.2 安装前端依赖

```bash
npm install react-router-dom zustand axios recharts lucide-react
npm install -D tailwindcss postcss autoprefixer
npx tailwindcss init -p
```

### P0.8.3 推荐前端目录

```text
frontend/src/
  app/
    App.tsx
  components/
    layout/
    ui/
  pages/
    dashboard/
    clinical-dataset/
    projects/
    centers/
    settings/
    login/
  routes/
  services/
    http.ts
    health.ts
  stores/
  types/
  utils/
```

### P0.8.4 前端开发阶段运行方式

```bash
cd ~/workspace/clinical-data-system/frontend
npm run dev
```

前端本地访问：

```text
http://localhost:5173
```

前端请求后端：

```text
http://localhost:8000/api
```

P0 阶段可先通过 Vite proxy 或直接配置 API\_BASE\_URL。

## P0.9 什么时候开始把前后端放进 Docker

### P0.9.1 不建议一开始容器化前后端的原因

1. 前端热更新会变麻烦。
2. 后端调试报错不如本地直观。
3. 初期依赖频繁变动，每次 build 会拖慢节奏。
4. 业务还没稳定前，容器化全家桶容易让注意力跑偏。

### P0.9.2 建议容器化时间点

| 阶段     | 容器化范围                                        |
| ------ | -------------------------------------------- |
| P0-P3  | 只容器化 PostgreSQL                              |
| P4-P6  | 开始补 backend Dockerfile 和 frontend Dockerfile |
| P6 完成后 | 进行完整 Docker Compose 预演                       |
| 正式部署前  | frontend + backend + postgres + nginx 全部容器化  |

### P0.9.3 Docker 化后的正式服务

```text
clinical-frontend      # 前端静态资源容器
clinical-backend       # FastAPI 后端容器
clinical-postgres      # PostgreSQL 数据库容器
clinical-nginx         # Nginx 统一入口
clinical-redis         # 后续可选
clinical-minio         # 后续可选
```

## P0.10 P0 验收标准

P0 完成后，需要满足以下标准：

- Git 仓库已经初始化。
- frontend、backend、deploy、docs、scripts、data-dev 目录完整。
- 后端 requirements.txt 和 requirements-dev.txt 已建立。
- 后端 Python 虚拟环境 `.venv` 可用。
- FastAPI 本地可启动。
- `/api/health` 和 `/api/version` 可访问。
- PostgreSQL 已通过 Docker 容器启动。
- 后端 `.env` 可以连接 Docker PostgreSQL。
- 前端 React + Vite 可启动。
- 前端能访问后端健康检查接口。
- 已明确：开发期前后端本地跑，数据库进 Docker；部署期全服务 Docker Compose。

---

# P1 基础主数据模块

## P1.1 目标

建立系统最基础的数据口径：项目、中心、阶段、资料模板、状态字典。

没有 P1，后续的文件、受试者、统计都会变成“无根之树”。

## P1.2 数据表

### projects 项目表

字段：

- id
- name
- code
- description
- status
- created\_at
- updated\_at

### centers 中心表

字段：

- id
- project\_id
- name
- code
- contact\_person
- status
- created\_at
- updated\_at

### stages 阶段表

字段：

- id
- project\_id
- name
- code
- sort\_order
- description

### stage\_templates 阶段资料模板表

字段：

- id
- project\_id
- stage\_id
- item\_name
- item\_code
- required
- sort\_order
- description

### dictionaries 状态字典表

字段：

- id
- dict\_type
- value
- label
- color
- sort\_order
- enabled

## P1.3 后端接口

```text
GET    /api/projects
POST   /api/projects
GET    /api/projects/{id}
PUT    /api/projects/{id}
DELETE /api/projects/{id}

GET    /api/projects/{project_id}/centers
POST   /api/centers
PUT    /api/centers/{id}
DELETE /api/centers/{id}

GET    /api/projects/{project_id}/stages
POST   /api/stages
PUT    /api/stages/{id}
DELETE /api/stages/{id}

GET    /api/stage-templates
POST   /api/stage-templates
PUT    /api/stage-templates/{id}
DELETE /api/stage-templates/{id}
```

## P1.4 前端页面

1. 项目管理页。
2. 中心管理页。
3. 阶段管理页。
4. 阶段资料模板页。
5. 状态字典配置页。

## P1.5 验收标准

- 可以新增小肠、结肠、胃部项目。
- 可以为每个项目添加多个中心。
- 可以配置启动阶段、试验进行阶段、总结阶段。
- 可以配置每个阶段下默认资料清单。
- 状态字典可被前端统一调用。

---

# P2 用户认证与权限体系

## P2.1 目标

正式系统必须从早期就引入登录和权限，避免后续所有接口裸奔。临床数据涉及敏感资料，权限不能等到最后补。

## P2.2 角色设计

| 角色                          | 权限定位            |
| --------------------------- | --------------- |
| admin 管理员                   | 系统全局管理          |
| project\_manager 项目负责人      | 管理指定项目          |
| center\_manager 中心负责人       | 管理指定中心          |
| clinical\_coordinator 临床协调员 | 上传和维护资料         |
| reviewer 审核人员               | 审核文件和数据项        |
| rd\_user 研发人员               | 查看临床数据、访问研发数据模块 |
| readonly 只读用户               | 只读查看            |

## P2.3 数据表

- users
- roles
- permissions
- user\_roles
- role\_permissions
- user\_project\_scopes
- user\_center\_scopes

## P2.4 接口

```text
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
POST /api/auth/change-password

GET  /api/users
POST /api/users
PUT  /api/users/{id}
DELETE /api/users/{id}

GET  /api/roles
POST /api/roles
PUT  /api/roles/{id}

GET  /api/permissions
```

## P2.5 权限控制原则

1. 后端接口必须校验权限，不能只靠前端隐藏按钮。
2. 数据权限按项目、中心限制。
3. 文件下载接口也要鉴权。
4. 研发人员默认不能写临床原始资料。
5. 所有写操作进入操作日志。

## P2.6 验收标准

- 用户可以登录。
- 不同角色看到不同菜单。
- 无权限接口返回 403。
- 用户只能看到授权项目和中心。
- 文件下载受权限控制。

---

# P3 临床数据集核心链路

## P3.1 目标

打通系统最核心业务链路：

```text
项目 → 中心 → 阶段 → 阶段资料 / 受试者列表 → 受试者详情 → 数据项状态
```

## P3.2 数据表

### subjects 受试者表

字段：

- id
- project\_id
- center\_id
- screening\_no
- gender
- age
- enrolled\_at
- added\_by
- review\_status
- data\_status
- created\_at
- updated\_at

### subject\_sections 受试者阶段表

字段：

- id
- project\_id
- subject\_id
- section\_code
- name
- visit\_name
- time\_window
- sort\_order
- description

### subject\_items 受试者数据项表

字段：

- id
- subject\_id
- section\_id
- item\_name
- item\_code
- sort\_order
- created\_at
- updated\_at
- upload\_status
- review\_status
- remark

### stage\_files 阶段文件记录表

字段：

- id
- project\_id
- center\_id
- stage\_id
- stage\_template\_id
- file\_name
- file\_type
- upload\_status
- review\_status
- added\_by
- added\_at
- remark
- updated\_at

受试者详情固定按 6 个业务阶段展示数据项：

1. 筛选阶段。
2. 入组与检查准备阶段。
3. 检查执行阶段。
4. 检查后早期随访阶段。
5. 异常或延迟随访阶段。
6. 试验完成阶段。

## P3.3 页面

1. 临床数据集入口页。
2. 项目下拉选择。
3. 中心下拉选择。
4. 启动阶段资料表。
5. 试验进行阶段受试者列表。
6. 受试者详情页。
7. 总结阶段资料表。

## P3.4 接口

```text
GET /api/clinical-datasets?project_id=&center_id=
GET /api/stage-files?project_id=&center_id=&stage_id=
GET /api/subjects?project_id=&center_id=
POST /api/subjects
GET /api/subjects/{id}
PUT /api/subjects/{id}
GET /api/subjects/{id}/sections
GET /api/subjects/{id}/items
PUT /api/subject-items/{id}
```

## P3.5 验收标准

- 可以选择项目和中心。
- 启动阶段可以看到资料清单。
- 试验进行阶段可以看到受试者列表。
- 点击受试者可以进入详情。
- 受试者详情可以按 6 个阶段展示数据项。
- 总结阶段可以看到资料清单。
- 所有数据来自 PostgreSQL，不再使用假数据。

---

# P4 文件上传与原文件绑定

## P4.1 目标

将系统从“数据台账”升级为“资料收集闭环”。

核心是：文件不是随便上传，而是必须绑定到项目、中心、阶段、受试者、数据项。

## P4.2 文件存储策略

正式部署建议优先采用：

```text
服务器挂载目录 / NAS 挂载目录
```

目录结构：

```text
file-storage/
  projects/
    {project_code}/
      centers/
        {center_code}/
          stage_files/
          subjects/
            {screening_no}/
              documents/
              images_raw/
              images_enhanced/
              annotations/
```

## P4.3 数据表

### files 文件总表

字段：

- id
- file\_id
- original\_name
- stored\_name
- file\_ext
- mime\_type
- file\_size
- file\_hash
- storage\_path
- storage\_type
- project\_id
- center\_id
- subject\_id
- stage\_id
- stage\_file\_id
- subject\_item\_id
- file\_category
- version
- uploaded\_by
- uploaded\_at
- status

### file\_versions 文件版本表

字段：

- id
- file\_id
- version
- storage\_path
- file\_hash
- uploaded\_by
- uploaded\_at
- change\_note

## P4.4 文件分类

| 类型                 | 说明           |
| ------------------ | ------------ |
| clinical\_document | 临床资料文件       |
| raw\_pdf           | 原始 PDF / 扫描件 |
| image\_raw         | 原始图像         |
| image\_enhanced    | 增强图像         |
| video\_raw         | 原始视频         |
| doctor\_annotation | 医生批注文档       |
| metadata\_json     | 元数据 JSON     |
| annotation\_json   | 标注 JSON      |
| report             | 报告文件         |

## P4.5 接口

```text
POST /api/files/upload
GET  /api/files/{id}
GET  /api/files/{id}/download
GET  /api/files/{id}/preview
POST /api/files/{id}/replace
GET  /api/files/{id}/versions
DELETE /api/files/{id}
```

## P4.6 验收标准

- 可以上传 PDF、图片、Excel、Word 等文件。
- 文件保存到服务器目录。
- 数据库记录文件路径和哈希。
- 文件可以绑定到阶段资料或受试者数据项。
- 文件可以下载。
- PDF 和图片可以预览，其他文件通过下载查看。
- 替换文件时保留版本记录。
- 上传 / 替换文件后自动更新绑定资料项上传状态。
- 删除采用硬删除，并在最后一个绑定文件删除后回退资料项状态。
- 无权限用户不能下载文件。

---

# P5 审核流与资料完整性

## P5.1 目标

建立临床资料流转闭环：上传、提交、审核、驳回、补充、通过。

## P5.2 状态设计

### 上传状态

- not\_uploaded 未上传
- uploaded 已上传
- supplement\_required 待补充
- replaced 已替换

### 审核状态

- unreviewed 未审核
- pending 待审核
- approved 审核通过
- rejected 审核驳回

### 资料完整性

- complete 资料齐全
- incomplete 资料不全
- checking 核查中

## P5.3 数据表

### review\_records 审核记录表

字段：

- id
- target\_type
- target\_id
- action
- review\_status
- reviewer\_id
- comment
- created\_at

## P5.4 接口

```text
POST /api/reviews/submit
POST /api/reviews/approve
POST /api/reviews/reject
GET  /api/reviews?target_type=&target_id=
POST /api/completeness/recalculate
```

## P5.5 完整性计算规则

初版规则：

1. 必填资料项全部上传，才可标记资料齐全。
2. 任一必填项未上传，则资料不全。
3. 任一已上传项被驳回，则资料不全。
4. 所有必填项审核通过，资料齐全。

## P5.6 验收标准

- 临床协调员可以上传并提交审核。
- 审核人员可以通过或驳回。
- 驳回时必须填写原因。
- 受试者资料状态可自动计算。
- 中心进度可以根据资料状态更新。

---

# P6 数据看板与统计分析

## P6.1 目标

让领导、项目负责人可以通过看板快速掌握项目进度、中心差异和风险点。

## P6.2 看板指标

| 指标      | 说明            |
| ------- | ------------- |
| 总完成案例数  | 当前项目下已完成案例数   |
| 研究中心数量  | 项目参与中心数       |
| 项目总用时   | 项目累计天数        |
| 平均用时/案例 | 单案例平均周期       |
| 中位数用时   | 中位完成周期        |
| 完成趋势    | 按周/月展示完成变化    |
| 审核状态分布  | 通过、待审核、驳回、未审核 |
| 资料完整性分布 | 齐全、不全、核查中     |
| 各中心完成情况 | 中心级对比         |

## P6.3 接口

```text
GET /api/dashboard/project/{project_id}
GET /api/dashboard/project/{project_id}/centers
GET /api/dashboard/project/{project_id}/trend
GET /api/dashboard/project/{project_id}/review-status
GET /api/dashboard/project/{project_id}/completeness
```

## P6.4 页面

1. 数据看板首页。
2. 项目切换。
3. 指标卡片。
4. 各中心完成表。
5. 完成趋势折线图。
6. 审核状态环形图。
7. 资料完整性柱状图。

## P6.5 验收标准

- 看板数据从数据库实时计算。
- 可以按项目切换。
- 可以看到各中心完成情况。
- 可以看到审核状态和资料完整性。
- 看板能支撑领导查看进度。

---

# P7 Excel 导入导出与批量维护

## P7.1 目标

公司现阶段大量数据仍来自 Excel，因此必须支持批量导入和导出，减少纯手工录入。

## P7.2 导入范围

1. 项目列表。
2. 中心列表。
3. 阶段资料模板。
4. 受试者列表。
5. 受试者数据项清单。
6. 研发 JSON 字段字典草案。

## P7.3 导出范围

1. 项目进度表。
2. 中心资料状态表。
3. 受试者资料完整性表。
4. 缺失项清单。
5. 审核记录表。
6. 文件清单。

## P7.4 接口

```text
POST /api/import/projects
POST /api/import/centers
POST /api/import/subjects
POST /api/import/stage-templates

GET /api/export/project-progress
GET /api/export/center-status
GET /api/export/subject-completeness
GET /api/export/missing-items
```

## P7.5 验收标准

- 可以下载导入模板。
- 可以上传 Excel 并校验格式。
- 错误行能提示原因。
- 导入成功后数据入库。
- 可以导出当前项目统计和缺失项。

---

# P8 操作日志、审计与备份

## P8.1 目标

让系统具备正式部署的治理能力：谁在什么时候对什么数据做了什么操作，都能查到。

## P8.2 操作日志范围

记录以下操作：

1. 登录 / 登出。
2. 新增 / 修改 / 删除项目。
3. 新增 / 修改 / 删除中心。
4. 新增 / 修改 / 删除受试者。
5. 文件上传 / 下载 / 替换 / 删除。
6. 审核通过 / 驳回。
7. 权限变更。
8. Excel 导入导出。
9. JSON 字典修改。

## P8.3 数据表

### operation\_logs

字段：

- id
- user\_id
- username
- action
- target\_type
- target\_id
- project\_id
- center\_id
- ip\_address
- user\_agent
- detail\_json
- created\_at

## P8.4 备份策略

### 数据库备份

```bash
pg_dump clinical_data > backups/clinical_data_$(date +%F).sql
```

### 文件备份

```bash
rsync -av file-storage/ backups/file-storage/
```

### 备份频率

| 类型  | 频率        |
| --- | --------- |
| 数据库 | 每日一次      |
| 文件  | 每日增量，每周全量 |
| 配置  | 每次发版前备份   |

## P8.5 验收标准

- 关键操作能查日志。
- 日志支持按用户、项目、时间、动作筛选。
- 数据库可以手动备份和恢复。
- 文件目录可以备份。
- Docker 服务重启后数据不丢失。

---

# P9 研发图像视频数据资产模块

## P9.1 目标

将研发侧需求正式并入系统，形成图像、视频、增强图像、医生批注、JSON 字典、病灶标注的统一管理能力。

## P9.2 权限原则

| 数据对象     | 研发权限 | 原则             |
| -------- | ---- | -------------- |
| 原始图像     | 读    | 不建议直接写改        |
| 原始视频     | 读    | 是否可写待确认        |
| 增强图像     | 读写   | 必须版本化          |
| 医生批注文档   | 读写   | 必须保留来源和版本      |
| 元数据 JSON | 读写   | 系统生成 + 人工补充    |
| 标注 JSON  | 读写   | 必须有标注人、时间、复核状态 |
| 临床原始文档   | 按需只读 | 临床主责           |

## P9.3 数据表

### media\_assets 媒体资产表

字段：

- id
- file\_id
- project\_id
- center\_id
- subject\_id
- exam\_id
- media\_type
- media\_role
- source\_file\_id
- file\_path
- metadata\_json
- quality\_status
- review\_status
- created\_at

### annotations 标注表

字段：

- id
- media\_asset\_id
- frame\_id
- lesion\_id
- lesion\_type
- anatomical\_site
- bbox\_json
- polygon\_json
- label\_source
- annotator\_id
- review\_status
- created\_at

### metadata\_schemas JSON 字典模板表

字段：

- id
- schema\_name
- schema\_type
- version
- schema\_json
- enabled
- created\_at

## P9.4 页面

1. 图像视频目录页。
2. 媒体资产详情页。
3. JSON 元数据查看/编辑页。
4. 标注 JSON 查看/编辑页。
5. 文件关联关系页。
6. 研发权限矩阵页。

## P9.5 验收标准

- 可以登记原始图像、原始视频、增强图像、医生批注文档。
- 可以建立原图与增强图关系。
- 可以维护元数据 JSON。
- 可以维护标注 JSON。
- 研发人员读写权限符合矩阵。
- 所有写操作有版本和日志。

---

# P10 数据质量检查与缺失项提醒

## P10.1 目标

让系统不只是存数据，还能主动发现缺失、异常和风险。

## P10.2 检查类型

1. 必填项缺失。
2. 受试者编号重复。
3. 中心编号异常。
4. 上传文件为空或损坏。
5. 文件类型不符合要求。
6. 时间顺序异常。
7. 审核状态长期停留待审核。
8. JSON 字段缺失。
9. 图像视频未关联报告。
10. 标注未复核。

## P10.3 页面

1. 数据质量检查首页。
2. 缺失项清单。
3. 异常时间清单。
4. 重复编号清单。
5. 文件异常清单。
6. 研发 JSON 缺失清单。

## P10.4 验收标准

- 可以一键运行质量检查。
- 可以按项目/中心查看问题。
- 可以导出问题清单。
- 可以跳转到对应数据项进行补充。

---

# P11 通知与协同入口

## P11.1 目标

将系统中的待办、缺失、驳回、待审核转化为协同提醒。

## P11.2 初期通知方式

1. 系统内通知。
2. 邮件提醒，视公司邮箱情况决定。
3. 飞书 / 企微 Webhook，后续接入。

## P11.3 通知场景

1. 有资料待审核。
2. 资料被驳回。
3. 必填资料缺失。
4. 中心进度滞后。
5. 文件版本被替换。
6. JSON 字典待补充。

## P11.4 验收标准

- 系统内能看到待办。
- 待审核资料能提醒审核人。
- 驳回资料能提醒上传人。
- 通知可追踪已读/未读。

---

# P12 OCR / 结构化提取预研模块

## P12.1 目标

在基础闭环稳定后，再探索原始 PDF、扫描件、图片的结构化提取能力。

## P12.2 原则

1. 只做固定模板优先。
2. 不承诺任意文件自动识别。
3. 不直接覆盖正式字段。
4. 识别结果必须进入人工校对。
5. 低置信度字段必须标记。

## P12.3 功能

1. 上传文件后创建识别任务。
2. OCR 输出文本。
3. 模板字段匹配。
4. 识别结果展示。
5. 人工校对。
6. 校对后写入正式字段。
7. 字段可回溯到原文件。

## P12.4 技术可选

| 类型   | 选项                            |
| ---- | ----------------------------- |
| OCR  | PaddleOCR / MinerU / 其他本地 OCR |
| 文档解析 | 版面分析模型                        |
| 字段抽取 | 规则 + 模板 + LLM 辅助              |
| 校对台  | 自研网页校对界面                      |

## P12.5 验收标准

- 固定模板 PDF 可抽取部分字段。
- 识别结果能人工校对。
- 校对后可写入数据项。
- 原文和字段可关联。

---

# P13 AI 辅助质控与报告摘要

## P13.1 目标

在数据结构、权限、文件、审核、质量检查成熟后，接入 AI 辅助能力。

## P13.2 能力方向

1. 文件完整性摘要。
2. 受试者资料摘要。
3. 缺失项解释。
4. 审核辅助提示。
5. 报告初稿摘要。
6. 研发标注辅助检查。
7. 数据集申报材料辅助生成。

## P13.3 原则

1. AI 只做辅助，不直接替代审核。
2. AI 输出必须可追溯来源。
3. 重要结论必须人工确认。
4. 医疗相关结论必须医生审核。

---

## 5. 推荐开发节奏

### 第 1 阶段：系统地基期

范围：P0 + P1 + P2

目标：

- 工程结构稳定。
- 数据库稳定。
- 登录和权限打通。
- 主数据能维护。

建议周期：2-3 周。

### 第 2 阶段：临床主链路期

范围：P3 + P4 + P5

目标：

- 项目/中心/阶段/受试者链路打通。
- 文件上传绑定完成。
- 审核流和完整性计算完成。

建议周期：3-5 周。

### 第 3 阶段：管理看板与批量能力期

范围：P6 + P7 + P8

目标：

- 管理层能看进度。
- Excel 能导入导出。
- 日志和备份具备正式部署条件。

建议周期：2-4 周。

### 第 4 阶段：研发数据资产并入期

范围：P9 + P10

目标：

- 图像视频目录、JSON 字典、权限矩阵和质量检查进入系统。

建议周期：3-6 周。

### 第 5 阶段：智能化扩展期

范围：P11 + P12 + P13

目标：

- 通知协同、OCR 结构化、AI 质控逐步接入。

建议周期：按专项推进。

---

## 6. Docker Compose 正式部署结构

### 6.1 服务组成

```text
clinical-frontend
clinical-backend
clinical-postgres
clinical-nginx
clinical-redis    后续可选
clinical-minio    后续可选
```

### 6.2 docker-compose.yml 草案

```yaml
services:
  postgres:
    image: postgres:16
    container_name: clinical-postgres
    restart: always
    env_file:
      - .env
    volumes:
      - ./postgres-data:/var/lib/postgresql/data
    networks:
      - clinical-net

  backend:
    build:
      context: ../backend
      dockerfile: Dockerfile
    container_name: clinical-backend
    restart: always
    env_file:
      - .env
    volumes:
      - ./file-storage:/app/file-storage
      - ./logs/backend:/app/logs
    depends_on:
      - postgres
    networks:
      - clinical-net

  frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
    container_name: clinical-frontend
    restart: always
    networks:
      - clinical-net

  nginx:
    image: nginx:1.25
    container_name: clinical-nginx
    restart: always
    ports:
      - "8080:80"
    volumes:
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf
      - ./logs/nginx:/var/log/nginx
    depends_on:
      - frontend
      - backend
    networks:
      - clinical-net

networks:
  clinical-net:
    driver: bridge
```

---

## 7. 正式部署前检查清单

### 7.1 技术检查

- 前端可正常 build。
- 后端测试通过。
- Alembic 数据迁移可执行。
- Docker Compose 可一键启动。
- 文件上传目录挂载成功。
- Nginx 代理正常。
- 数据库持久化正常。
- 容器重启后数据不丢失。

### 7.2 安全检查

- 默认管理员密码已修改。
- JWT 密钥已使用生产配置。
- 数据库密码不写死在代码里。
- 文件下载必须鉴权。
- 删除操作必须校验权限。
- 关键操作写入日志。

### 7.3 业务检查

- 项目、中心、阶段数据已初始化。
- 角色和用户已创建。
- 阶段资料模板已配置。
- 受试者编号规则已确认。
- 文件分类和命名规则已确认。
- 审核流程已确认。

---

## 8. 最小正式可用版本建议

如果领导希望尽快看到可用结果，建议最小正式可用版本不要超过 P0-P6。

### 最小正式版本范围

1. P0 项目初始化与正式架构。
2. P1 基础主数据。
3. P2 登录和权限。
4. P3 临床数据集主链路。
5. P4 文件上传与绑定。
6. P5 审核流与完整性。
7. P6 数据看板。

### 最小正式版本不包含

1. OCR 自动结构化。
2. AI 报告生成。
3. 自动病灶标注。
4. 医院系统对接。
5. 复杂 EDC 能力。
6. 法规级电子签名。

### 最小正式版本成功标准

```text
登录系统
  ↓
选择项目和中心
  ↓
查看阶段资料
  ↓
新增受试者
  ↓
进入受试者详情
  ↓
上传原始文件
  ↓
提交审核
  ↓
审核通过 / 驳回
  ↓
自动更新资料完整性
  ↓
看板展示项目和中心进度
```

只要这条链路跑通，系统就已经从“原型展示”进入“正式临床数据收集底座”的阶段。

---

## 9. 给领导汇报时的简版说法

本系统建议按正式业务系统建设，不再按演示网页推进。技术路线采用 React + TypeScript 做前端，FastAPI + SQLAlchemy 做后端，PostgreSQL 做正式数据库，文件存储优先对接服务器挂载目录或 NAS，后续可以扩展 MinIO。开发阶段先在 Mac 上完成本地开发和 Docker 预演，正式部署时通过 Docker Compose 部署到内网服务器。

落地上建议拆成多个阶段：先完成工程架构、主数据、登录权限；再打通项目、中心、阶段、受试者、原始文件上传、审核和完整性计算；之后建设数据看板、Excel 导入导出、操作日志和备份；再把研发图像视频、JSON 字典、标注和权限矩阵纳入系统；最后再考虑 OCR、自动结构化和 AI 质控。

第一版不建议承诺自动识别、自动病灶标注和 AI 报告，而是优先完成可用、可管、可追溯的资料收集闭环。这样系统可以先落地，再逐步长出智能化能力。
