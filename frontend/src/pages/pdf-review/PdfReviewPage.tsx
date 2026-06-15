import axios from "axios";
import * as pdfjsLib from "pdfjs-dist";
import pdfWorkerUrl from "pdfjs-dist/build/pdf.worker.mjs?url";
import {
  ArrowLeft,
  Check,
  ClipboardCheck,
  ChevronLeft,
  ChevronRight,
  EyeOff,
  LocateFixed,
  Minus,
  MousePointer2,
  Plus,
  RotateCcw,
  RotateCw,
  Save,
  SquarePen,
  Trash2,
} from "lucide-react";
import { PointerEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useParams, useSearchParams } from "react-router-dom";

import { DocumentExtractedFieldsPanel } from "@/components/document-fields/DocumentExtractedFieldsPanel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { SelectField, TextAreaField } from "@/components/ui/form";
import { buildRestoreState, type NavigationOriginState } from "@/lib/navigation-origin";
import { filesApi } from "@/services/files";
import { pdfReviewApi } from "@/services/pdf-review";
import { useAuthStore } from "@/stores/auth-store";
import type { PdfAnnotation, PdfReviewFile } from "@/types/pdf-review";

pdfjsLib.GlobalWorkerOptions.workerSrc = pdfWorkerUrl;

type PdfJsModule = typeof pdfjsLib;

type DraftRect = {
  page_no: number;
  x: number;
  y: number;
  width: number;
  height: number;
};

type Point = {
  x: number;
  y: number;
};

type Rotation = 0 | 90 | 180 | 270;

type NormalizedRect = {
  x: number;
  y: number;
  width: number;
  height: number;
};

const issueTypes = [
  { value: "missing_page", label: "缺页" },
  { value: "wrong_page", label: "错页" },
  { value: "unclear_scan", label: "扫描不清晰" },
  { value: "inconsistent_info", label: "信息不一致" },
  { value: "missing_signature", label: "签名缺失" },
  { value: "missing_stamp", label: "盖章缺失" },
  { value: "missing_date", label: "日期缺失" },
  { value: "wrong_subject", label: "受试者不匹配" },
  { value: "wrong_document", label: "资料类型不匹配" },
  { value: "other", label: "其他" },
];

const severityLabels = {
  low: "一般",
  medium: "重要",
  high: "严重",
};

const statusLabels: Record<string, string> = {
  open: "待处理",
  task_created: "已生成任务",
  submitted: "待复审",
  resolved: "已解决",
  rejected: "复审退回",
  closed: "已关闭",
};

const taskStatusLabels: Record<string, string> = {
  pending: "待整改",
  processing: "处理中",
  submitted: "待复审",
  returned: "再次退回",
  closed: "已关闭",
  cancelled: "已取消",
};

function toneForSeverity(severity: string) {
  if (severity === "high") return "danger";
  if (severity === "medium") return "warning";
  return "neutral";
}

function toneForTaskStatus(status: string | null) {
  if (status === "closed") return "success";
  if (status === "returned" || status === "pending") return "danger";
  if (status === "submitted") return "warning";
  return "neutral";
}

function errorDetail(error: unknown) {
  if (!axios.isAxiosError(error)) return null;
  const detail = error.response?.data?.detail;
  return typeof detail === "string" ? detail : null;
}

function clamp(value: number) {
  return Math.min(1, Math.max(0, value));
}

function pointFromEvent(event: PointerEvent<SVGSVGElement>): Point {
  const rect = event.currentTarget.getBoundingClientRect();
  return {
    x: clamp((event.clientX - rect.left) / rect.width),
    y: clamp((event.clientY - rect.top) / rect.height),
  };
}

function normalizeRotation(value: number): Rotation {
  const normalized = ((value % 360) + 360) % 360;
  if (normalized === 90 || normalized === 180 || normalized === 270) {
    return normalized;
  }
  return 0;
}

function rotateRectToDisplay(rect: NormalizedRect, rotation: Rotation): NormalizedRect {
  if (rotation === 90) {
    return {
      x: 1 - (rect.y + rect.height),
      y: rect.x,
      width: rect.height,
      height: rect.width,
    };
  }
  if (rotation === 180) {
    return {
      x: 1 - (rect.x + rect.width),
      y: 1 - (rect.y + rect.height),
      width: rect.width,
      height: rect.height,
    };
  }
  if (rotation === 270) {
    return {
      x: rect.y,
      y: 1 - (rect.x + rect.width),
      width: rect.height,
      height: rect.width,
    };
  }
  return rect;
}

function rotateRectToCanonical(rect: NormalizedRect, rotation: Rotation): NormalizedRect {
  return rotateRectToDisplay(rect, normalizeRotation(360 - rotation));
}

async function loadPdfWithModule(
  module: PdfJsModule,
  workerSrc: string,
  bytes: Uint8Array,
) {
  module.GlobalWorkerOptions.workerSrc = workerSrc;
  return module.getDocument({
    data: bytes.slice(),
    isImageDecoderSupported: false,
    isOffscreenCanvasSupported: false,
  }).promise;
}

async function withTimeout<T>(promise: Promise<T>, timeoutMs: number, label: string): Promise<T> {
  let timeoutId: ReturnType<typeof window.setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timeoutId = window.setTimeout(() => reject(new Error(`${label} timed out`)), timeoutMs);
  });
  try {
    return await Promise.race([promise, timeout]);
  } finally {
    if (timeoutId !== undefined) {
      window.clearTimeout(timeoutId);
    }
  }
}

async function loadPdfDocument(data: ArrayBuffer) {
  const bytes = new Uint8Array(data);
  try {
    return await withTimeout(
      loadPdfWithModule(pdfjsLib, pdfWorkerUrl, bytes),
      5000,
      "PDF.js primary loader",
    );
  } catch (error) {
    console.warn("PDF.js primary loader failed, retrying with legacy build.", error);
    const legacyPdfjs = (await import("pdfjs-dist/legacy/build/pdf.mjs")) as PdfJsModule;
    const legacyWorkerUrl = (
      await import("pdfjs-dist/legacy/build/pdf.worker.mjs?url")
    ).default;
    return withTimeout(
      loadPdfWithModule(legacyPdfjs, legacyWorkerUrl, bytes),
      8000,
      "PDF.js legacy loader",
    );
  }
}

export function PdfReviewPage() {
  const params = useParams();
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const fileId = Number(params.fileId);
  const requestedVersion = Number(searchParams.get("version")) || undefined;
  const requestedFileVersionId = Number(searchParams.get("file_version_id")) || undefined;
  const requestedReadOnly = searchParams.get("mode") === "readonly";
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canAnnotate = hasPermission("pdf_review:annotate");
  const canWriteFiles = hasPermission("files:write");
  const canReadTasks = hasPermission("correction_tasks:read");
  const [reviewFile, setReviewFile] = useState<PdfReviewFile | null>(null);
  const [pdfDoc, setPdfDoc] = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [pageNo, setPageNo] = useState(1);
  const [scale, setScale] = useState(1.2);
  const [pageRotations, setPageRotations] = useState<Record<number, Rotation>>({});
  const [pageSize, setPageSize] = useState({ width: 0, height: 0 });
  const [tool, setTool] = useState<"select" | "annotate">("select");
  const [showAnnotations, setShowAnnotations] = useState(true);
  const [draft, setDraft] = useState<DraftRect | null>(null);
  const [draftStart, setDraftStart] = useState<Point | null>(null);
  const [issueType, setIssueType] = useState("missing_signature");
  const [severity, setSeverity] = useState<"low" | "medium" | "high">("medium");
  const [comment, setComment] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const origin = ((location.state as { origin?: NavigationOriginState } | null)?.origin ?? null);
  const backState = buildRestoreState(origin);
  const backTarget = origin?.from ?? "/clinical-dataset";
  const backLabel = origin?.backLabel ?? "返回数据集";
  const taskOrigin =
    origin ??
    ({
      from: "/correction-tasks",
      backLabel: "返回任务",
    } satisfies NavigationOriginState);
  const pageRotation = pageRotations[pageNo] ?? 0;
  const isReadOnlyReview = requestedReadOnly || Boolean(reviewFile?.read_only);
  const canEditAnnotations = canAnnotate && !isReadOnlyReview;

  const annotationsForPage = useMemo(
    () => (reviewFile?.annotations ?? []).filter((annotation) => annotation.page_no === pageNo),
    [pageNo, reviewFile?.annotations],
  );

  const loadReviewFile = useCallback(async (clearMessage = true) => {
    if (!fileId) return null;
    try {
      const data = await pdfReviewApi.getReviewFile(fileId, requestedVersion, requestedFileVersionId);
      setReviewFile(data);
      setPageNo(1);
      if (clearMessage) {
        setMessage(null);
      }
      return data;
    } catch {
      setMessage("PDF审阅信息加载失败");
      return null;
    }
  }, [fileId, requestedFileVersionId, requestedVersion]);

  useEffect(() => {
    void loadReviewFile();
  }, [loadReviewFile]);

  useEffect(() => {
    setPageRotations({});
  }, [fileId, requestedFileVersionId, requestedVersion]);

  useEffect(() => {
    let cancelled = false;
    async function loadPdf() {
      if (!reviewFile) return;
      try {
        const blob = await filesApi.previewFile(reviewFile.file_id, reviewFile.version);
        const data = await blob.arrayBuffer();
        const document = await loadPdfDocument(data);
        if (!cancelled) {
          setPdfDoc(document);
          setPageNo(1);
        }
      } catch {
        if (!cancelled) {
          setMessage("PDF文件加载失败");
          setPdfDoc(null);
        }
      }
    }
    void loadPdf();
    return () => {
      cancelled = true;
    };
  }, [reviewFile]);

  useEffect(() => {
    let cancelled = false;
    async function renderPage() {
      if (!pdfDoc || !canvasRef.current) return;
      const page = await pdfDoc.getPage(pageNo);
      if (cancelled || !canvasRef.current) return;
      const viewport = page.getViewport({ scale, rotation: pageRotation });
      const canvas = canvasRef.current;
      const context = canvas.getContext("2d");
      if (!context) return;
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.width = `${viewport.width}px`;
      canvas.style.height = `${viewport.height}px`;
      setPageSize({ width: viewport.width, height: viewport.height });
      await page.render({ canvasContext: context, viewport }).promise;
    }
    void renderPage();
    return () => {
      cancelled = true;
    };
  }, [pageNo, pageRotation, pdfDoc, scale]);

  function handleVersionChange(version: number) {
    setSearchParams({
      version: String(version),
      ...(isReadOnlyReview ? { mode: "readonly" } : {}),
    });
  }

  function rotatePage(delta: number) {
    setPageRotations((current) => ({
      ...current,
      [pageNo]: normalizeRotation((current[pageNo] ?? 0) + delta),
    }));
  }

  function handlePointerDown(event: PointerEvent<SVGSVGElement>) {
    if (!canEditAnnotations || tool !== "annotate") return;
    const point = pointFromEvent(event);
    const canonicalRect = rotateRectToCanonical(
      { x: point.x, y: point.y, width: 0.001, height: 0.001 },
      pageRotation,
    );
    event.currentTarget.setPointerCapture(event.pointerId);
    setDraftStart(point);
    setDraft({ page_no: pageNo, ...canonicalRect });
  }

  function handlePointerMove(event: PointerEvent<SVGSVGElement>) {
    if (!draftStart || !draft) return;
    const point = pointFromEvent(event);
    const x = Math.min(draftStart.x, point.x);
    const y = Math.min(draftStart.y, point.y);
    const width = Math.abs(point.x - draftStart.x);
    const height = Math.abs(point.y - draftStart.y);
    const canonicalRect = rotateRectToCanonical({ x, y, width, height }, pageRotation);
    setDraft({ page_no: pageNo, ...canonicalRect });
  }

  function handlePointerUp(event: PointerEvent<SVGSVGElement>) {
    if (!draftStart || !draft) return;
    event.currentTarget.releasePointerCapture(event.pointerId);
    setDraftStart(null);
    const displayDraft = rotateRectToDisplay(draft, pageRotation);
    if (displayDraft.width < 0.005 || displayDraft.height < 0.005) {
      setDraft(null);
    }
  }

  async function saveAnnotation() {
    if (isReadOnlyReview) {
      setMessage("SSU 文件仅支持只读在线审阅");
      return;
    }
    if (!reviewFile || !draft || !comment.trim()) {
      setMessage("请先画框并填写批注说明");
      return;
    }
    try {
      const hadActiveTask = Boolean(reviewFile.active_task_id);
      await pdfReviewApi.createAnnotation({
        file_id: reviewFile.file_id,
        file_version_id: reviewFile.file_version_id,
        page_no: draft.page_no,
        x: draft.x,
        y: draft.y,
        width: draft.width,
        height: draft.height,
        issue_type: issueType,
        severity,
        comment: comment.trim(),
      });
      setDraft(null);
      setComment("");
      const refreshed = await loadReviewFile(false);
      if (refreshed?.active_task_id) {
        setMessage(hadActiveTask ? "已加入整改任务" : "已创建整改任务");
      } else {
        setMessage("批注已保存，但未读取到整改任务，请刷新后重试");
      }
    } catch {
      setMessage("批注保存失败");
    }
  }

  async function updateAnnotationComment(annotation: PdfAnnotation) {
    const next = window.prompt("修改批注说明", annotation.comment);
    if (next === null) return;
    if (!next.trim()) {
      setMessage("批注说明不能为空");
      return;
    }
    try {
      await pdfReviewApi.updateAnnotation(annotation.id, { comment: next.trim() });
      await loadReviewFile();
    } catch {
      setMessage("批注修改失败");
    }
  }

  async function resolveAnnotation(annotation: PdfAnnotation) {
    try {
      await pdfReviewApi.updateAnnotation(annotation.id, { status: "resolved" });
      await loadReviewFile();
    } catch {
      setMessage("批注状态更新失败");
    }
  }

  async function deleteAnnotation(annotation: PdfAnnotation) {
    if (!window.confirm("确认关闭该批注？")) return;
    try {
      await pdfReviewApi.deleteAnnotation(annotation.id);
      await loadReviewFile();
    } catch (error) {
      const detail = errorDetail(error);
      if (detail?.includes("correction flow has started")) {
        setMessage("该任务已进入整改流程，当前批注不能删除");
        return;
      }
      setMessage("批注关闭失败");
    }
  }

  function locate(annotation: PdfAnnotation) {
    setPageNo(annotation.page_no);
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <Button asChild variant="ghost" className="mb-2 px-0">
            <Link to={backTarget} state={backState}>
              <ArrowLeft className="size-4" aria-hidden="true" />
              {backLabel}
            </Link>
          </Button>
          <h1 className="text-xl font-semibold tracking-normal text-slate-950">
            {reviewFile?.file_name ?? "PDF在线审阅"}
          </h1>
          {reviewFile && (
            <p className="mt-1 text-sm text-slate-500">
              v{reviewFile.version} · 批注 {reviewFile.annotations.length} 条
            </p>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {reviewFile && (
            <SelectField
              value={String(reviewFile.version)}
              onChange={(event) => handleVersionChange(Number(event.target.value))}
              className="h-9 w-28"
            >
              {reviewFile.versions.map((version) => (
                <option key={version.id} value={version.version}>
                  v{version.version}
                </option>
              ))}
            </SelectField>
          )}
          <Button
            variant={tool === "select" ? "secondary" : "ghost"}
            onClick={() => setTool("select")}
          >
            <MousePointer2 className="size-4" aria-hidden="true" />
            选择
          </Button>
          <Button
            variant={tool === "annotate" ? "secondary" : "ghost"}
            onClick={() => setTool("annotate")}
            disabled={!canEditAnnotations}
          >
            <SquarePen className="size-4" aria-hidden="true" />
            画框
          </Button>
          <Button variant="ghost" onClick={() => setShowAnnotations((value) => !value)}>
            <EyeOff className="size-4" aria-hidden="true" />
            批注
          </Button>
        </div>
      </div>

      {message && (
        <Badge
          tone={
            message.includes("失败") || message.includes("请") || message.includes("未读取")
              ? "danger"
              : "success"
          }
        >
          {message}
        </Badge>
      )}

      <div className="grid min-h-[720px] gap-4 xl:grid-cols-[1fr_360px]">
        <div className="overflow-auto rounded-md border border-slate-200 bg-slate-200 p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-1">
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setPageNo((value) => Math.max(1, value - 1))}
                disabled={pageNo <= 1}
              >
                <ChevronLeft className="size-4" aria-hidden="true" />
              </Button>
              <span className="px-2 text-sm font-medium text-slate-700">
                {pageNo} / {pdfDoc?.numPages ?? "-"}
              </span>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => setPageNo((value) => Math.min(pdfDoc?.numPages ?? value, value + 1))}
                disabled={!pdfDoc || pageNo >= pdfDoc.numPages}
              >
                <ChevronRight className="size-4" aria-hidden="true" />
              </Button>
            </div>
            <div className="flex items-center gap-1">
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setScale((value) => Math.max(0.6, value - 0.15))}
              >
                <Minus className="size-4" aria-hidden="true" />
              </Button>
              <span className="w-14 text-center text-sm text-slate-600">
                {Math.round(scale * 100)}%
              </span>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setScale((value) => Math.min(2.4, value + 0.15))}
              >
                <Plus className="size-4" aria-hidden="true" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => rotatePage(-90)}
                title="逆时针旋转90度"
                aria-label="逆时针旋转90度"
              >
                <RotateCcw className="size-4" aria-hidden="true" />
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => rotatePage(90)}
                title="顺时针旋转90度"
                aria-label="顺时针旋转90度"
              >
                <RotateCw className="size-4" aria-hidden="true" />
              </Button>
            </div>
          </div>
          <div
            className="relative mx-auto bg-white shadow-sm"
            style={{ width: pageSize.width || 1, height: pageSize.height || 1 }}
          >
            <canvas ref={canvasRef} />
            <svg
              className="absolute inset-0"
              style={{ cursor: tool === "annotate" && canEditAnnotations ? "crosshair" : "default" }}
              width={pageSize.width}
              height={pageSize.height}
              onPointerDown={handlePointerDown}
              onPointerMove={handlePointerMove}
              onPointerUp={handlePointerUp}
            >
              {showAnnotations &&
                annotationsForPage.map((annotation, index) => {
                  const displayRect = rotateRectToDisplay(annotation, pageRotation);
                  return (
                    <g key={annotation.id}>
                      <rect
                        x={displayRect.x * pageSize.width}
                        y={displayRect.y * pageSize.height}
                        width={displayRect.width * pageSize.width}
                        height={displayRect.height * pageSize.height}
                        fill="rgba(16, 185, 129, 0.12)"
                        stroke="#059669"
                        strokeWidth="2"
                      />
                      <text
                        x={displayRect.x * pageSize.width + 6}
                        y={displayRect.y * pageSize.height + 18}
                        className="fill-emerald-700 text-sm font-semibold"
                      >
                        #{index + 1}
                      </text>
                    </g>
                  );
                })}
              {draft &&
                draft.page_no === pageNo &&
                (() => {
                  const displayDraft = rotateRectToDisplay(draft, pageRotation);
                  return (
                    <rect
                      x={displayDraft.x * pageSize.width}
                      y={displayDraft.y * pageSize.height}
                      width={displayDraft.width * pageSize.width}
                      height={displayDraft.height * pageSize.height}
                      fill="rgba(220, 38, 38, 0.12)"
                      stroke="#dc2626"
                      strokeDasharray="6 4"
                      strokeWidth="2"
                    />
                  );
                })()}
            </svg>
          </div>
        </div>

        <div className="space-y-4">
          {draft && (
            <Card>
              <CardContent className="space-y-3 py-4">
                <div>
                  <h2 className="text-sm font-semibold text-slate-900">新增批注</h2>
                  <p className="mt-1 text-xs text-slate-500">第 {draft.page_no} 页</p>
                </div>
                <SelectField value={issueType} onChange={(event) => setIssueType(event.target.value)}>
                  {issueTypes.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </SelectField>
                <SelectField
                  value={severity}
                  onChange={(event) => setSeverity(event.target.value as "low" | "medium" | "high")}
                >
                  <option value="low">一般</option>
                  <option value="medium">重要</option>
                  <option value="high">严重</option>
                </SelectField>
                <TextAreaField
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                  placeholder="填写问题说明"
                />
                <div className="flex gap-2">
                  <Button onClick={() => void saveAnnotation()}>
                    <Save className="size-4" aria-hidden="true" />
                    保存
                  </Button>
                  <Button variant="ghost" onClick={() => setDraft(null)}>
                    取消
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {reviewFile && (
            <DocumentExtractedFieldsPanel
              fileId={reviewFile.file_id}
              version={reviewFile.version}
              canWrite={canWriteFiles}
              defaultOpen
              onChanged={() => void loadReviewFile(false)}
            />
          )}

          <Card>
            <CardContent className="space-y-3 py-4">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-900">批注列表</h2>
                <Badge>{reviewFile?.annotations.length ?? 0} 条</Badge>
              </div>
              <div className="space-y-2">
                {(reviewFile?.annotations ?? []).map((annotation) => (
                  <div key={annotation.id} className="rounded-md border border-slate-200 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 text-sm">
                        <span className="font-medium text-slate-900">
                          第 {annotation.page_no} 页 ·{" "}
                          {issueTypes.find((item) => item.value === annotation.issue_type)?.label ??
                            annotation.issue_type}
                        </span>
                        <span className="mt-1 block break-words text-xs text-slate-600">
                          {annotation.comment}
                        </span>
                      </div>
                      <Badge tone={toneForSeverity(annotation.severity)}>
                        {severityLabels[annotation.severity]}
                      </Badge>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-1">
                      <Badge>{statusLabels[annotation.status] ?? annotation.status}</Badge>
                      <Button size="sm" variant="ghost" onClick={() => locate(annotation)}>
                        <LocateFixed className="size-4" aria-hidden="true" />
                      </Button>
                      {canEditAnnotations && (
                        <>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => void updateAnnotationComment(annotation)}
                          >
                            编辑
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => void resolveAnnotation(annotation)}
                          >
                            <Check className="size-4" aria-hidden="true" />
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => void deleteAnnotation(annotation)}
                          >
                            <Trash2 className="size-4" aria-hidden="true" />
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
                {reviewFile && reviewFile.annotations.length === 0 && (
                  <p className="rounded-md border border-dashed border-slate-200 p-4 text-sm text-slate-500">
                    暂无批注
                  </p>
                )}
              </div>
            </CardContent>
          </Card>

          {!isReadOnlyReview && (
          <Card>
            <CardContent className="space-y-3 py-4">
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-sm font-semibold text-slate-900">当前整改任务</h2>
                {reviewFile?.active_task_status ? (
                  <Badge tone={toneForTaskStatus(reviewFile.active_task_status)}>
                    {taskStatusLabels[reviewFile.active_task_status] ?? reviewFile.active_task_status}
                  </Badge>
                ) : (
                  <Badge tone="neutral">未创建</Badge>
                )}
              </div>
              {reviewFile?.active_task_id ? (
                <>
                  <p className="text-sm text-slate-600">
                    当前文件已有 1 条活动任务，聚合批注 {reviewFile.active_task_annotation_count} 条。
                  </p>
                  {canReadTasks ? (
                    <Button asChild variant="secondary">
                      <Link
                        to={`/correction-tasks/${reviewFile.active_task_id}`}
                        state={{ origin: taskOrigin }}
                      >
                        <ClipboardCheck className="size-4" aria-hidden="true" />
                        查看任务详情
                      </Link>
                    </Button>
                  ) : (
                    <p className="text-xs text-slate-500">当前账号没有整改任务查看权限</p>
                  )}
                </>
              ) : (
                <p className="text-sm text-slate-500">
                  保存第一条有效批注后，系统会自动为当前文件创建整改任务。
                </p>
              )}
            </CardContent>
          </Card>
          )}
        </div>
      </div>
    </div>
  );
}
