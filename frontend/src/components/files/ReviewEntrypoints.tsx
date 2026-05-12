import { ListChecks, SquarePen } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
  subjectItemId?: number;
  canReadFiles: boolean;
  refreshKey?: number;
  linkState?: { origin: NavigationOriginState };
  onNavigate?: () => void;
};

export function ReviewEntrypoints({
  stageFileId,
  subjectItemId,
  canReadFiles,
  refreshKey = 0,
  linkState,
  onNavigate,
}: ReviewEntrypointsProps) {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canReadPdfReview = hasPermission("pdf_review:read");
  const canReadTasks = hasPermission("correction_tasks:read");
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [tasks, setTasks] = useState<CorrectionTask[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  const currentPdf = useMemo(() => files.find(isPdfFile) ?? null, [files]);
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
        subject_item_id: subjectItemId,
        status: "active",
      });
      setFiles(fileData);
      const pdf = fileData.find(isPdfFile);
      if (pdf && canReadTasks) {
        setTasks(await pdfReviewApi.listTasks({ file_id: pdf.id }));
      } else {
        setTasks([]);
      }
    } catch {
      setFiles([]);
      setTasks([]);
      setMessage("审阅入口加载失败");
    }
  }, [canReadFiles, canReadTasks, stageFileId, subjectItemId]);

  useEffect(() => {
    void loadData();
  }, [loadData, refreshKey]);

  if (!canReadFiles) {
    return <span className="text-xs text-slate-400">无文件权限</span>;
  }

  const reviewDisabledText = currentPdf ? "当前账号没有在线审阅权限" : "请先上传文件后再进行审阅";
  const taskDisabledText = currentPdf ? "暂无整改任务" : "请先上传文件后再查看任务单";

  return (
    <div className="min-w-[150px] space-y-2">
      <div className="flex flex-wrap gap-1">
        {currentPdf && canReadPdfReview ? (
          <Tooltip label="在线审阅 PDF">
            <Button
              asChild
              size="sm"
              variant="ghost"
              aria-label="在线审阅 PDF"
              title="在线审阅 PDF"
            >
              <Link
                to={`/pdf-review/files/${currentPdf.id}?version=${currentPdf.version}`}
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

        {currentPdf && canReadTasks && primaryTask ? (
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
                    : `/correction-tasks?file_id=${currentPdf.id}`
                }
                state={linkState}
                onClick={onNavigate}
              >
                <ListChecks className="size-4" aria-hidden="true" />
              </Link>
            </Button>
          </Tooltip>
        ) : (
          <Tooltip label={taskDisabledText}>
            <Button
              size="sm"
              variant="ghost"
              disabled={!currentPdf || !canReadTasks}
              onClick={() => setMessage(taskDisabledText)}
              aria-label={taskDisabledText}
              title={taskDisabledText}
            >
              <ListChecks className="size-4" aria-hidden="true" />
            </Button>
          </Tooltip>
        )}
      </div>
      {primaryTask ? (
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
