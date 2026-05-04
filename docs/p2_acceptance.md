# P2 验收记录

## 验收目标

P2 完成用户认证、JWT 登录、RBAC 权限、项目/中心数据范围控制，并将 P1 主数据接口切换为登录后访问。

## 默认账号

开发和首次验收默认管理员：

- 用户名：`admin`
- 密码：`Admin@123456`

正式部署前必须通过 `.env` 修改 `INITIAL_ADMIN_PASSWORD`。

## 后端范围

- `users`
- `roles`
- `permissions`
- `user_roles`
- `role_permissions`
- `user_project_scopes`
- `user_center_scopes`

## 内置角色

- `admin`
- `project_manager`
- `center_manager`
- `clinical_coordinator`
- `reviewer`
- `rd_user`
- `readonly`

## 认证与权限接口

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/me`
- `POST /api/auth/change-password`
- `GET /api/users`
- `POST /api/users`
- `PUT /api/users/{id}`
- `DELETE /api/users/{id}`
- `GET /api/roles`
- `POST /api/roles`
- `PUT /api/roles/{id}`
- `GET /api/permissions`

## 前端范围

- `/login` 真实登录页
- `/users` 用户管理
- `/roles` 角色管理
- Axios 自动注入 Bearer Token
- `401` 自动清理登录态并跳回登录页
- 菜单按后端返回权限动态显示
- P1 主数据页面已在 token 模式下运行

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

- [x] 用户可以登录。
- [x] `/api/auth/me` 返回当前用户、角色、权限、项目范围和中心范围。
- [x] 无 token 访问 P1 接口返回 `401`。
- [x] 无权限写接口返回 `403`。
- [x] admin 可访问和维护全部主数据。
- [x] 非 admin 用户只能看到授权项目/中心。
- [x] 越权维护项目返回 `403`。
- [x] 用户创建、角色分配、项目/中心范围分配已有测试覆盖。
- [x] 前端登录、路由保护、菜单权限和 token 注入已接入。

