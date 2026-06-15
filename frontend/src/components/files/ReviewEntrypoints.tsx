import { ListChecks, SquarePen } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SelectField } from "@/components/ui/form";
import { Tooltip } from "@/components/ui/tooltip";
import type { NavigationOriginState } from "@/lib/navigation-origin";
import { filesApi } from "@/services/files";
import { pdfReviewApi } from "@/services/pdf-review";
import { useAuthStore } from "@/stores/auth-store";
import type { FileRecord } from "@/types/files";
import type { CorrectionTask } from "@/types/pdf-review";

const taskStatusLabels: Record<string, string> = {
  pending: "待整改",
  processing: "处理中",
  submitted: "待复审",
  returned: "再次退回",
  closed: "已关闭",
  cancelled: "已取消",
};

function taskStatusTone(status: string) {
  if (status === "closed") return "success";
  if (status === "returned" || status === "pending") return "danger";
  if (status === "submitted") return "warning";
  return "neutral";
}

function isPdfFile(file: FileRecord) {
  return file.mime_type === "application/pdf" || file.original_name.toLowerCase().endsWith(".pdf");
}

type ReviewEntrypointsProps = {
  stageFileId?: number;
  ssuProgressId?: number;
  subjectItemId?: number;
  canReadFiles: boolean;
  readOnlyReview?: boolean;
  refreshKey?: number;
  linkState?: { origin: NavigationOriginState };
  onNavigate?: () => void;
};

export function ReviewEntrypoints({
  stageFileId,
  ssuProgressId,
  subjectItemId,
  canReadFiles,
  readOnlyReview = false,
  refreshKey = 0,
  linkState,
  onNavigate,
}: ReviewEntrypointsProps) {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canReadPdfReview = hasPermission("pdf_review:read");
  const canReadTasks = hasPermission("correction_tasks:read");
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [selectedPdfId, setSelectedPdfId] = useState<number | null>(null);
  const [tasks, setTasks] = useState<CorrectionTask[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  const pdfFiles = useMemo(() => files.filter(isPdfFile), [files]);
  const selectedPdf = useMemo(
    () => pdfFiles.find((file) => file.id === selectedPdfId) ?? pdfFiles[0] ?? null,
    [pdfFiles, selectedPdfId],
  );
  const primaryTask = useMemo(
    () =>
      tasks.find((task) => !["closed", "cancelled"].includes(task.status)) ??
      tasks[0] ??
      null,
    [tasks],
  );

  const loadData = useCallback(async () => {
    if (!canReadFiles) return;
    try {
      const fileData = await filesApi.listFiles({
        stage_file_id: stageFileId,
        ssu_progress_id: ssuProgressId,
        subject_item_id: subjectItemId,
        status: "active",
      });
      setFiles(fileData);
      setMessage(null);
    } catch {
      setFiles([]);
      setTasks([]);
      setMessage("审阅入口加载失败");
    }
  }, [canReadFiles, ssuProgressId, stageFileId, subjectItemId]);

  useEffect(() => {
    void loadData();
  }, [loadData, refreshKey]);

  useEffect(() => {
    if (pdfFiles.length === 0) {
      setSelectedPdfId(null);
      return;
    }
    if (!selectedPdfId || !pdfFiles.some((file) => file.id === selectedPdfId)) {
      setSelectedPdfId(pdfFiles[0].id);
    }
  }, [pdfFiles, selectedPdfId]);

  useEffect(() => {
    let cancelled = false;
    async function loadTasks() {
      if (!selectedPdf || !canReadTasks || readOnlyReview) {
        setTasks([]);
        return;
      }
      try {
        const taskData = await pdfReviewApi.listTasks({ file_id: selectedPdf.id });
        if (!cancelled) {
          setTasks(taskData);
        }
      } catch {
        if (!cancelled) {
          setTasks([]);
          setMessage("整改任务加载失败");
        }
      }
    }
    void loadTasks();
    return () => {
      cancelled = true;
    };
  }, [canReadTasks, readOnlyReview, selectedPdf]);

  if (!canReadFiles) {
    return <span className="text-xs text-slate-400">无文件权限</span>;
  }

  const reviewDisabledText = selectedPdf ? "当前账号没有在线审阅权限" : "请先上传文件后再进行审阅";
  const taskDisabledText = selectedPdf ? "暂无整改任务" : "请先上传文件后再查看任务单";

  return (
    <div className="min-w-[150px] space-y-2">
      {pdfFiles.length > 1 && (
        <SelectField
          value={String(selectedPdf?.id ?? "")}
          onChange={(event) => setSelectedPdfId(Number(event.target.value))}
          className="h-8 max-w-52 text-xs"
          aria-label="选择审阅 PDF"
          title={selectedPdf?.original_name ?? "选择审阅 PDF"}
        >
          {pdfFiles.map((file) => (
            <option key={file.id} value={file.id}>
              {file.original_name} · v{file.version}
            </option>
          ))}
        </SelectField>
      )}
      <div className="flex flex-wrap gap-1">
        {selectedPdf && canReadPdfReview ? (
          <Tooltip label="在线审阅 PDF">
            <Button
              asChild
              size="sm"
              variant="ghost"
              aria-label="在线审阅 PDF"
              title="在线审阅 PDF"
            >
              <Link
                to={`/pdf-review/files/${selectedPdf.id}?version=${selectedPdf.version}${
                  readOnlyReview ? "&mode=readonly" : ""
                }`}
                state={linkState}
                onClick={onNavigate}
              >
                <SquarePen className="size-4" aria-hidden="true" />
              </Link>
            </Button>
          </Tooltip>
        ) : (
          <Tooltip label={reviewDisabledText}>
            <Button
              size="sm"
              variant="ghost"
              disabled
              aria-label={reviewDisabledText}
              title={reviewDisabledText}
            >
              <SquarePen className="size-4" aria-hidden="true" />
            </Button>
          </Tooltip>
        )}

        {!readOnlyReview && selectedPdf && canReadTasks && primaryTask ? (
          <Tooltip label="查看整改任务单">
            <Button
              asChild
              size="sm"
              variant="ghost"
              aria-label="查看整改任务单"
              title="查看整改任务单"
            >
              <Link
                to={
                  tasks.length === 1
                    ? `/correction-tasks/${primaryTask.id}`
                    : `/correction-tasks?file_id=${selectedPdf.id}`
                }
                state={linkState}
                onClick={onNavigate}
              >
                <ListChecks className="size-4" aria-hidden="true" />
              </Link>
            </Button>
          </Tooltip>
        ) : (
          <Tooltip label={readOnlyReview ? "SSU 文件仅在线审阅，不生成整改任务" : taskDisabledText}>
            <Button
              size="sm"
              variant="ghost"
              disabled={!selectedPdf || !canReadTasks || readOnlyReview}
              onClick={() => setMessage(readOnlyReview ? "SSU 文件仅在线审阅" : taskDisabledText)}
              aria-label={readOnlyReview ? "SSU 文件仅在线审阅" : taskDisabledText}
              title={readOnlyReview ? "SSU 文件仅在线审阅" : taskDisabledText}
            >
              <ListChecks className="size-4" aria-hidden="true" />
            </Button>
          </Tooltip>
        )}
      </div>
      {readOnlyReview ? (
        <Badge tone="neutral">只读审阅</Badge>
      ) : primaryTask ? (
        <Badge tone={taskStatusTone(primaryTask.status)}>
          任务单 · {taskStatusLabels[primaryTask.status] ?? primaryTask.status}
        </Badge>
      ) : (
        <Badge tone="neutral">无任务</Badge>
      )}
      {message && <p className="text-xs text-slate-500">{message}</p>}
    </div>
  );
}
