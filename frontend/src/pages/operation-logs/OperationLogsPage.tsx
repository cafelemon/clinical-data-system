import { Search, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, SelectField } from "@/components/ui/form";
import { inputClassName } from "@/lib/form-styles";
import { masterDataApi } from "@/services/master-data";
import { operationLogsApi } from "@/services/operation-logs";
import { useAuthStore } from "@/stores/auth-store";
import type { Center, Project } from "@/types/master-data";
import type { OperationLog, OperationLogFilters } from "@/types/operation-log";

const limit = 20;

function compactDetail(detail: Record<string, unknown> | null) {
  if (!detail || Object.keys(detail).length === 0) return "";
  const text = JSON.stringify(detail);
  return text.length > 140 ? `${text.slice(0, 140)}...` : text;
}

function toNumber(value: string) {
  const numberValue = Number(value);
  return Number.isFinite(numberValue) && numberValue > 0 ? numberValue : undefined;
}

function buildFilters(
  filters: {
    username: string;
    action: string;
    targetType: string;
    targetId: string;
    projectId: number | undefined;
    centerId: number | undefined;
    createdFrom: string;
    createdTo: string;
  },
  offset: number,
): OperationLogFilters {
  return {
    username: filters.username || undefined,
    action: filters.action || undefined,
    target_type: filters.targetType || undefined,
    target_id: toNumber(filters.targetId),
    project_id: filters.projectId,
    center_id: filters.centerId,
    created_from: filters.createdFrom || undefined,
    created_to: filters.createdTo || undefined,
    limit,
    offset,
  };
}

function LogTable({ logs }: { logs: OperationLog[] }) {
  if (logs.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
        暂无操作日志
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[1080px] text-left text-sm">
        <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-3 py-2 font-medium">时间</th>
            <th className="px-3 py-2 font-medium">用户</th>
            <th className="px-3 py-2 font-medium">动作</th>
            <th className="px-3 py-2 font-medium">对象</th>
            <th className="px-3 py-2 font-medium">项目/中心</th>
            <th className="px-3 py-2 font-medium">IP</th>
            <th className="px-3 py-2 font-medium">摘要</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {logs.map((log) => (
            <tr key={log.id}>
              <td className="px-3 py-3 text-slate-600">
                {new Date(log.created_at).toLocaleString()}
              </td>
              <td className="px-3 py-3 text-slate-900">{log.username ?? "-"}</td>
              <td className="px-3 py-3">
                <Badge tone="neutral">{log.action}</Badge>
              </td>
              <td className="px-3 py-3 text-slate-600">
                {log.target_type ?? "-"}
                {log.target_id ? ` #${log.target_id}` : ""}
              </td>
              <td className="px-3 py-3 text-slate-600">
                {log.project_id ? `P${log.project_id}` : "-"}
                {log.center_id ? ` / C${log.center_id}` : ""}
              </td>
              <td className="px-3 py-3 text-slate-600">{log.ip_address ?? "-"}</td>
              <td className="max-w-80 px-3 py-3 text-slate-600">{compactDetail(log.detail_json)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function OperationLogsPage() {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canReadLogs = hasPermission("operation_logs:read");
  const [projects, setProjects] = useState<Project[]>([]);
  const [centers, setCenters] = useState<Center[]>([]);
  const [logs, setLogs] = useState<OperationLog[]>([]);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFilters] = useState({
    username: "",
    action: "",
    targetType: "",
    targetId: "",
    projectId: undefined as number | undefined,
    centerId: undefined as number | undefined,
    createdFrom: "",
    createdTo: "",
  });

  const page = useMemo(() => Math.floor(offset / limit) + 1, [offset]);
  const pageCount = useMemo(() => Math.max(Math.ceil(total / limit), 1), [total]);

  const refresh = useCallback(async () => {
    if (!canReadLogs) return;
    setLoading(true);
    setError(null);
    try {
      const result = await operationLogsApi.list(buildFilters(filters, offset));
      setLogs(result.items);
      setTotal(result.total);
    } catch {
      setLogs([]);
      setTotal(0);
      setError("操作日志加载失败");
    } finally {
      setLoading(false);
    }
  }, [canReadLogs, filters, offset]);

  useEffect(() => {
    if (!canReadLogs) return;
    async function loadProjects() {
      try {
        setProjects(await masterDataApi.listProjects());
      } catch {
        setProjects([]);
      }
    }
    void loadProjects();
  }, [canReadLogs]);

  useEffect(() => {
    if (!canReadLogs) return;
    async function loadCenters() {
      try {
        setCenters(await masterDataApi.listCenters(filters.projectId));
      } catch {
        setCenters([]);
      }
    }
    void loadCenters();
  }, [canReadLogs, filters.projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (!canReadLogs) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">操作日志</h1>
          <p className="mt-1 text-sm text-slate-500">业务审计与治理追踪</p>
        </div>
        <Card>
          <CardContent className="flex items-center gap-3 py-8 text-sm text-slate-600">
            <ShieldCheck className="size-5 text-slate-400" aria-hidden="true" />
            当前账号没有操作日志权限
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">操作日志</h1>
          <p className="mt-1 text-sm text-slate-500">业务审计与治理追踪</p>
        </div>
        <Button type="button" variant="secondary" onClick={() => void refresh()} disabled={loading}>
          <Search className="size-4" aria-hidden="true" />
          查询
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>筛选条件</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Field label="用户">
              <input
                className={inputClassName()}
                value={filters.username}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, username: event.target.value }))
                }
                placeholder="username"
              />
            </Field>
            <Field label="动作">
              <input
                className={inputClassName()}
                value={filters.action}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, action: event.target.value }))
                }
                placeholder="project.update"
              />
            </Field>
            <Field label="对象类型">
              <input
                className={inputClassName()}
                value={filters.targetType}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, targetType: event.target.value }))
                }
                placeholder="subject"
              />
            </Field>
            <Field label="对象 ID">
              <input
                className={inputClassName()}
                value={filters.targetId}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, targetId: event.target.value }))
                }
                inputMode="numeric"
              />
            </Field>
            <Field label="项目">
              <SelectField
                value={filters.projectId ?? ""}
                onChange={(event) => {
                  const projectId = Number(event.target.value) || undefined;
                  setOffset(0);
                  setFilters((current) => ({ ...current, projectId, centerId: undefined }));
                }}
              >
                <option value="">全部项目</option>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </SelectField>
            </Field>
            <Field label="中心">
              <SelectField
                value={filters.centerId ?? ""}
                onChange={(event) => {
                  setOffset(0);
                  setFilters((current) => ({
                    ...current,
                    centerId: Number(event.target.value) || undefined,
                  }));
                }}
              >
                <option value="">全部中心</option>
                {centers.map((center) => (
                  <option key={center.id} value={center.id}>
                    {center.name}
                  </option>
                ))}
              </SelectField>
            </Field>
            <Field label="开始时间">
              <input
                type="datetime-local"
                className={inputClassName()}
                value={filters.createdFrom}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, createdFrom: event.target.value }))
                }
              />
            </Field>
            <Field label="结束时间">
              <input
                type="datetime-local"
                className={inputClassName()}
                value={filters.createdTo}
                onChange={(event) =>
                  setFilters((current) => ({ ...current, createdTo: event.target.value }))
                }
              />
            </Field>
          </div>
        </CardContent>
      </Card>

      {error && <Badge tone="danger">{error}</Badge>}

      <Card>
        <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <CardTitle>日志列表</CardTitle>
          <Badge tone="neutral">共 {total} 条</Badge>
        </CardHeader>
        <CardContent className="space-y-4">
          <LogTable logs={logs} />
          <div className="flex items-center justify-between gap-3">
            <Button
              type="button"
              variant="secondary"
              disabled={offset === 0 || loading}
              onClick={() => setOffset((current) => Math.max(current - limit, 0))}
            >
              上一页
            </Button>
            <span className="text-sm text-slate-500">
              第 {page} / {pageCount} 页
            </span>
            <Button
              type="button"
              variant="secondary"
              disabled={offset + limit >= total || loading}
              onClick={() => setOffset((current) => current + limit)}
            >
              下一页
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
