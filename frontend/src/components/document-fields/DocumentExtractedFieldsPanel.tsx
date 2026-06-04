import { ChevronDown, ChevronUp, RefreshCw, Save } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { TextAreaField } from "@/components/ui/form";
import { inputClassName } from "@/lib/form-styles";
import { filesApi } from "@/services/files";
import { pdfPacketsApi } from "@/services/pdf-packets";
import type { DocumentExtractedField } from "@/types/document-fields";
import type { FileRecord } from "@/types/files";

type BadgeTone = "neutral" | "success" | "warning" | "danger";

type DocumentExtractedFieldsPanelProps = {
  title?: string;
  subjectItemId?: number;
  fileId?: number;
  version?: number;
  segmentId?: number;
  canWrite: boolean;
  defaultOpen?: boolean;
  refreshKey?: number;
  onChanged?: () => void;
};

const statusLabels: Record<string, string> = {
  extracted: "已提取",
  needs_input: "待补录",
  confirmed: "已确认",
};

function statusTone(status: string): BadgeTone {
  if (status === "confirmed" || status === "extracted") return "success";
  if (status === "needs_input") return "warning";
  return "neutral";
}

function valueForField(field: DocumentExtractedField) {
  return field.raw_value || field.normalized_value || "";
}

function confidenceLabel(value: number) {
  if (!value) return "-";
  return `${Math.round(value * 100)}%`;
}

export function DocumentExtractedFieldsPanel({
  title = "提取字段",
  subjectItemId,
  fileId,
  version,
  segmentId,
  canWrite,
  defaultOpen = false,
  refreshKey = 0,
  onChanged,
}: DocumentExtractedFieldsPanelProps) {
  const [open, setOpen] = useState(defaultOpen);
  const [fields, setFields] = useState<DocumentExtractedField[]>([]);
  const [targetFile, setTargetFile] = useState<FileRecord | null>(null);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [loading, setLoading] = useState(false);
  const [savingId, setSavingId] = useState(0);
  const [message, setMessage] = useState<string | null>(null);

  const needsInputCount = useMemo(
    () => fields.filter((field) => field.status === "needs_input").length,
    [fields],
  );

  const resolvedFileId = fileId ?? targetFile?.id ?? 0;
  const hasFieldSource = Boolean(segmentId || resolvedFileId);

  const loadFields = useCallback(async () => {
    if (!open) return;
    setLoading(true);
    setMessage(null);
    try {
      if (segmentId) {
        const data = await pdfPacketsApi.listSegmentExtractedFields(segmentId);
        setFields(data);
        setDrafts(Object.fromEntries(data.map((field) => [field.id, valueForField(field)])));
        return;
      }
      let nextFileId = fileId ?? 0;
      let nextFile: FileRecord | null = null;
      if (!nextFileId && subjectItemId) {
        const files = await filesApi.listFiles({
          subject_item_id: subjectItemId,
          status: "active",
        });
        nextFile = files[0] ?? null;
        nextFileId = nextFile?.id ?? 0;
      }
      setTargetFile(nextFile);
      if (!nextFileId) {
        setFields([]);
        setDrafts({});
        return;
      }
      const data = await filesApi.listExtractedFields(nextFileId, version);
      setFields(data);
      setDrafts(Object.fromEntries(data.map((field) => [field.id, valueForField(field)])));
    } catch {
      setMessage("字段接口异常，请刷新或联系管理员");
    } finally {
      setLoading(false);
    }
  }, [fileId, open, segmentId, subjectItemId, version]);

  useEffect(() => {
    setOpen(defaultOpen);
  }, [defaultOpen, refreshKey]);

  useEffect(() => {
    void loadFields();
  }, [loadFields, refreshKey]);

  async function saveField(field: DocumentExtractedField) {
    const nextValue = drafts[field.id] ?? "";
    setSavingId(field.id);
    setMessage(null);
    try {
      if (segmentId) {
        await pdfPacketsApi.updateSegmentExtractedField(segmentId, field.id, {
          raw_value: nextValue,
        });
      } else if (resolvedFileId) {
        await filesApi.updateExtractedField(resolvedFileId, field.id, {
          raw_value: nextValue,
        });
      }
      setMessage("字段已保存");
      await loadFields();
      onChanged?.();
    } catch {
      setMessage("字段保存失败");
    } finally {
      setSavingId(0);
    }
  }

  async function reanalyze() {
    if (!resolvedFileId) return;
    setLoading(true);
    setMessage(null);
    try {
      const data = await filesApi.analyzeExtractedFields(resolvedFileId, version, true);
      setFields(data);
      setDrafts(Object.fromEntries(data.map((field) => [field.id, valueForField(field)])));
      setMessage("字段已重新识别");
      onChanged?.();
    } catch {
      setMessage("重新识别失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-md border border-slate-200 bg-slate-50/70">
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left"
        onClick={() => setOpen((value) => !value)}
      >
        <span className="flex min-w-0 items-center gap-2">
          <span className="text-sm font-semibold text-slate-900">{title}</span>
          {needsInputCount > 0 ? (
            <Badge tone="warning">待补录 {needsInputCount}</Badge>
          ) : fields.length > 0 ? (
            <Badge tone="success">已提取 {fields.length}</Badge>
          ) : (
            <Badge tone="neutral">未识别</Badge>
          )}
        </span>
        {open ? (
          <ChevronUp className="size-4 shrink-0 text-slate-500" aria-hidden="true" />
        ) : (
          <ChevronDown className="size-4 shrink-0 text-slate-500" aria-hidden="true" />
        )}
      </button>

      {open && (
        <div className="space-y-3 border-t border-slate-200 px-3 py-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-xs text-slate-500">
              {segmentId
                ? "资料包片段字段"
                : targetFile
                  ? `${targetFile.original_name} · v${targetFile.version}`
                  : fileId
                    ? `文件 #${fileId}`
                    : "请先上传 PDF 后补录字段"}
            </p>
            <div className="flex gap-1">
              <Button size="sm" variant="ghost" onClick={() => void loadFields()} disabled={loading}>
                <RefreshCw className="size-4" aria-hidden="true" />
              </Button>
              {!segmentId && resolvedFileId > 0 && canWrite && (
                <Button size="sm" variant="secondary" onClick={() => void reanalyze()} disabled={loading}>
                  重新识别
                </Button>
              )}
            </div>
          </div>

          {message && (
            <Badge tone={message.includes("失败") || message.includes("异常") ? "danger" : "success"}>
              {message}
            </Badge>
          )}

          {fields.length === 0 ? (
            <div className="rounded-md border border-dashed border-slate-200 bg-white px-3 py-4 text-center text-sm text-slate-500">
              {loading
                ? "字段读取中"
                : hasFieldSource
                  ? "当前资料类型暂未配置字段骨架，可点击重新识别或联系管理员"
                  : "请先上传 PDF，上传后这里会生成可手填的字段"}
            </div>
          ) : (
            <div className="grid gap-2 lg:grid-cols-2 2xl:grid-cols-3">
              {fields.map((field) => (
                <div key={field.id} className="rounded-md border border-slate-200 bg-white p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-slate-900">{field.field_label}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {field.field_key} · 置信度 {confidenceLabel(field.confidence)}
                      </p>
                    </div>
                    <Badge tone={statusTone(field.status)}>
                      {statusLabels[field.status] ?? field.status}
                    </Badge>
                  </div>
                  {field.value_type === "long_text" ? (
                    <TextAreaField
                      className="mt-3 min-h-24"
                      value={drafts[field.id] ?? ""}
                      onChange={(event) =>
                        setDrafts((current) => ({ ...current, [field.id]: event.target.value }))
                      }
                      readOnly={!canWrite}
                    />
                  ) : (
                    <input
                      className={inputClassName("mt-3 h-9")}
                      value={drafts[field.id] ?? ""}
                      onChange={(event) =>
                        setDrafts((current) => ({ ...current, [field.id]: event.target.value }))
                      }
                      readOnly={!canWrite}
                    />
                  )}
                  <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                    <p className="text-xs text-slate-500">
                      {field.source_page_no ? `来源页 ${field.source_page_no}` : "无来源页"}
                      {field.manually_edited ? " · 人工修改" : ""}
                    </p>
                    {canWrite && (
                      <Button
                        size="sm"
                        onClick={() => void saveField(field)}
                        disabled={savingId === field.id}
                      >
                        <Save className="size-4" aria-hidden="true" />
                        保存
                      </Button>
                    )}
                  </div>
                  {field.source_text && (
                    <p className="mt-2 rounded bg-slate-50 p-2 text-xs leading-5 text-slate-500">
                      {field.source_text}
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
