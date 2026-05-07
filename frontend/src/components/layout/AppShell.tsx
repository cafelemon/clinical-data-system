import {
  Activity,
  BookOpen,
  Building2,
  ChevronDown,
  Database,
  FileText,
  FileSpreadsheet,
  FileSearch,
  FolderKanban,
  LayoutDashboard,
  ListTree,
  LogOut,
  ClipboardList,
  Settings,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { authApi } from "@/services/auth";
import { masterDataApi } from "@/services/master-data";
import { useAuthStore } from "@/stores/auth-store";
import { cn } from "@/lib/utils";
import type { Center, Project } from "@/types/master-data";

type NavItem = {
  to: string;
  label: string;
  icon: LucideIcon;
  permissions: string[];
  adminOnly?: boolean;
};

const navItems: NavItem[] = [
  { to: "/", label: "看板", icon: LayoutDashboard, permissions: ["dashboard:read"] },
  {
    to: "/clinical-dataset",
    label: "临床数据集",
    icon: Database,
    permissions: ["clinical_data:read"],
  },
  {
    to: "/excel-io",
    label: "导入导出",
    icon: FileSpreadsheet,
    permissions: ["imports:read", "imports:write", "exports:read"],
  },
  {
    to: "/pdf-packets",
    label: "PDF资料包",
    icon: FileSearch,
    permissions: ["pdf_packets:read"],
  },
  { to: "/projects", label: "项目", icon: FolderKanban, permissions: ["master_data:read"], adminOnly: true },
  { to: "/centers", label: "中心", icon: Building2, permissions: ["master_data:read"], adminOnly: true },
  { to: "/stages", label: "阶段", icon: ListTree, permissions: ["master_data:read"], adminOnly: true },
  { to: "/stage-templates", label: "模板", icon: FileText, permissions: ["master_data:read"], adminOnly: true },
  { to: "/dictionaries", label: "字典", icon: BookOpen, permissions: ["dictionaries:read"], adminOnly: true },
  {
    to: "/operation-logs",
    label: "操作日志",
    icon: ClipboardList,
    permissions: ["operation_logs:read"],
    adminOnly: true,
  },
  { to: "/users", label: "用户", icon: ShieldCheck, permissions: ["users:read"], adminOnly: true },
  { to: "/roles", label: "角色", icon: ShieldCheck, permissions: ["roles:read"], adminOnly: true },
  {
    to: "/settings",
    label: "设置",
    icon: Settings,
    permissions: ["users:read", "roles:read", "dictionaries:read"],
    adminOnly: true,
  },
];

type DatasetTreeItem = {
  project: Project;
  centers: Center[];
};

function buildDatasetPath(projectId?: number, centerId?: number, stage = "STARTUP") {
  const params = new URLSearchParams();
  if (projectId) params.set("project_id", String(projectId));
  if (centerId) params.set("center_id", String(centerId));
  if (stage) params.set("stage", stage);
  const query = params.toString();
  return `/clinical-dataset${query ? `?${query}` : ""}`;
}

export function AppShell() {
  const user = useAuthStore((state) => state.user);
  const clearSession = useAuthStore((state) => state.clearSession);
  const hasAnyPermission = useAuthStore((state) => state.hasAnyPermission);
  const location = useLocation();
  const navigate = useNavigate();
  const isClinicalDataset = location.pathname.startsWith("/clinical-dataset");
  const canReadClinicalDataset = hasAnyPermission(["clinical_data:read"]);
  const visibleNavItems = navItems.filter(
    (item) => (!item.adminOnly || user?.is_admin) && hasAnyPermission(item.permissions),
  );
  const [datasetTree, setDatasetTree] = useState<DatasetTreeItem[]>([]);
  const [datasetTreeLoading, setDatasetTreeLoading] = useState(false);

  const datasetParams = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const selectedProjectId = Number(datasetParams.get("project_id")) || undefined;
  const selectedCenterId = Number(datasetParams.get("center_id")) || undefined;
  const selectedStage = datasetParams.get("stage") || "STARTUP";

  useEffect(() => {
    if (!isClinicalDataset || !canReadClinicalDataset) return;
    let cancelled = false;

    async function loadDatasetTree() {
      setDatasetTreeLoading(true);
      try {
        const projects = await masterDataApi.listProjects();
        const centersByProject = await Promise.all(
          projects.map(async (project) => ({
            project,
            centers: await masterDataApi.listCenters(project.id),
          })),
        );
        if (!cancelled) {
          setDatasetTree(centersByProject);
        }
      } catch {
        if (!cancelled) {
          setDatasetTree([]);
        }
      } finally {
        if (!cancelled) {
          setDatasetTreeLoading(false);
        }
      }
    }

    void loadDatasetTree();
    return () => {
      cancelled = true;
    };
  }, [canReadClinicalDataset, isClinicalDataset]);

  function handleDatasetProject(project: Project, centers: Center[]) {
    navigate(buildDatasetPath(project.id, centers[0]?.id, selectedStage));
  }

  function handleDatasetCenter(project: Project, center: Center) {
    navigate(buildDatasetPath(project.id, center.id, selectedStage));
  }

  async function handleLogout() {
    try {
      await authApi.logout();
    } finally {
      clearSession();
      window.location.assign("/login");
    }
  }

  return (
    <div className="min-h-screen bg-slate-100 text-slate-950">
      <aside className="fixed inset-y-0 left-0 hidden h-screen w-64 flex-col border-r border-slate-200 bg-white px-4 py-5 lg:flex">
        <div className="flex shrink-0 items-center gap-3 px-2">
          <div className="flex size-10 items-center justify-center rounded-lg bg-emerald-600 text-white">
            <Activity className="size-5" aria-hidden="true" />
          </div>
          <div>
            <p className="text-sm font-semibold leading-5">临床数据收集系统</p>
            <p className="text-xs text-slate-500">Clinical Data System</p>
          </div>
        </div>

        <nav className="mt-8 min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
          {visibleNavItems.map((item) => (
            <div key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  cn(
                    "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-950",
                    isActive && "bg-slate-900 text-white hover:bg-slate-900 hover:text-white",
                  )
                }
              >
                <item.icon className="size-4" aria-hidden="true" />
                <span className="flex-1">{item.label}</span>
                {item.to === "/clinical-dataset" && isClinicalDataset && (
                  <ChevronDown className="size-4" aria-hidden="true" />
                )}
              </NavLink>
              {item.to === "/clinical-dataset" && isClinicalDataset && canReadClinicalDataset && (
                <div className="mt-2 space-y-2 border-l border-slate-200 pl-3">
                  {datasetTreeLoading && (
                    <p className="px-3 py-2 text-xs text-slate-400">正在加载项目中心</p>
                  )}
                  {!datasetTreeLoading && datasetTree.length === 0 && (
                    <p className="px-3 py-2 text-xs text-slate-400">暂无授权项目中心</p>
                  )}
                  {datasetTree.map(({ project, centers }) => {
                    const projectActive = selectedProjectId === project.id;
                    return (
                      <div key={project.id} className="space-y-1">
                        <button
                          type="button"
                          className={cn(
                            "flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-left text-xs font-medium text-slate-500 hover:bg-slate-100 hover:text-slate-900",
                            projectActive && "bg-slate-100 text-slate-900",
                          )}
                          onClick={() => handleDatasetProject(project, centers)}
                        >
                          <FolderKanban className="size-3.5 shrink-0" aria-hidden="true" />
                          <span className="min-w-0 flex-1 truncate">{project.name}</span>
                        </button>
                        {projectActive && (
                          <div className="space-y-1 pl-5">
                            {centers.length === 0 ? (
                              <p className="px-3 py-1.5 text-xs text-slate-400">暂无授权中心</p>
                            ) : (
                              centers.map((center) => (
                                <button
                                  key={center.id}
                                  type="button"
                                  className={cn(
                                    "flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-left text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-900",
                                    selectedCenterId === center.id && "bg-emerald-50 text-emerald-700",
                                  )}
                                  onClick={() => handleDatasetCenter(project, center)}
                                >
                                  <Building2 className="size-3.5 shrink-0" aria-hidden="true" />
                                  <span className="min-w-0 flex-1 truncate">{center.name}</span>
                                </button>
                              ))
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          ))}
        </nav>

        <div className="mt-4 shrink-0 border-t border-slate-200 pt-4">
          <p className="truncate text-sm font-medium text-slate-800">
            {user?.full_name || user?.username}
          </p>
          <p className="truncate text-xs text-slate-500">{user?.roles.join(", ")}</p>
          <Button type="button" variant="ghost" className="mt-3 w-full justify-start" onClick={handleLogout}>
            <LogOut className="size-4" aria-hidden="true" />
            退出登录
          </Button>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur lg:hidden">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-semibold">临床数据收集系统</p>
              <p className="text-xs text-slate-500">P0 工程骨架</p>
            </div>
          </div>
          <nav className="mt-3 grid grid-cols-4 gap-1 sm:grid-cols-8">
            {visibleNavItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  cn(
                    "flex h-11 items-center justify-center rounded-md text-slate-500",
                    isActive && "bg-slate-900 text-white",
                  )
                }
                aria-label={item.label}
              >
                <item.icon className="size-4" aria-hidden="true" />
              </NavLink>
            ))}
          </nav>
        </header>

        <main
          className={cn(
            "mx-auto w-full px-4 py-6 sm:px-6 lg:px-8",
            isClinicalDataset ? "max-w-[1600px]" : "max-w-7xl",
          )}
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
