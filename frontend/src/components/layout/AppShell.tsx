import {
  Activity,
  BookOpen,
  Building2,
  Database,
  FileText,
  FolderKanban,
  LayoutDashboard,
  ListTree,
  LogOut,
  Settings,
  ShieldCheck,
} from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { authApi } from "@/services/auth";
import { useAuthStore } from "@/stores/auth-store";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/", label: "看板", icon: LayoutDashboard, permissions: ["master_data:read"] },
  { to: "/projects", label: "项目", icon: FolderKanban, permissions: ["master_data:read"] },
  { to: "/centers", label: "中心", icon: Building2, permissions: ["master_data:read"] },
  { to: "/stages", label: "阶段", icon: ListTree, permissions: ["master_data:read"] },
  { to: "/stage-templates", label: "模板", icon: FileText, permissions: ["master_data:read"] },
  { to: "/dictionaries", label: "字典", icon: BookOpen, permissions: ["dictionaries:read"] },
  { to: "/users", label: "用户", icon: ShieldCheck, permissions: ["users:read"] },
  { to: "/roles", label: "角色", icon: ShieldCheck, permissions: ["roles:read"] },
  { to: "/clinical-dataset", label: "数据集", icon: Database, permissions: ["clinical_data:read"] },
  {
    to: "/settings",
    label: "设置",
    icon: Settings,
    permissions: ["users:read", "roles:read", "dictionaries:read"],
  },
];

export function AppShell() {
  const user = useAuthStore((state) => state.user);
  const clearSession = useAuthStore((state) => state.clearSession);
  const hasAnyPermission = useAuthStore((state) => state.hasAnyPermission);
  const visibleNavItems = navItems.filter((item) => hasAnyPermission(item.permissions));

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
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-slate-200 bg-white px-4 py-5 lg:block">
        <div className="flex items-center gap-3 px-2">
          <div className="flex size-10 items-center justify-center rounded-lg bg-emerald-600 text-white">
            <Activity className="size-5" aria-hidden="true" />
          </div>
          <div>
            <p className="text-sm font-semibold leading-5">临床数据收集系统</p>
            <p className="text-xs text-slate-500">Clinical Data System</p>
          </div>
        </div>

        <nav className="mt-8 space-y-1">
          {visibleNavItems.map((item) => (
            <NavLink
              key={item.to}
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
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="absolute inset-x-4 bottom-4 border-t border-slate-200 pt-4">
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

        <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
