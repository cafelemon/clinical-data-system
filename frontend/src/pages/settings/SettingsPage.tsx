import {
  BookOpen,
  ClipboardList,
  Database,
  FileSearch,
  RotateCcw,
  Settings,
  ShieldCheck,
  Users,
} from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import {
  ManagementNotice,
  ManagementPageHeader,
  ManagementStatCard,
} from "@/components/management/ManagementPage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { systemManagementApi } from "@/services/system-management";
import { useAuthStore } from "@/stores/auth-store";
import type { SystemManagementOverview } from "@/types/system-management";

export function SettingsPage() {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const [overview, setOverview] = useState<SystemManagementOverview | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function loadOverview() {
    try {
      setOverview(await systemManagementApi.getOverview());
      setMessage(null);
    } catch {
      setOverview(null);
      setMessage("系统管理总览加载失败");
    }
  }

  useEffect(() => {
    void loadOverview();
  }, []);

  const masterDataTotal = overview
    ? overview.master_data.project_count +
      overview.master_data.center_count +
      overview.master_data.stage_count +
      overview.master_data.stage_template_count +
      overview.master_data.dictionary_count
    : 0;
  const workflowTotal = overview
    ? overview.workflows.pdf_packet_count + overview.workflows.correction_task_count
    : 0;

  return (
    <div className="space-y-6">
      <ManagementPageHeader
        title="系统管理控制台"
        description="后台配置、权限治理、流程工具和全局状态收口"
        icon={Settings}
        actions={
          <Button variant="secondary" onClick={() => void loadOverview()}>
            <RotateCcw className="size-4" aria-hidden="true" />
            刷新
          </Button>
        }
      />

      {message && <Badge tone="danger">{message}</Badge>}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <ManagementStatCard
          label="主数据配置"
          value={masterDataTotal}
          detail={`项目 ${overview?.master_data.project_count ?? 0} · 中心 ${overview?.master_data.center_count ?? 0}`}
          icon={Database}
        />
        <ManagementStatCard
          label="身份与权限"
          value={overview?.identity.user_count ?? 0}
          detail={`角色 ${overview?.identity.role_count ?? 0} · 停用用户 ${overview?.identity.inactive_user_count ?? 0}`}
          icon={Users}
          tone="teal"
        />
        <ManagementStatCard
          label="流程工具"
          value={workflowTotal}
          detail={`资料包 ${overview?.workflows.pdf_packet_count ?? 0} · 整改 ${overview?.workflows.correction_task_count ?? 0}`}
          icon={ClipboardList}
          tone={overview?.workflows.open_correction_task_count ? "amber" : "blue"}
        />
        <ManagementStatCard
          label="维护数据"
          value={overview?.manual_maintenance.total_count ?? 0}
          detail={`里程碑 ${overview?.manual_maintenance.milestone_count ?? 0} · 重要事项 ${overview?.manual_maintenance.important_task_count ?? 0}`}
          icon={BookOpen}
          tone="slate"
        />
        <ManagementStatCard
          label="审计日志"
          value={overview?.audit.operation_log_count ?? 0}
          detail="登录、配置、资料与审核操作"
          icon={ShieldCheck}
          tone="teal"
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <Card>
          <CardHeader>
            <CardTitle>快捷入口</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {hasPermission("master_data:read") && (
                <Button asChild variant="secondary">
                  <Link to="/centers">中心管理</Link>
                </Button>
              )}
              {hasPermission("master_data:read") && (
                <Button asChild variant="secondary">
                  <Link to="/stage-templates">阶段资料模板</Link>
                </Button>
              )}
              {hasPermission("dictionaries:read") && (
                <Button asChild variant="secondary">
                  <Link to="/dictionaries">状态字典</Link>
                </Button>
              )}
              {hasPermission("users:read") && (
                <Button asChild variant="secondary">
                  <Link to="/users">用户管理</Link>
                </Button>
              )}
              {hasPermission("roles:read") && (
                <Button asChild variant="secondary">
                  <Link to="/roles">角色管理</Link>
                </Button>
              )}
              {hasPermission("operation_logs:read") && (
                <Button asChild variant="secondary">
                  <Link to="/operation-logs">操作日志</Link>
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
        <div className="space-y-4">
          <ManagementNotice
            title="3.5 待升级：PDF 在线审阅工作台"
            description="本轮保留 PDF 审阅页核心交互，3.5 再统一画布、批注列表和工具栏。"
            tone="amber"
          />
          <ManagementNotice
            title="本轮边界"
            description="不新增数据库迁移，不改 OCR/解析算法，不改权限模型。"
          />
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>治理状态</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-md border border-[#DDE7F0] bg-slate-50 p-4">
              <p className="text-xs text-slate-500">停用配置</p>
              <p className="mt-2 text-sm font-semibold text-slate-900">
                阶段 {overview?.master_data.disabled_stage_count ?? 0} · 字典 {overview?.master_data.disabled_dictionary_count ?? 0}
              </p>
            </div>
            <div className="rounded-md border border-[#DDE7F0] bg-slate-50 p-4">
              <p className="text-xs text-slate-500">整改风险</p>
              <p className="mt-2 text-sm font-semibold text-slate-900">
                开放 {overview?.workflows.open_correction_task_count ?? 0} · 待复审 {overview?.workflows.pending_review_task_count ?? 0}
              </p>
            </div>
            <div className="rounded-md border border-[#DDE7F0] bg-slate-50 p-4">
              <p className="text-xs text-slate-500">识别结果</p>
              <p className="mt-2 text-sm font-semibold text-slate-900">
                资料包 {overview?.workflows.pdf_packet_count ?? 0} · 片段 {overview?.workflows.pdf_packet_segment_count ?? 0}
              </p>
            </div>
          </div>
          <div className="mt-4 flex items-center gap-2 text-sm text-slate-500">
            <FileSearch className="size-4" aria-hidden="true" />
            PDF 在线审阅页核心交互已冻结，等待 3.5 专项重构。
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
