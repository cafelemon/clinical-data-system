import { useCallback, useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";
import { inputClassName } from "@/lib/form-styles";
import { clinicalDataApi } from "@/services/clinical-data";
import type { SubjectItem, SubjectItemRemarkResponse } from "@/types/clinical-data";

type RemarkAutosaveCellProps = {
  item: SubjectItem;
  canWrite: boolean;
  onSaved: (itemId: number, response: SubjectItemRemarkResponse) => void;
};

type SaveStatus = "idle" | "dirty" | "saving" | "saved" | "error";

function statusText(status: SaveStatus) {
  if (status === "dirty") return "待保存";
  if (status === "saving") return "保存中...";
  if (status === "saved") return "已保存";
  if (status === "error") return "保存失败，请重试";
  return "";
}

export function RemarkAutosaveCell({ item, canWrite, onSaved }: RemarkAutosaveCellProps) {
  const initialValue = item.remark ?? "";
  const [value, setValue] = useState(initialValue);
  const [savedValue, setSavedValue] = useState(initialValue);
  const [status, setStatus] = useState<SaveStatus>("idle");
  const saveSeqRef = useRef(0);
  const valueRef = useRef(initialValue);

  useEffect(() => {
    const nextValue = item.remark ?? "";
    valueRef.current = nextValue;
    setValue(nextValue);
    setSavedValue(nextValue);
    setStatus("idle");
  }, [item.id, item.remark]);

  const saveRemark = useCallback(async () => {
    if (!canWrite || value === savedValue) {
      if (status !== "idle" && value === savedValue) setStatus("saved");
      return;
    }
    const seq = saveSeqRef.current + 1;
    saveSeqRef.current = seq;
    const submittedValue = value;
    setStatus("saving");
    try {
      const response = await clinicalDataApi.updateSubjectItemRemark(item.id, {
        remark: value.trim() || null,
      });
      if (saveSeqRef.current !== seq) return;
      const nextSavedValue = response.remark ?? "";
      setSavedValue(nextSavedValue);
      const canApplySavedValue =
        valueRef.current === submittedValue || valueRef.current.trim() === nextSavedValue;
      if (canApplySavedValue) {
        valueRef.current = nextSavedValue;
        setValue(nextSavedValue);
        setStatus("saved");
        onSaved(item.id, response);
      } else {
        setStatus("dirty");
      }
    } catch {
      if (saveSeqRef.current === seq) setStatus("error");
    }
  }, [canWrite, item.id, onSaved, savedValue, status, value]);

  useEffect(() => {
    if (!canWrite || value === savedValue) return;
    setStatus("dirty");
    const timer = window.setTimeout(() => {
      void saveRemark();
    }, 800);
    return () => window.clearTimeout(timer);
  }, [canWrite, saveRemark, savedValue, value]);

  function handleBlur() {
    void saveRemark();
  }

  function handleChange(nextValue: string) {
    valueRef.current = nextValue;
    setValue(nextValue);
  }

  if (!canWrite) {
    return <span className="text-sm text-slate-600">{item.remark || "-"}</span>;
  }

  return (
    <div className="min-w-[180px] space-y-1">
      <textarea
        className={cn(
          inputClassName("min-h-9 resize-none py-2 text-xs transition-all focus:min-h-20"),
          status === "error" && "border-red-300 focus-visible:outline-red-400",
        )}
        value={value}
        onChange={(event) => handleChange(event.target.value)}
        onBlur={handleBlur}
        rows={1}
        placeholder="备注"
      />
      {status !== "idle" && (
        <p
          className={cn(
            "text-xs",
            status === "error" ? "text-red-600" : "text-slate-500",
            status === "saved" && "text-emerald-600",
          )}
        >
          {statusText(status)}
        </p>
      )}
    </div>
  );
}
