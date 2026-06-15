import { FileText, Layers3, RotateCcw, Save } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { EntityTable } from "@/components/master-data/EntityTable";
import { ManagementPageHeader, ManagementStatCard } from "@/components/management/ManagementPage";
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
  template_scope: "center_file",
  required: true,
  sort_order: 0,
  recognition_keywords: "",
  description: "",
};

function stageMatchesScope(stage: Stage, scope: StageTemplatePayload["template_scope"]) {
  if (!stage.enabled) return false;
  const stageCode = stage.option_code ?? stage.code;
  if (scope === "subject_item") return stage.phase_code === "TRIAL" && stageCode !== "TRIAL_MATERIALS";
  return (
    stage.phase_code === "STARTUP" ||
    stage.phase_code === "CLOSEOUT" ||
    stageCode === "TRIAL_MATERIALS"
  );
}

function scopeLabel(scope: string) {
  return scope === "subject_item" ? "受试者资料项" : "中心资料项";
}

function phaseLabel(phaseCode: string | null) {
  if (phaseCode === "STARTUP") return "试验准备阶段";
  if (phaseCode === "TRIAL") return "试验进行阶段";
  if (phaseCode === "CLOSEOUT") return "试验结束阶段";
  return "";
}

function stageOptionLabel(stage: Stage) {
  const phase = phaseLabel(stage.phase_code);
  if (!phase) return stage.name;
  if (stage.option_code?.endsWith("_MATERIALS") || stage.name === "资料准备" || stage.name === "准备资料") {
    return `${phase}${stage.name}`;
  }
  return stage.name;
}

export function StageTemplatesPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [stages, setStages] = useState<Stage[]>([]);
  const [templates, setTemplates] = useState<StageTemplate[]>([]);
  const [projectFilter, setProjectFilter] = useState<number | undefined>();
  const [stageFilter, setStageFilter] = useState<number | undefined>();
  const [scopeFilter, setScopeFilter] = useState<StageTemplatePayload["template_scope"]>("center_file");
  const [form, setForm] = useState<StageTemplatePayload>(defaultForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const projectNameById = useMemo(
    () => new Map(projects.map((project) => [project.id, project.name])),
    [projects],
  );
  const stageById = useMemo(() => new Map(stages.map((stage) => [stage.id, stage])), [stages]);
  const formStages = stages.filter(
    (stage) => stage.project_id === form.project_id && stageMatchesScope(stage, form.template_scope),
  );
  const filteredStageOptions = projectFilter
    ? stages.filter((stage) => stage.project_id === projectFilter && stageMatchesScope(stage, scopeFilter))
    : stages.filter((stage) => stageMatchesScope(stage, scopeFilter));
  const requiredTemplateCount = templates.filter((template) => template.required).length;

  async function loadData(
    nextProjectFilter = projectFilter,
    nextStageFilter = stageFilter,
    nextScopeFilter = scopeFilter,
  ) {
    const [projectData, stageData, templateData] = await Promise.all([
      masterDataApi.listProjects(),
      masterDataApi.listStages(),
      masterDataApi.listStageTemplates(nextProjectFilter, nextStageFilter, nextScopeFilter),
    ]);
    setProjects(projectData);
    setStages(stageData);
    setTemplates(templateData);
    if (!form.project_id && projectData.length > 0) {
      const firstProject = projectData[0];
      const firstStage = stageData.find(
        (stage) => stage.project_id === firstProject.id && stageMatchesScope(stage, nextScopeFilter),
      );
      setForm((current) => ({
        ...current,
        project_id: firstProject.id,
        stage_id: firstStage?.id ?? 0,
        template_scope: nextScopeFilter,
      }));
    }
  }

  useEffect(() => {
    async function initialize() {
      const [projectData, stageData, templateData] = await Promise.all([
        masterDataApi.listProjects(),
        masterDataApi.listStages(),
        masterDataApi.listStageTemplates(undefined, undefined, "center_file"),
      ]);
      setProjects(projectData);
      setStages(stageData);
      setTemplates(templateData);
      if (projectData.length > 0) {
        const firstProject = projectData[0];
        const firstStage = stageData.find(
          (stage) => stage.project_id === firstProject.id && stageMatchesScope(stage, "center_file"),
        );
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
    const firstStage = stages.find(
      (stage) => stage.project_id === projectId && stageMatchesScope(stage, form.template_scope),
    );
    setEditingId(null);
    setForm({
      ...defaultForm,
      project_id: projectId,
      stage_id: firstStage?.id ?? 0,
      template_scope: form.template_scope,
    });
  }

  function handleProjectChange(projectId: number) {
    const firstStage = stages.find(
      (stage) => stage.project_id === projectId && stageMatchesScope(stage, form.template_scope),
    );
    setForm((current) => ({ ...current, project_id: projectId, stage_id: firstStage?.id ?? 0 }));
  }

  function handleScopeChange(scope: StageTemplatePayload["template_scope"]) {
    const firstStage = stages.find(
      (stage) => stage.project_id === form.project_id && stageMatchesScope(stage, scope),
    );
    setForm((current) => ({
      ...current,
      template_scope: scope,
      stage_id: firstStage?.id ?? 0,
    }));
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
      template_scope: form.template_scope,
      recognition_keywords: form.recognition_keywords?.trim() || null,
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
      template_scope: template.template_scope,
      required: template.required,
      sort_order: template.sort_order,
      recognition_keywords: template.recognition_keywords ?? "",
      description: template.description ?? "",
    });
  }

  async function handleProjectFilterChange(value: string) {
    const nextProjectId = value ? Number(value) : undefined;
    setProjectFilter(nextProjectId);
    setStageFilter(undefined);
    await loadData(nextProjectId, undefined, scopeFilter);
  }

  async function handleStageFilterChange(value: string) {
    const nextStageId = value ? Number(value) : undefined;
    setStageFilter(nextStageId);
    await loadData(projectFilter, nextStageId, scopeFilter);
  }

  async function handleScopeFilterChange(value: string) {
    const nextScope = value as StageTemplatePayload["template_scope"];
    setScopeFilter(nextScope);
    setStageFilter(undefined);
    await loadData(projectFilter, undefined, nextScope);
  }

  return (
    <div className="space-y-6">
      <ManagementPageHeader
        title="阶段资料模板"
        description="配置中心级与受试者资料项默认清单"
        icon={FileText}
        badge="后台配置"
        actions={
          <Button variant="secondary" onClick={() => void loadData()}>
            <RotateCcw className="size-4" aria-hidden="true" />
            刷新
          </Button>
        }
      />

      {message && <Badge tone={message.includes("失败") || message.includes("选择") ? "danger" : "success"}>{message}</Badge>}

      <section className="grid gap-3 sm:grid-cols-3">
        <ManagementStatCard label="资料模板" value={templates.length} detail={`必填 ${requiredTemplateCount}`} icon={FileText} />
        <ManagementStatCard label="模板用途" value={scopeLabel(scopeFilter)} detail={projectFilter ? "单项目筛选" : "全部项目"} icon={Layers3} tone="teal" />
        <ManagementStatCard label="可选阶段" value={filteredStageOptions.length} detail="随项目和用途联动" icon={RotateCcw} tone="slate" />
      </section>

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
                      {stageOptionLabel(stage)}
                    </option>
                  ))}
                </SelectField>
              </Field>
              <Field label="模板用途">
                <SelectField
                  value={form.template_scope}
                  onChange={(event) =>
                    handleScopeChange(event.target.value as StageTemplatePayload["template_scope"])
                  }
                  required
                >
                  <option value="center_file">中心资料项</option>
                  <option value="subject_item">受试者资料项</option>
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
              <Field label="识别关键词">
                <TextAreaField
                  value={form.recognition_keywords ?? ""}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      recognition_keywords: event.target.value,
                    }))
                  }
                  placeholder="知情同意书，ICF"
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
              <div className="grid gap-2 sm:grid-cols-3">
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
                  value={scopeFilter}
                  onChange={(event) => void handleScopeFilterChange(event.target.value)}
                >
                  <option value="center_file">中心资料项</option>
                  <option value="subject_item">受试者资料项</option>
                </SelectField>
                <SelectField
                  value={stageFilter ?? ""}
                  onChange={(event) => void handleStageFilterChange(event.target.value)}
                >
                  <option value="">全部阶段</option>
                  {filteredStageOptions.map((stage) => (
                    <option key={stage.id} value={stage.id}>
                      {stageOptionLabel(stage)}
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
              emptyDescription="选择项目、阶段和用途后新增资料项"
              onEdit={handleEdit}
              onDelete={(template) => void handleDelete(template)}
              columns={[
                { key: "project", label: "项目", render: (template) => projectNameById.get(template.project_id) ?? "-" },
                { key: "stage", label: "阶段", render: (template) => {
                  const stage = stageById.get(template.stage_id);
                  return stage ? stageOptionLabel(stage) : "-";
                } },
                { key: "scope", label: "用途", render: (template) => scopeLabel(template.template_scope) },
                { key: "name", label: "资料", render: (template) => template.item_name },
                { key: "code", label: "编码", render: (template) => template.item_code },
                { key: "keywords", label: "识别关键词", render: (template) => template.recognition_keywords || "-" },
                {
                  key: "required",
                  label: "要求",
                  render: (template) => (
                    <Badge tone={template.required ? "warning" : "neutral"}>
                      {template.required ? "必填" : "选填"}
                    </Badge>
                  ),
                },
                { key: "sort", label: "排序", render: (template) => template.sort_order },
              ]}
            />
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
