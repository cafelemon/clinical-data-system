import { BarChart3, RefreshCcw } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SelectField } from "@/components/ui/form";
import { dashboardApi } from "@/services/dashboard";
import { masterDataApi } from "@/services/master-data";
import { useAuthStore } from "@/stores/auth-store";
import type { Project } from "@/types/master-data";
import type {
  DashboardCenter,
  DashboardCompleteness,
  DashboardProjectSummary,
  DashboardReviewStatus,
  DashboardTrendPoint,
} from "@/types/dashboard";

const dataStatusLabels: Record<string, string> = {
  complete: "资料齐全",
  checking: "核查中",
  incomplete: "资料不全",
};

const reviewStatusLabels: Record<string, string> = {
  unreviewed: "未审核",
  pending: "待审核",
  approved: "已通过",
  rejected: "已驳回",
};

const chartColors = {
  complete: "#059669",
  checking: "#d97706",
  incomplete: "#e11d48",
  unreviewed: "#64748b",
  pending: "#d97706",
  approved: "#059669",
  rejected: "#e11d48",
};

function statusTone(status: string) {
  if (status === "complete" || status === "approved") return "success";
  if (status === "checking" || status === "pending" || status === "unreviewed") return "warning";
  if (status === "incomplete" || status === "rejected") return "danger";
  return "neutral";
}

function formatPercent(value: number) {
  return `${value.toFixed(1)}%`;
}

function metricValue(value: number, suffix = "") {
  return `${value.toLocaleString()}${suffix}`;
}

function EmptyChart({ label }: { label: string }) {
  return (
    <div className="flex h-64 items-center justify-center rounded-md border border-dashed border-slate-200 bg-slate-50 text-sm text-slate-500">
      {label}
    </div>
  );
}

function MetricCard({
  label,
  value,
  badge,
}: {
  label: string;
  value: string;
  badge: string;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-slate-500">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex items-end justify-between">
          <span className="text-3xl font-semibold text-slate-950">{value}</span>
          <Badge tone="neutral">{badge}</Badge>
        </div>
      </CardContent>
    </Card>
  );
}

function CenterTable({ centers }: { centers: DashboardCenter[] }) {
  if (centers.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
        暂无中心数据
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-3 py-2 font-medium">中心</th>
            <th className="px-3 py-2 font-medium">受试者</th>
            <th className="px-3 py-2 font-medium">已完成</th>
            <th className="px-3 py-2 font-medium">完成率</th>
            <th className="px-3 py-2 font-medium">完整性</th>
            <th className="px-3 py-2 font-medium">待审核</th>
            <th className="px-3 py-2 font-medium">驳回</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {centers.map((center) => (
            <tr key={center.center_id}>
              <td className="px-3 py-3 font-medium text-slate-900">{center.center_name}</td>
              <td className="px-3 py-3 text-slate-600">{center.subject_count}</td>
              <td className="px-3 py-3 text-slate-600">{center.completed_subject_count}</td>
              <td className="px-3 py-3 text-slate-600">{formatPercent(center.completion_rate)}</td>
              <td className="px-3 py-3">
                <Badge tone={statusTone(center.completeness_status)}>
                  {dataStatusLabels[center.completeness_status] ?? center.completeness_status}
                </Badge>
              </td>
              <td className="px-3 py-3 text-slate-600">{center.pending_review_count}</td>
              <td className="px-3 py-3 text-slate-600">{center.rejected_review_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TrendChart({ trend }: { trend: DashboardTrendPoint[] }) {
  if (trend.length === 0) return <EmptyChart label="暂无完成趋势" />;
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={trend} margin={{ top: 12, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="period" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Line
            type="monotone"
            dataKey="completed_count"
            name="完成案例"
            stroke="#2563eb"
            strokeWidth={2}
            dot={{ r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function ReviewChart({ reviewStatus }: { reviewStatus: DashboardReviewStatus | null }) {
  const data = reviewStatus
    ? (Object.entries(reviewStatus) as Array<[keyof DashboardReviewStatus, number]>).map(
        ([status, value]) => ({
          status,
          label: reviewStatusLabels[status],
          value,
        }),
      )
    : [];
  if (data.every((item) => item.value === 0)) return <EmptyChart label="暂无审核状态" />;
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="label"
            innerRadius={56}
            outerRadius={88}
            paddingAngle={2}
          >
            {data.map((item) => (
              <Cell key={item.status} fill={chartColors[item.status]} />
            ))}
          </Pie>
          <Tooltip />
        </PieChart>
      </ResponsiveContainer>
      <div className="mt-2 flex flex-wrap gap-2">
        {data.map((item) => (
          <Badge key={item.status} tone={statusTone(item.status)}>
            {item.label} {item.value}
          </Badge>
        ))}
      </div>
    </div>
  );
}

function CompletenessChart({ completeness }: { completeness: DashboardCompleteness | null }) {
  const data = completeness
    ? [
        { name: "阶段资料", ...completeness.stage_files },
        { name: "受试者", ...completeness.subjects },
      ]
    : [];
  if (
    data.length === 0 ||
    data.every((item) => item.complete + item.checking + item.incomplete === 0)
  ) {
    return <EmptyChart label="暂无完整性数据" />;
  }
  return (
    <div className="h-64">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 12, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
          <Tooltip />
          <Bar dataKey="complete" name="资料齐全" stackId="a" fill={chartColors.complete} />
          <Bar dataKey="checking" name="核查中" stackId="a" fill={chartColors.checking} />
          <Bar dataKey="incomplete" name="资料不全" stackId="a" fill={chartColors.incomplete} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export function DashboardPage() {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canReadDashboard = hasPermission("dashboard:read");
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | undefined>();
  const [summary, setSummary] = useState<DashboardProjectSummary | null>(null);
  const [centers, setCenters] = useState<DashboardCenter[]>([]);
  const [trend, setTrend] = useState<DashboardTrendPoint[]>([]);
  const [reviewStatus, setReviewStatus] = useState<DashboardReviewStatus | null>(null);
  const [completeness, setCompleteness] = useState<DashboardCompleteness | null>(null);
  const [granularity, setGranularity] = useState<"week" | "month">("week");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const metrics = useMemo(
    () => [
      {
        label: "完成案例数",
        value: metricValue(summary?.completed_subject_count ?? 0),
        badge: "案例",
      },
      {
        label: "研究中心",
        value: metricValue(summary?.visible_center_count ?? 0),
        badge: "中心",
      },
      {
        label: "项目总用时",
        value: metricValue(summary?.project_days ?? 0, "天"),
        badge: "累计",
      },
      {
        label: "平均用时/案例",
        value: metricValue(summary?.average_days_per_subject ?? 0, "天"),
        badge: "平均",
      },
      {
        label: "中位数用时",
        value: metricValue(summary?.median_days_per_subject ?? 0, "天"),
        badge: "中位",
      },
    ],
    [summary],
  );

  const refreshDashboard = useCallback(async () => {
    if (!projectId || !canReadDashboard) return;
    setLoading(true);
    setError(null);
    try {
      const [summaryData, centerData, trendData, reviewData, completenessData] =
        await Promise.all([
          dashboardApi.getProjectSummary(projectId),
          dashboardApi.listProjectCenters(projectId),
          dashboardApi.getProjectTrend(projectId, granularity),
          dashboardApi.getReviewStatus(projectId),
          dashboardApi.getCompleteness(projectId),
        ]);
      setSummary(summaryData);
      setCenters(centerData);
      setTrend(trendData);
      setReviewStatus(reviewData);
      setCompleteness(completenessData);
    } catch {
      setError("看板数据加载失败");
      setSummary(null);
      setCenters([]);
      setTrend([]);
      setReviewStatus(null);
      setCompleteness(null);
    } finally {
      setLoading(false);
    }
  }, [canReadDashboard, granularity, projectId]);

  useEffect(() => {
    if (!canReadDashboard) return;
    async function loadProjects() {
      try {
        const data = await masterDataApi.listProjects();
        setProjects(data);
        setProjectId((current) =>
          current && data.some((project) => project.id === current)
            ? current
            : data[0]?.id,
        );
      } catch {
        setProjects([]);
        setError("项目列表加载失败");
      }
    }
    void loadProjects();
  }, [canReadDashboard]);

  useEffect(() => {
    void refreshDashboard();
  }, [refreshDashboard]);

  if (!canReadDashboard) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">数据看板</h1>
          <p className="mt-1 text-sm text-slate-500">项目进度、中心差异与审核风险</p>
        </div>
        <Card>
          <CardContent className="flex items-center gap-3 py-8 text-sm text-slate-600">
            <BarChart3 className="size-5 text-slate-400" aria-hidden="true" />
            当前账号没有看板权限
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">数据看板</h1>
          <p className="mt-1 text-sm text-slate-500">项目进度、中心差异与审核风险</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <SelectField
            value={projectId ?? ""}
            onChange={(event) => setProjectId(Number(event.target.value) || undefined)}
            className="h-10 w-48"
          >
            <option value="">选择项目</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </SelectField>
          <SelectField
            value={granularity}
            onChange={(event) => setGranularity(event.target.value as "week" | "month")}
            className="h-10 w-28"
          >
            <option value="week">按周</option>
            <option value="month">按月</option>
          </SelectField>
          <Button variant="secondary" onClick={() => void refreshDashboard()} disabled={loading}>
            <RefreshCcw className="size-4" aria-hidden="true" />
            刷新
          </Button>
        </div>
      </div>

      {error && <Badge tone="danger">{error}</Badge>}
      {!projectId && (
        <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
          暂无可查看项目
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {metrics.map((metric) => (
          <MetricCard key={metric.label} {...metric} />
        ))}
      </div>

      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>完成趋势</CardTitle>
          </CardHeader>
          <CardContent>
            <TrendChart trend={trend} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>审核状态分布</CardTitle>
          </CardHeader>
          <CardContent>
            <ReviewChart reviewStatus={reviewStatus} />
          </CardContent>
        </Card>
      </section>

      <section className="grid gap-4 xl:grid-cols-[0.8fr_1.2fr]">
        <Card>
          <CardHeader>
            <CardTitle>资料完整性分布</CardTitle>
          </CardHeader>
          <CardContent>
            <CompletenessChart completeness={completeness} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>各中心完成情况</CardTitle>
          </CardHeader>
          <CardContent>
            <CenterTable centers={centers} />
          </CardContent>
        </Card>
      </section>

      {loading && <p className="text-sm text-slate-500">正在加载</p>}
    </div>
  );
}
