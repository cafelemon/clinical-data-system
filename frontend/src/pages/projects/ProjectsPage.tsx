import { RotateCcw, Save } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { EntityTable } from "@/components/master-data/EntityTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, SelectField, TextAreaField } from "@/components/ui/form";
import { inputClassName } from "@/lib/form-styles";
import { masterDataApi } from "@/services/master-data";
import type { DictionaryItem, Project, ProjectPayload } from "@/types/master-data";

const defaultForm: ProjectPayload = {
  name: "",
  code: "",
  description: "",
  status: "active",
};

const fallbackStatuses: DictionaryItem[] = [
  {
    id: 0,
    dict_type: "project_status",
    value: "active",
    label: "启用",
    color: "success",
    sort_order: 1,
    enabled: true,
    created_at: "",
    updated_at: "",
  },
  {
    id: -1,
    dict_type: "project_status",
    value: "paused",
    label: "暂停",
    color: "warning",
    sort_order: 2,
    enabled: true,
    created_at: "",
    updated_at: "",
  },
  {
    id: -2,
    dict_type: "project_status",
    value: "closed",
    label: "关闭",
    color: "neutral",
    sort_order: 3,
    enabled: true,
    created_at: "",
    updated_at: "",
  },
];

export function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [statuses, setStatuses] = useState<DictionaryItem[]>(fallbackStatuses);
  const [form, setForm] = useState<ProjectPayload>(defaultForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function loadData() {
    setLoading(true);
    try {
      const [projectData, statusData] = await Promise.all([
        masterDataApi.listProjects(),
        masterDataApi.listDictionaries("project_status"),
      ]);
      setProjects(projectData);
      setStatuses(statusData.length > 0 ? statusData.filter((item) => item.enabled) : fallbackStatuses);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadData();
  }, []);

  function resetForm() {
    setEditingId(null);
    setForm(defaultForm);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = {
      ...form,
      name: form.name.trim(),
      code: form.code.trim(),
      description: form.description?.trim() || null,
    };
    try {
      if (editingId) {
        await masterDataApi.updateProject(editingId, payload);
        setMessage("项目已更新");
      } else {
        await masterDataApi.createProject(payload);
        setMessage("项目已创建");
      }
      resetForm();
      await loadData();
    } catch {
      setMessage("保存失败，请检查编码是否重复");
    }
  }

  async function handleDelete(project: Project) {
    if (!window.confirm(`确认删除项目：${project.name}？`)) return;
    await masterDataApi.deleteProject(project.id);
    await loadData();
  }

  function handleEdit(project: Project) {
    setEditingId(project.id);
    setForm({
      name: project.name,
      code: project.code,
      description: project.description ?? "",
      status: project.status,
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">项目管理</h1>
          <p className="mt-1 text-sm text-slate-500">维护临床项目基础口径</p>
        </div>
        <Button variant="secondary" onClick={() => void loadData()} disabled={loading}>
          <RotateCcw className="size-4" aria-hidden="true" />
          刷新
        </Button>
      </div>

      {message && <Badge tone={message.includes("失败") ? "danger" : "success"}>{message}</Badge>}

      <section className="grid gap-4 xl:grid-cols-[360px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>{editingId ? "编辑项目" : "新建项目"}</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleSubmit}>
              <Field label="项目名称">
                <input
                  className={inputClassName()}
                  value={form.name}
                  onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                  placeholder="小肠项目"
                  required
                />
              </Field>
              <Field label="项目编码">
                <input
                  className={inputClassName()}
                  value={form.code}
                  onChange={(event) => setForm((current) => ({ ...current, code: event.target.value }))}
                  placeholder="SMALL_INTESTINE"
                  required
                />
              </Field>
              <Field label="状态">
                <SelectField
                  value={form.status}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, status: event.target.value }))
                  }
                >
                  {statuses.map((status) => (
                    <option key={status.value} value={status.value}>
                      {status.label}
                    </option>
                  ))}
                </SelectField>
              </Field>
              <Field label="说明">
                <TextAreaField
                  value={form.description ?? ""}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, description: event.target.value }))
                  }
                  placeholder="项目范围、资料口径或备注"
                />
              </Field>
              <div className="flex gap-2">
                <Button type="submit">
                  <Save className="size-4" aria-hidden="true" />
                  保存
                </Button>
                {editingId && (
                  <Button type="button" variant="secondary" onClick={resetForm}>
                    取消
                  </Button>
                )}
              </div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>项目列表</CardTitle>
          </CardHeader>
          <CardContent>
            <EntityTable
              rows={projects}
              getRowKey={(project) => project.id}
              emptyLabel="暂无项目"
              onEdit={handleEdit}
              onDelete={(project) => void handleDelete(project)}
              columns={[
                { key: "name", label: "名称", render: (project) => project.name },
                { key: "code", label: "编码", render: (project) => project.code },
                {
                  key: "status",
                  label: "状态",
                  render: (project) =>
                    statuses.find((status) => status.value === project.status)?.label ?? project.status,
                },
                {
                  key: "description",
                  label: "说明",
                  render: (project) => project.description || "-",
                },
              ]}
            />
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
