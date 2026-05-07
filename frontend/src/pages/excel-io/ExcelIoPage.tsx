import { Download, FileSpreadsheet, Upload } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, SelectField } from "@/components/ui/form";
import { excelIoApi } from "@/services/excel-io";
import { masterDataApi } from "@/services/master-data";
import { useAuthStore } from "@/stores/auth-store";
import type { ExportKind, ImportKind, ImportResult } from "@/types/excel-io";
import type { Project } from "@/types/master-data";

const importTargets: Array<{ kind: ImportKind; label: string }> = [
  { kind: "projects", label: "项目列表" },
  { kind: "centers", label: "中心列表" },
  { kind: "stage-templates", label: "阶段资料模板" },
  { kind: "subjects", label: "受试者列表" },
];

const exportTargets: Array<{ kind: ExportKind; label: string }> = [
  { kind: "project-progress", label: "项目进度表" },
  { kind: "center-status", label: "中心资料状态表" },
  { kind: "subject-completeness", label: "受试者资料完整性表" },
  { kind: "missing-items", label: "缺失项清单" },
];

function resultTone(result: ImportResult | null) {
  if (!result) return "neutral";
  return result.errors.length > 0 ? "danger" : "success";
}

function ImportResultPanel({ result }: { result: ImportResult | null }) {
  if (!result) {
    return (
      <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-3 py-4 text-sm text-slate-500">
        暂无导入结果
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Badge tone={resultTone(result)}>总行数 {result.total_rows}</Badge>
        <Badge tone="success">新增 {result.created_count}</Badge>
        <Badge tone="warning">更新 {result.updated_count}</Badge>
        <Badge tone={result.errors.length > 0 ? "danger" : "neutral"}>
          错误 {result.errors.length}
        </Badge>
      </div>
      {result.errors.length > 0 && (
        <div className="max-h-64 overflow-auto rounded-md border border-slate-200">
          <table className="w-full min-w-[520px] text-left text-sm">
            <thead className="border-b border-slate-200 bg-slate-50 text-xs text-slate-500">
              <tr>
                <th className="px-3 py-2 font-medium">行号</th>
                <th className="px-3 py-2 font-medium">字段</th>
                <th className="px-3 py-2 font-medium">原因</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {result.errors.map((error, index) => (
                <tr key={`${error.row}-${error.field}-${index}`}>
                  <td className="px-3 py-2 text-slate-600">{error.row}</td>
                  <td className="px-3 py-2 text-slate-600">{error.field}</td>
                  <td className="px-3 py-2 text-slate-800">{error.message}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export function ExcelIoPage() {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const isAdmin = useAuthStore((state) => Boolean(state.user?.is_admin));
  const canReadImports = hasPermission("imports:read");
  const canWriteImports = hasPermission("imports:write");
  const canReadExports = hasPermission("exports:read");
  const hasAnyExcelPermission = canReadImports || canWriteImports || canReadExports;
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState<number | undefined>();
  const [files, setFiles] = useState<Partial<Record<ImportKind, File>>>({});
  const [results, setResults] = useState<Partial<Record<ImportKind, ImportResult>>>({});
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const selectedProjectName = useMemo(
    () => projects.find((project) => project.id === projectId)?.name ?? "",
    [projectId, projects],
  );
  const visibleImportTargets = useMemo(
    () => (isAdmin ? importTargets : importTargets.filter((target) => target.kind === "subjects")),
    [isAdmin],
  );

  useEffect(() => {
    if (!canReadExports) return;
    let cancelled = false;
    async function loadProjects() {
      try {
        const data = await masterDataApi.listProjects();
        if (cancelled) return;
        setProjects(data);
        setProjectId((current) =>
          current && data.some((project) => project.id === current)
            ? current
            : data[0]?.id,
        );
      } catch {
        if (!cancelled) {
          setProjects([]);
          setMessage("项目列表加载失败");
        }
      }
    }
    void loadProjects();
    return () => {
      cancelled = true;
    };
  }, [canReadExports]);

  async function handleTemplate(kind: ImportKind) {
    setBusyKey(`template:${kind}`);
    setMessage(null);
    try {
      await excelIoApi.downloadImportTemplate(kind);
    } catch {
      setMessage("模板下载失败");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleImport(kind: ImportKind) {
    const file = files[kind];
    if (!file) {
      setMessage("请选择 Excel 文件");
      return;
    }
    setBusyKey(`import:${kind}`);
    setMessage(null);
    try {
      const result = await excelIoApi.importExcel(kind, file);
      setResults((current) => ({ ...current, [kind]: result }));
      setMessage(result.errors.length > 0 ? "导入校验未通过" : "导入完成");
    } catch {
      setMessage("导入失败");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleExport(kind: ExportKind) {
    setBusyKey(`export:${kind}`);
    setMessage(null);
    try {
      await excelIoApi.exportExcel(kind, projectId);
      setMessage("导出已生成");
    } catch {
      setMessage("导出失败");
    } finally {
      setBusyKey(null);
    }
  }

  if (!hasAnyExcelPermission) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">导入导出</h1>
          <p className="mt-1 text-sm text-slate-500">Excel 批量维护</p>
        </div>
        <Card>
          <CardContent className="flex items-center gap-3 py-8 text-sm text-slate-600">
            <FileSpreadsheet className="size-5 text-slate-400" aria-hidden="true" />
            当前账号没有导入导出权限
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">导入导出</h1>
          <p className="mt-1 text-sm text-slate-500">Excel 批量维护</p>
        </div>
        {canReadExports && (
          <Field label="项目" className="w-full sm:w-72">
            <SelectField
              value={projectId ?? ""}
              onChange={(event) => setProjectId(Number(event.target.value) || undefined)}
            >
              <option value="">选择项目</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </SelectField>
          </Field>
        )}
      </div>

      {message && <Badge tone={message.includes("失败") || message.includes("未通过") ? "danger" : "success"}>{message}</Badge>}

      {canReadImports && (
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <FileSpreadsheet className="size-5 text-slate-500" aria-hidden="true" />
            <h2 className="text-base font-semibold text-slate-950">导入模板</h2>
          </div>
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {visibleImportTargets.map((target) => (
              <Card key={target.kind}>
                <CardHeader>
                  <CardTitle>{target.label}</CardTitle>
                </CardHeader>
                <CardContent>
                  <Button
                    type="button"
                    variant="secondary"
                    className="w-full"
                    onClick={() => void handleTemplate(target.kind)}
                    disabled={busyKey === `template:${target.kind}`}
                  >
                    <Download className="size-4" aria-hidden="true" />
                    下载模板
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}

      {canWriteImports && (
        <section className="space-y-3">
          <div className="flex items-center gap-2">
            <Upload className="size-5 text-slate-500" aria-hidden="true" />
            <h2 className="text-base font-semibold text-slate-950">批量导入</h2>
          </div>
          <div className="grid gap-4 xl:grid-cols-2">
            {visibleImportTargets.map((target) => (
              <Card key={target.kind}>
                <CardHeader>
                  <CardTitle>{target.label}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex flex-col gap-3 sm:flex-row">
                    <input
                      type="file"
                      accept=".xlsx"
                      className="block h-10 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1 file:text-sm file:text-slate-700"
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        setFiles((current) => ({ ...current, [target.kind]: file }));
                      }}
                    />
                    <Button
                      type="button"
                      className="shrink-0"
                      onClick={() => void handleImport(target.kind)}
                      disabled={!files[target.kind] || busyKey === `import:${target.kind}`}
                    >
                      <Upload className="size-4" aria-hidden="true" />
                      上传
                    </Button>
                  </div>
                  <ImportResultPanel result={results[target.kind] ?? null} />
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}

      {canReadExports && (
        <section className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Download className="size-5 text-slate-500" aria-hidden="true" />
              <h2 className="text-base font-semibold text-slate-950">报表导出</h2>
            </div>
            {selectedProjectName && <Badge tone="neutral">{selectedProjectName}</Badge>}
          </div>
          {!projectId && (
            <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
              暂无可导出项目
            </div>
          )}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {exportTargets.map((target) => (
              <Card key={target.kind}>
                <CardHeader>
                  <CardTitle>{target.label}</CardTitle>
                </CardHeader>
                <CardContent>
                  <Button
                    type="button"
                    variant="secondary"
                    className="w-full"
                    onClick={() => void handleExport(target.kind)}
                    disabled={!projectId || busyKey === `export:${target.kind}`}
                  >
                    <Download className="size-4" aria-hidden="true" />
                    导出
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
