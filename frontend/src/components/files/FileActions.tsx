import { Download, Eye, FileText, History, RefreshCw, Trash2, Upload, X } from "lucide-react";
import { ChangeEvent, DragEvent, useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { filesApi } from "@/services/files";
import type { FileRecord, FileVersion } from "@/types/files";

type FileActionsProps = {
  stageFileId?: number;
  subjectItemId?: number;
  defaultCategory?: string;
  canRead: boolean;
  canWrite: boolean;
  canDelete: boolean;
  onChanged?: () => void;
};

function isPdfFile(file: File) {
  return file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
}

function canPreview(mimeType: string) {
  return mimeType === "application/pdf" || mimeType.startsWith("image/");
}

function formatSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function formatDateTime(value: string) {
  return value.replace("T", " ").slice(0, 16);
}

function openBlob(blob: Blob, filename?: string) {
  const url = window.URL.createObjectURL(blob);
  if (filename) {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    window.setTimeout(() => window.URL.revokeObjectURL(url), 500);
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer");
  window.setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
}

export function FileActions({
  stageFileId,
  subjectItemId,
  defaultCategory = "clinical_document",
  canRead,
  canWrite,
  canDelete,
  onChanged,
}: FileActionsProps) {
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [versions, setVersions] = useState<Record<number, FileVersion[]>>({});
  const [historyFile, setHistoryFile] = useState<FileRecord | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);

  const loadFiles = useCallback(async () => {
    if (!canRead) return;
    const data = await filesApi.listFiles({
      stage_file_id: stageFileId,
      subject_item_id: subjectItemId,
      status: "active",
    });
    setFiles(data);
  }, [canRead, stageFileId, subjectItemId]);

  useEffect(() => {
    void loadFiles();
  }, [loadFiles]);

  const uploadSelectedFile = useCallback(
    async (selectedFile: File) => {
      if (!isPdfFile(selectedFile)) {
        setMessage("请上传 PDF 文件");
        return;
      }
      setUploading(true);
      try {
        await filesApi.uploadFile({
          file: selectedFile,
          fileCategory: defaultCategory,
          stageFileId,
          subjectItemId,
        });
        setMessage("上传成功");
        await loadFiles();
        onChanged?.();
      } catch {
        setMessage("上传失败");
      } finally {
        setUploading(false);
      }
    },
    [defaultCategory, loadFiles, onChanged, stageFileId, subjectItemId],
  );

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0];
    event.target.value = "";
    if (!selectedFile) return;
    await uploadSelectedFile(selectedFile);
  }

  function handleDragOver(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    if (!canWrite || uploading) return;
    event.dataTransfer.dropEffect = "copy";
    setDragging(true);
  }

  function handleDragLeave(event: DragEvent<HTMLDivElement>) {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setDragging(false);
    }
  }

  async function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (!canWrite || uploading) return;
    const droppedFiles = Array.from(event.dataTransfer.files);
    if (droppedFiles.length === 0) return;
    if (droppedFiles.length > 1) {
      setMessage("一次只能上传一个文件");
      return;
    }
    await uploadSelectedFile(droppedFiles[0]);
  }

  async function handleReplace(file: FileRecord, event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0];
    event.target.value = "";
    if (!selectedFile) return;
    if (!isPdfFile(selectedFile)) {
      setMessage("请上传 PDF 文件");
      return;
    }
    try {
      await filesApi.replaceFile(file.id, selectedFile, "前端重新上传");
      setMessage("重新上传成功");
      await loadFiles();
      onChanged?.();
    } catch {
      setMessage("重新上传失败");
    }
  }

  async function handleDownload(file: FileRecord, version?: number) {
    try {
      const { blob, filename } = await filesApi.downloadFile(file.id, version);
      openBlob(blob, filename);
    } catch {
      setMessage("下载失败");
    }
  }

  async function handlePreview(file: FileRecord, version?: number) {
    try {
      const blob = await filesApi.previewFile(file.id, version);
      openBlob(blob);
    } catch {
      setMessage("该文件暂不支持查看");
    }
  }

  async function openHistory(file: FileRecord) {
    try {
      if (!versions[file.id]) {
        const data = await filesApi.listVersions(file.id);
        setVersions((current) => ({ ...current, [file.id]: data }));
      }
      setHistoryFile(file);
    } catch {
      setMessage("历史版本加载失败");
    }
  }

  async function handleDelete(file: FileRecord) {
    if (!window.confirm(`确认删除文件：${file.original_name}？`)) return;
    try {
      await filesApi.deleteFile(file.id);
      setMessage("文件已删除");
      await loadFiles();
      onChanged?.();
    } catch {
      setMessage("删除失败");
    }
  }

  if (!canRead) {
    return <span className="text-xs text-slate-400">无文件权限</span>;
  }

  return (
    <div className="min-w-[220px] space-y-2">
      {message && (
        <Badge
          tone={
            message.includes("失败") ||
            message.includes("不支持") ||
            message.includes("只能") ||
            message.includes("请")
              ? "danger"
              : "success"
          }
        >
          {message}
        </Badge>
      )}

      {files.length === 0 ? (
        canWrite ? (
          <div
            className={cn(
              "flex min-h-10 w-40 max-w-full items-center justify-center rounded-md border border-dashed border-slate-300 bg-slate-50 px-3 py-2 text-xs font-medium text-slate-600 transition",
              dragging && "border-emerald-500 bg-emerald-50 text-emerald-700",
              uploading && "opacity-60",
            )}
            onDragOver={handleDragOver}
            onDragEnter={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={(event) => void handleDrop(event)}
          >
            <label className="inline-flex cursor-pointer items-center gap-2">
              <Upload className="size-4 shrink-0" aria-hidden="true" />
              <span>{uploading ? "上传中" : "上传 PDF"}</span>
              <input
                type="file"
                accept="application/pdf,.pdf"
                className="hidden"
                onChange={handleUpload}
                disabled={uploading}
              />
            </label>
          </div>
        ) : (
          <div className="rounded-md border border-dashed border-slate-200 px-3 py-2 text-xs text-slate-500">
            暂无文件
          </div>
        )
      ) : (
        <div className="space-y-2">
          {files.map((file) => (
            <div key={file.id} className="rounded-md border border-slate-200 bg-white p-2">
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-slate-900" title={file.original_name}>
                    <FileText className="mr-1 inline size-3" aria-hidden="true" />
                    {file.original_name}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    v{file.version} · {formatSize(file.file_size)}
                  </p>
                </div>
                <div className="flex shrink-0 flex-wrap justify-end gap-1">
                  <Tooltip label="下载当前文件">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => void handleDownload(file)}
                      aria-label="下载当前文件"
                      title="下载当前文件"
                    >
                      <Download className="size-4" aria-hidden="true" />
                    </Button>
                  </Tooltip>
                  <Tooltip label="查看历史版本">
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => void openHistory(file)}
                      aria-label="查看历史版本"
                      title="查看历史版本"
                    >
                      <History className="size-4" aria-hidden="true" />
                    </Button>
                  </Tooltip>
                  {canWrite && (
                    <Tooltip label="重新上传并生成新版本">
                      <Button
                        asChild
                        size="sm"
                        variant="ghost"
                        aria-label="重新上传并生成新版本"
                        title="重新上传并生成新版本"
                      >
                        <label>
                          <RefreshCw className="size-4" aria-hidden="true" />
                          <input
                            type="file"
                            accept="application/pdf,.pdf"
                            className="hidden"
                            onChange={(event) => void handleReplace(file, event)}
                          />
                        </label>
                      </Button>
                    </Tooltip>
                  )}
                  {canDelete && (
                    <Tooltip label="删除当前文件">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => void handleDelete(file)}
                        aria-label="删除当前文件"
                        title="删除当前文件"
                      >
                        <Trash2 className="size-4" aria-hidden="true" />
                      </Button>
                    </Tooltip>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {historyFile && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/30 p-4">
          <div className="w-full max-w-3xl rounded-md bg-white shadow-xl">
            <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-4 py-3">
              <div>
                <h2 className="text-base font-semibold text-slate-950">文件历史</h2>
                <p className="mt-1 text-xs text-slate-500">{historyFile.original_name}</p>
              </div>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setHistoryFile(null)}
                aria-label="关闭历史版本"
                title="关闭历史版本"
              >
                <X className="size-4" aria-hidden="true" />
              </Button>
            </div>
            <div className="max-h-[70vh] overflow-auto p-4">
              <table className="w-full min-w-[680px] text-left text-sm">
                <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-3 py-2 font-medium">版本号</th>
                    <th className="px-3 py-2 font-medium">文件名</th>
                    <th className="px-3 py-2 font-medium">上传人</th>
                    <th className="px-3 py-2 font-medium">上传时间</th>
                    <th className="px-3 py-2 font-medium">文件大小</th>
                    <th className="px-3 py-2 font-medium">状态</th>
                    <th className="px-3 py-2 font-medium">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {(versions[historyFile.id] ?? []).map((version) => (
                    <tr key={version.id}>
                      <td className="px-3 py-3 font-medium text-slate-900">v{version.version}</td>
                      <td className="max-w-72 px-3 py-3 text-slate-600">
                        <span className="block truncate" title={version.original_name}>
                          {version.original_name}
                        </span>
                      </td>
                      <td className="px-3 py-3 text-slate-600">
                        {version.uploaded_by ? `用户 #${version.uploaded_by}` : "-"}
                      </td>
                      <td className="px-3 py-3 text-slate-600">
                        {formatDateTime(version.uploaded_at)}
                      </td>
                      <td className="px-3 py-3 text-slate-600">{formatSize(version.file_size)}</td>
                      <td className="px-3 py-3">
                        <Badge tone={version.version === historyFile.version ? "success" : "neutral"}>
                          {version.version === historyFile.version ? "当前" : "历史"}
                        </Badge>
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex gap-1">
                          <Tooltip label="下载该版本">
                            <Button
                              size="sm"
                              variant="ghost"
                              onClick={() => void handleDownload(historyFile, version.version)}
                              aria-label="下载该版本"
                              title="下载该版本"
                            >
                              <Download className="size-4" aria-hidden="true" />
                            </Button>
                          </Tooltip>
                          {canPreview(version.mime_type) && (
                            <Tooltip label="查看该版本">
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => void handlePreview(historyFile, version.version)}
                                aria-label="查看该版本"
                                title="查看该版本"
                              >
                                <Eye className="size-4" aria-hidden="true" />
                              </Button>
                            </Tooltip>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {(versions[historyFile.id] ?? []).length === 0 && (
                <p className="py-8 text-center text-sm text-slate-500">暂无历史版本</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
