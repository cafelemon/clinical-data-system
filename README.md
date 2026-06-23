# 巡常临床数据智能管理系统

`clinical-data-system` 是面向临床研究资料收集、质量核查、PDF 审阅、资料包识别和图像数据管理的内部业务系统。

如果是项目交接或首次接手，请先读 `docs/handover.md`。本文保留为 10 分钟快速入口，完整背景、模块地图、运行验证、发布边界和 V4.2.2 交接说明都集中在交接文档中。

当前生产基线为 `V3.5.5`。当前生产交付已覆盖 V1 至 V3.5.5 的应用能力，不再使用“V3 仅为内部迭代、生产只交付 V1/V2”的旧口径。

V4.0.0 进入规划基线：大版本 4 定位为服务研发中心算法需求的临床数据资产化体系，短期以 Subject Snapshot、Image Evidence Index 和 Snapshot JSON 导出为主。V4.0.0 只落地资产架构、Snapshot/Schema、差距和路线，不新增后端 API、数据库 migration 或前端交互。

V4.0.1 完成运行时界面版本痕迹清理：生产界面只呈现业务语义，版本演进继续由本文、`docs/process.md` 和 `docs/version_history.md` 追溯。

V4.1.5 完成 Subject Snapshot 系列收口：V4.1 的数据模型、预检、生成、下载和历史管理进入稳定基线；下一阶段进入 V4.2 Image Evidence Index。

V4.2.0 落地 Image Evidence 数据模型基线：新增图像证据索引持久化口径，但不生成索引、不解析报告图片、不做 Landmark 反查、不新增前端入口。

V4.2.1 落地 PDF 电子报告图片索引：上传后自动提取内嵌图片并写入 `report_package` / `report_image` 证据，支持后端重建；Office 报告暂记为不支持，不识别医生标注图或 Landmark。

V4.2.2 落地 Landmark Image 反查与复核：按报告经过时长定位增强图并回溯 raw 同帧，识别绿色医生圈注，支持候选复核、人工确认和三图预览。

## 1. 当前能力

- 项目、中心、阶段、资料模板、字典、用户、角色和权限管理。
- 试验准备、试验进行、试验结束三阶段资料管理，以及 SSU 进展维护。
- 受试者资料项、文件版本、审核记录、操作日志和整改任务闭环。
- PDF 在线预览、画框批注、整改重传和复审。
- PDF 资料包 OCR、智能切分、人工拆分/合并/修正、确认入库。
- 项目方案 PDF 解析、版本留痕、草稿修正和访视/资料项配置应用。
- 文件字段提取、来源页与置信度记录、人工核查、规范值展示和 SSU 回写。
- 数据驾驶舱、独立看板维护、Excel 导入导出和项目/中心范围汇总。
- 原始图像、增强图像和电子报告管理；zip 原包保留、安全解包和统计。
- PDF 电子报告内嵌图片自动索引、SHA256 去重、来源页追溯和后端重建。
- 报告图到增强图、raw 同帧的 Landmark 反查，医生圈注识别和前端人工复核。
- V4.0.0 临床数据资产化规划：以 Subject 为归属中心，建立 Snapshot、Image Evidence、AlgorithmRun、Dataset 等资产口径；JSON 是 Snapshot 的导出形式，不是核心资产本身。

## 2. 当前业务口径

### 2.1 访视和资料项

- 已应用试验方案的项目，以方案生成的访视和资料项为准。
- 无已应用方案时，才使用系统默认访视模板兜底。
- 资料包识别必须二次匹配当前受试者已有 `subject_items`，不能自动落到当前受试者不存在的旧资料项。
- “若有”资料需要上传并审核通过，或明确声明无此材料，才计为完整。

### 2.2 字段提取

- 字段提取已经正式落地，不再属于后置规划。
- 提取结果绑定文件版本或 PDF 资料包片段，保留原值、规范值、来源页、置信度和核查状态。
- 日期和时间允许多种人工输入写法，展示时归一为 `YYYY/MM/DD` 或 `YYYY/MM/DD HH:mm`。
- 自动提取失败时仍生成可人工补录的字段骨架。

### 2.3 图像数据

- 图像类型为 `raw`、`enhanced`、`report`。
- 原始图像和增强图像使用 zip 上传，单文件业务上限为 `4GB`。
- 增强图像必须在原始图像上传后才能上传。
- 系统保留原 zip，并将内容安全解压到版本目录，统计图片数量、总大小和扩展名分布。

### 2.4 OCR 环境

- Mac 本地开发：Apple Vision OCR，默认端口 `8048`。
- Linux 生产：PaddleOCR GPU。
- 应用版本发布默认只替换 backend/frontend，不重建、不替换生产 OCR GPU 基线。

### 2.5 V4 临床数据资产化

- V4 设计以资产对象为中心：`Project`、`Subject`、`Snapshot`、`Image Evidence`、`ReportImage`、`AlgorithmRun`、`Dataset`。
- 正式研发交付必须基于不可变 Snapshot，禁止把实时库状态直接作为训练或研发交付来源。
- JSON 是 Snapshot 的导出形式，保留业务编码标识，如项目、中心和筛选号，不导出姓名、身份证等直接身份信息。
- V4.1 已完成 Subject Snapshot 基线：V4.1.0 落地 `subject_snapshots` 数据模型，V4.1.1 落地生成前校验和 `snapshot_quality_checks`，V4.1.2 落地单受试者 `released_snapshot` 生成和 JSON 文件固化，V4.1.3 落地 Snapshot JSON 下载/导出，V4.1.4 落地历史管理和前端入口，V4.1.5 完成系列收口和 V4.2 衔接。
- V4.2 建立 Image Evidence Index：V4.2.0 已落地数据模型，V4.2.1 已完成 PDF 报告图片索引，V4.2.2 已完成 Landmark 反查、标注图识别和前端复核，V4.2.3 负责 Image Evidence Index 导出；不做全量逐图索引。
- V4.3 以后病灶草稿、算法结果、训练/研究数据集构建按 V4.1/V4.2 反馈再细化；短期不把病灶资产作为必须落地范围。

## 3. 文档索引

| 文档 | 用途 |
| --- | --- |
| `README.md` | 当前系统能力、统一业务口径和本地运行入口 |
| `docs/handover.md` | 离职/接手交接主文档，串联背景、模块、运行、验证、发布和 V4.2.2 当前状态 |
| `docs/process.md` | 版本边界、历史记录、验收状态和生产变更原则 |
| `docs/version_history.md` | 版本号、日期和一句话时间线 |
| `docs/tech_plan.md` | 当前技术架构、模块边界和关键实现原则 |
| `docs/database_field_design.md` | 已落库表、字段关系和后续候选字段 |
| `docs/deploy_migration.md` | 应用发布包制作、生产替换、验证和回滚 |
| `V4落地方案.md` | V4 短期落地路线、资产化原则和冲突处理优先口径 |

文档冲突时，当前口径优先级为：实际代码与数据库迁移 > `V4落地方案.md` 的短期 V4 口径 > `README.md` > 专题文档中的当前基线 > 明确标记的历史记录。`总体规划26-27.md` 属于中长期平台蓝图，`巡常临床高质量数据集建设指导方案（V1.0）.md` 属于补充参考，不反向约束 V4.1/V4.2。

## 4. 本地开发

启动开发数据库：

```bash
docker compose -f deploy/docker-compose.dev.yml up -d postgres
```

启动后端：

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

启动前端：

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

按需启动本地 OCR：

```bash
MAC_VISION_OCR_PORT=8048 backend/.venv/bin/python scripts/mac_vision_ocr_api.py
```

默认地址：

- 前端：http://127.0.0.1:5173
- 后端健康检查：http://127.0.0.1:8000/api/health
- 后端 OpenAPI：http://127.0.0.1:8000/docs
- OCR 健康检查：http://127.0.0.1:8048/health

开发默认管理员：`admin` / `Admin@123456`。

## 5. 验证命令

```bash
cd backend
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/alembic current
.venv/bin/alembic check

cd ../frontend
npm run lint
npm run build
```

V3.5.5 重点回归：

```bash
cd backend
.venv/bin/python -m pytest tests/test_pdf_packets.py tests/test_image_data.py tests/test_document_extracted_fields.py
```

V4.0.0 文档验收：

```bash
rg -n "V4.0.0|Subject Snapshot|Image Evidence|Snapshot JSON|AlgorithmRun|Dataset" README.md docs/*.md
```

V4.1.5 收口验收：

```bash
rg -n "V4.1.5|V4.2|Image Evidence|subject_snapshots|snapshot_quality_checks" README.md docs/*.md
```

V4.2.0 数据模型验收：

```bash
cd backend
.venv/bin/python -m pytest tests/test_image_evidence_index.py
.venv/bin/python -m ruff check app/models/image_evidence.py app/schemas/image_evidence.py tests/test_image_evidence_index.py
```

V4.2.1 报告图片索引验收：

```bash
cd backend
.venv/bin/python -m pytest tests/test_report_image_index.py tests/test_image_evidence_index.py
.venv/bin/python -m ruff check app/services/report_image_index.py app/api/v1/endpoints/image_data.py tests/test_report_image_index.py
```

V4.2.2 Landmark 反查验收：

```bash
cd backend
.venv/bin/python -m pytest tests/test_landmark_index.py tests/test_report_image_index.py tests/test_image_data.py
.venv/bin/python -m ruff check app/services/landmark_index.py app/api/v1/endpoints/image_data.py tests/test_landmark_index.py

cd ../frontend
npm run lint
npm run build
```

## 6. 生产发布

- 生产项目目录：`/data/jiafei/clinical-data-system`。
- 应用发布包只包含 backend/frontend 镜像、`docker-compose.app-release.yml` 和 SHA256 校验文件。
- 替换应用时必须使用 `--no-build --no-deps backend frontend`，避免连带重建 OCR、PostgreSQL 或其他服务。
- 发布前必须备份 PostgreSQL 和文件存储，发布后验证前端、后端和 OCR 健康状态。

完整命令见 `docs/deploy_migration.md`。
