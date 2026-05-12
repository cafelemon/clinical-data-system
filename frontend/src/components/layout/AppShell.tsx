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
  ClipboardCheck,
  PanelLeftClose,
  PanelLeftOpen,
  Settings,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
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
  {
    to: "/correction-tasks",
    label: "整改任务",
    icon: ClipboardCheck,
    permissions: ["correction_tasks:read"],
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

type SidebarMode = "fixed" | "auto-hide";

const SIDEBAR_MODE_STORAGE_KEY = "clinical-data-sidebar-mode";

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
  const [sidebarMode, setSidebarMode] = useState<SidebarMode>(() => {
    if (typeof window === "undefined") return "fixed";
    return window.localStorage.getItem(SIDEBAR_MODE_STORAGE_KEY) === "auto-hide"
      ? "auto-hide"
      : "fixed";
  });
  const [autoSidebarOpen, setAutoSidebarOpen] = useState(false);
  const openTimerRef = useRef<number | null>(null);
  const closeTimerRef = useRef<number | null>(null);

  const datasetParams = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const selectedProjectId = Number(datasetParams.get("project_id")) || undefined;
  const selectedCenterId = Number(datasetParams.get("center_id")) || undefined;
  const selectedStage = datasetParams.get("stage") || "STARTUP";
  const sidebarExpanded = sidebarMode === "fixed" || autoSidebarOpen;

  function clearSidebarTimer(timerRef: { current: number | null }) {
    if (timerRef.current === null) return;
    window.clearTimeout(timerRef.current);
    timerRef.current = null;
  }

  function openAutoSidebarSoon() {
    if (sidebarMode !== "auto-hide") return;
    clearSidebarTimer(closeTimerRef);
    clearSidebarTimer(openTimerRef);
    openTimerRef.current = window.setTimeout(() => {
      setAutoSidebarOpen(true);
      openTimerRef.current = null;
    }, 3000);
  }

  function closeAutoSidebarSoon() {
    if (sidebarMode !== "auto-hide") return;
    clearSidebarTimer(openTimerRef);
    clearSidebarTimer(closeTimerRef);
    closeTimerRef.current = window.setTimeout(() => {
      setAutoSidebarOpen(false);
      closeTimerRef.current = null;
    }, 3000);
  }

  function toggleSidebarMode() {
    setSidebarMode((current) => {
      const next = current === "fixed" ? "auto-hide" : "fixed";
      window.localStorage.setItem(SIDEBAR_MODE_STORAGE_KEY, next);
      setAutoSidebarOpen(next === "fixed");
      return next;
    });
    clearSidebarTimer(openTimerRef);
    clearSidebarTimer(closeTimerRef);
  }

  useEffect(
    () => () => {
      clearSidebarTimer(openTimerRef);
      clearSidebarTimer(closeTimerRef);
    },
    [],
  );

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
      {sidebarMode === "auto-hide" && (
        <div
          className="fixed inset-y-0 left-0 z-30 hidden w-5 lg:block"
          onMouseEnter={openAutoSidebarSoon}
          onMouseLeave={closeAutoSidebarSoon}
        />
      )}

      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 hidden h-screen flex-col border-r border-slate-200 bg-white py-5 transition-[width] duration-200 lg:flex",
          sidebarExpanded ? "w-64 px-4" : "w-20 px-3",
        )}
        onMouseEnter={openAutoSidebarSoon}
        onMouseLeave={closeAutoSidebarSoon}
      >
        <div
          className={cn(
            "flex shrink-0 items-center px-2",
            sidebarExpanded ? "gap-3" : "justify-center",
          )}
        >
          <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-emerald-600 text-white">
            <Activity className="size-5" aria-hidden="true" />
          </div>
          {sidebarExpanded && (
            <div className="min-w-0">
              <p className="text-sm font-semibold leading-5">临床数据收集系统</p>
              <p className="text-xs text-slate-500">Clinical Data System</p>
            </div>
          )}
        </div>

        <div className="mt-4 flex shrink-0 justify-center">
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className={cn("h-8", sidebarExpanded ? "w-full justify-start px-3" : "w-10 px-0")}
            onClick={toggleSidebarMode}
            title={sidebarMode === "fixed" ? "切换为自动收起" : "固定展开侧栏"}
            aria-label={sidebarMode === "fixed" ? "切换为自动收起" : "固定展开侧栏"}
          >
            {sidebarMode === "fixed" ? (
              <PanelLeftClose className="size-4 shrink-0" aria-hidden="true" />
            ) : (
              <PanelLeftOpen className="size-4 shrink-0" aria-hidden="true" />
            )}
            {sidebarExpanded && (
              <span>{sidebarMode === "fixed" ? "自动收起" : "固定展开"}</span>
            )}
          </Button>
        </div>

        <nav
          className={cn(
            "mt-6 min-h-0 flex-1 space-y-1 overflow-y-auto",
            sidebarExpanded ? "pr-1" : "",
          )}
        >
          {visibleNavItems.map((item) => (
            <div key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  cn(
                    "flex items-center rounded-md py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-950",
                    sidebarExpanded ? "gap-3 px-3" : "justify-center px-0",
                    isActive && "bg-slate-900 text-white hover:bg-slate-900 hover:text-white",
                  )
                }
                title={!sidebarExpanded ? item.label : undefined}
              >
                <item.icon className="size-4 shrink-0" aria-hidden="true" />
                {sidebarExpanded && <span className="flex-1">{item.label}</span>}
                {sidebarExpanded && item.to === "/clinical-dataset" && isClinicalDataset && (
                  <ChevronDown className="size-4" aria-hidden="true" />
                )}
              </NavLink>
              {sidebarExpanded &&
                item.to === "/clinical-dataset" &&
                isClinicalDataset &&
                canReadClinicalDataset && (
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

        <div
          className={cn(
            "mt-4 shrink-0 border-t border-slate-200 pt-4",
            sidebarExpanded ? "" : "flex flex-col items-center",
          )}
        >
          {sidebarExpanded ? (
            <>
              <p className="truncate text-sm font-medium text-slate-800">
                {user?.full_name || user?.username}
              </p>
              <p className="truncate text-xs text-slate-500">{user?.roles.join(", ")}</p>
            </>
          ) : (
            <div
              className="flex size-10 items-center justify-center rounded-full bg-slate-100 text-sm font-medium text-slate-700"
              title={user?.full_name || user?.username}
            >
              {(user?.full_name || user?.username || "U").slice(0, 1).toUpperCase()}
            </div>
          )}
          <Button
            type="button"
            variant="ghost"
            className={cn("mt-3", sidebarExpanded ? "w-full justify-start" : "w-10 px-0")}
            onClick={handleLogout}
            title="退出登录"
            aria-label="退出登录"
          >
            <LogOut className="size-4" aria-hidden="true" />
            {sidebarExpanded && "退出登录"}
          </Button>
        </div>
      </aside>

      <div className={cn(sidebarMode === "fixed" ? "lg:pl-64" : "lg:pl-20")}>
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
