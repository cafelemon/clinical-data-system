import { ClipboardList, Eye, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SelectField } from "@/components/ui/form";
import type { NavigationOriginState } from "@/lib/navigation-origin";
import { pdfReviewApi } from "@/services/pdf-review";
import { useAuthStore } from "@/stores/auth-store";
import type { CorrectionTask } from "@/types/pdf-review";

const statusLabels: Record<string, string> = {
  pending: "待处理",
  processing: "处理中",
  submitted: "待复审",
  returned: "再次退回",
  closed: "已关闭",
  cancelled: "已取消",
};

function statusTone(status: string) {
  if (status === "closed") return "success";
  if (status === "returned") return "danger";
  if (status === "submitted") return "warning";
  return "neutral";
}

function formatDateTime(value: string | null) {
  return value ? value.replace("T", " ").slice(0, 16) : "-";
}

export function CorrectionTasksPage() {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canRead = hasPermission("correction_tasks:read");
  const fileId = Number(searchParams.get("file_id")) || undefined;
  const [statusFilter, setStatusFilter] = useState(searchParams.get("status") ?? "");
  const [tasks, setTasks] = useState<CorrectionTask[]>([]);
  const [message, setMessage] = useState<string | null>(null);
  const origin: NavigationOriginState = {
    from: `${location.pathname}${location.search}`,
    backLabel: "返回任务",
  };

  const loadTasks = useCallback(async () => {
    if (!canRead) return;
    try {
      const data = await pdfReviewApi.listTasks({
        file_id: fileId,
        status: statusFilter || undefined,
      });
      setTasks(data);
      setMessage(null);
    } catch {
      setMessage("整改任务加载失败");
    }
  }, [canRead, fileId, statusFilter]);

  useEffect(() => {
    void loadTasks();
  }, [loadTasks]);

  function updateStatusFilter(status: string) {
    setStatusFilter(status);
    const next = new URLSearchParams(searchParams);
    if (status) {
      next.set("status", status);
    } else {
      next.delete("status");
    }
    setSearchParams(next);
  }

  if (!canRead) {
    return <p className="text-sm text-slate-500">当前账号没有整改任务权限</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">整改任务</h1>
          <p className="mt-1 text-sm text-slate-500">
            跟踪 PDF 批注生成的整改、重传和复审状态
          </p>
        </div>
        <Button variant="secondary" onClick={() => void loadTasks()}>
          <RotateCcw className="size-4" aria-hidden="true" />
          刷新
        </Button>
      </div>

      {message && <Badge tone="danger">{message}</Badge>}

      <div className="flex flex-wrap items-center gap-2">
        <SelectField
          value={statusFilter}
          onChange={(event) => updateStatusFilter(event.target.value)}
          className="h-9 w-40"
        >
          <option value="">全部状态</option>
          <option value="pending">待处理</option>
          <option value="submitted">待复审</option>
          <option value="returned">再次退回</option>
          <option value="closed">已关闭</option>
        </SelectField>
        {fileId && <Badge>文件 #{fileId}</Badge>}
      </div>

      <div className="grid gap-3">
        {tasks.map((task) => (
          <Card key={task.id}>
            <CardHeader>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <ClipboardList className="size-4" aria-hidden="true" />
                    {task.title}
                  </CardTitle>
                  <p className="mt-1 text-xs text-slate-500">
                    {task.task_no} · 创建 {formatDateTime(task.created_at)}
                  </p>
                </div>
                <Badge tone={statusTone(task.status)}>
                  {statusLabels[task.status] ?? task.status}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="space-y-1 text-sm text-slate-600">
                  <p>批注：{task.annotations.length} 条</p>
                  <p>提交：{formatDateTime(task.submitted_at)}</p>
                  <p>复审：{formatDateTime(task.reviewed_at)}</p>
                </div>
                <Button asChild variant="secondary">
                  <Link to={`/correction-tasks/${task.id}`} state={{ origin }}>
                    <Eye className="size-4" aria-hidden="true" />
                    查看
                  </Link>
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
        {tasks.length === 0 && (
          <div className="rounded-md border border-dashed border-slate-200 bg-white p-8 text-sm text-slate-500">
            暂无整改任务
          </div>
        )}
      </div>
    </div>
  );
}
