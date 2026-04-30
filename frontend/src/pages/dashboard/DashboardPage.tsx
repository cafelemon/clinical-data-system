import { AlertCircle, CheckCircle2, Clock3, RefreshCcw } from "lucide-react";
import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getHealth, getVersion } from "@/services/health";
import type { HealthResponse, VersionResponse } from "@/types/health";

const summaryItems = [
  { label: "项目", value: "0", tone: "neutral" },
  { label: "中心", value: "0", tone: "neutral" },
  { label: "资料项", value: "0", tone: "neutral" },
  { label: "待处理", value: "0", tone: "warning" },
] as const;

export function DashboardPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [version, setVersion] = useState<VersionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function refreshHealth() {
    setLoading(true);
    setError(null);
    try {
      const [healthData, versionData] = await Promise.all([getHealth(), getVersion()]);
      setHealth(healthData);
      setVersion(versionData);
    } catch {
      setHealth(null);
      setVersion(null);
      setError("后端暂未连接");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshHealth();
  }, []);

  const isReady = health?.status === "ok";

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">工作台</h1>
          <p className="mt-1 text-sm text-slate-500">P0 工程骨架与服务连通状态</p>
        </div>
        <Button variant="secondary" onClick={refreshHealth} disabled={loading}>
          <RefreshCcw className="size-4" aria-hidden="true" />
          刷新
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {summaryItems.map((item) => (
          <Card key={item.label}>
            <CardHeader className="pb-2">
              <CardTitle className="text-slate-500">{item.label}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-end justify-between">
                <span className="text-3xl font-semibold text-slate-950">{item.value}</span>
                <Badge tone={item.tone}>P1 接入</Badge>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <section className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader>
            <CardTitle>后端服务</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3">
                <div className="flex size-11 items-center justify-center rounded-lg bg-slate-100">
                  {loading ? (
                    <Clock3 className="size-5 text-slate-500" aria-hidden="true" />
                  ) : isReady ? (
                    <CheckCircle2 className="size-5 text-emerald-600" aria-hidden="true" />
                  ) : (
                    <AlertCircle className="size-5 text-amber-600" aria-hidden="true" />
                  )}
                </div>
                <div>
                  <p className="text-sm font-medium text-slate-950">
                    {loading ? "检查中" : isReady ? "运行正常" : error}
                  </p>
                  <p className="text-sm text-slate-500">
                    {health?.service ?? "clinical-data-system"} · v{version?.version ?? "0.1.0"}
                  </p>
                </div>
              </div>
              <Badge tone={isReady ? "success" : "warning"}>{isReady ? "Ready" : "Pending"}</Badge>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>当前阶段</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 text-sm text-slate-600">
              <div className="flex items-center justify-between">
                <span>独立 Git 仓库</span>
                <Badge tone="success">完成</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span>FastAPI 框架</span>
                <Badge tone="success">完成</Badge>
              </div>
              <div className="flex items-center justify-between">
                <span>React 框架</span>
                <Badge tone="success">完成</Badge>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

