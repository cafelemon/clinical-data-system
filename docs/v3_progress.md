# V3 任务进度表

本文只记录 V3 任务推进状态，不改写主方案文档主体。每完成一个阶段后，更新“已完成什么、验证结果、下一步做什么、当前风险”。

## 1. 当前阶段与目标

当前阶段：P0 资料包切分闭环。

阶段目标：

- 以 `010005.pdf` 全 27 页作为第一优先级样本基准，不再只验收前 12 页。
- 后端完成页面分类、自动切分、人工拆分/合并/修改/确认冻结、重新识别保护和调试报告接口。
- 前端完成资料包页面上的拆分、合并、页码/资料项修正、确认/解除确认、强制重新识别和识别原因查看。
- 保留现有 API、表结构和资料包入库路径。
- 本阶段不做字段抽取，不进入 P1，不改生产 OCR 方案。

## 2. 任务清单与状态

| 任务 | 状态 | 说明 |
| --- | --- | --- |
| 新增 V3 进度表 | 已完成 | 新增 `docs/v3_progress.md`，后续阶段持续更新。 |
| P0.1 标题强识别收尾 | 已完成 | 已补齐长标题优先、标题位置感知、强标题切段和 debug reason。 |
| P0.2 页面文本标准化 | 已完成 | 已拆出 `page_text_normalizer.py`，分类统一使用标准化文本并保留原始 OCR。 |
| 后端页面分类模块 | 已完成 | 新增文本标准化、文档类型注册表、页级分类器。 |
| Segment builder 增强 | 已完成 | 按页级结果合并连续资料项，强标题切段，多页资料允许延续。 |
| `analyze_packet` 接入新 builder | 已完成 | 保留现有 API 和表结构，继续写入现有 segment 字段。 |
| 本地 debug JSON 输出 | 已完成 | 写入 `_debug/pdf-packet-analysis/latest.json` 和 packet 级报告。 |
| `010005.pdf` 全 27 页后端回归 | 已完成 | 已新增并通过 27 页 API 级切分测试。 |
| P0.7 重新识别保护 | 已完成 | 默认保留人工确认、人工修改和已上传片段；`force=true` 才覆盖人工结果。 |
| P0.8 人工拆分 API | 已完成 | 支持一个片段拆成多个连续子片段，断裂/重叠/越界返回 400。 |
| P0.9 人工合并 API | 已完成 | 只允许同包内连续且未上传片段合并。 |
| P0.10 人工确认/解除确认 API | 已完成 | 确认写入 `manually_confirmed`，解除确认回到 `pending_review`。 |
| P0.11 analysis-report API | 已完成 | 返回最近一次 packet debug JSON，包含 pages、segments、raw/normalized/head/tail 和 reason。 |
| P0.12 前端人工闭环 | 已完成 | 资料包页面可拆分、合并、修改、确认/解除确认、查看识别原因、默认/强制重新识别。 |
| `010001.pdf` 第二样本回归 | 未开始 | 待 `010005` 主规则稳定后加入。 |
| 字段抽取 | 未开始 | 不属于 P0 当前后端阶段。 |

## 3. 本轮完成记录

### 2026-05-13

已完成：

- 新增 `backend/app/services/pdf_packet_classifier.py`。
- 新增 `backend/app/services/page_text_normalizer.py`。
- 增加 OCR 文本标准化，处理空白、标点、全角半角、页眉页脚/水印噪声、日期格式和部分常见 OCR 错字。
- P0.1 标题强识别完成收尾：长标题优先、专有标题优先、标题位置影响置信度、强标题强制切段。
- 建立 P0 文档类型注册表，覆盖：
  - 知情同意书
  - 知情同意书交接表
  - CT报告
  - HIS记录
  - 入组审核记录表
  - 生命体征记录表
  - 舒适度评价表
  - 图像质量评价表
  - 设备常用功能/设备稳定性复合页
  - 其他次要指标评价表
  - 中心阅片评价结果表
  - 胶囊内镜报告
- `analyze_packet` 已接入新 segment builder，不新增 migration。
- 新增最近一次分析 debug JSON，记录每页原始 OCR、标准化文本、head/tail lines、分类原因和最终 segment 合并原因。
- 新增 `010005.pdf` 全 27 页后端集成测试。
- 使用本机 Apple Vision OCR 对真实 `010005.pdf` 完成端到端复验，真实 OCR 输出下切出 `12 segments, 27 text/OCR pages`。
- 补齐 P0.7-P0.12：`reanalyze`、`split`、`merge`、`confirm`、`unlock`、`analysis-report` API 均已接入现有资料包权限、scope 校验和 `record_operation`。
- `analyze_packet` 重新识别默认保留人工确认、人工修改和已上传片段，并将新自动结果裁剪避开保留页码；强制重新识别才覆盖人工结果。
- `PdfPacketsPage` 已从旧的只展示识别片段体验扩展到完整 P0 操作闭环：12 段基准可在页面查看、拆分、合并、修正、确认冻结和查看识别原因。
- 前端 `pdf-packets` service/types 已扩展 P0 API 和调试报告类型，保持原有上传、分析、segment CRUD 和入库接口兼容。

## 4. 样本验收记录

### 4.1 `010005.pdf`

当前状态：已完成 P0 切分闭环测试。

验证命令：

```bash
cd /Users/jiafei/workspace/clinical-data-system/backend
.venv/bin/python -m ruff check app/services/page_text_normalizer.py app/services/pdf_packet_classifier.py app/services/pdf_packets.py app/api/v1/endpoints/pdf_packets.py app/schemas/pdf_packet.py tests/test_pdf_packets.py
.venv/bin/python -m pytest tests/test_pdf_packets.py::test_pdf_packet_splits_010005_full_27_pages_by_v3_p0_baseline
.venv/bin/python -m pytest tests/test_pdf_packets.py
curl -sS http://127.0.0.1:8048/health
cd /Users/jiafei/workspace/clinical-data-system
cd frontend && npm run build
cd /Users/jiafei/workspace/clinical-data-system
git diff --check
```

验证结果：

- Ruff 检查通过：`All checks passed!`。
- `git diff --check` 通过。
- 单测 `test_pdf_packet_splits_010005_full_27_pages_by_v3_p0_baseline` 通过。
- `test_pdf_packets.py` 全部通过：`9 passed`。
- 前端 `npm run build` 通过。
- 当前测试基准切出 `12 segments, 27 text/OCR pages`。
- 本机 Apple Vision OCR 服务健康检查返回 `service=mac-vision-ocr-api`。
- 真实 `010005.pdf` 端到端上传分析通过，真实 OCR 输出下切出 `12 segments, 27 text/OCR pages`。
- 人工闭环验收通过：拆分一个片段为连续子片段、合并连续片段、确认冻结、解除确认、默认重新识别保留人工结果、强制重新识别覆盖人工结果。
- 边界验收通过：页码重叠修改返回 400，断裂/重叠拆分返回 400，非连续合并返回 400，已上传片段参与合并返回 400。
- `analysis-report` 返回页级 `raw_text`、`normalized_text`、`head_lines`、`tail_lines` 和 segment `reason`。

当前切分结果：

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

关键断言：

- 前 12 页满足 `1-1`、`2-2`、`3-3`、`4-12`。
- `13-15` 不再归到“知情同意书”。
- `20-23` 不再误归到“肠道准备情况”。
- `25-26` 不再误归到“肠道准备情况”。
- `22-23` 默认映射到“其他次要指标评价表”，debug reason 保留“设备常用功能/设备稳定性”命中特征。
- 前端资料包页面不再停留在旧 9 类展示体验，类型与页面操作已覆盖当前 `010005.pdf` 的 12 段 P0 基准。
- 手工确认片段后，默认重新识别不丢失确认结果；强制重新识别经过二次确认入口并覆盖人工结果。

偏差记录：

- 暂无测试偏差。
- 真实 OCR 首次复验曾出现 `20 segments` 和 `22-24` 合并偏差，已通过 P0.1/P0.2 规则收紧修复。
- 当前真实 OCR 复验结果已与 P0 全量基准一致。

### 4.2 `010001.pdf`

当前状态：未开始。

计划：

- 在 `010005.pdf` 主规则稳定后加入第二样本回归。
- 重点观察 `010001.pdf` 是否存在与 `010005.pdf` 不同的标题、页眉、水印或 OCR 错字。

## 5. 下一步计划

1. 加入 `010001.pdf` 第二样本回归，验证规则是否可以跨样本复用。
2. 继续观察真实 OCR 噪声，如出现误分，优先补充标准化与负向词，不改表结构。
3. P0 通过第二样本和人工验收后，再进入 P1 字段抽取，不在 P0 内提前扩表。

## 6. 当前问题与风险

- 当前 27 页测试已覆盖 P0 基准 OCR 文本，真实 Apple Vision OCR 也已完成一次端到端复验；但真实 OCR 输出仍可能随系统版本、图片质量或识别参数存在轻微漂移。
- `22-23` 是复合表单，当前按既有资料项默认映射到“其他次要指标评价表”；如领导要求拆得更细，后续可能需要新增或调整资料项结构。
- 当前 debug JSON 写在本地文件存储目录下，并通过 `analysis-report` 作为研发排查接口返回；它不是正式审计历史。
- P0 人工确认暂时复用 `status` 与 `operation_logs`，没有 `reviewed_by/reviewed_at/revision` 等正式审计字段；如需正式审计，需要进入 P0+ 或 P1 前置 migration。
