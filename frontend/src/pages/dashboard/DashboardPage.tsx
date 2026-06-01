import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  ClipboardCheck,
  Database,
  FileWarning,
  RefreshCcw,
  TrendingUp,
  Users,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SelectField } from "@/components/ui/form";
import { dashboardApi } from "@/services/dashboard";
import { masterDataApi } from "@/services/master-data";
import { useAuthStore } from "@/stores/auth-store";
import type { DashboardV323Overview } from "@/types/dashboard";
import type { Center, Project } from "@/types/master-data";

const statusLabels: Record<string, string> = {
  complete: "齐全",
  checking: "核查中",
  incomplete: "不全",
  unreviewed: "未审核",
  pending: "待审核",
  approved: "已通过",
  rejected: "已驳回",
  open: "未关闭",
  closed: "已关闭",
  done: "已完成",
  in_progress: "进行中",
  not_started: "未开始",
};

function pct(value: number) {
  return `${Number.isFinite(value) ? value.toFixed(1) : "0.0"}%`;
}

function statusLabel(value: string) {
  return statusLabels[value] ?? value;
}

function statusTone(value: string) {
  if (["complete", "approved", "done", "closed"].includes(value)) return "success";
  if (["incomplete", "rejected", "overdue"].includes(value)) return "danger";
  if (["checking", "pending", "due_soon", "open", "in_progress"].includes(value)) return "warning";
  return "neutral";
}

function KpiCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = "neutral",
}: {
  label: string;
  value: string | number;
  hint: string;
  icon: typeof Users;
  tone?: "neutral" | "success" | "warning" | "danger";
}) {
  const colors = {
    neutral: "border-slate-200 bg-white text-slate-700",
    success: "border-emerald-200 bg-emerald-50 text-emerald-700",
    warning: "border-amber-200 bg-amber-50 text-amber-700",
    danger: "border-rose-200 bg-rose-50 text-rose-700",
  };
  return (
    <div className={`rounded-md border p-4 ${colors[tone]}`}>
      <div className="flex items-center justify-between gap-3">
        <span className="text-sm font-medium">{label}</span>
        <Icon className="size-5" aria-hidden="true" />
      </div>
      <div className="mt-3 text-3xl font-semibold tracking-normal text-slate-950">{value}</div>
      <div className="mt-1 text-xs text-slate-500">{hint}</div>
    </div>
  );
}

function RatioBar({
  complete,
  checking,
  incomplete,
}: {
  complete: number;
  checking: number;
  incomplete: number;
}) {
  const total = complete + checking + incomplete;
  const safeTotal = total || 1;
  return (
    <div className="h-3 overflow-hidden rounded-full bg-slate-100">
      <div className="flex h-full">
        <div className="bg-emerald-500" style={{ width: `${(complete / safeTotal) * 100}%` }} />
        <div className="bg-amber-400" style={{ width: `${(checking / safeTotal) * 100}%` }} />
        <div className="bg-rose-500" style={{ width: `${(incomplete / safeTotal) * 100}%` }} />
      </div>
    </div>
  );
}

function EmptyState({ label }: { label: string }) {
  return <div className="rounded-md border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-500">{label}</div>;
}

export function DashboardPage() {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canReadDashboard = hasPermission("dashboard:read");
  const [projects, setProjects] = useState<Project[]>([]);
  const [centers, setCenters] = useState<Center[]>([]);
  const [projectId, setProjectId] = useState<number | undefined>();
  const [centerId, setCenterId] = useState<number | undefined>();
  const [overview, setOverview] = useState<DashboardV323Overview | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === projectId),
    [projectId, projects],
  );
  const selectedCenter = useMemo(
    () => centers.find((center) => center.id === centerId),
    [centerId, centers],
  );

  const refresh = useCallback(async () => {
    if (!canReadDashboard) return;
    setLoading(true);
    setMessage(null);
    try {
      setOverview(await dashboardApi.getV323Overview(projectId, centerId));
    } catch {
      setOverview(null);
      setMessage("看板数据加载失败");
    } finally {
      setLoading(false);
    }
  }, [canReadDashboard, centerId, projectId]);

  useEffect(() => {
    if (!canReadDashboard) return;
    async function loadProjects() {
      try {
        setProjects(await masterDataApi.listProjects());
      } catch {
        setMessage("项目列表加载失败");
      }
    }
    void loadProjects();
  }, [canReadDashboard]);

  useEffect(() => {
    if (!projectId) {
      setCenters([]);
      setCenterId(undefined);
      return;
    }
    async function loadCenters() {
      const data = await masterDataApi.listCenters(projectId);
      setCenters(data);
      setCenterId((current) => (current && data.some((center) => center.id === current) ? current : undefined));
    }
    void loadCenters();
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  if (!canReadDashboard) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold tracking-normal text-slate-950">看板</h1>
        <Card>
          <CardContent className="flex items-center gap-3 py-8 text-sm text-slate-600">
            <AlertTriangle className="size-5 text-slate-400" aria-hidden="true" />
            当前账号没有看板权限
          </CardContent>
        </Card>
      </div>
    );
  }

  const completeness = overview?.completeness ?? { complete: 0, checking: 0, incomplete: 0 };
  const reviews = overview?.reviews ?? { approved: 0, pending: 0, rejected: 0, unreviewed: 0 };
  const trendMax = Math.max(...(overview?.trends.map((point) => point.completed_count) ?? [0]), 1);

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 border-b border-slate-200 pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-medium text-slate-500">V3.2.3 运营看板</p>
          <h1 className="mt-1 text-3xl font-semibold tracking-normal text-slate-950">临床数据运营总览</h1>
          <p className="mt-2 text-sm text-slate-500">
            自动汇总临床数据集，辅以手工维护的计划、里程碑和风险事项。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SelectField
            value={projectId ?? ""}
            onChange={(event) => {
              setProjectId(Number(event.target.value) || undefined);
              setCenterId(undefined);
            }}
            className="h-10 w-56"
          >
            <option value="">全部项目</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </SelectField>
          <SelectField
            value={centerId ?? ""}
            onChange={(event) => setCenterId(Number(event.target.value) || undefined)}
            disabled={!projectId}
            className="h-10 w-48"
          >
            <option value="">全部中心</option>
            {centers.map((center) => (
              <option key={center.id} value={center.id}>
                {center.name}
              </option>
            ))}
          </SelectField>
          <Button variant="secondary" onClick={() => void refresh()} disabled={loading}>
            <RefreshCcw className="size-4" aria-hidden="true" />
            刷新
          </Button>
        </div>
      </div>

      {message && <Badge tone="danger">{message}</Badge>}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="汇总范围"
          value={selectedCenter?.name ?? selectedProject?.name ?? "全部项目"}
          hint={`${overview?.kpis.project_count ?? 0} 个项目 / ${overview?.kpis.center_count ?? 0} 个中心`}
          icon={Database}
        />
        <KpiCard
          label="受试者完成率"
          value={pct(overview?.kpis.completion_rate ?? 0)}
          hint={`${overview?.kpis.completed_subject_count ?? 0}/${overview?.kpis.subject_count ?? 0} 例完成`}
          icon={Users}
          tone="success"
        />
        <KpiCard
          label="待处理审核"
          value={(overview?.kpis.pending_review_count ?? 0) + (overview?.kpis.rejected_review_count ?? 0)}
          hint={`待审 ${overview?.kpis.pending_review_count ?? 0} / 驳回 ${overview?.kpis.rejected_review_count ?? 0}`}
          icon={ClipboardCheck}
          tone={(overview?.kpis.rejected_review_count ?? 0) > 0 ? "danger" : "warning"}
        />
        <KpiCard
          label="计划预警"
          value={overview?.kpis.active_warning_count ?? 0}
          hint={`下周计划入组 ${overview?.enrollment.planned_next_week ?? 0}`}
          icon={FileWarning}
          tone={(overview?.kpis.active_warning_count ?? 0) > 0 ? "danger" : "neutral"}
        />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <CardHeader>
            <CardTitle>资料完整性</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <RatioBar {...completeness} />
            <div className="grid gap-3 sm:grid-cols-3">
              <Badge tone="success">齐全 {completeness.complete}</Badge>
              <Badge tone="warning">核查中 {completeness.checking}</Badge>
              <Badge tone="danger">不全 {completeness.incomplete}</Badge>
            </div>
            <div className="grid gap-3 text-sm sm:grid-cols-2">
              <div className="rounded-md bg-slate-50 p-3">
                <div className="text-slate-500">中心级资料</div>
                <div className="mt-1 font-medium text-slate-900">
                  齐全 {overview?.stage_files.complete ?? 0} / 不全 {overview?.stage_files.incomplete ?? 0}
                </div>
              </div>
              <div className="rounded-md bg-slate-50 p-3">
                <div className="text-slate-500">受试者资料</div>
                <div className="mt-1 font-medium text-slate-900">
                  齐全 {overview?.subjects.complete ?? 0} / 不全 {overview?.subjects.incomplete ?? 0}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>审核状态</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(["approved", "pending", "rejected", "unreviewed"] as const).map((key) => (
              <div key={key} className="flex items-center justify-between rounded-md bg-slate-50 px-3 py-2 text-sm">
                <span className="text-slate-600">{statusLabel(key)}</span>
                <Badge tone={statusTone(key)}>{reviews[key]}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>中心状态排行</CardTitle>
          </CardHeader>
          <CardContent>
            {overview && overview.centers.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-left text-sm">
                  <thead className="border-b border-slate-200 text-xs text-slate-500">
                    <tr>
                      <th className="px-3 py-2 font-medium">项目</th>
                      <th className="px-3 py-2 font-medium">中心</th>
                      <th className="px-3 py-2 font-medium">受试者</th>
                      <th className="px-3 py-2 font-medium">完成率</th>
                      <th className="px-3 py-2 font-medium">完整性</th>
                      <th className="px-3 py-2 font-medium">待处理</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {overview.centers.slice(0, 12).map((center) => (
                      <tr key={center.center_id}>
                        <td className="px-3 py-3 text-slate-600">{center.project_name}</td>
                        <td className="px-3 py-3 font-medium text-slate-900">{center.center_name}</td>
                        <td className="px-3 py-3 text-slate-600">{center.completed_subject_count}/{center.subject_count}</td>
                        <td className="px-3 py-3 text-slate-600">{pct(center.completion_rate)}</td>
                        <td className="px-3 py-3">
                          <Badge tone={statusTone(center.completeness_status)}>{statusLabel(center.completeness_status)}</Badge>
                        </td>
                        <td className="px-3 py-3 text-slate-600">
                          {center.pending_review_count + center.rejected_review_count}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState label="当前范围暂无中心数据" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>完成趋势</CardTitle>
          </CardHeader>
          <CardContent>
            {overview && overview.trends.length > 0 ? (
              <div className="space-y-3">
                {overview.trends.slice(-8).map((point) => (
                  <div key={point.period} className="grid grid-cols-[88px_1fr_36px] items-center gap-3 text-sm">
                    <span className="text-xs text-slate-500">{point.period}</span>
                    <div className="h-3 rounded-full bg-slate-100">
                      <div
                        className="h-3 rounded-full bg-sky-500"
                        style={{ width: `${(point.completed_count / trendMax) * 100}%` }}
                      />
                    </div>
                    <span className="text-right font-medium text-slate-900">{point.completed_count}</span>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState label="暂无完成趋势数据" />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>预警与近期事项</CardTitle>
          </CardHeader>
          <CardContent>
            {overview && overview.warnings.length > 0 ? (
              <div className="divide-y divide-slate-100">
                {overview.warnings.slice(0, 8).map((warning) => (
                  <div key={`${warning.source}-${warning.project_id}-${warning.id}`} className="grid gap-2 py-3 text-sm sm:grid-cols-[80px_1fr_104px] sm:items-center">
                    <Badge tone={warning.warning_level === "overdue" ? "danger" : "warning"}>
                      {warning.warning_level === "overdue" ? "预警" : "临近"}
                    </Badge>
                    <div>
                      <div className="font-medium text-slate-900">{warning.title}</div>
                      <div className="text-xs text-slate-500">
                        {warning.project_name}{warning.center_name ? ` / ${warning.center_name}` : ""}
                      </div>
                    </div>
                    <span className="text-slate-600">{warning.planned_date}</span>
                  </div>
                ))}
              </div>
            ) : (
              <EmptyState label="当前范围暂无逾期或临近事项" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>手工补充数据摘要</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-3">
              <KpiCard
                label="合同例数"
                value={overview?.enrollment.contract_count ?? 0}
                hint="来自入组计划维护"
                icon={CheckCircle2}
              />
              <KpiCard
                label="临床事件"
                value={overview?.manual_supplements.clinical_event_count ?? 0}
                hint="来自事件维护"
                icon={TrendingUp}
              />
              <KpiCard
                label="器械问题"
                value={overview?.manual_supplements.device_issue_count ?? 0}
                hint="来自器械问题维护"
                icon={BarChart3}
              />
            </div>
          </CardContent>
        </Card>
      </div>

      {loading && <p className="text-sm text-slate-500">正在加载</p>}
    </div>
  );
}
