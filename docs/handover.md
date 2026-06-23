# clinical-data-system 项目交接说明

本文面向后续接手 `clinical-data-system` 的研发、测试和运维同事。目标不是替代所有专题文档，而是把项目背景、当前状态、运行方式、关键模块、发布边界和 V4.2.2 最新工作串成一条能接手的主线。

如果只看一份文档，请先看本文；如果要查细节，再跳到对应专题文档。

## 1. 项目定位

`clinical-data-system` 是巡常临床数据智能管理系统，服务临床研究资料收集、质量核查、PDF 在线审阅、资料包 OCR 识别、字段提取、数据看板和图像数据管理。

系统当前有两条并行口径：

- 生产应用基线：`V3.5.5`。生产已经覆盖 V1 到 V3.5.5 的业务能力，不再使用“V3 只是内部迭代、生产只交付 V1/V2”的旧说法。
- V4 研发基线：以临床数据资产化为目标，逐步建立 Subject Snapshot、Image Evidence Index、Landmark Image 和后续算法研发数据交付能力。

接手时最容易踩坑的是把“已生产交付”和“V4 研发基线”混在一起。当前写法应保持：

- `V3.5.5` 是当前生产基线。
- `V4.0.0` 是资产化和 Snapshot/Schema 的规划基线，不是一个已经新增 API 或前端交互的生产功能版本。
- `V4.1.5` 已完成 Subject Snapshot 系列收口。
- `V4.2.2` 已完成 Landmark Image 反查与复核，但不包含 Image Evidence 导出、病灶资产或训练集构建。

## 2. 首读文档地图

| 文档 | 什么时候看 |
| --- | --- |
| `README.md` | 项目快速入口、当前版本口径、本地启动和基础验证命令。 |
| `docs/handover.md` | 接手项目时从头理解系统，也就是本文。 |
| `docs/process.md` | 查版本边界、验收状态、历史决策和下一步计划。 |
| `docs/tech_plan.md` | 查架构、模块边界、技术原则、V4 资产化方案。 |
| `docs/database_field_design.md` | 查数据库表、字段关系和后续候选字段。 |
| `docs/deploy_migration.md` | 查开发到生产迁移、打包、上线、回滚和生产校验。 |
| `docs/version_history.md` | 查简短版本时间线。 |

文档冲突时，优先级为：实际代码与数据库迁移 > `V4落地方案.md` 的短期 V4 口径 > `README.md` > 专题文档中的当前基线 > 明确标记的历史记录。

## 3. 当前状态

### 3.1 生产主线

生产侧当前应按 `V3.5.5` 理解，核心能力包括：

- 项目、中心、用户、角色和权限管理。
- 试验准备、试验进行、试验结束三阶段资料管理。
- 受试者资料项、文件版本、审核记录、整改任务闭环。
- PDF 在线预览、画框批注、重传和复审。
- PDF 资料包 OCR、智能切分、人工修正、确认入库。
- 项目方案 PDF 解析、草稿修正、访视和资料项配置应用。
- 文件字段提取、人工核查、规范值展示和 SSU 回写。
- 数据驾驶舱、Excel 导入导出、项目和中心维度汇总。
- 原始图像、增强图像和电子报告上传、解包、统计和版本留痕。

### 3.2 V4 研发主线

V4 的方向是临床数据资产化，核心不是单纯导出 JSON，而是形成可追溯、可冻结、可复核的研发交付对象。

当前已完成：

- V4.1 Snapshot：`subject_snapshots`、生成前校验、单受试者 released snapshot、JSON 固化和下载、历史管理、前端入口。
- V4.2 Image Evidence 数据模型：`image_evidence_index` 作为图像证据索引主表，不额外新增逐图数据库表。
- V4.2.1 报告图片索引：PDF 电子报告上传后自动提取内嵌图片，生成 `report_package` 和 `report_image`。
- V4.2.2 Landmark 反查：报告图经过时长 → 增强图候选匹配 → raw 同帧回溯；同时识别医生绿色圈注并生成 `marked_image`。

尚未完成，不要在文档或验收里写成已完成：

- V4.2.3 Image Evidence Index 导出。
- 病灶资产、病灶草稿、算法结果资产。
- 训练集或研究数据集构建。
- Snapshot JSON 中直接扩展 Image Evidence 明细。

## 4. 模块地图

### 4.1 项目、中心、受试者

项目是最高业务归属，中心隶属于项目，受试者隶属于项目和中心。权限控制也围绕项目/中心范围展开。

接手要点：

- 不要把筛选号、报告显示编号、胶囊 ID 混为一个字段。
- 例如 V4.2.2 样例中，受试者筛选号是 `08008`，报告显示名是 `CCE-138`，胶囊 ID 是 `PCB250601027`。
- 资料项和图像记录都应该以受试者为归属中心。

### 4.2 资料项和文件版本

受试者资料项来自项目方案或默认模板。已应用试验方案的项目，以方案生成的访视和资料项为准；没有已应用方案时才使用默认模板兜底。

文件上传后会形成版本、审核记录、操作日志和整改闭环。资料包识别时必须二次匹配当前受试者已有 `subject_items`，不能把历史旧资料项自动落到当前受试者身上。

### 4.3 PDF 资料包和字段提取

PDF 资料包能力包含 OCR、智能切分、人工拆分/合并/修正、确认入库。字段提取绑定文件版本或资料包片段，保留原值、规范值、来源页、置信度和核查状态。

自动提取失败时仍要生成可人工补录的字段骨架，不能因为 OCR 不稳定就丢掉后续人工核查入口。

### 4.4 数据驾驶舱

驾驶舱用于项目/中心维度汇总和 Excel 导入导出。它不是 V4 资产化的核心，但属于当前生产能力的一部分，生产发布前需要避免影响既有看板。

### 4.5 图像数据

图像数据分三类：

- `raw`：胶囊原始图像包，zip 上传。
- `enhanced`：增强图像包，zip 上传，要求原始图像先上传。
- `report`：电子报告，当前 Landmark 反查只支持 PDF。

系统保留原 zip，同时安全解压到版本目录，统计图片数量、总大小和扩展名分布。图像上传单文件业务上限当前为 `4GB`，后端配置、生产 Nginx、前端提示和部署文档需要保持一致。

### 4.6 Subject Snapshot

Snapshot 是 V4 的稳定资产对象。正式研发交付必须基于不可变 Snapshot，禁止直接把实时库状态作为算法训练或研发交付来源。

JSON 是 Snapshot 的导出形式，不是核心资产本身。导出时保留项目、中心、筛选号等业务编码，不导出姓名、身份证等直接身份信息。

### 4.7 Image Evidence

Image Evidence 使用 `image_evidence_index` 承载不同证据类型：

- `report_package`：电子报告包级证据。
- `report_image`：PDF 内嵌报告图片。
- `marked_image`：医生绿色圈注报告图，和 `report_image` 共用物理图片。
- `landmark_image`：从报告时间点反查到的 raw 同帧证据。

V4.2 不做全量逐图数据库索引。Landmark 反查只按报告时间点生成少量候选，候选、分数、版本和人工确认信息保存在 `payload_json`。

## 5. 技术架构

### 5.1 后端

后端位于 `backend/app`，基于 FastAPI、SQLAlchemy、Alembic 和 PostgreSQL。

常用位置：

- `backend/app/api/v1/endpoints`：HTTP API。
- `backend/app/models`：数据库 ORM。
- `backend/app/schemas`：Pydantic schema。
- `backend/app/services`：业务服务。
- `backend/app/core`：配置、权限、文件安全等基础能力。
- `backend/alembic`：数据库 migration。
- `backend/tests`：后端测试。

### 5.2 前端

前端位于 `frontend/src`，基于 React、TypeScript 和 Vite。

常用位置：

- `frontend/src/pages`：页面。
- `frontend/src/services`：API 封装。
- `frontend/src/types`：前端类型。
- `frontend/src/stores`：状态管理。

### 5.3 数据库和文件存储

PostgreSQL 保存业务状态、索引、权限和操作日志。文件存储保存上传原包、解压文件、报告图片、Snapshot JSON 等物理文件。

生产发布时，应用代码和镜像可以替换，但 PostgreSQL 数据卷和文件存储不是应用发布包的一部分。上线前必须备份数据库和文件存储，不能把“替换代码目录”理解成“替换全部业务数据”。

### 5.4 OCR

OCR 有两个环境口径：

- Mac 本地开发：Apple Vision OCR，默认 `8048` 端口，仅用于本地调试。
- Linux 生产：PaddleOCR GPU，是生产基线。

应用版本发布默认只替换 backend/frontend，不重建、不替换生产 OCR GPU 基线。

## 6. 本地开发流程

### 6.1 启动数据库

```bash
docker compose -f deploy/docker-compose.dev.yml up -d postgres
```

### 6.2 启动后端

```bash
cd backend
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

如果本机使用 Python 3.12 独立环境，也可以按实际环境使用 `.venv312/bin/python`。关键是安装 `backend/requirements.txt` 和 `backend/requirements-dev.txt` 中的依赖。

### 6.3 启动前端

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173
```

### 6.4 按需启动 OCR

```bash
MAC_VISION_OCR_PORT=8048 backend/.venv/bin/python scripts/mac_vision_ocr_api.py
```

### 6.5 默认地址和账号

| 项 | 默认值 |
| --- | --- |
| 前端 | `http://127.0.0.1:5173` |
| 后端健康检查 | `http://127.0.0.1:8000/api/health` |
| 后端 OpenAPI | `http://127.0.0.1:8000/docs` |
| OCR 健康检查 | `http://127.0.0.1:8048/health` |
| 开发管理员 | `admin` / `Admin@123456` |

## 7. 关键目录和不要提交的内容

| 路径 | 说明 |
| --- | --- |
| `backend/app` | 后端应用代码。 |
| `backend/tests` | 后端测试。 |
| `frontend/src` | 前端应用代码。 |
| `docs` | 当前项目文档。 |
| `deploy` | Docker、Linux、生产迁移相关文件。 |
| `scripts` | 本地脚本、验收脚本、打包辅助脚本。 |
| `V4材料/` | 本地真实样例材料，只用于调试和验收，不提交 Git。 |

`V4材料/` 体积很大，包含真实样例 raw/enhanced/report。它应该被 `.gitignore` 排除。提交前务必检查：

```bash
git status --short
```

不要把真实图像样例、生产导出文件、数据库 dump 或本机临时 zip 提交到代码仓库。

## 8. V4.2.2 Landmark Image 交接重点

### 8.1 业务目标

V4.2.2 解决的是报告图像证据反查问题：医生报告里给出的图，不应该只停留在 PDF 截图层面，而要能定位到增强图，并回溯到 raw 同帧。

链路为：

1. PDF 电子报告上传后，V4.2.1 提取内嵌图片为 `report_image`。
2. OCR 读取报告图角标中的经过时长，例如 `00:00:33`。
3. 从 raw 包内 `ispLog.txt` 获取首帧时间，文件名解析作为回退。
4. 用首帧时间加报告经过时长，生成目标秒和相邻秒候选。
5. 用 OpenCV/NumPy 对报告图和增强候选做遮罩相似度匹配。
6. 用相同文件名找到 raw 同帧。
7. 写入 `landmark_image`，并按医生绿色圈注写入 `marked_image`。

### 8.2 状态口径

Landmark 单条证据的匹配状态：

- `resolved`：唯一高置信匹配。
- `approx_matched`：存在候选但需要人工复核。
- `unresolved`：无候选或无法定位。
- `not_supported`：资料格式或条件不支持。

接口返回的汇总状态：

- `waiting_for_assets`
- `indexed`
- `partial`
- `unresolved`
- `not_supported`
- `failed`

### 8.3 权限

读取和预览继续使用 `image_data:read`。重建和人工确认使用 `image_data:manage_evidence`。

只读角色不应具备重建和确认权限。图像业务角色、项目/中心管理类角色可以做复核操作。

### 8.4 API

核心 API：

- `POST /api/image-data/{report_record_id}/landmarks/index`：显式重建 Landmark。
- `GET /api/image-data/{report_record_id}/landmarks`：查询状态、统计和分组结果。
- `POST /api/image-evidence/{landmark_id}/confirm`：人工确认候选。
- `GET /api/image-evidence/{evidence_id}/preview?variant=report|enhanced|raw`：预览报告图、增强图或 raw 同帧。

### 8.5 前端入口

前端在图像数据的电子报告行展开区显示 Landmark 复核面板。面板应展示：

- 报告图。
- 增强命中图。
- raw 同帧图。
- 消化道位置。
- 报告经过时间。
- 状态和分数。
- 是否识别到绿色圈注。
- 重建、候选切换、人工确认操作。

### 8.6 武汉中心 08008 验收样例

样例口径：

- 项目：`C200CN`
- 中心：`08` / 武汉大学人民医院
- 受试者：`08008`
- 分组：实验组
- 性别：女
- 年龄：55
- 报告显示编号：`CCE-138`
- 胶囊 ID：`PCB250601027`

资料结构：

- raw：按 `08008/PCB250601027/...` 打包。
- enhanced：按 `08008/...` 打包。
- report：`CCE-138.pdf`。

期望结果：

- raw 图像数量：`60,728`
- enhanced 图像数量：`60,728`
- 报告 11 个时间点全部命中增强图。
- 11 个时间点都能关联 raw 同帧。
- 绿色圈注图建立 `marked_image`，自然绿色组织色不得误判为圈注。

本地验收脚本：

```bash
backend/.venv312/bin/python scripts/import_v422_08008.py
```

该脚本依赖本机样例包和本地开发数据库。样例包属于本地验收材料，不提交 Git。

## 9. 测试和验收

### 9.1 通用验证

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

### 9.2 V4.2.2 重点验证

```bash
cd backend
.venv/bin/python -m pytest tests/test_landmark_index.py tests/test_report_image_index.py tests/test_image_evidence_index.py tests/test_image_data.py
.venv/bin/python -m ruff check app/services/landmark_index.py app/services/report_image_index.py app/api/v1/endpoints/image_data.py app/schemas/image_evidence.py tests/test_landmark_index.py tests/test_report_image_index.py tests/test_image_data.py

cd ../frontend
npm run lint
npm run build
```

### 9.3 已知测试噪音处理

如果全量 pytest、全量 ruff 或 Alembic 检查失败，不要直接认定当前功能坏了。先区分：

- 是否是当前改动涉及的目标测试失败。
- 是否是历史遗留 lint、历史测试漂移或本地数据库 schema 漂移。
- 是否是本地 OCR、PostgreSQL、端口权限或沙箱限制导致的环境失败。

交付时至少要给出目标测试结果、前端构建结果和无法完成项的明确原因。

## 10. 生产发布交接

生产迁移细节以 `docs/deploy_migration.md` 为准。这里保留必须记住的原则：

- 生产项目目录：`/data/jiafei/clinical-data-system`。
- 应用发布包只包含 backend/frontend 镜像、compose 发布文件和校验文件。
- 替换应用时使用 `--no-build --no-deps backend frontend`，避免连带重建 OCR、PostgreSQL 或其他服务。
- 发布前备份 PostgreSQL 和文件存储。
- 发布后验证前端、后端、OCR 健康状态。
- 如果发布包含数据库 migration，必须先确认备份、迁移顺序和回滚策略。

生产不是把开发目录整体复制过去。生产数据库和文件存储是持久化业务资产，不能被应用包覆盖。

## 11. 后续路线

短期建议按以下顺序推进：

1. V4.2.3：Image Evidence Index 导出，明确导出内容、权限和与 Snapshot 的关系。
2. V4.2.x 稳定化：更多真实中心/受试者样例回归，补充 OCR 异常、Office 报告、不完整资料包等边界。
3. V4.3：病灶草稿、算法结果和训练/研究数据集构建方案。
4. 生产侧稳定化：继续收敛全量测试、ruff 和 Alembic drift，减少交付时的历史噪音。

不要提前把 V4.3 的病灶资产或训练集写成 V4.2.2 已交付能力。

## 12. 接手人 checklist

### 第一天：把项目跑起来

- [ ] 阅读 `README.md` 和本文。
- [ ] 启动 PostgreSQL。
- [ ] 启动后端和前端。
- [ ] 使用 `admin` / `Admin@123456` 登录。
- [ ] 打开后端 `/api/health` 和 `/docs`。
- [ ] 跑一次后端目标测试和前端 build。

### 第一周：能改一个小功能

- [ ] 找到后端 API、service、schema、model 的对应关系。
- [ ] 找到前端 page、service、type 的对应关系。
- [ ] 能解释项目/中心/受试者/资料项/文件版本之间的关系。
- [ ] 能解释 raw、enhanced、report 三类图像资料和 Image Evidence 的关系。
- [ ] 能在本地复现一个 V4.2.2 Landmark 查询或重建流程。

### 发布前：不要动错生产资产

- [ ] 明确本次发布是否包含数据库 migration。
- [ ] 备份 PostgreSQL。
- [ ] 备份或确认文件存储挂载。
- [ ] 不重建 OCR GPU 服务，除非本次任务明确要求。
- [ ] 不覆盖生产数据库卷和文件存储。
- [ ] 发布后检查前端、后端、OCR 健康状态。
- [ ] 抽查核心业务页面和本次改动页面。

## 13. 常见坑

- 把 `V4.0.0` 写成已实现功能。正确说法：规划/资产化基线。
- 把 `CCE-138` 当成筛选号。正确说法：08008 是筛选号，CCE-138 是报告显示编号。
- 把 `V4材料/` 提交进 Git。正确做法：只本地使用，保持 ignore。
- 图像证据想建全量逐图数据库索引。当前 V4.2 口径是不做全量逐图索引。
- 发布应用时误伤 OCR、PostgreSQL 或文件存储。应用发布只替换 backend/frontend。
- 看到全量检查失败就改一大片历史代码。应先定位是否和当前任务相关，避免扩大变更范围。
