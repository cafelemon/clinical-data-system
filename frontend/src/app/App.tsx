import { useEffect } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { authApi } from "@/services/auth";
import { useAuthStore } from "@/stores/auth-store";
import { CentersPage } from "@/pages/centers/CentersPage";
import { ClinicalDatasetPage } from "@/pages/clinical-dataset/ClinicalDatasetPage";
import { DashboardPage } from "@/pages/dashboard/DashboardPage";
import { DictionariesPage } from "@/pages/dictionaries/DictionariesPage";
import { LoginPage } from "@/pages/login/LoginPage";
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

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginRoute />} />
      <Route element={<ProtectedShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/centers" element={<CentersPage />} />
        <Route path="/stages" element={<StagesPage />} />
        <Route path="/stage-templates" element={<StageTemplatesPage />} />
        <Route path="/dictionaries" element={<DictionariesPage />} />
        <Route path="/users" element={<UsersPage />} />
        <Route path="/roles" element={<RolesPage />} />
        <Route path="/clinical-dataset" element={<ClinicalDatasetPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
