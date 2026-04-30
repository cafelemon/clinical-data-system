import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "@/components/layout/AppShell";
import { CentersPage } from "@/pages/centers/CentersPage";
import { ClinicalDatasetPage } from "@/pages/clinical-dataset/ClinicalDatasetPage";
import { DashboardPage } from "@/pages/dashboard/DashboardPage";
import { LoginPage } from "@/pages/login/LoginPage";
import { ProjectsPage } from "@/pages/projects/ProjectsPage";
import { SettingsPage } from "@/pages/settings/SettingsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<AppShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="/projects" element={<ProjectsPage />} />
        <Route path="/centers" element={<CentersPage />} />
        <Route path="/clinical-dataset" element={<ClinicalDatasetPage />} />
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

