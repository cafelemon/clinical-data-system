# P1 验收记录

## 验收目标

P1 完成基础主数据模块，覆盖项目、中心、阶段、阶段资料模板和状态字典。系统应具备统一数据口径，并为 P2 权限、P3 临床数据集链路提供基础。

## 后端范围

- `projects` 项目表
- `centers` 中心表
- `stages` 阶段表
- `stage_templates` 阶段资料模板表
- `dictionaries` 状态字典表

## 接口范围

- `GET /api/projects`
- `POST /api/projects`
- `GET /api/projects/{id}`
- `PUT /api/projects/{id}`
- `DELETE /api/projects/{id}`
- `GET /api/projects/{project_id}/centers`
- `GET /api/centers`
- `POST /api/centers`
- `PUT /api/centers/{id}`
- `DELETE /api/centers/{id}`
- `GET /api/projects/{project_id}/stages`
- `GET /api/stages`
- `POST /api/stages`
- `PUT /api/stages/{id}`
- `DELETE /api/stages/{id}`
- `GET /api/stage-templates`
- `POST /api/stage-templates`
- `PUT /api/stage-templates/{id}`
- `DELETE /api/stage-templates/{id}`
- `GET /api/dictionaries`
- `POST /api/dictionaries`
- `PUT /api/dictionaries/{id}`
- `DELETE /api/dictionaries/{id}`

## 前端范围

- 项目管理页：`/projects`
- 中心管理页：`/centers`
- 阶段管理页：`/stages`
- 阶段资料模板页：`/stage-templates`
- 状态字典配置页：`/dictionaries`
- 看板页已接入 P1 数量统计

## 验收命令

```bash
cd backend
python -m pytest
python -m ruff check .
alembic current
alembic check
```

```bash
cd frontend
npm run lint
npm run build
```

## 验收清单

- [x] 可以新增小肠、结肠、胃部项目。
- [x] 可以为每个项目添加多个中心。
- [x] 可以配置启动阶段、试验进行阶段、总结阶段。
- [x] 可以配置每个阶段下默认资料清单。
- [x] 状态字典可被前端统一调用。
- [x] 后端 CRUD 流程已有测试覆盖。
- [x] Alembic 已生成并执行 P1 表结构迁移。

