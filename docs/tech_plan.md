# 技术落地方案

本文是 `clinical-data-system` 的长期技术方案文档，用于沉淀架构、模块边界、资料包识别方案和后续 V3 实施规则。

## 1. 总体架构

```text
Frontend React/Vite
  |
  | /api
  v
Backend FastAPI
  |
  +-- PostgreSQL
  +-- File Storage
  +-- OCR Service
        |
        +-- Mac Dev: Apple Vision OCR
        +-- Linux Prod: PaddleOCR GPU
```

系统核心链路：

1. 项目/中心/阶段/资料模板配置。
2. 受试者资料项生成。
3. 资料上传或 PDF 资料包上传。
4. OCR 与资料包切分。
5. 人工校正、确认、上传入库。
6. PDF 在线审阅、批注和整改任务。
7. V3.1.0 数据看板工作台。
8. V3.2.0 临床数据集准备/结束阶段资料清单与 SSU 进展。
9. V3.2 后续重塑资料分类、板块体系和审核布局。
10. 后续字段结构化抽取和质控。

## 2. 模块边界

| 模块 | 责任 | 不负责 |
| --- | --- | --- |
| 主数据 | 项目、中心、阶段、模板、字典 | PDF 识别规则 |
| 临床资料项 | 受试者资料项、上传状态、审核状态 | OCR 页级分类 |
| 文件与版本 | 原文件、版本、下载、历史 | 批注业务解释 |
| PDF 审阅 | 在线预览、画框批注、整改任务 | 资料包 OCR 切分 |
| PDF 资料包 | 上传整包、OCR、切分、人工修正、确认入库 | 字段级结构化抽取 |
| OCR 服务 | 图片/PDF 页面文本识别 | 业务分类和资料项映射 |
| V3.1.0 数据看板 | 项目进度、入组计划、受试者结果、事件、器械问题、预警、重要事项 | PDF 资料包 OCR、生产 GPU OCR |
| V3.2.1 临床数据集 | 准备/结束阶段中心级资料清单、SSU 进展维护、若有资料无材料声明口径 | 试验进行阶段重构、OCR 自动识别 SSU |
| V3.2 分类与布局 | 资料分类、板块体系、审核布局 | 具体字段抽取 |
| V3 字段抽取 | 结构化字段、字段审核、字段沉淀 | 重新定义资料板块 |

## 3. 环境方案

### 3.1 Mac 本地开发

- 前端：`5173`
- 后端：`8000`
- OCR：`8048`
- 数据库：本地 Docker PostgreSQL
- 文件存储：`data-dev/file-storage`

Mac OCR 使用 Apple Vision OCR，目标是便于本地开发和真实样本调试。

### 3.2 Linux 生产

- 前端、后端、PostgreSQL、Nginx、OCR 通过 Docker Compose 管理。
- OCR 使用 PaddleOCR GPU 镜像。
- 生产交付优先使用离线镜像包和模型缓存包。
- 不在生产服务器在线 build GPU OCR 镜像。

## 4. V2 PDF 审阅方案

V2 已完成 PDF 审阅和整改闭环。

### 4.1 前端

- PDF.js 渲染 PDF。
- 批注层使用归一化坐标。
- 审阅页支持翻页、缩放、画框、批注列表。
- 整改任务入口与文件栏分离。

### 4.2 后端

核心表：

- `pdf_annotations`
- `correction_tasks`
- `correction_task_annotations`
- `files`
- `file_versions`
- `operation_logs`

核心原则：

- 原始 PDF 不被写入批注。
- 批注作为结构化数据保存。
- 整改重传生成新的文件版本。
- 复审不通过时同一整改任务继续循环。

## 5. V3 资料包方案

V3 当前关键顺序是：

```text
V3-P0 完成切分闭环 -> V3.1 重塑分类和布局 -> 再进入字段抽取
```

当前发现的问题说明，不能只把注意力放在单页分类准确率上。`010001.pdf` 的偏差不是系统切分闭环失败，而是资料分类、板块分组和审核布局定义不准确。资料包识别必须先确认临床审核视角下的板块分组是否合理，否则后续字段抽取会建立在错误结构上。

### 5.1 概念定义

| 概念 | 定义 | 示例 |
| --- | --- | --- |
| 板块 | 临床审核视角的一组资料集合 | 知情同意、影像检查、门诊病历、入组审核、设备/图像评价 |
| 资料项 | 系统中可入库、可审核、可追踪的标准资料项 | 知情同意书、CT报告、HIS记录 |
| 片段 | PDF 资料包中连续页码范围 | `4-12 门诊病历` |
| 字段 | 从某个资料项中抽取的结构化信息 | 检查日期、受试者编号、签名日期 |

### 5.2 当前 P0 实现

后端服务：

- `page_text_normalizer.py`
- `pdf_packet_classifier.py`
- `pdf_packets.py`
- `pdf_packets` API endpoints

前端页面：

- `frontend/src/pages/pdf-packets/PdfPacketsPage.tsx`

已实现：

- OCR 文本标准化。
- 文档类型注册表。
- 页级分类。
- 强标题切段。
- 连续页合并。
- 负向规则和互斥规则。
- `analysis-report` 调试报告。
- 人工拆分、合并、修正、确认和上传入库。
- 默认重新识别保护人工结果。
- 强制重新识别覆盖人工结果。

### 5.3 识别链路

```text
PDF packet
  -> OCR pages
  -> raw_text
  -> normalized_text
  -> page classifier
  -> segment builder
  -> draft segments
  -> manual review
  -> confirm and upload
```

### 5.4 板块优先规则

后续调整规则时按以下顺序判断：

1. 这个页面属于哪个临床资料板块？
2. 这个板块是否对应已有资料项？
3. 当前资料项是否应该拆分或合并？
4. 分类器错在哪里：标题、正文关键词、页眉水印、OCR 错字，还是负向规则缺失？
5. 是否需要调整板块定义，而不是只调关键词？

不要在板块未稳定前进入字段抽取。

## 6. V3-P0 当前基准

`010005.pdf` 已通过主样本闭环。

当前输出：

```text
12 segments, 27 text/OCR pages
```

当前切分：

```text
1-1    知情同意书                         -> 知情同意书
2-2    知情同意书交接记录表               -> 知情同意书交接表
3-3    医学影像检查报告单                 -> CT报告
4-12   门诊病历                           -> HIS记录
13-15  入组审核/入组评估相关材料           -> 入组审核记录表
16-16  生命体征记录表                     -> 生命体征记录表
17-17  舒适度评价表                       -> 舒适度评价表
18-21  图像质量评价表                     -> 图像质量评价表
22-23  设备常用功能/设备稳定性             -> 其他次要指标评价表
24-24  其他次要标准评价表/胶囊内镜报告信息  -> 其他次要指标评价表
25-26  独立评估人检查图像质量评估表         -> 中心阅片评价结果表
27-27  胶囊内镜报告                       -> 胶囊内镜报告
```

`010001.pdf` 已用于观察复用性，当前结论是：

- 偏差不属于系统切分闭环失败。
- 偏差主要来自资料分类和板块体系不准确。
- 不继续在 V3-P0 中用零散关键词修补。
- 下一阶段进入 V3.1，重塑分类与布局。

## 7. V3.1 分类与布局重塑

V3.1 是 V3-P0 之后的下一阶段，主要目标是重塑资料分类、板块体系和资料包审核布局。

当前已知结论：

- V3-P0 已结束。
- `010005.pdf` 验证通过。
- `010001.pdf` 偏差不归因为系统闭环失败。
- 主要问题是分类和板块体系不准确。
- 用户正在整理具体资料，后续以真实资料结构为依据设计 V3.1。

V3.1 暂定工作方向：

1. 梳理临床审核真实板块。
2. 明确每个板块下包含哪些资料项。
3. 区分“板块展示”和“资料项入库”的边界。
4. 调整资料包审核页面布局，让人工审核先看板块，再处理片段。
5. 根据新分类体系调整识别规则，而不是继续用零散关键词补丁。

V3.1 完成后，再判断是否进入字段结构化抽取。

## 8. V3.1.0 数据看板工作台

V3.1.0 聚焦首页 `/` 数据看板，把旧的统计概览升级为系统内维护的临床项目工作台。

### 8.1 数据模型

新增表均包含 `project_id`、可选 `center_id`、`created_at`、`updated_at`：

| 表 | 用途 |
| --- | --- |
| `dashboard_milestones` | 进度甘特图和预期偏离预警，维护伦理批件、合同完成、省局备案、启动时间、方案修正案、入组等里程碑 |
| `dashboard_enrollment_plans` | 入组计划表，维护合同例数、筛选、当前入组、阳性入组、下周计划等中心级指标 |
| `dashboard_subject_overviews` | 整体情况表，维护筛选号、知情/吞服时间、器械序列号、图像数量、视频时长和情况描述 |
| `dashboard_device_handovers` | 器械交接记录表，维护器械交接、归还、批次号、序列号和交接状态 |
| `dashboard_subject_results` | 受试者结果统计表，维护阅片号、筛选号、全结肠完成判断、息肉统计、匹配结果和其他诊断 |
| `dashboard_clinical_events` | 临床事件记录，维护事件、发生时间、类型、严重程度和备注 |
| `dashboard_device_issues` | 器械问题记录表，维护问题时间、问题描述、是否解决、问题类型和中心机构 |
| `dashboard_important_tasks` | 重要紧急事项完成，维护事项、负责人、计划/实际完成日期、状态、重要程度和紧急程度 |

权限：

- 新增 `dashboard:write`。
- 管理员、项目负责人、中心负责人、临床协调员默认具备写权限。
- 审核员、研发人员、只读用户默认只读。

### 8.2 API

新增 API 前缀为 `/api/dashboard/v31`：

```text
GET /dashboard/v31/project/{project_id}/overview
GET/POST/PATCH/DELETE /dashboard/v31/milestones
GET/POST/PATCH/DELETE /dashboard/v31/enrollment-plans
GET/POST/PATCH/DELETE /dashboard/v31/subject-overviews
GET/POST/PATCH/DELETE /dashboard/v31/device-handovers
GET/POST/PATCH/DELETE /dashboard/v31/subject-results
GET/POST/PATCH/DELETE /dashboard/v31/clinical-events
GET/POST/PATCH/DELETE /dashboard/v31/device-issues
GET/POST/PATCH/DELETE /dashboard/v31/important-tasks
GET /dashboard/v31/import-template/{kind}
POST /dashboard/v31/import/{kind}
GET /dashboard/v31/export/{kind}
```

旧看板 API 保留：

```text
GET /dashboard/project/{project_id}
GET /dashboard/project/{project_id}/centers
GET /dashboard/project/{project_id}/trend
GET /dashboard/project/{project_id}/review-status
GET /dashboard/project/{project_id}/completeness
```

### 8.3 前端

`DashboardPage` 不新增菜单，继续挂在首页 `/`：

- 顶部筛选：项目、中心、刷新、模板、导入、导出。
- 一级板块：实验项目、整体进度计划达成情况。
- 实验项目下 7 个子视图。
- 整体进度下 2 个子视图。
- 表格支持新增、编辑、删除、Excel 模板、导入、导出。
- 无 `dashboard:write` 权限时隐藏写操作。

### 8.4 预警规则

第一版只按计划日期判断：

- 计划日期早于今天且未完成：`overdue`。
- 计划日期在未来 7 天内且未完成：`due_soon`。
- 已填写实际完成日期，或状态为完成/关闭：不预警。

### 8.5 飞书参考材料

飞书 `C200CN临床情况一览表` 只作为字段和样式核对材料。首次实现时导出到 `V3.1材料/`，系统运行不依赖飞书实时同步。

## 9. V3.2.0 临床数据集补全

V3.2.0 聚焦“临床数据集”板块，阶段代码保持兼容，展示和默认资料模板按临床数据库框架与 2022 版基本文件目录补齐。

### 9.1 阶段结构

父阶段代码不变：

| code | 展示名 | 说明 |
| --- | --- | --- |
| `STARTUP` | 试验准备阶段 | 资料准备 + SSU 进展 |
| `TRIAL` | 试验进行阶段 | 本版不调整二级阶段和受试者资料项 |
| `CLOSEOUT` | 试验结束阶段 | 仅展示资料准备 |

子阶段：

- `STARTUP_MATERIALS`：资料准备。
- `SSU_PROJECT_APPROVAL`、`SSU_ETHICS`、`SSU_AGREEMENT_SIGNING`、`SSU_PROVINCIAL_FILING`、`SSU_STARTUP_MEETING`：SSU 进展节点。
- `CLOSEOUT_MATERIALS`：资料准备。

旧 STARTUP/CLOSEOUT 子阶段保留历史数据但设为 disabled，不删除阶段、模板、上传文件或审核记录。

### 9.2 资料清单

`STARTUP_MATERIALS` 默认生成 26 个 `center_file` 模板，对应基本文件目录第 1-26 项；`CLOSEOUT_MATERIALS` 默认生成 10 个 `center_file` 模板，对应第 46-55 项。名称含“若有”的模板默认 `required=false`，其余默认 `required=true`。

完整性计算统计全部中心资料。必填资料必须上传并审核通过；名称含“若有”的资料未上传时默认资料不全，只有上传并审核通过，或人工声明“无此材料”后才算资料齐全。`stage_files` 通过 `not_applicable`、`not_applicable_reason`、`not_applicable_by`、`not_applicable_at` 记录无材料声明。

### 9.3 SSU 进展模型

新增 `clinical_ssu_progress`，唯一范围为 `project_id + center_id + stage_code`。

字段：

- 状态：`status`。
- 日期：`submitted_at`、`approved_at`、`completed_at`。
- 维护信息：`version_info`、`file_checklist`、`summary`、`fee_detail`、`notes`。

API 挂在 `/api/clinical-datasets/ssu-progress`，沿用 `clinical_data:read/write` 权限和项目/中心范围隔离。读取临床数据集时会为中心自动补齐 5 个 SSU 节点。

### 9.4 前端组织

临床数据集页面：

- 阶段导航显示“试验准备阶段 / 试验进行阶段 / 试验结束阶段”。
- 试验准备阶段在阶段导航下展开“SSU进展 / 资料准备”两个子目录，默认进入 SSU 进展；两个子目录互斥展示。
- SSU 节点展示关联资料摘要，不重复创建上传项，并同步展示“无此材料”状态。
- 试验结束阶段直接展示 10 项资料准备上传表，不展示旧 closeout 子阶段导航。
- 若有资料以“若有”标识，资料表提供“无此材料”开关和可选备注；资料类型列不再面向使用者展示，长资料名称换行展示。

### 9.5 兼容策略

- URL、权限、统计和数据库外键继续使用 `STARTUP/TRIAL/CLOSEOUT`。
- 准备阶段二级视图通过 `view=ssu|materials` 表示，缺省或非法值默认 `ssu`。
- 既有项目访问临床数据集时自动补齐新阶段和默认模板。
- 人工禁用的现有子阶段不在运行时被自动重新启用。
- 本版不调整“试验进行阶段”及受试者访视资料项。

## 10. 字段抽取预案

字段抽取只在 V3.2 后续分类体系和审核布局稳定后启动。

优先资料项：

- 知情同意书
- 知情同意书交接表
- CT报告
- HIS记录
- 入组审核记录表

字段抽取原则：

- 先抽高价值字段，不追求一次性覆盖全部表单。
- 字段结果必须可人工修正。
- 字段结果应保留来源页码和识别依据。
- 字段结构设计优先支持审核和追溯，而不是只服务展示。

建议字段结果结构：

```json
{
  "field_key": "exam_date",
  "field_label": "检查日期",
  "value": "2025-05-09",
  "source_pages": [3],
  "confidence": 0.91,
  "reason": "命中 CT 报告检查日期区域",
  "status": "pending_review"
}
```

## 11. 前端交互原则

资料包页面应接近人工审核工作台：

- 筛选条件放在页面顶部。
- 左侧展示识别片段表格。
- 右侧固定展示识别原因。
- 新增片段、合并、拆分属于人工整理工具。
- 页码、识别名称、资料项修改采用失焦保存。
- 确认和上传合并为醒目的“确认并上传”。
- 已上传片段不可编辑，不允许重复上传。

前端不应把识别原因藏在表格底部，也不应把主要确认动作混在普通辅助操作里。

## 12. 后端规则原则

- 保持现有 API、数据库和入库路径兼容。
- P0 阶段优先使用规则、标准化和 debug reason 解决问题。
- 不为单个样本硬编码页码。
- 不在 P0 内提前扩字段抽取表。
- 对人工确认、人工修改、已上传片段默认保护。
- 强制重新识别必须是明确入口。
- 所有分割、合并、页码修改必须做连续性和重叠校验。

## 13. 测试策略

### 13.1 常规验证

```bash
cd backend
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .

cd ../frontend
npm run lint
npm run build
```

### 13.2 V3-P0 验证

```bash
cd backend
.venv/bin/python -m pytest tests/test_pdf_packets.py
```

必须人工验证：

- 上传资料包。
- 查看识别片段。
- 查看识别原因。
- 修改页码和资料项。
- 拆分片段。
- 合并片段。
- 确认并上传。
- 默认重新识别保留人工结果。
- 强制重新识别覆盖人工结果。

### 13.3 V3.2 分类与布局验证

V3.2 后续分类与布局验证结论应写入 `docs/process.md`，至少记录：

- 新分类体系。
- 新板块体系。
- 每个板块包含的资料项。
- 资料包页面布局变化。
- `010005.pdf` 和 `010001.pdf` 在新体系下的审核结果。
- 是否可以进入字段结构化抽取。

### 13.4 V3.1.0 数据看板验证

- Alembic migration 可升级。
- V3.1 看板 8 类数据 CRUD 通过。
- 只读用户不能写入，项目/中心范围隔离有效。
- Excel 模板、导入、导出可用，重复导入按业务唯一键更新。
- 首页 `/` 可按项目/中心筛选并切换 2 个一级板块、7 个实验项目子视图和 2 个整体进度子视图。
- 新增逾期未完成里程碑后出现预警，完成该里程碑后预警消失。

### 13.5 V3.2.0 临床数据集验证

- Alembic migration 可升级，且只有一个 head。
- 新项目自动生成新阶段结构和默认资料模板。
- 既有项目访问临床数据集时自动补齐新阶段/模板，并禁用旧 STARTUP/CLOSEOUT 子阶段。
- 试验准备阶段显示 26 项资料准备和 5 个 SSU 进展节点。
- 试验结束阶段显示 10 项资料准备，不显示旧 closeout 分段。
- 若有文件默认计入完整性缺失；上传审核通过或声明无此材料后才算齐全。
- SSU 进展 CRUD 权限和项目/中心范围隔离通过。
- `npm run build` 通过，上传/审核/一键审批原流程不回归。

## 14. 文档维护规则

以后只维护四份核心文档：

- `README.md`
- `docs/process.md`
- `docs/tech_plan.md`
- `docs/deploy_migration.md`

新增内容归档规则：

- 系统说明、启动方式、当前版本口径 -> `README.md`
- 阶段进度、验收记录、版本命名、下一步计划 -> `docs/process.md`
- 架构、技术方案、规则设计、交互原则、测试策略 -> `docs/tech_plan.md`
- 开发到生产迁移、镜像打包、生产替换命令、端口口径 -> `docs/deploy_migration.md`

除非是交付包内必须单独携带的命令清单，否则不要再新增零散 Markdown 计划书。
