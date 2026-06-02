import {
  AlertCircle,
  Copy,
  Download,
  FileArchive,
  FileText,
  Image as ImageIcon,
  Loader2,
  Upload,
} from "lucide-react";
import { ChangeEvent, Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, SelectField } from "@/components/ui/form";
import { cn } from "@/lib/utils";
import { imageDataApi } from "@/services/image-data";
import { masterDataApi } from "@/services/master-data";
import { useAuthStore } from "@/stores/auth-store";
import type { ImageDataType, SubjectImageRecord, SubjectImageRow } from "@/types/image-data";
import type { Center, Project } from "@/types/master-data";

const typeTabs: Array<{
  type: ImageDataType;
  label: string;
  description: string;
  icon: typeof ImageIcon;
  accept: string;
}> = [
  {
    type: "raw",
    label: "原始图像上传",
    description: "按试验序列号上传原始图像压缩包",
    icon: FileArchive,
    accept: ".zip,application/zip,application/x-zip-compressed",
  },
  {
    type: "enhanced",
    label: "增强图像上传",
    description: "研发算法补强后的图像压缩包",
    icon: ImageIcon,
    accept: ".zip,application/zip,application/x-zip-compressed",
  },
  {
    type: "report",
    label: "电子报告上传",
    description: "PDF、Word 或 Excel 格式电子报告",
    icon: FileText,
    accept: ".pdf,.doc,.docx,.xls,.xlsx",
  },
];

const subjectArmLabels: Record<string, string> = {
  experimental: "实验组",
  control: "对照组",
};

const statusLabels: Record<string, string> = {
  not_uploaded: "未上传",
  uploaded: "已完成",
};

function normalizeImageType(value: string | null): ImageDataType {
  return value === "enhanced" || value === "report" ? value : "raw";
}

function formatBytes(value: number | null | undefined) {
  if (!value) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function formatDateTime(value: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 16).replace("T", " ");
  return date.toLocaleString("zh-CN", { hour12: false });
}

function extensionSummary(record: SubjectImageRecord) {
  const entries = Object.entries(record.image_extensions_json ?? {});
  if (entries.length === 0) return "-";
  return entries.map(([ext, count]) => `${ext.toUpperCase()} ${count}`).join(" / ");
}

function statusTone(status: string): "success" | "warning" {
  return status === "uploaded" ? "success" : "warning";
}

export function ImageDataPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const activeType = normalizeImageType(searchParams.get("type"));
  const selectedProjectId = Number(searchParams.get("project_id")) || undefined;
  const selectedCenterId = Number(searchParams.get("center_id")) || undefined;
  const [projects, setProjects] = useState<Project[]>([]);
  const [centers, setCenters] = useState<Center[]>([]);
  const [rows, setRows] = useState<SubjectImageRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [metadataLoading, setMetadataLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [busyRecordId, setBusyRecordId] = useState<number | null>(null);

  const activeTab = useMemo(
    () => typeTabs.find((tab) => tab.type === activeType) ?? typeTabs[0],
    [activeType],
  );
  const selectedProject = projects.find((project) => project.id === selectedProjectId);
  const canUploadRaw = hasPermission("image_data:upload_raw");
  const canUploadEnhanced = hasPermission("image_data:upload_enhanced");
  const canUploadReport = hasPermission("image_data:upload_report");
  const canCopyRaw = hasPermission("image_data:copy_raw");
  const canDelete = hasPermission("image_data:delete");

  const canUploadCurrent =
    (activeType === "raw" && canUploadRaw) ||
    (activeType === "enhanced" && canUploadEnhanced) ||
    (activeType === "report" && canUploadReport);
  const canDownloadCurrent =
    (activeType === "raw" && canUploadRaw) ||
    (activeType === "enhanced" && canUploadEnhanced) ||
    (activeType === "report" && canUploadReport);

  const loadRows = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const nextRows = await imageDataApi.listRows({
        project_id: selectedProjectId,
        center_id: selectedCenterId,
        image_type: activeType,
      });
      setRows(nextRows);
    } catch (err) {
      setRows([]);
      setError(err instanceof Error ? err.message : "图像数据加载失败");
    } finally {
      setLoading(false);
    }
  }, [activeType, selectedCenterId, selectedProjectId]);

  useEffect(() => {
    let cancelled = false;

    async function loadMetadata() {
      setMetadataLoading(true);
      try {
        const nextProjects = await masterDataApi.listProjects();
        const nextCenters = await masterDataApi.listCenters(selectedProjectId);
        if (!cancelled) {
          setProjects(nextProjects);
          setCenters(nextCenters);
        }
      } catch {
        if (!cancelled) {
          setProjects([]);
          setCenters([]);
        }
      } finally {
        if (!cancelled) setMetadataLoading(false);
      }
    }

    void loadMetadata();
    return () => {
      cancelled = true;
    };
  }, [selectedProjectId]);

  useEffect(() => {
    void loadRows();
  }, [loadRows]);

  function updateParams(next: {
    type?: ImageDataType;
    project_id?: number | null;
    center_id?: number | null;
  }) {
    const params = new URLSearchParams(searchParams);
    if (next.type) params.set("type", next.type);
    if ("project_id" in next) {
      if (next.project_id) params.set("project_id", String(next.project_id));
      else params.delete("project_id");
      params.delete("center_id");
    }
    if ("center_id" in next) {
      if (next.center_id) params.set("center_id", String(next.center_id));
      else params.delete("center_id");
    }
    setSearchParams(params);
  }

  async function handleUpload(row: SubjectImageRow, event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setBusyRecordId(row.record.id);
    setError(null);
    try {
      await imageDataApi.upload(row.record.id, file);
      await loadRows();
      setExpandedId(row.record.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setBusyRecordId(null);
    }
  }

  async function handleDownload(record: SubjectImageRecord, mode: "download" | "raw-copy") {
    setBusyRecordId(record.id);
    setError(null);
    try {
      const fallbackName = record.original_name ?? `${record.screening_no_snapshot}-${record.image_type}`;
      if (mode === "raw-copy") {
        await imageDataApi.rawCopy(record.id, fallbackName);
      } else {
        await imageDataApi.download(record.id, fallbackName);
      }
      await loadRows();
    } catch (err) {
      setError(err instanceof Error ? err.message : "下载失败");
    } finally {
      setBusyRecordId(null);
    }
  }

  async function handleDelete(record: SubjectImageRecord) {
    if (!window.confirm("确认清空这条图像数据记录吗？")) return;
    setBusyRecordId(record.id);
    setError(null);
    try {
      await imageDataApi.delete(record.id);
      setExpandedId(null);
      await loadRows();
    } catch (err) {
      setError(err instanceof Error ? err.message : "清空失败");
    } finally {
      setBusyRecordId(null);
    }
  }

  function renderUploadControl(row: SubjectImageRow) {
    const rawReady = row.raw_record?.upload_status === "uploaded";
    const disabled =
      !canUploadCurrent ||
      busyRecordId === row.record.id ||
      (activeType === "enhanced" && !rawReady);
    return (
      <label
        className={cn(
          "inline-flex h-8 cursor-pointer items-center justify-center gap-2 rounded-md bg-slate-900 px-3 text-xs font-medium text-white transition hover:bg-slate-800",
          disabled && "pointer-events-none opacity-50",
        )}
        title={activeType === "enhanced" && !rawReady ? "请先上传原始图像" : undefined}
      >
        {busyRecordId === row.record.id ? (
          <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
        ) : (
          <Upload className="size-3.5" aria-hidden="true" />
        )}
        上传
        <input
          type="file"
          className="sr-only"
          accept={activeTab.accept}
          disabled={disabled}
          onChange={(event) => void handleUpload(row, event)}
        />
      </label>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">图像数据</h1>
          <p className="mt-1 text-sm text-slate-500">
            按项目、中心和试验序列号管理原始图像、增强图像和电子报告
          </p>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 md:w-[520px]">
          <Field label="项目">
            <SelectField
              value={selectedProjectId ? String(selectedProjectId) : ""}
              onChange={(event) =>
                updateParams({ project_id: Number(event.target.value) || null })
              }
              disabled={metadataLoading}
            >
              <option value="">全部项目</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </SelectField>
          </Field>
          <Field label="中心">
            <SelectField
              value={selectedCenterId ? String(selectedCenterId) : ""}
              onChange={(event) => updateParams({ center_id: Number(event.target.value) || null })}
              disabled={metadataLoading || centers.length === 0}
            >
              <option value="">全部中心</option>
              {centers.map((center) => (
                <option key={center.id} value={center.id}>
                  {center.name}
                </option>
              ))}
            </SelectField>
          </Field>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[240px_minmax(0,1fr)]">
        <aside className="rounded-md border border-slate-200 bg-white p-2">
          <div className="space-y-1">
            {typeTabs.map((tab) => {
              const Icon = tab.icon;
              const active = tab.type === activeType;
              return (
                <button
                  key={tab.type}
                  type="button"
                  className={cn(
                    "flex w-full items-start gap-3 rounded-md px-3 py-3 text-left transition",
                    active ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100",
                  )}
                  onClick={() => updateParams({ type: tab.type })}
                >
                  <Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  <span className="min-w-0">
                    <span className="block text-sm font-medium">{tab.label}</span>
                    <span
                      className={cn(
                        "mt-0.5 block text-xs",
                        active ? "text-slate-200" : "text-slate-400",
                      )}
                    >
                      {tab.description}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </aside>

        <section className="min-w-0 space-y-4">
          <Card>
            <CardContent className="flex flex-col gap-3 py-4 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-sm font-medium text-slate-900">{activeTab.label}</p>
                <p className="mt-1 text-xs text-slate-500">
                  当前范围：{selectedProject?.name ?? "全部项目"}
                  {selectedCenterId
                    ? ` / ${centers.find((center) => center.id === selectedCenterId)?.name ?? "指定中心"}`
                    : " / 全部中心"}
                </p>
              </div>
              <div className="grid grid-cols-3 gap-2 text-center text-xs text-slate-500">
                <div className="rounded-md bg-slate-50 px-3 py-2">
                  <p className="text-base font-semibold text-slate-900">{rows.length}</p>
                  <p>试验人员</p>
                </div>
                <div className="rounded-md bg-emerald-50 px-3 py-2">
                  <p className="text-base font-semibold text-emerald-700">
                    {rows.filter((row) => row.record.upload_status === "uploaded").length}
                  </p>
                  <p>已完成</p>
                </div>
                <div className="rounded-md bg-amber-50 px-3 py-2">
                  <p className="text-base font-semibold text-amber-700">
                    {rows.filter((row) => row.record.upload_status !== "uploaded").length}
                  </p>
                  <p>未上传</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {error && (
            <div className="flex items-center gap-2 rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              <AlertCircle className="size-4" aria-hidden="true" />
              {error}
            </div>
          )}

          <div className="overflow-hidden rounded-md border border-slate-200 bg-white">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50 text-left text-xs font-medium uppercase tracking-normal text-slate-500">
                  <tr>
                    <th className="px-4 py-3">试验序列号</th>
                    <th className="px-4 py-3">分组</th>
                    <th className="px-4 py-3">上传状态</th>
                    <th className="px-4 py-3">版本</th>
                    <th className="px-4 py-3">文件摘要</th>
                    <th className="px-4 py-3 text-right">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {loading && (
                    <tr>
                      <td colSpan={6} className="px-4 py-12 text-center text-slate-500">
                        正在加载图像数据
                      </td>
                    </tr>
                  )}
                  {!loading && rows.length === 0 && (
                    <tr>
                      <td colSpan={6} className="px-4 py-12 text-center text-slate-500">
                        暂无试验人员
                      </td>
                    </tr>
                  )}
                  {!loading &&
                    rows.map((row) => {
                      const record = row.record;
                      const uploaded = record.upload_status === "uploaded";
                      const expanded = expandedId === record.id;
                      const rawReady = row.raw_record?.upload_status === "uploaded";
                      return (
                        <Fragment key={record.id}>
                          <tr className="hover:bg-slate-50">
                            <td className="px-4 py-3 font-medium text-slate-900">
                              {row.screening_no}
                            </td>
                            <td className="px-4 py-3 text-slate-600">
                              {row.subject_arm ? subjectArmLabels[row.subject_arm] : "-"}
                            </td>
                            <td className="px-4 py-3">
                              <button
                                type="button"
                                className="text-left"
                                disabled={!uploaded}
                                onClick={() => setExpandedId(expanded ? null : record.id)}
                              >
                                <Badge tone={statusTone(record.upload_status)}>
                                  {statusLabels[record.upload_status] ?? record.upload_status}
                                </Badge>
                              </button>
                              {activeType === "enhanced" && !rawReady && (
                                <p className="mt-1 text-xs text-amber-600">等待原始图像</p>
                              )}
                            </td>
                            <td className="px-4 py-3 text-slate-600">v{record.version}</td>
                            <td className="max-w-[320px] px-4 py-3 text-slate-600">
                              {uploaded ? (
                                <div className="space-y-1">
                                  <p className="truncate">{record.original_name}</p>
                                  <p className="text-xs text-slate-400">
                                    {activeType === "report"
                                      ? formatBytes(record.file_size)
                                      : `${record.image_count} 张 / ${formatBytes(record.image_total_size)}`}
                                  </p>
                                </div>
                              ) : (
                                "-"
                              )}
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex justify-end gap-2">
                                {renderUploadControl(row)}
                                {uploaded && canDownloadCurrent && (
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="secondary"
                                    onClick={() => void handleDownload(record, "download")}
                                    disabled={busyRecordId === record.id}
                                  >
                                    <Download className="size-3.5" aria-hidden="true" />
                                    下载
                                  </Button>
                                )}
                                {activeType === "raw" && uploaded && canCopyRaw && (
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="secondary"
                                    onClick={() => void handleDownload(record, "raw-copy")}
                                    disabled={busyRecordId === record.id}
                                  >
                                    <Copy className="size-3.5" aria-hidden="true" />
                                    副本
                                  </Button>
                                )}
                                {uploaded && canDelete && (
                                  <Button
                                    type="button"
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => void handleDelete(record)}
                                    disabled={busyRecordId === record.id}
                                  >
                                    清空
                                  </Button>
                                )}
                              </div>
                            </td>
                          </tr>
                          {expanded && (
                            <tr className="bg-slate-50">
                              <td colSpan={6} className="px-4 py-4">
                                <div className="grid gap-3 text-xs text-slate-600 md:grid-cols-4">
                                  <DetailItem label="图片数量" value={`${record.image_count} 张`} />
                                  <DetailItem
                                    label="图片总大小"
                                    value={formatBytes(record.image_total_size)}
                                  />
                                  <DetailItem
                                    label="上传文件大小"
                                    value={formatBytes(record.file_size)}
                                  />
                                  <DetailItem
                                    label="上传时间"
                                    value={formatDateTime(record.uploaded_at)}
                                  />
                                  <DetailItem label="文件类型" value={record.file_ext ?? "-"} />
                                  <DetailItem label="扩展名分布" value={extensionSummary(record)} />
                                  <DetailItem
                                    label="文件 Hash"
                                    value={record.file_hash ? record.file_hash.slice(0, 16) : "-"}
                                  />
                                  <DetailItem
                                    label="解析提示"
                                    value={record.parse_warning ?? "无"}
                                    warning={Boolean(record.parse_warning)}
                                  />
                                </div>
                              </td>
                            </tr>
                          )}
                        </Fragment>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </div>

          {!canUploadCurrent && (
            <p className="text-xs text-slate-500">
              当前账号可查看图像数据状态；上传能力由角色权限控制。
            </p>
          )}
        </section>
      </div>
    </div>
  );
}

function DetailItem({
  label,
  value,
  warning = false,
}: {
  label: string;
  value: string;
  warning?: boolean;
}) {
  return (
    <div className="rounded-md bg-white px-3 py-2">
      <p className="text-slate-400">{label}</p>
      <p className={cn("mt-1 break-words font-medium text-slate-800", warning && "text-amber-700")}>
        {value}
      </p>
    </div>
  );
}
