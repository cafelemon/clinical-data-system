import { CheckCheck } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { clinicalDataApi } from "@/services/clinical-data";
import type { ReviewBatchApproveTarget } from "@/types/clinical-data";

type BatchApproveButtonProps = {
  targets: ReviewBatchApproveTarget[];
  label: string;
  confirmText: string;
  onChanged: () => void;
};

export function BatchApproveButton({
  targets,
  label,
  confirmText,
  onChanged,
}: BatchApproveButtonProps) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [messageTone, setMessageTone] = useState<"success" | "warning" | "danger">("success");

  async function handleApprove() {
    if (targets.length === 0) return;
    if (!window.confirm(confirmText)) return;
    setBusy(true);
    try {
      const result = await clinicalDataApi.approveReviewsBatch({ targets });
      setMessage(`已通过 ${result.approved_count} 项，跳过 ${result.skipped_count} 项`);
      setMessageTone(result.approved_count > 0 ? "success" : "warning");
      onChanged();
    } catch {
      setMessage("一键审批失败");
      setMessageTone("danger");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button
        type="button"
        size="sm"
        variant="secondary"
        onClick={() => void handleApprove()}
        disabled={busy || targets.length === 0}
      >
        <CheckCheck className="size-4" aria-hidden="true" />
        {label}
      </Button>
      {message && <Badge tone={messageTone}>{message}</Badge>}
    </div>
  );
}
