import { Download, Eye, FileText, History, RefreshCw, Trash2, Upload } from "lucide-react";
import { ChangeEvent, useCallback, useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SelectField } from "@/components/ui/form";
import { filesApi } from "@/services/files";
import type { FileRecord, FileVersion } from "@/types/files";

const categories = [
  { value: "clinical_document", label: "临床资料" },
  { value: "raw_pdf", label: "原始 PDF" },
  { value: "image_raw", label: "原始图像" },
  { value: "image_enhanced", label: "增强图像" },
  { value: "video_raw", label: "原始视频" },
  { value: "doctor_annotation", label: "医生批注" },
  { value: "metadata_json", label: "元数据 JSON" },
  { value: "annotation_json", label: "标注 JSON" },
  { value: "report", label: "报告文件" },
];

type FileActionsProps = {
  stageFileId?: number;
  subjectItemId?: number;
  defaultCategory?: string;
  canRead: boolean;
  canWrite: boolean;
  canDelete: boolean;
  onChanged?: () => void;
};

function canPreview(file: FileRecord) {
  return file.mime_type === "application/pdf" || file.mime_type.startsWith("image/");
}

function formatSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
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
  const [category, setCategory] = useState(defaultCategory);
  const [versions, setVersions] = useState<Record<number, FileVersion[]>>({});
  const [message, setMessage] = useState<string | null>(null);

  const loadFiles = useCallback(async () => {
    if (!canRead) return;
    const data = await filesApi.listFiles({ stage_file_id: stageFileId, subject_item_id: subjectItemId });
    setFiles(data);
  }, [canRead, stageFileId, subjectItemId]);

  useEffect(() => {
    void loadFiles();
  }, [loadFiles]);

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0];
    event.target.value = "";
    if (!selectedFile) return;
    try {
      await filesApi.uploadFile({
        file: selectedFile,
        fileCategory: category,
        stageFileId,
        subjectItemId,
      });
      setMessage("上传成功");
      await loadFiles();
      onChanged?.();
    } catch {
      setMessage("上传失败");
    }
  }

  async function handleReplace(file: FileRecord, event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0];
    event.target.value = "";
    if (!selectedFile) return;
    try {
      await filesApi.replaceFile(file.id, selectedFile, "前端替换");
      setMessage("替换成功");
      await loadFiles();
      onChanged?.();
    } catch {
      setMessage("替换失败");
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
      setMessage("该文件暂不支持预览");
    }
  }

  async function handleVersions(file: FileRecord) {
    if (versions[file.id]) {
      setVersions((current) => {
        const next = { ...current };
        delete next[file.id];
        return next;
      });
      return;
    }
    const data = await filesApi.listVersions(file.id);
    setVersions((current) => ({ ...current, [file.id]: data }));
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
    <div className="space-y-2">
      {message && <Badge tone={message.includes("失败") || message.includes("不支持") ? "danger" : "success"}>{message}</Badge>}
      {canWrite && (
        <div className="flex flex-wrap items-center gap-2">
          <SelectField
            value={category}
            onChange={(event) => setCategory(event.target.value)}
            className="h-8 w-32 text-xs"
          >
            {categories.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </SelectField>
          <Button asChild size="sm" variant="secondary">
            <label>
              <Upload className="size-4" aria-hidden="true" />
              上传
              <input type="file" className="hidden" onChange={handleUpload} />
            </label>
          </Button>
        </div>
      )}
      {files.length === 0 ? (
        <div className="rounded-md border border-dashed border-slate-200 px-3 py-2 text-xs text-slate-500">
          暂无文件
        </div>
      ) : (
        <div className="space-y-2">
          {files.map((file) => (
            <div key={file.id} className="rounded-md border border-slate-200 bg-white p-2">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-slate-900">
                    <FileText className="mr-1 inline size-3" aria-hidden="true" />
                    {file.original_name}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    v{file.version} · {formatSize(file.file_size)}
                  </p>
                </div>
                <div className="flex flex-wrap gap-1">
                  <Button size="sm" variant="ghost" onClick={() => void handleDownload(file)}>
                    <Download className="size-4" aria-hidden="true" />
                  </Button>
                  {canPreview(file) && (
                    <Button size="sm" variant="ghost" onClick={() => void handlePreview(file)}>
                      <Eye className="size-4" aria-hidden="true" />
                    </Button>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => void handleVersions(file)}>
                    <History className="size-4" aria-hidden="true" />
                  </Button>
                  {canWrite && (
                    <Button asChild size="sm" variant="ghost">
                      <label>
                        <RefreshCw className="size-4" aria-hidden="true" />
                        <input
                          type="file"
                          className="hidden"
                          onChange={(event) => void handleReplace(file, event)}
                        />
                      </label>
                    </Button>
                  )}
                  {canDelete && (
                    <Button size="sm" variant="ghost" onClick={() => void handleDelete(file)}>
                      <Trash2 className="size-4" aria-hidden="true" />
                    </Button>
                  )}
                </div>
              </div>
              {versions[file.id] && (
                <div className="mt-2 space-y-1 border-t border-slate-100 pt-2">
                  {versions[file.id].map((version) => (
                    <div
                      key={version.id}
                      className="flex items-center justify-between gap-2 text-xs text-slate-600"
                    >
                      <span>
                        v{version.version} · {version.original_name}
                      </span>
                      <div className="flex gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => void handleDownload(file, version.version)}
                        >
                          <Download className="size-4" aria-hidden="true" />
                        </Button>
                        {canPreview({
                          ...file,
                          mime_type: version.mime_type,
                        }) && (
                          <Button
                            size="sm"
                            variant="ghost"
                            onClick={() => void handlePreview(file, version.version)}
                          >
                            <Eye className="size-4" aria-hidden="true" />
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
