import { RotateCcw, Save } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { EntityTable } from "@/components/master-data/EntityTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, SelectField, TextAreaField } from "@/components/ui/form";
import { inputClassName } from "@/lib/form-styles";
import { masterDataApi } from "@/services/master-data";
import type { Project, Stage, StagePayload } from "@/types/master-data";

const defaultForm: StagePayload = {
  project_id: 0,
  name: "",
  code: "",
  sort_order: 0,
  description: "",
};

export function StagesPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [stages, setStages] = useState<Stage[]>([]);
  const [projectFilter, setProjectFilter] = useState<number | undefined>();
  const [form, setForm] = useState<StagePayload>(defaultForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const projectNameById = useMemo(
    () => new Map(projects.map((project) => [project.id, project.name])),
    [projects],
  );

  async function loadData(nextProjectFilter = projectFilter) {
    const [projectData, stageData] = await Promise.all([
      masterDataApi.listProjects(),
      masterDataApi.listStages(nextProjectFilter),
    ]);
    setProjects(projectData);
    setStages(stageData);
    if (!form.project_id && projectData.length > 0) {
      setForm((current) => ({ ...current, project_id: projectData[0].id }));
    }
  }

  useEffect(() => {
    async function initialize() {
      const [projectData, stageData] = await Promise.all([
        masterDataApi.listProjects(),
        masterDataApi.listStages(),
      ]);
      setProjects(projectData);
      setStages(stageData);
      if (projectData.length > 0) {
        setForm((current) => ({ ...current, project_id: projectData[0].id }));
      }
    }

    void initialize();
  }, []);

  function resetForm() {
    setEditingId(null);
    setForm((current) => ({
      ...defaultForm,
      project_id: current.project_id || projects[0]?.id || 0,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.project_id) {
      setMessage("请先选择项目");
      return;
    }
    const payload = {
      ...form,
      name: form.name.trim(),
      code: form.code.trim(),
      sort_order: Number(form.sort_order) || 0,
      description: form.description?.trim() || null,
    };
    try {
      if (editingId) {
        await masterDataApi.updateStage(editingId, payload);
        setMessage("阶段已更新");
      } else {
        await masterDataApi.createStage(payload);
        setMessage("阶段已创建");
      }
      resetForm();
      await loadData();
    } catch {
      setMessage("保存失败，请检查阶段编码是否重复");
    }
  }

  async function handleDelete(stage: Stage) {
    if (!window.confirm(`确认删除阶段：${stage.name}？`)) return;
    await masterDataApi.deleteStage(stage.id);
    await loadData();
  }

  function handleEdit(stage: Stage) {
    setEditingId(stage.id);
    setForm({
      project_id: stage.project_id,
      name: stage.name,
      code: stage.code,
      sort_order: stage.sort_order,
      description: stage.description ?? "",
    });
  }

  async function handleFilterChange(value: string) {
    const nextProjectId = value ? Number(value) : undefined;
    setProjectFilter(nextProjectId);
    await loadData(nextProjectId);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">阶段管理</h1>
          <p className="mt-1 text-sm text-slate-500">配置启动、进行、总结等项目阶段</p>
        </div>
        <Button variant="secondary" onClick={() => void loadData()}>
          <RotateCcw className="size-4" aria-hidden="true" />
          刷新
        </Button>
      </div>

      {message && <Badge tone={message.includes("失败") || message.includes("选择") ? "danger" : "success"}>{message}</Badge>}

      <section className="grid gap-4 xl:grid-cols-[360px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>{editingId ? "编辑阶段" : "新建阶段"}</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleSubmit}>
              <Field label="所属项目">
                <SelectField
                  value={form.project_id || ""}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, project_id: Number(event.target.value) }))
                  }
                  required
                >
                  <option value="" disabled>
                    选择项目
                  </option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </SelectField>
              </Field>
              <Field label="阶段名称">
                <input
                  className={inputClassName()}
                  value={form.name}
                  onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                  placeholder="启动阶段"
                  required
                />
              </Field>
              <Field label="阶段编码">
                <input
                  className={inputClassName()}
                  value={form.code}
                  onChange={(event) => setForm((current) => ({ ...current, code: event.target.value }))}
                  placeholder="STARTUP"
                  required
                />
              </Field>
              <Field label="排序">
                <input
                  className={inputClassName()}
                  type="number"
                  value={form.sort_order}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, sort_order: Number(event.target.value) }))
                  }
                />
              </Field>
              <Field label="说明">
                <TextAreaField
                  value={form.description ?? ""}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, description: event.target.value }))
                  }
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
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <CardTitle>阶段列表</CardTitle>
              <SelectField
                className="sm:w-56"
                value={projectFilter ?? ""}
                onChange={(event) => void handleFilterChange(event.target.value)}
              >
                <option value="">全部项目</option>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </SelectField>
            </div>
          </CardHeader>
          <CardContent>
            <EntityTable
              rows={stages}
              getRowKey={(stage) => stage.id}
              emptyLabel="暂无阶段"
              onEdit={handleEdit}
              onDelete={(stage) => void handleDelete(stage)}
              columns={[
                { key: "project", label: "项目", render: (stage) => projectNameById.get(stage.project_id) ?? "-" },
                { key: "name", label: "阶段", render: (stage) => stage.name },
                { key: "code", label: "编码", render: (stage) => stage.code },
                { key: "sort", label: "排序", render: (stage) => stage.sort_order },
                { key: "description", label: "说明", render: (stage) => stage.description || "-" },
              ]}
            />
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
