import { RotateCcw, Save } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { EntityTable } from "@/components/master-data/EntityTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, SelectField, TextAreaField } from "@/components/ui/form";
import { inputClassName } from "@/lib/form-styles";
import { masterDataApi } from "@/services/master-data";
import type { Project, Stage, StageTemplate, StageTemplatePayload } from "@/types/master-data";

const defaultForm: StageTemplatePayload = {
  project_id: 0,
  stage_id: 0,
  item_name: "",
  item_code: "",
  required: true,
  sort_order: 0,
  description: "",
};

export function StageTemplatesPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [stages, setStages] = useState<Stage[]>([]);
  const [templates, setTemplates] = useState<StageTemplate[]>([]);
  const [projectFilter, setProjectFilter] = useState<number | undefined>();
  const [stageFilter, setStageFilter] = useState<number | undefined>();
  const [form, setForm] = useState<StageTemplatePayload>(defaultForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const projectNameById = useMemo(
    () => new Map(projects.map((project) => [project.id, project.name])),
    [projects],
  );
  const stageById = useMemo(() => new Map(stages.map((stage) => [stage.id, stage])), [stages]);
  const formStages = stages.filter((stage) => stage.project_id === form.project_id);
  const filteredStageOptions = projectFilter
    ? stages.filter((stage) => stage.project_id === projectFilter)
    : stages;

  async function loadData(nextProjectFilter = projectFilter, nextStageFilter = stageFilter) {
    const [projectData, stageData, templateData] = await Promise.all([
      masterDataApi.listProjects(),
      masterDataApi.listStages(),
      masterDataApi.listStageTemplates(nextProjectFilter, nextStageFilter),
    ]);
    setProjects(projectData);
    setStages(stageData);
    setTemplates(templateData);
    if (!form.project_id && projectData.length > 0) {
      const firstProject = projectData[0];
      const firstStage = stageData.find((stage) => stage.project_id === firstProject.id);
      setForm((current) => ({
        ...current,
        project_id: firstProject.id,
        stage_id: firstStage?.id ?? 0,
      }));
    }
  }

  useEffect(() => {
    async function initialize() {
      const [projectData, stageData, templateData] = await Promise.all([
        masterDataApi.listProjects(),
        masterDataApi.listStages(),
        masterDataApi.listStageTemplates(),
      ]);
      setProjects(projectData);
      setStages(stageData);
      setTemplates(templateData);
      if (projectData.length > 0) {
        const firstProject = projectData[0];
        const firstStage = stageData.find((stage) => stage.project_id === firstProject.id);
        setForm((current) => ({
          ...current,
          project_id: firstProject.id,
          stage_id: firstStage?.id ?? 0,
        }));
      }
    }

    void initialize();
  }, []);

  function resetForm() {
    const projectId = form.project_id || projects[0]?.id || 0;
    const firstStage = stages.find((stage) => stage.project_id === projectId);
    setEditingId(null);
    setForm({ ...defaultForm, project_id: projectId, stage_id: firstStage?.id ?? 0 });
  }

  function handleProjectChange(projectId: number) {
    const firstStage = stages.find((stage) => stage.project_id === projectId);
    setForm((current) => ({ ...current, project_id: projectId, stage_id: firstStage?.id ?? 0 }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.project_id || !form.stage_id) {
      setMessage("请先选择项目和阶段");
      return;
    }
    const payload = {
      ...form,
      item_name: form.item_name.trim(),
      item_code: form.item_code.trim(),
      sort_order: Number(form.sort_order) || 0,
      description: form.description?.trim() || null,
    };
    try {
      if (editingId) {
        await masterDataApi.updateStageTemplate(editingId, payload);
        setMessage("资料模板已更新");
      } else {
        await masterDataApi.createStageTemplate(payload);
        setMessage("资料模板已创建");
      }
      resetForm();
      await loadData();
    } catch {
      setMessage("保存失败，请检查资料项编码是否重复");
    }
  }

  async function handleDelete(template: StageTemplate) {
    if (!window.confirm(`确认删除资料项：${template.item_name}？`)) return;
    await masterDataApi.deleteStageTemplate(template.id);
    await loadData();
  }

  function handleEdit(template: StageTemplate) {
    setEditingId(template.id);
    setForm({
      project_id: template.project_id,
      stage_id: template.stage_id,
      item_name: template.item_name,
      item_code: template.item_code,
      required: template.required,
      sort_order: template.sort_order,
      description: template.description ?? "",
    });
  }

  async function handleProjectFilterChange(value: string) {
    const nextProjectId = value ? Number(value) : undefined;
    setProjectFilter(nextProjectId);
    setStageFilter(undefined);
    await loadData(nextProjectId, undefined);
  }

  async function handleStageFilterChange(value: string) {
    const nextStageId = value ? Number(value) : undefined;
    setStageFilter(nextStageId);
    await loadData(projectFilter, nextStageId);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">阶段资料模板</h1>
          <p className="mt-1 text-sm text-slate-500">配置每个阶段的默认资料清单</p>
        </div>
        <Button variant="secondary" onClick={() => void loadData()}>
          <RotateCcw className="size-4" aria-hidden="true" />
          刷新
        </Button>
      </div>

      {message && <Badge tone={message.includes("失败") || message.includes("选择") ? "danger" : "success"}>{message}</Badge>}

      <section className="grid gap-4 xl:grid-cols-[380px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>{editingId ? "编辑资料项" : "新建资料项"}</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleSubmit}>
              <Field label="所属项目">
                <SelectField
                  value={form.project_id || ""}
                  onChange={(event) => handleProjectChange(Number(event.target.value))}
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
              <Field label="所属阶段">
                <SelectField
                  value={form.stage_id || ""}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, stage_id: Number(event.target.value) }))
                  }
                  required
                >
                  <option value="" disabled>
                    选择阶段
                  </option>
                  {formStages.map((stage) => (
                    <option key={stage.id} value={stage.id}>
                      {stage.name}
                    </option>
                  ))}
                </SelectField>
              </Field>
              <Field label="资料名称">
                <input
                  className={inputClassName()}
                  value={form.item_name}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, item_name: event.target.value }))
                  }
                  placeholder="伦理批件"
                  required
                />
              </Field>
              <Field label="资料编码">
                <input
                  className={inputClassName()}
                  value={form.item_code}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, item_code: event.target.value }))
                  }
                  placeholder="ETHICS_APPROVAL"
                  required
                />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="是否必填">
                  <SelectField
                    value={form.required ? "true" : "false"}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, required: event.target.value === "true" }))
                    }
                  >
                    <option value="true">必填</option>
                    <option value="false">选填</option>
                  </SelectField>
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
              </div>
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
            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
              <CardTitle>资料项列表</CardTitle>
              <div className="grid gap-2 sm:grid-cols-2">
                <SelectField
                  value={projectFilter ?? ""}
                  onChange={(event) => void handleProjectFilterChange(event.target.value)}
                >
                  <option value="">全部项目</option>
                  {projects.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </SelectField>
                <SelectField
                  value={stageFilter ?? ""}
                  onChange={(event) => void handleStageFilterChange(event.target.value)}
                >
                  <option value="">全部阶段</option>
                  {filteredStageOptions.map((stage) => (
                    <option key={stage.id} value={stage.id}>
                      {stage.name}
                    </option>
                  ))}
                </SelectField>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <EntityTable
              rows={templates}
              getRowKey={(template) => template.id}
              emptyLabel="暂无阶段资料模板"
              onEdit={handleEdit}
              onDelete={(template) => void handleDelete(template)}
              columns={[
                { key: "project", label: "项目", render: (template) => projectNameById.get(template.project_id) ?? "-" },
                { key: "stage", label: "阶段", render: (template) => stageById.get(template.stage_id)?.name ?? "-" },
                { key: "name", label: "资料", render: (template) => template.item_name },
                { key: "code", label: "编码", render: (template) => template.item_code },
                { key: "required", label: "要求", render: (template) => (template.required ? "必填" : "选填") },
                { key: "sort", label: "排序", render: (template) => template.sort_order },
              ]}
            />
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
