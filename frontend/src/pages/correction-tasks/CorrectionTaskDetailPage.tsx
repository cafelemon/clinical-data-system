import {
  ArrowLeft,
  Check,
  FileUp,
  LocateFixed,
  RotateCcw,
  Send,
  X,
} from "lucide-react";
import { ChangeEvent, useCallback, useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TextAreaField } from "@/components/ui/form";
import { buildRestoreState, type NavigationOriginState } from "@/lib/navigation-origin";
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

const issueLabels: Record<string, string> = {
  missing_page: "缺页",
  wrong_page: "错页",
  unclear_scan: "扫描不清晰",
  inconsistent_info: "信息不一致",
  missing_signature: "签名缺失",
  missing_stamp: "盖章缺失",
  missing_date: "日期缺失",
  wrong_subject: "受试者不匹配",
  wrong_document: "资料类型不匹配",
  other: "其他",
};

const annotationStatusLabels: Record<string, string> = {
  open: "待处理",
  task_created: "已生成任务",
  submitted: "待复审",
  resolved: "已解决",
  rejected: "复审退回",
  closed: "已关闭",
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

export function CorrectionTaskDetailPage() {
  const params = useParams();
  const location = useLocation();
  const taskId = Number(params.taskId);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canSubmit = hasPermission("correction_tasks:submit");
  const canReview = hasPermission("correction_tasks:review");
  const [task, setTask] = useState<CorrectionTask | null>(null);
  const [remark, setRemark] = useState("");
  const [reviewComment, setReviewComment] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const origin =
    ((location.state as { origin?: NavigationOriginState } | null)?.origin ?? null) ??
    ({
      from: "/correction-tasks",
      backLabel: "返回任务",
    } satisfies NavigationOriginState);
  const backState = buildRestoreState(origin);

  const loadTask = useCallback(async () => {
    if (!taskId) return;
    try {
      const data = await pdfReviewApi.getTask(taskId);
      setTask(data);
      setMessage(null);
    } catch {
      setMessage("整改任务加载失败");
    }
  }, [taskId]);

  useEffect(() => {
    void loadTask();
  }, [loadTask]);

  async function submitFile(event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0];
    event.target.value = "";
    if (!selectedFile || !task) return;
    setBusy(true);
    try {
      const updated = await pdfReviewApi.submitTask(task.id, selectedFile, remark.trim() || undefined);
      setTask(updated);
      setRemark("");
      setMessage("整改文件已提交，等待复审");
    } catch {
      setMessage("整改文件提交失败");
    } finally {
      setBusy(false);
    }
  }

  async function approveTask() {
    if (!task) return;
    setBusy(true);
    try {
      const updated = await pdfReviewApi.approveTask(task.id, reviewComment.trim() || undefined);
      setTask(updated);
      setReviewComment("");
      setMessage("复审已通过");
    } catch {
      setMessage("复审通过失败");
    } finally {
      setBusy(false);
    }
  }

  async function returnTask() {
    if (!task) return;
    const comment = reviewComment.trim();
    if (!comment) {
      setMessage("请填写再次退回原因");
      return;
    }
    setBusy(true);
    try {
      const updated = await pdfReviewApi.returnTask(task.id, comment);
      setTask(updated);
      setReviewComment("");
      setMessage("已再次退回整改");
    } catch {
      setMessage("再次退回失败");
    } finally {
      setBusy(false);
    }
  }

  if (!task) {
    return (
      <div className="space-y-4">
        <Button asChild variant="ghost" className="px-0">
          <Link to={origin.from} state={backState}>
            <ArrowLeft className="size-4" aria-hidden="true" />
            {origin.backLabel}
          </Link>
        </Button>
        {message ? <Badge tone="danger">{message}</Badge> : <p>正在加载</p>}
      </div>
    );
  }

  const firstAnnotation = task.annotations[0];
  const reviewLink = firstAnnotation
    ? `/pdf-review/files/${task.file_id}?file_version_id=${firstAnnotation.file_version_id}`
    : `/pdf-review/files/${task.file_id}`;
  const reviewState = { origin };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Button asChild variant="ghost" className="mb-2 px-0">
            <Link to={origin.from} state={backState}>
              <ArrowLeft className="size-4" aria-hidden="true" />
              {origin.backLabel}
            </Link>
          </Button>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">{task.title}</h1>
          <p className="mt-1 text-sm text-slate-500">{task.task_no}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge tone={statusTone(task.status)}>{statusLabels[task.status] ?? task.status}</Badge>
            <Badge>批注 {task.annotations.length} 条</Badge>
          </div>
        </div>
        <Button variant="secondary" onClick={() => void loadTask()}>
          <RotateCcw className="size-4" aria-hidden="true" />
          刷新
        </Button>
      </div>

      {message && (
        <Badge tone={message.includes("失败") || message.includes("请") ? "danger" : "success"}>
          {message}
        </Badge>
      )}

      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>任务信息</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <p className="text-xs text-slate-500">创建时间</p>
                <p className="mt-1 font-medium">{formatDateTime(task.created_at)}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">提交时间</p>
                <p className="mt-1 font-medium">{formatDateTime(task.submitted_at)}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">复审时间</p>
                <p className="mt-1 font-medium">{formatDateTime(task.reviewed_at)}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">关闭时间</p>
                <p className="mt-1 font-medium">{formatDateTime(task.closed_at)}</p>
              </div>
              <div className="sm:col-span-2">
                <p className="text-xs text-slate-500">整改说明</p>
                <p className="mt-1 whitespace-pre-wrap text-slate-700">
                  {task.description || "-"}
                </p>
              </div>
              <div className="sm:col-span-2">
                <p className="text-xs text-slate-500">上传说明</p>
                <p className="mt-1 whitespace-pre-wrap text-slate-700">
                  {task.submission_remark || "-"}
                </p>
              </div>
              <div className="sm:col-span-2">
                <p className="text-xs text-slate-500">复审意见</p>
                <p className="mt-1 whitespace-pre-wrap text-slate-700">
                  {task.review_comment || "-"}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div className="flex items-center justify-between gap-2">
                <CardTitle>批注问题</CardTitle>
                <Button asChild variant="secondary">
                  <Link to={reviewLink} state={reviewState}>
                    <LocateFixed className="size-4" aria-hidden="true" />
                    打开审阅
                  </Link>
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {task.annotations.map((annotation, index) => (
                <div key={annotation.id} className="rounded-md border border-slate-200 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge>#{index + 1}</Badge>
                    <span className="text-sm font-medium text-slate-900">
                      第 {annotation.page_no} 页 ·{" "}
                      {issueLabels[annotation.issue_type] ?? annotation.issue_type}
                    </span>
                    <Badge>{annotationStatusLabels[annotation.status] ?? annotation.status}</Badge>
                  </div>
                  <p className="mt-2 whitespace-pre-wrap text-sm text-slate-600">
                    {annotation.comment}
                  </p>
                  <Button asChild size="sm" variant="ghost" className="mt-2">
                    <Link
                      to={`/pdf-review/files/${task.file_id}?file_version_id=${annotation.file_version_id}`}
                      state={reviewState}
                    >
                      <LocateFixed className="size-4" aria-hidden="true" />
                      定位
                    </Link>
                  </Button>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          {canSubmit && task.status !== "closed" && task.status !== "cancelled" && (
            <Card>
              <CardContent className="space-y-3 py-4">
                <h2 className="text-sm font-semibold text-slate-900">提交整改文件</h2>
                <TextAreaField
                  value={remark}
                  onChange={(event) => setRemark(event.target.value)}
                  placeholder="整改说明"
                />
                <Button asChild disabled={busy}>
                  <label>
                    <FileUp className="size-4" aria-hidden="true" />
                    上传PDF
                    <input
                      type="file"
                      accept="application/pdf,.pdf"
                      className="hidden"
                      onChange={(event) => void submitFile(event)}
                    />
                  </label>
                </Button>
              </CardContent>
            </Card>
          )}

          {canReview && task.status === "submitted" && (
            <Card>
              <CardContent className="space-y-3 py-4">
                <h2 className="text-sm font-semibold text-slate-900">复审操作</h2>
                <TextAreaField
                  value={reviewComment}
                  onChange={(event) => setReviewComment(event.target.value)}
                  placeholder="复审意见；再次退回时必填"
                />
                <div className="flex flex-wrap gap-2">
                  <Button onClick={() => void approveTask()} disabled={busy}>
                    <Check className="size-4" aria-hidden="true" />
                    通过
                  </Button>
                  <Button variant="ghost" onClick={() => void returnTask()} disabled={busy}>
                    <X className="size-4" aria-hidden="true" />
                    再次退回
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          <Card>
            <CardContent className="space-y-2 py-4 text-sm text-slate-600">
              <p className="font-medium text-slate-900">流转</p>
              <p>
                <Send className="mr-1 inline size-4" aria-hidden="true" />
                创建后由上传人按批注整改并提交新版本。
              </p>
              <p>复审通过后任务关闭；不通过则原任务再次退回。</p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
