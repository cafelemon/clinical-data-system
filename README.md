# 巡常临床数据智能管理系统

`clinical-data-system` 是面向临床研究资料收集、质量核查、PDF 审阅、资料包识别和图像数据管理的内部业务系统。

当前生产基线为 `V3.5.5`。当前生产交付已覆盖 V1 至 V3.5.5 的应用能力，不再使用“V3 仅为内部迭代、生产只交付 V1/V2”的旧口径。

V4.0.0 进入规划基线：大版本 4 定位为服务研发中心算法需求的受试者级字段化 JSON 证据包。V4.0.0 只落地方案、schema、差距和路线，不新增后端 API、数据库 migration 或前端交互。

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
- V4.0.0 研发证据包规划：面向每名受试者生成 subject JSON，组织临床树、字段索引、图像索引和算法结果扩展位。

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
- 原始图像和增强图像使用 zip 上传，单文件业务上限为 `3GB`。
- 增强图像必须在原始图像上传后才能上传。
- 系统保留原 zip，并将内容安全解压到版本目录，统计图片数量、总大小和扩展名分布。

### 2.4 OCR 环境

- Mac 本地开发：Apple Vision OCR，默认端口 `8048`。
- Linux 生产：PaddleOCR GPU。
- 应用版本发布默认只替换 backend/frontend，不重建、不替换生产 OCR GPU 基线。

### 2.5 V4 JSON 证据包

- subject JSON 定位为研发证据包，不是单纯审计包，也不是只给训练的轻量表。
- JSON 保留业务编码标识，如项目、中心和筛选号，不导出姓名、身份证等直接身份信息。
- JSON 未来按不可变快照版本管理，记录 schema、生成时间、来源版本和文件 hash，保障训练复现。
- 图像不内联进 JSON，只记录原包、解压目录、逐图相对路径和 hash/size 等索引信息。
- 算法病灶识别、模型版本和标注框等结果在 V4.0.0 只预留扩展位，等算法输出格式明确后细化。

## 3. 文档索引

| 文档 | 用途 |
| --- | --- |
| `README.md` | 当前系统能力、统一业务口径和本地运行入口 |
| `docs/process.md` | 版本边界、历史记录、验收状态和生产变更原则 |
| `docs/version_history.md` | 版本号、日期和一句话时间线 |
| `docs/tech_plan.md` | 当前技术架构、模块边界和关键实现原则 |
| `docs/database_field_design.md` | 已落库表、字段关系和后续候选字段 |
| `docs/deploy_migration.md` | 应用发布包制作、生产替换、验证和回滚 |

文档冲突时，当前口径优先级为：实际代码与数据库迁移 > `README.md` > 专题文档中的当前基线 > 明确标记的历史记录。

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
rg -n "V4.0.0|schema_version|fields_index|images_index|algorithm_runs|research-json" README.md docs/*.md
```

## 6. 生产发布

- 生产项目目录：`/data/jiafei/clinical-data-system`。
- 应用发布包只包含 backend/frontend 镜像、`docker-compose.app-release.yml` 和 SHA256 校验文件。
- 替换应用时必须使用 `--no-build --no-deps backend frontend`，避免连带重建 OCR、PostgreSQL 或其他服务。
- 发布前必须备份 PostgreSQL 和文件存储，发布后验证前端、后端和 OCR 健康状态。

完整命令见 `docs/deploy_migration.md`。
