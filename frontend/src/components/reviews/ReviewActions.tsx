import { Check, History, Send, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { inputClassName } from "@/lib/form-styles";
import { clinicalDataApi } from "@/services/clinical-data";
import type { ReviewRecord, ReviewTargetType } from "@/types/clinical-data";

const uploadedStatuses = new Set(["uploaded", "replaced"]);

const actionLabels: Record<string, string> = {
  submit: "提交",
  approve: "通过",
  reject: "驳回",
  recalculate: "重算",
};

type ReviewActionsProps = {
  targetType: ReviewTargetType;
  targetId: number;
  uploadStatus: string;
  reviewStatus: string;
  canSubmit: boolean;
  canReview: boolean;
  canReadRecords: boolean;
  showLatest?: boolean;
  onChanged: () => void;
};

function formatRecord(record: ReviewRecord) {
  const action = actionLabels[record.action] ?? record.action;
  const date = new Date(record.created_at).toLocaleDateString();
  return `${action} · ${date}`;
}

export function ReviewActions({
  targetType,
  targetId,
  uploadStatus,
  reviewStatus,
  canSubmit,
  canReview,
  canReadRecords,
  showLatest = true,
  onChanged,
}: ReviewActionsProps) {
  const [records, setRecords] = useState<ReviewRecord[]>([]);
  const [recordsOpen, setRecordsOpen] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [rejectComment, setRejectComment] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const latestRecord = records[0];
  const canSubmitTarget = useMemo(
    () =>
      canSubmit &&
      uploadedStatuses.has(uploadStatus) &&
      reviewStatus !== "pending" &&
      reviewStatus !== "approved",
    [canSubmit, reviewStatus, uploadStatus],
  );
  const canReviewTarget = canReview && reviewStatus === "pending";

  const loadRecords = useCallback(async () => {
    if (!canReadRecords) return;
    const data = await clinicalDataApi.listReviewRecords(targetType, targetId);
    setRecords(data);
  }, [canReadRecords, targetId, targetType]);

  useEffect(() => {
    setRecords([]);
    setRecordsOpen(false);
    setRejectOpen(false);
    setRejectComment("");
    setMessage(null);
  }, [targetId, targetType]);

  useEffect(() => {
    if (showLatest && canReadRecords) {
      void loadRecords();
    }
  }, [canReadRecords, loadRecords, showLatest]);

  async function runAction(action: "submit" | "approve" | "reject") {
    const comment = action === "reject" ? rejectComment.trim() : undefined;
    if (action === "reject" && !comment) {
      setMessage("请填写驳回原因");
      return;
    }
    setBusy(true);
    try {
      if (action === "submit") {
        await clinicalDataApi.submitReview({ target_type: targetType, target_id: targetId });
        setMessage("已提交审核");
      }
      if (action === "approve") {
        await clinicalDataApi.approveReview({ target_type: targetType, target_id: targetId });
        setMessage("已审核通过");
      }
      if (action === "reject") {
        await clinicalDataApi.rejectReview({
          target_type: targetType,
          target_id: targetId,
          comment,
        });
        setMessage("已驳回");
        setRejectOpen(false);
        setRejectComment("");
      }
      await loadRecords();
      onChanged();
    } catch {
      setMessage("操作失败");
    } finally {
      setBusy(false);
    }
  }

  async function toggleRecords() {
    if (!recordsOpen) {
      await loadRecords();
    }
    setRecordsOpen((current) => !current);
  }

  return (
    <div className="min-w-[180px] space-y-2">
      <div className="flex flex-wrap gap-1">
        {canSubmitTarget && (
          <Button
            size="sm"
            variant="secondary"
            onClick={() => void runAction("submit")}
            disabled={busy}
            title="提交审核"
          >
            <Send className="size-4" aria-hidden="true" />
            提交
          </Button>
        )}
        {canReviewTarget && (
          <>
            <Button
              size="sm"
              variant="secondary"
              onClick={() => void runAction("approve")}
              disabled={busy}
              title="审核通过"
            >
              <Check className="size-4" aria-hidden="true" />
              通过
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setRejectOpen((current) => !current)}
              disabled={busy}
              title="驳回"
            >
              <X className="size-4" aria-hidden="true" />
              驳回
            </Button>
          </>
        )}
        {canReadRecords && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => void toggleRecords()}
            disabled={busy}
            title="审核记录"
          >
            <History className="size-4" aria-hidden="true" />
            记录
          </Button>
        )}
      </div>

      {rejectOpen && (
        <div className="flex flex-col gap-2">
          <input
            className={inputClassName("h-8 text-xs")}
            value={rejectComment}
            onChange={(event) => setRejectComment(event.target.value)}
            placeholder="驳回原因"
            required
          />
          <Button
            size="sm"
            variant="secondary"
            onClick={() => void runAction("reject")}
            disabled={busy}
          >
            确认驳回
          </Button>
        </div>
      )}

      {message && (
        <Badge tone={message.includes("失败") || message.includes("原因") ? "danger" : "success"}>
          {message}
        </Badge>
      )}

      {showLatest && latestRecord && !recordsOpen && (
        <p className="text-xs text-slate-500">
          最近：{formatRecord(latestRecord)}
          {latestRecord.comment ? ` · ${latestRecord.comment}` : ""}
        </p>
      )}

      {recordsOpen && (
        <div className="space-y-1 border-t border-slate-100 pt-2 text-xs text-slate-600">
          {records.length === 0 ? (
            <p>暂无审核记录</p>
          ) : (
            records.slice(0, 5).map((record) => (
              <p key={record.id}>
                {formatRecord(record)}
                {record.comment ? ` · ${record.comment}` : ""}
              </p>
            ))
          )}
        </div>
      )}
    </div>
  );
}
