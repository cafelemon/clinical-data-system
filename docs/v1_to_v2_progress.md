# V1 到 V2 迭代进度记录

本文是本次 `V1 -> V2` 大版本迭代的唯一进度源，用于持续记录 PDF 在线审阅与整改闭环模块的设计决策、实施状态、验证结果和生产上线注意事项。

## V1 当前基线

- 当前基线提交：`35e4bb4 Lock V1 baseline and add Linux migration docs`
- 当前开发分支：`codex-v2-pdf-review-workflow`
- V1 基线文档：`docs/v1_release_baseline.md`
- 生产 OCR 基线：Linux GPU，`PaddlePaddle GPU 3.3.1`，`PaddleOCR 3.3.1`，CUDA wheel 源 `cu129`，运行设备 `gpu:0`
- 不可回退点：
  - 不回退到旧 `3.2.0 + cu118` OCR 生产方案
  - 原始 PDF 和历史版本不直接写入批注、不覆盖
  - 生产升级前必须备份数据库和文件存储

## V2 目标

V2 定义为“临床资料在线审阅与整改闭环模块”，在 V1 的资料上传、PDF 拆分、文件版本、审核记录和操作日志基础上新增：

- PDF 在线预览
- 画框批注
- 批注保存和刷新回显
- 批注生成整改任务
- 上传人整改重传并生成新文件版本
- 审核人复审通过或再次退回
- 全链路操作日志和版本追溯

V2.0 不包含导出带批注 PDF、整改报告导出和统计看板。2026-05-12 收到的 V2.1 计划书实际聚焦“临床数据集详情页 UI 工作台化”，本轮按当前前后端和数据库现状优先落地该 UI/交互目标。

## 阶段进度表

| 阶段 | 状态 | 开始时间 | 完成时间 | 主要改动 | 验证结果 |
| --- | --- | --- | --- | --- | --- |
| P0 V2 基线与进度文档 | 已完成 | 2026-05-12 | 2026-05-12 | 创建进度文档、V2 分支、数据库模型与权限 migration | Alembic 本地升级通过 |
| P1 PDF 在线审阅页 | 已完成 | 2026-05-12 | 2026-05-12 | 接入 PDF.js，新增审阅页和文件卡片入口 | 前端构建通过 |
| P2 画框批注 MVP | 已完成 | 2026-05-12 | 2026-05-12 | SVG 批注层、归一化坐标、批注 CRUD | 后端闭环测试覆盖批注保存回显 |
| P3 整改任务闭环 | 已完成 | 2026-05-12 | 2026-05-12 | 新增整改任务、重传生成 `FileVersion`、任务详情页 | 后端闭环测试覆盖任务创建与重传 |
| P4 复审与状态流转 | 已完成 | 2026-05-12 | 2026-05-12 | 复审通过/再次退回、资料项状态同步 | 后端闭环测试覆盖退回、再提交、通过 |
| P5 审计、入口整合与生产准备 | 已完成 | 2026-05-12 | 2026-05-12 | 关键动作写入 `operation_logs`，补齐入口与测试 | 后端全量测试与前端构建通过 |

## V2.1 UI 优化进度

V2.1 目标：将受试者资料项页面从“系统字段堆叠表”调整为“临床资料审核工作台”，并接入 V2 已有的 PDF 审阅、批注、整改任务和版本链路。

| 阶段 | 状态 | 完成时间 | 主要改动 | 验证结果 |
| --- | --- | --- | --- | --- |
| P0 字段隐藏与表格重排 | 已完成 | 2026-05-12 | 受试者详情资料项表格调整为“数据项 / 上传人 / 审核人 / 必填 / 上传状态 / 审核状态 / 文件 / 审阅 / 更新记录 / 备注”，隐藏编码、更新时间、完整性和操作列 | 前端构建通过 |
| P1 文件栏简化 | 已完成 | 2026-05-12 | 文件栏只保留上传 PDF、文件名、版本大小、下载、历史、重新上传、删除；历史版本改为弹窗 | 前端构建通过 |
| P2 审阅栏独立 | 已完成 | 2026-05-12 | 新增独立审阅入口组件，展示在线审阅和任务单状态，和文件资产操作分离 | 前端构建通过 |
| P3 更新记录合并 | 已完成 | 2026-05-12 | 后端新增资料项 timeline，将上传、重新上传、审核、批注、任务、备注更新汇总为统一记录；前端新增记录弹窗 | 后端新增用例通过 |
| P4 备注自动保存 | 已完成 | 2026-05-12 | 新增备注 PATCH 接口；前端备注输入停止 800ms 后自动保存，失焦补保存，并显示保存中、已保存、失败状态 | 后端新增用例通过 |
| P5 Tooltip 优化 | 已完成 | 2026-05-12 | 新增统一快速 tooltip，文件栏和审阅栏图标按钮补齐明确文案、`aria-label` 和 `title` | 前端 lint 无新增错误 |

## 关键决策记录

- 审阅对象：绑定拆分后入库的 `files` / `file_versions`
- 资料包职责：`pdf_packets` 继续负责上传、OCR 和拆分，不承载 V2 批注闭环
- 批注存储：批注作为结构化数据保存到 `pdf_annotations`
- 坐标策略：保存 0-1 归一化坐标，避免缩放和屏幕差异导致偏移
- 任务策略：整改任务采用“原任务循环”，复审不通过时同一任务再次退回
- 页面入口：优先放在受试者详情页的资料项文件卡片旁，同时提供整改任务列表
- 权限策略：新增 `pdf_review:*` 和 `correction_tasks:*` 细分权限
- 上线节奏：分段可上线、分段验收
- V2.1 实施策略：不为 UI 计划新增不必要业务表；复用现有 `files` / `file_versions`、`review_records`、`pdf_annotations`、`correction_tasks` 和 `operation_logs` 生成资料项更新记录

## 变更清单

### 后端

- 新增 `PdfAnnotation`、`CorrectionTask`、`CorrectionTaskAnnotation` 模型
- 新增 PDF 审阅和整改任务 API
- 整改提交复用现有 `FileAsset` / `FileVersion` 版本链
- 复审动作同步 `SubjectItem` / `StageFile` 审核状态并写入 `ReviewRecord`
- 新增 `PATCH /api/subject-items/{item_id}/remark`
- 新增 `GET /api/subject-items/{item_id}/timeline`

### 前端

- 新增 PDF 在线审阅页
- 新增整改任务列表页和详情页
- 文件卡片新增在线审阅和整改任务入口
- 左侧导航新增整改任务入口
- 受试者详情资料项表格完成 V2.1 重排
- 文件栏和审阅栏拆分为独立组件
- 新增备注自动保存单元格和更新记录弹窗
- 图标按钮统一快速 tooltip

### 数据库

- 新增 `pdf_annotations`
- 新增 `correction_tasks`
- 新增 `correction_task_annotations`

### 权限

- 新增 `pdf_review:read`
- 新增 `pdf_review:annotate`
- 新增 `pdf_review:manage`
- 新增 `correction_tasks:read`
- 新增 `correction_tasks:create`
- 新增 `correction_tasks:submit`
- 新增 `correction_tasks:review`

### 部署文档

- 生产上线仍沿用 V1 的“备份数据库和文件存储 -> 同步代码 -> 执行 migration -> 重启服务”原则
- 本阶段暂不改生产 OCR 镜像和离线包方案

## 测试与验收记录

已执行：

- `cd backend && .venv/bin/alembic upgrade head`
  - 结果：通过
  - 记录：`a7c9d2e4f601 -> b2f0c7d8e9a1`
- `cd backend && .venv/bin/python -m pytest tests/test_pdf_review_workflow.py -q`
  - 结果：`2 passed`
- `cd backend && .venv/bin/python -m pytest -q`
  - 结果：`39 passed`
- `cd backend && .venv/bin/ruff check app/api/v1/endpoints/clinical_data.py app/schemas/clinical_data.py app/schemas/__init__.py tests/test_pdf_review_workflow.py`
  - 结果：通过
- `cd frontend && npm run lint`
  - 结果：无错误
  - 备注：`frontend/src/pages/pdf-packets/PdfPacketsPage.tsx` 存在既有 React hooks dependency warnings，本轮未改动
- `cd frontend && npm run build`
  - 结果：通过
  - 备注：Vite 提示 PDF worker 和主包 chunk 较大，属于 PDF.js 引入后的体积提示，不影响构建产物生成
- `2026-05-13` V2 PDF 审阅生产构建浏览器复测
  - 结果：Safari、Chrome、夸克均可在 `http://127.0.0.1:18081/pdf-review/files/2?version=1` 渲染 `010001-知情同意书.pdf`，显示 `1/1`、批注列表和批注框
  - 备注：Chrome Console 只剩 PDF 内部字典 warning，无 MIME / worker 加载错误
- `2026-05-13` 离线替换包生成与解包校验
  - 结果：`backups/migration/v2-replace/clinical-data-pdfjs-mjs-fix-20260513.tar.gz` 生成完成，包内 `SHA256SUMS` 校验通过
  - 内容：后端镜像 `clinical-backend:20260513-pdf-preview-fix`、前端镜像 `clinical-frontend:20260513-pdfjs-mjs-fix`、compose 覆盖文件和替换命令文档

待手工验收：
- 手工验收：
  - 打开拆分后的 PDF 文件审阅页
  - 画框批注、刷新回显、缩放不偏移
  - 选择批注生成整改任务
  - 上传人提交整改 PDF 后生成新版本
  - 审核人再次退回后同一任务继续循环
  - 审核人复审通过后任务关闭，资料项状态变为已通过

## 生产上线备注

生产上线前必须确认：

- 已备份生产数据库
- 已备份生产文件存储目录
- migration 已在测试环境用生产数据副本验证
- 后端 Python 文件替换后重启 backend 容器
- 前端静态资源或镜像替换后重启 frontend / Nginx
- 本次 V2 不需要重建 OCR GPU 容器，除非 OCR 服务代码另有改动
