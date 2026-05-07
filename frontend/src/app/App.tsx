import { useEffect } from "react";
import type { ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { Card, CardContent } from "@/components/ui/card";
import { authApi } from "@/services/auth";
import { useAuthStore } from "@/stores/auth-store";
import { CentersPage } from "@/pages/centers/CentersPage";
import { ClinicalDatasetPage } from "@/pages/clinical-dataset/ClinicalDatasetPage";
import { SubjectDetailPage } from "@/pages/clinical-dataset/SubjectDetailPage";
import { DashboardPage } from "@/pages/dashboard/DashboardPage";
import { DictionariesPage } from "@/pages/dictionaries/DictionariesPage";
import { ExcelIoPage } from "@/pages/excel-io/ExcelIoPage";
import { LoginPage } from "@/pages/login/LoginPage";
import { OperationLogsPage } from "@/pages/operation-logs/OperationLogsPage";
import { PdfPacketsPage } from "@/pages/pdf-packets/PdfPacketsPage";
import { ProjectsPage } from "@/pages/projects/ProjectsPage";
import { RolesPage } from "@/pages/roles/RolesPage";
import { SettingsPage } from "@/pages/settings/SettingsPage";
import { StageTemplatesPage } from "@/pages/stage-templates/StageTemplatesPage";
import { StagesPage } from "@/pages/stages/StagesPage";
import { UsersPage } from "@/pages/users/UsersPage";

function ProtectedShell() {
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);
  const initialized = useAuthStore((state) => state.initialized);
  const setUser = useAuthStore((state) => state.setUser);
  const setInitialized = useAuthStore((state) => state.setInitialized);
  const clearSession = useAuthStore((state) => state.clearSession);

  useEffect(() => {
    let cancelled = false;

    async function initialize() {
      if (!token) {
        setInitialized(true);
        return;
      }
      if (user) {
        setInitialized(true);
        return;
      }
      try {
        const currentUser = await authApi.me();
        if (!cancelled) {
          setUser(currentUser);
          setInitialized(true);
        }
      } catch {
        if (!cancelled) {
          clearSession();
        }
      }
    }

    void initialize();
    return () => {
      cancelled = true;
    };
  }, [clearSession, setInitialized, setUser, token, user]);

  if (!token) {
    return <Navigate to="/login" replace />;
  }
  if (!initialized) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-100 text-sm text-slate-500">
        正在进入系统
      </main>
    );
  }
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  return <AppShell />;
}

function LoginRoute() {
  const token = useAuthStore((state) => state.token);
  const user = useAuthStore((state) => state.user);
  if (token && user) {
    return <Navigate to="/" replace />;
  }
  return <LoginPage />;
}

function AdminOnlyRoute({ title, children }: { title: string; children: ReactNode }) {
  const user = useAuthStore((state) => state.user);
  if (user?.is_admin) {
    return children;
  }
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-normal text-slate-950">{title}</h1>
        <p className="mt-1 text-sm text-slate-500">该入口仅管理员可见</p>
      </div>
      <Card>
        <CardContent className="py-8 text-sm text-slate-600">
          当前账号没有维护该模块的权限
        </CardContent>
      </Card>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />
      <Route element={<ProtectedShell />}>
        <Route index element={<DashboardPage />} />
        <Route
          path="/projects"
          element={
            <AdminOnlyRoute title="项目管理">
              <ProjectsPage />
            </AdminOnlyRoute>
          }
        />
        <Route
          path="/centers"
          element={
            <AdminOnlyRoute title="中心管理">
              <CentersPage />
            </AdminOnlyRoute>
          }
        />
        <Route
          path="/stages"
          element={
            <AdminOnlyRoute title="阶段管理">
              <StagesPage />
            </AdminOnlyRoute>
          }
        />
        <Route
          path="/stage-templates"
          element={
            <AdminOnlyRoute title="阶段资料模板">
              <StageTemplatesPage />
            </AdminOnlyRoute>
          }
        />
        <Route
          path="/dictionaries"
          element={
            <AdminOnlyRoute title="状态字典">
              <DictionariesPage />
            </AdminOnlyRoute>
          }
        />
        <Route path="/excel-io" element={<ExcelIoPage />} />
        <Route path="/pdf-packets" element={<PdfPacketsPage />} />
        <Route
          path="/operation-logs"
          element={
            <AdminOnlyRoute title="操作日志">
              <OperationLogsPage />
            </AdminOnlyRoute>
          }
        />
        <Route
          path="/users"
          element={
            <AdminOnlyRoute title="用户管理">
              <UsersPage />
            </AdminOnlyRoute>
          }
        />
        <Route
          path="/roles"
          element={
            <AdminOnlyRoute title="角色管理">
              <RolesPage />
            </AdminOnlyRoute>
          }
        />
        <Route path="/clinical-dataset" element={<ClinicalDatasetPage />} />
        <Route path="/clinical-dataset/subjects/:subjectId" element={<SubjectDetailPage />} />
        <Route
          path="/settings"
          element={
            <AdminOnlyRoute title="设置">
              <SettingsPage />
            </AdminOnlyRoute>
          }
        />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
