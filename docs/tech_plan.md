# 技术落地方案

本文是 `clinical-data-system` 的长期技术方案文档，用于沉淀当前架构、模块边界、资料包识别、字段核查、图像上传和生产发布原则。历史版本章节用于解释演进过程，不代表当前限制。

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
9. V3.2.2 试验进行阶段资料准备、固定访视阶段和旧阶段迁移。
10. V3.2.3 看板展示化、手工维护拆分和数据库字段设计文档。
11. V3.3.0 试验方案解析、版本留痕和项目配置初始化。
12. V3.4.0 图像数据管理、研发副本下载和电子报告上传。
13. V3.4.7 已应用方案访视优先生效和默认访视兜底。
14. V3.5 文件/SSU 字段提取、字段核查、规范值展示和进展回写。
15. V3.5.5 当前受试者资料项约束下的结肠资料包识别和 3GB 图像包上传。
16. V4.0.0 受试者级字段化 JSON 与算法研发证据包基线。

## 2. 模块边界

| 模块 | 责任 | 不负责 |
| --- | --- | --- |
| 主数据 | 项目、中心、阶段、模板、字典 | PDF 识别规则 |
| 临床资料项 | 受试者资料项、上传状态、审核状态 | OCR 页级分类 |
| 文件与版本 | 原文件、版本、下载、历史 | 批注业务解释 |
| PDF 审阅 | 在线预览、画框批注、整改任务 | 资料包 OCR 切分 |
| PDF 资料包 | 上传整包、OCR、切分、当前受试者资料项映射、人工修正、确认入库 | 定义业务字段含义 |
| OCR 服务 | 图片/PDF 页面文本识别 | 业务分类和资料项映射 |
| V3.1.0 数据看板 | 项目进度、入组计划、受试者结果、事件、器械问题、预警、重要事项 | PDF 资料包 OCR、生产 GPU OCR |
| 临床数据集 | 三阶段中心资料、SSU 进展、若有资料声明、方案访视优先生效、默认访视兜底 | 资料包页级 OCR 分类 |
| 看板 | 纯展示运营看板、独立维护入口、自动优先聚合接口 | 替代临床数据集成为主数据源 |
| 试验方案 | 项目级方案 PDF 版本、访视/资料项/中心解析草稿、人工修正和确认应用 | 自动删除有文件的历史配置 |
| 图像数据 | 原始/增强图像和电子报告、3GB zip 上传、安全解包统计、研发原始副本下载 | 单张图片预览和算法任务调度 |
| 字段提取 | 文件版本或资料包片段字段、规范值、来源页、置信度、人工核查和 SSU 回写 | 替代原文件和人工最终判断 |
| V4 研发证据包 | subject JSON schema、临床树、字段索引、图像索引、快照和算法扩展位 | V4.0.0 不实现导出 API、不训练模型、不定义完整算法结果格式 |

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
- 常规应用发布只替换 backend/frontend，并使用 `--no-build --no-deps` 保持 OCR 和 PostgreSQL 不变。
- 生产 Nginx、后端配置和前端上传超时共同支持 `3GB` 图像包。

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

V3-P0 时的历史实施顺序是：

```text
V3-P0 完成切分闭环 -> 分类和布局调整 -> 字段抽取
```

字段抽取已在 V3.5 落地。当前资料包识别的首要约束是：规则只能提供通用命中，最终建议必须映射到当前受试者实际存在的资料项；不存在同名资料项时不得继续沿用旧项目名称。

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

板块、资料项和字段规则可以持续迭代，但必须保留来源页、识别原因和人工核查能力，避免规则调整失去可追溯性。

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
- 后续在 V3.2 分类与布局方向继续重塑分类和审核布局。

## 7. 历史分类与布局方向

V3.2 后续分类与布局重塑用于承接 V3-P0 暴露出的资料分类和板块问题，主要目标是重塑资料分类、板块体系和资料包审核布局。

当前已知结论：

- V3-P0 已结束。
- `010005.pdf` 验证通过。
- `010001.pdf` 偏差不归因为系统闭环失败。
- 主要问题是分类和板块体系不准确。
- 用户正在整理具体资料，后续以真实资料结构为依据设计分类和布局方案。

后续暂定工作方向：

1. 梳理临床审核真实板块。
2. 明确每个板块下包含哪些资料项。
3. 区分“板块展示”和“资料项入库”的边界。
4. 调整资料包审核页面布局，让人工审核先看板块，再处理片段。
5. 根据新分类体系调整识别规则，而不是继续用零散关键词补丁。

字段结构化抽取已经进入正式能力。后续分类与布局调整需兼容 `document_extracted_fields` 和已有文件/片段证据关系。

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

## 9. 临床数据集结构

V3.2 建立了三阶段、中心资料和默认 V1-V4 访视基线；V3.4.7 起，受试者访视演进为“已应用方案优先、默认模板兜底”。以下 V1-V4 内容用于说明默认基线和历史迁移，不应理解为所有项目当前都固定四个访视。

### 9.1 阶段结构

父阶段代码不变：

| code | 展示名 | 说明 |
| --- | --- | --- |
| `STARTUP` | 试验准备阶段 | 资料准备 + SSU 进展 |
| `TRIAL` | 试验进行阶段 | 资料准备 + 方案访视；无方案时使用默认 V1-V4 访视 |
| `CLOSEOUT` | 试验结束阶段 | 仅展示资料准备 |

子阶段：

- `STARTUP_MATERIALS`：资料准备。
- `SSU_PROJECT_APPROVAL`、`SSU_ETHICS`、`SSU_AGREEMENT_SIGNING`、`SSU_PROVINCIAL_FILING`、`SSU_STARTUP_MEETING`：SSU 进展节点。
- `TRIAL_MATERIALS`：试验进行阶段中心级资料准备。
- `V1_SCREENING_VISIT`、`V2_EXPERIMENTAL_FOLLOWUP_VISIT`、`V3_CONTROL_FOLLOWUP_VISIT`、`V4_UNSCHEDULED_VISIT`：无已应用方案时的默认受试者访视。
- `PROTOCOL_VISIT_001` 等：由已应用方案生成的项目访视，数量和名称以方案为准。
- `CLOSEOUT_MATERIALS`：资料准备。

旧 STARTUP/CLOSEOUT 子阶段保留历史数据但设为 disabled，不删除阶段、模板、上传文件或审核记录。旧试验进行阶段六段式结构迁移到 V1-V4 固定访视阶段后禁用，不再作为用户维护主结构。

### 9.2 资料清单

`STARTUP_MATERIALS` 默认生成 26 个 `center_file` 模板，对应基本文件目录第 1-26 项；`TRIAL_MATERIALS` 默认生成 19 个 `center_file` 模板，对应第 27-45 项；`CLOSEOUT_MATERIALS` 默认生成 10 个 `center_file` 模板，对应第 46-55 项。名称含“若有”的模板默认 `required=false`，其余默认 `required=true`。

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
- 试验进行阶段默认进入“试验实施访视阶段受试者列表”，可切换到“资料准备”查看第 27-45 项中心级资料。
- 受试者详情优先按方案访视展示资料项；无方案项目按默认 V1-V4 访视展示。
- 试验结束阶段直接展示 10 项资料准备上传表，不展示旧 closeout 子阶段导航。
- 若有资料以“若有”标识，资料表提供“无此材料”开关和可选备注；资料类型列不再面向使用者展示，长资料名称换行展示。

### 9.5 兼容策略

- URL、权限、统计和数据库外键继续使用 `STARTUP/TRIAL/CLOSEOUT`。
- 准备阶段二级视图通过 `view=ssu|materials` 表示，缺省或非法值默认 `ssu`。
- 试验进行阶段二级视图通过 `view=visits|materials` 表示，缺省或非法值默认 `visits`。
- 既有项目访问临床数据集时自动补齐新阶段和默认模板。
- 人工禁用的现有子阶段不在运行时被自动重新启用。
- 默认 V1-V4 访视不作为普通阶段让用户手动增删改；方案访视通过方案解析、人工确认和应用流程维护。
- 方案应用后同步既有受试者；有文件、备注或审核痕迹的历史访视继续保留。

### 9.6 V3.2.3 看板展示化

V3.2.3 将首页 `/` 调整为纯展示运营看板，手工维护能力迁移到 `/dashboard-maintenance`。

数据源优先级：

1. 自动汇总：`subjects`、`stage_files`、`subject_items`、完整性服务和审核状态。
2. 手工补充：沿用 V3.1 的 `dashboard_*` 表，提供计划、里程碑、事件、器械问题和重要事项。
3. 后续字段：在 `docs/database_field_design.md` 中记录规划字段，字段抽取落库后再替代对应手工补充项。

新增展示接口：

```text
GET /api/dashboard/v323/overview?project_id=&center_id=
```

接口支持全部项目、单项目、单项目单中心三级汇总，返回范围信息、核心指标、完整性、审核状态、入组、中心排行、完成趋势、预警和手工补充摘要。

权限规则：

- `dashboard:read` 可访问展示看板。
- 看板维护写入除 `dashboard:write` 外，还必须是管理员或 `project_manager`。
- 项目负责人只能维护自己 `user_project_scopes` 内项目；中心负责人和协调员不可写看板维护数据。

### 9.7 V3.3.0 试验方案解析

V3.3.0 在项目管理中新增项目级“临床试验方案”模块，用于把方案 PDF 中的试验流程表和机构表转成可审查、可修正、可应用的项目配置草稿。

核心链路：

1. 上传方案 PDF，写入 `trial_protocol_versions` 并保留版本、文件 hash、页数、解析状态和原始解析草稿。
2. 文本提取复用 PDF 资料包能力：优先 `pypdf` / `pdftotext -layout`，文本为空时走现有 OCR API 或 OCR 命令兜底。
3. 规则解析“试验流程”页的访视列、窗口期、资料项行和 `√/√*`，`√*` 进入草稿时默认 `required=false`。
4. 规则解析“临床试验机构和主要研究者信息”页的机构代号、机构名称、备案号和研究者。
5. 用户在前端预览草稿中人工修正，确认应用后差异写入 `TRIAL` 下方案访视、受试者资料模板和中心主数据，并同步既有受试者的方案访视结构。

应用约束：

- 访视阶段编码使用 `PROTOCOL_VISIT_001` 这类稳定编码，名称显示为 `访视1:筛选期`。
- 访视资料模板编码使用 `PROTOCOL_V001_ITEM001` 这类稳定编码，同编码重复应用时更新而不重复创建。
- 中心以 `centers(project_id, code)` 判重，更新名称、研究者和备案号说明。
- 有文件或历史数据的旧访视/资料项必须保留；无文件的默认兜底访视可在方案生效后退出主展示结构。
- 已应用方案优先于默认访视；无已应用方案的项目继续使用默认访视兜底。
- 规则解析不依赖大模型，不自动创建受试者。

### 9.8 V3.4.0 图像数据管理

V3.4.0 新增“图像数据”主模块，按受试者试验序列号管理原始图像、增强图像和电子报告。

核心链路：

1. 受试者创建后自动生成 `raw`、`enhanced`、`report` 三条 `subject_image_records`。
2. 历史受试者访问图像数据列表时懒补齐缺失记录，保证试验数据和图像数据行级同步。
3. 原始图像和增强图像以 zip 包上传，保存原始 zip，并安全解包统计常见图片扩展名数量、图片总大小和扩展名分布。
4. 电子报告允许 PDF、Word、Excel 文件，在线预览继续复用现有 PDF 能力，不在本轮扩展 Office 预览。
5. 研发人员通过 `/api/image-data/{record_id}/raw-copy` 下载原始图像副本，并上传增强图像，不直接覆盖原始图像记录。

权限规则：

- `image_data:read`：查看状态和元数据。
- `image_data:upload_raw`：上传或下载原始图像记录。
- `image_data:copy_raw`：研发原始图像副本下载入口。
- `image_data:upload_enhanced`：上传或下载增强图像记录。
- `image_data:upload_report`：上传或下载电子报告。
- `image_data:delete`：清空图像数据记录。

安全边界：

- zip 解包必须拒绝绝对路径和 `..` 路径穿越。
- zip 根目录名不强制等于 `subjects.screening_no`，不一致时仅写入 `parse_warning`。
- 单文件上传上限为 `3072MB`；生产代理层 `client_max_body_size` 同步为 `3g`。
- 增强图像必须在对应原始图像已上传后才能上传。
- 当前不做单图缩略图、单图预览、算法任务调度，也不创建独立研发副本记录。

## 10. 字段提取与核查

字段提取已在 V3.5 落地，覆盖受试者 PDF、PDF 资料包片段和 SSU PDF。字段证据统一持久化到 `document_extracted_fields`。

当前重点资料：

- 知情同意书
- 知情同意书交接表
- CT报告
- HIS记录
- 入组审核记录表

实现原则：

- 先抽高价值字段，不追求一次性覆盖全部表单。
- 字段结果必须可人工修正。
- 字段结果必须保留原值、规范值、来源页码、置信度和核查状态。
- 字段结构设计优先支持审核和追溯，而不是只服务展示。
- 自动识别失败时生成可手工补录的字段骨架。
- 日期/时间规范值使用 ISO 形式存储，前端统一展示为 `YYYY/MM/DD` 或 `YYYY/MM/DD HH:mm`。
- SSU 字段经人工核查后可回写现有进展字段，但字段证据仍保留在提取表中。

建议字段结果结构：

```json
{
  "field_key": "exam_date",
  "field_label": "检查日期",
  "raw_value": "2025.05.09 08.07",
  "normalized_value": "2025-05-09 08:07",
  "source_page_no": 3,
  "confidence": 0.91,
  "evidence_text": "命中 CT 报告检查日期区域",
  "status": "extracted"
}
```

## 11. V4 subject JSON 证据包

V4 大版本服务研发中心算法需求，核心产物是每名受试者一份 subject JSON。JSON 定位为研发证据包：既能让算法按字段和图像索引取数，也能保留来源资料、来源页、字段状态和置信度，便于训练复现和问题追溯。

V4.0.0 只落地方案和 schema 基线，不实现代码。

### 11.1 当前数据基础

V3.5.5 已具备以下可聚合数据：

- `subjects`：受试者主记录、项目、中心、筛选号和关键日期。
- `subject_sections` / `subject_items`：访视结构、资料项、上传状态、审核状态和必填口径。
- `file_assets` / `file_versions`：资料文件、版本、来源资料包页码和文件 hash。
- `document_extracted_fields`：字段原值、规范值、来源页、来源文本、置信度、状态、人工修改和确认人。
- `subject_image_records`：原始图像、增强图像、电子报告的原包、解压目录、数量、大小和扩展名分布。

当前缺口：

- 缺少受试者级 JSON 聚合器和统一 schema version。
- 缺少不可变 JSON 快照表，无法稳定复现训练输入。
- 缺少逐图文件索引，目前只能表达 zip 包和解压目录统计。
- 缺少算法运行结果模型，增强图像和 AI 病灶识别结果还没有独立结果表。
- 缺少训练包导出目录、批量导出和算法消费验收流程。

### 11.2 JSON v0 顶层结构

subject JSON v0 顶层固定结构如下：

```json
{
  "schema_version": "subject-json/v0",
  "generated_at": "2026-06-12T00:00:00+08:00",
  "snapshot_id": null,
  "project": {},
  "center": {},
  "subject": {},
  "clinical_tree": [],
  "fields_index": {},
  "images_index": {
    "raw": {},
    "enhanced": {},
    "report": {}
  },
  "source_documents": [],
  "algorithm_runs": [],
  "quality_summary": {}
}
```

顶层含义：

- `schema_version`：JSON schema 版本，V4.0.0 固定为 `subject-json/v0`。
- `generated_at`：生成时间；未来正式快照必须使用不可变生成时间。
- `snapshot_id`：正式快照 ID；V4.0.0 只定义字段，V4.1 再实现。
- `project` / `center` / `subject`：业务编码标识，不放姓名、身份证等直接身份信息。
- `clinical_tree`：按访视和资料项组织的临床上下文。
- `fields_index`：按 `field_key` 扁平聚合字段，服务算法快速取字段。
- `images_index`：按 `raw`、`enhanced`、`report` 组织图像和报告索引。
- `source_documents`：参与 JSON 的文件版本清单。
- `algorithm_runs`：算法运行结果扩展位，V4.0.0 不细化病灶识别字段。
- `quality_summary`：字段、资料、图像和待补录概览。

### 11.3 临床树和字段索引

`clinical_tree` 保留临床资料结构：

```json
[
  {
    "section_code": "PROTOCOL_VISIT_002",
    "section_name": "访视2:检查期-胶囊检查日",
    "items": [
      {
        "item_code": "PROTOCOL_V002_ITEM004",
        "item_name": "结肠胶囊检查",
        "required": true,
        "upload_status": "uploaded",
        "review_status": "approved",
        "file_versions": [],
        "fields": []
      }
    ]
  }
]
```

`fields_index` 按字段 key 聚合全量字段证据：

```json
{
  "subject_signed_at": [
    {
      "field_label": "受试者签署时间",
      "value_type": "datetime",
      "raw_value": "2025.12.18 08.07",
      "normalized_value": "2025-12-18 08:07",
      "status": "confirmed",
      "confidence": 0.78,
      "manually_edited": true,
      "source": {
        "subject_item_code": "PROTOCOL_V001_ITEM001",
        "file_version_id": 12,
        "document_type": "informed_consent",
        "source_page_no": 7
      }
    }
  ]
}
```

字段导出原则：

- 全量导出字段证据，不因为 `needs_input`、低置信或未确认而丢弃。
- 算法消费方按 `status`、`confidence`、`manually_edited` 自行筛选。
- `normalized_value` 是算法优先读取值；没有规范值时可回退 `raw_value`。
- `source` 必须能追溯到资料项、文件版本或资料包片段。

### 11.4 图像索引

`images_index` 按图像类型组织：

```json
{
  "raw": {
    "record_id": 31,
    "upload_status": "uploaded",
    "original_package": {
      "storage_path": "projects/C200CN/centers/06/subjects/06012/image_data/raw/v1/xxxx.zip",
      "file_hash": "sha256...",
      "file_size": 753962081
    },
    "extracted_dir": "projects/C200CN/centers/06/subjects/06012/image_data/raw/v1/extracted",
    "image_count": 1000,
    "image_total_size": 123456789,
    "extensions": {
      "jpeg": 1000
    },
    "files": [
      {
        "relative_path": "06012/PCB250801013/00/000001-0000001-100150.jpeg",
        "extension": "jpeg",
        "size": 11047,
        "hash": null
      }
    ]
  }
}
```

图像导出原则：

- JSON 不内联图片，只记录原包、解压目录和逐图相对路径。
- V4.0.0 只定义逐图索引结构；当前系统尚未落库逐图清单。
- V4.2 需要补 `subject_image_file_index`，记录每张图的相对路径、大小、扩展名和 hash。
- 增强图像仍依赖原始图像；增强图像回存后，V4.3 刷新 JSON 并保留 raw/enhanced 关联。

### 11.5 快照、接口和未来模型

未来接口草案：

```text
GET  /api/subjects/{id}/research-json/preview
POST /api/subjects/{id}/research-json/snapshots
GET  /api/subjects/{id}/research-json/snapshots/{snapshot_id}/download
```

未来模型草案：

- `subject_json_snapshots`：`subject_id`、`schema_version`、`snapshot_version`、`storage_path`、`file_hash`、`generated_by`、`generated_at`、`status`。
- `subject_image_file_index`：`subject_image_record_id`、`relative_path`、`extension`、`file_size`、`file_hash`、`frame_no` 或排序号。
- `algorithm_runs`：`subject_id`、`input_snapshot_id`、`algorithm_name`、`model_version`、`status`、`started_at`、`completed_at`。
- `algorithm_results`：`algorithm_run_id`、`result_type`、`target_image_path`、`payload_json`、`confidence`、`review_status`。

V4.0.0 不新增这些模型，只把它们作为 V4.1-V4.4 的实现锚点。

### 11.6 4.x 路线

| 版本 | 目标 | 主要产出 | 边界 |
| --- | --- | --- | --- |
| `V4.0.0` | 建立方案和 schema 基线 | subject JSON v0、差距、路线、验收 | 不实现代码 |
| `V4.1.x` | 单受试者 JSON 生成 | 聚合器、预览、快照下载 | 不做批量训练包 |
| `V4.2.x` | 图像逐图索引和训练包 | 逐图清单、批量导出、训练目录 | 不做模型训练编排 |
| `V4.3.x` | 增强图像回存后扩充 JSON | raw/enhanced 关联、快照刷新 | 不定义病灶结果细节 |
| `V4.4.x` | 算法结果回写 | algorithm_runs/results、AI 病灶识别扩展 | 具体字段随算法输出定 |

## 12. 前端交互原则

资料包页面应接近人工审核工作台：

- 筛选条件放在页面顶部。
- 左侧展示识别片段表格。
- 右侧固定展示识别原因。
- 新增片段、合并、拆分属于人工整理工具。
- 页码、识别名称、资料项修改采用失焦保存。
- 确认和上传合并为醒目的“确认并上传”。
- 已上传片段不可编辑，不允许重复上传。

前端不应把识别原因藏在表格底部，也不应把主要确认动作混在普通辅助操作里。

## 13. 后端规则原则

- 保持现有 API、数据库和入库路径兼容。
- 资料包分类优先使用规则、标准化和 debug reason 解决问题。
- 不为单个样本硬编码页码。
- 通用规则命中后必须二次匹配当前受试者资料项。
- 对人工确认、人工修改、已上传片段默认保护。
- 强制重新识别必须是明确入口。
- 所有分割、合并、页码修改必须做连续性和重叠校验。

## 14. 测试策略

### 14.1 常规验证

```bash
cd backend
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .

cd ../frontend
npm run lint
npm run build
```

### 14.2 V3-P0 验证

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

### 14.3 V3.2 分类与布局验证

本节保留为历史验证清单。后续分类与布局变更至少记录：

- 新分类体系。
- 新板块体系。
- 每个板块包含的资料项。
- 资料包页面布局变化。
- `010005.pdf` 和 `010001.pdf` 在新体系下的审核结果。
- 对现有字段证据、资料项映射和历史文件的兼容性。

### 14.4 V3.1.0 数据看板验证

- Alembic migration 可升级。
- V3.1 看板 8 类数据 CRUD 通过。
- 只读用户不能写入，项目/中心范围隔离有效。
- Excel 模板、导入、导出可用，重复导入按业务唯一键更新。
- 首页 `/` 可按项目/中心筛选并切换 2 个一级板块、7 个实验项目子视图和 2 个整体进度子视图。
- 新增逾期未完成里程碑后出现预警，完成该里程碑后预警消失。

### 14.5 V3.2 临床数据集验证

- Alembic migration 可升级，且只有一个 head。
- 新项目自动生成新阶段结构和默认资料模板。
- 既有项目访问临床数据集时自动补齐新阶段/模板，并禁用旧 STARTUP/CLOSEOUT 子阶段。
- 试验准备阶段显示 26 项资料准备和 5 个 SSU 进展节点。
- 试验进行阶段显示第 27-45 项资料准备，并默认进入试验实施访视阶段受试者列表。
- 已应用方案的项目按方案访视展示并同步既有受试者；无方案项目使用默认访视兜底；有历史文件的旧访视资料不得丢失。
- 试验结束阶段显示 10 项资料准备，不显示旧 closeout 分段。
- 若有文件默认计入完整性缺失；上传审核通过或声明无此材料后才算齐全。
- SSU 进展 CRUD 权限和项目/中心范围隔离通过。
- `npm run build` 通过，上传/审核/一键审批原流程不回归。

### 14.6 V3.4 图像数据验证

- Alembic migration 可升级并创建 `subject_image_records`。
- 新增受试者后自动同步三类图像记录，删除受试者后级联删除图像记录。
- 历史受试者缺少图像记录时，访问 `/api/image-data` 会懒补齐。
- 原始/增强 zip 上传后统计图片数量、图片总大小和扩展名分布，路径穿越 zip 被拒绝。
- 研发角色可下载原始副本并上传增强图像，但不能上传原始图像。
- 协调员可上传原始图像和电子报告，但不能上传增强图像。
- 前端 `/image-data` 三个子页分开展示，增强图像在原始图像未上传时禁用上传按钮。

### 14.7 V3.5.5 回归验证

- 结肠资料包规则命中后默认映射到当前受试者的 `结肠胶囊检查`、`结肠镜检查`、`阅片` 和 `性能评价`。
- 当前受试者无同名资料项时，不生成指向旧项目资料项的建议 ID。
- 小肠资料包原有规则保持兼容。
- `06012.zip` 和 `06012_enhanced.zip` 按原始、增强顺序上传后保留原包并显示解压统计。
- 超过 `3072MB` 返回 413，非法 zip 和路径穿越继续拒绝。
- 人工日期输入如 `2025.12.18 08.07` 展示为 `2025/12/18 08:07`。

### 14.8 V4.0.0 文档和 schema 验证

- `README.md` 明确 V3.5.5 是生产基线，V4.0.0 是规划和 schema 基线。
- `docs/process.md` 记录 V4.0.0 目标、边界、现状差距、4.x 路线和验收口径。
- `docs/version_history.md` 有 2026-06-12 的 V4.0.0 时间线条目。
- `docs/tech_plan.md` 定义 subject JSON v0 顶层结构、`clinical_tree`、`fields_index`、`images_index`、`algorithm_runs` 和未来接口/模型草案。
- 文档中不得把 V4.0.0 写成已实现导出 API、已新增数据库或已支持算法结果回写。
- 以 `C200CN / 06 / 06012` 为样例时，schema 可以表达受试者、访视资料项、字段证据、原始图像、增强图像和电子报告。

## 15. 文档维护规则

以后只维护以下六份核心文档：

- `README.md`
- `docs/process.md`
- `docs/version_history.md`
- `docs/tech_plan.md`
- `docs/deploy_migration.md`
- `docs/database_field_design.md`

新增内容归档规则：

- 系统说明、启动方式、当前版本口径 -> `README.md`
- 阶段进度、验收记录、版本命名、下一步计划 -> `docs/process.md`
- 版本号、发布日期和一句话摘要 -> `docs/version_history.md`
- 架构、技术方案、规则设计、交互原则、测试策略 -> `docs/tech_plan.md`
- 开发到生产迁移、镜像打包、生产替换命令、端口口径 -> `docs/deploy_migration.md`
- 数据库 ERD、字段口径、规划字段 -> `docs/database_field_design.md`

除非是交付包内必须单独携带的命令清单，否则不要再新增零散 Markdown 计划书。
