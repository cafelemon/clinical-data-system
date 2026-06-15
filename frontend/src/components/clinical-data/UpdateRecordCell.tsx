import { History, X } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { clinicalDataApi } from "@/services/clinical-data";
import type { SubjectItemTimelineEntry } from "@/types/clinical-data";

type UpdateRecordCellProps = {
  itemId: number;
  refreshKey?: number;
};

function formatDate(value: string) {
  return new Date(value).toLocaleDateString();
}

function formatDateTime(value: string) {
  return new Date(value).toLocaleString();
}

export function UpdateRecordCell({ itemId, refreshKey = 0 }: UpdateRecordCellProps) {
  const [records, setRecords] = useState<SubjectItemTimelineEntry[]>([]);
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const latestRecord = records[0] ?? null;
  const modalRecords = useMemo(() => records.slice(0, 20), [records]);

  const loadRecords = useCallback(async () => {
    try {
      const data = await clinicalDataApi.listSubjectItemTimeline(itemId, 20);
      setRecords(data);
      setMessage(null);
    } catch {
      setRecords([]);
      setMessage("记录加载失败");
    }
  }, [itemId]);

  useEffect(() => {
    void loadRecords();
  }, [loadRecords, refreshKey]);

  return (
    <div className="min-w-[150px] space-y-1">
      <Button
        size="sm"
        variant="ghost"
        onClick={() => setOpen(true)}
        aria-label="查看完整更新记录"
        title="查看完整更新记录"
      >
        <History className="size-4" aria-hidden="true" />
        记录
      </Button>
      {latestRecord ? (
        <p className="text-xs text-slate-500">
          最近：{latestRecord.action_label} · {formatDate(latestRecord.occurred_at)}
        </p>
      ) : (
        <p className="text-xs text-slate-400">{message ?? "暂无记录"}</p>
      )}

      {open && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-slate-950/30 p-4">
          <div className="w-full max-w-5xl rounded-md bg-white shadow-xl">
            <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-4 py-3">
              <div>
                <h2 className="text-base font-semibold text-slate-950">更新记录</h2>
                <p className="mt-1 text-xs text-slate-500">资料项 #{itemId} 的关键动作</p>
              </div>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => setOpen(false)}
                aria-label="关闭更新记录"
                title="关闭更新记录"
              >
                <X className="size-4" aria-hidden="true" />
              </Button>
            </div>
            <div className="max-h-[70vh] overflow-auto p-4">
              {message && <Badge tone="danger">{message}</Badge>}
              <table className="mt-2 w-full min-w-[900px] text-left text-sm">
                <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                  <tr>
                    <th className="px-3 py-2 font-medium">时间</th>
                    <th className="px-3 py-2 font-medium">操作人</th>
                    <th className="px-3 py-2 font-medium">操作类型</th>
                    <th className="px-3 py-2 font-medium">操作说明</th>
                    <th className="px-3 py-2 font-medium">关联文件版本</th>
                    <th className="px-3 py-2 font-medium">关联任务单</th>
                    <th className="px-3 py-2 font-medium">备注</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {modalRecords.map((record) => (
                    <tr key={record.id}>
                      <td className="px-3 py-3 text-slate-600">
                        {formatDateTime(record.occurred_at)}
                      </td>
                      <td className="px-3 py-3 text-slate-600">{record.actor || "-"}</td>
                      <td className="px-3 py-3">
                        <Badge>{record.action_label}</Badge>
                      </td>
                      <td className="max-w-72 px-3 py-3 text-slate-600">
                        {record.description || "-"}
                      </td>
                      <td className="px-3 py-3 text-slate-600">
                        {record.file_version ? `v${record.file_version}` : "-"}
                      </td>
                      <td className="px-3 py-3 text-slate-600">
                        {record.task_id ? `#${record.task_id}` : "-"}
                      </td>
                      <td className="max-w-72 px-3 py-3 text-slate-600">
                        {record.remark || "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {modalRecords.length === 0 && (
                <p className="py-8 text-center text-sm text-slate-500">暂无更新记录</p>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
