import { Power, RotateCcw, Save } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { EntityTable } from "@/components/master-data/EntityTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, SelectField, TextAreaField } from "@/components/ui/form";
import { inputClassName } from "@/lib/form-styles";
import { masterDataApi } from "@/services/master-data";
import type { Project, Stage, StageOptionGroup } from "@/types/master-data";

type StageForm = {
  project_id: number;
  phase_code: string;
  option_code: string;
  sort_order: number;
  enabled: boolean;
  description: string;
};

const defaultForm: StageForm = {
  project_id: 0,
  phase_code: "STARTUP",
  option_code: "",
  sort_order: 0,
  enabled: true,
  description: "",
};

export function StagesPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [stageOptions, setStageOptions] = useState<StageOptionGroup[]>([]);
  const [stages, setStages] = useState<Stage[]>([]);
  const [projectFilter, setProjectFilter] = useState<number | undefined>();
  const [phaseFilter, setPhaseFilter] = useState("STARTUP");
  const [form, setForm] = useState<StageForm>(defaultForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const projectNameById = useMemo(
    () => new Map(projects.map((project) => [project.id, project.name])),
    [projects],
  );
  const phaseNameByCode = useMemo(
    () => new Map(stageOptions.map((group) => [group.phase_code, group.phase_name])),
    [stageOptions],
  );
  const optionGroupsByCode = useMemo(
    () => new Map(stageOptions.map((group) => [group.phase_code, group])),
    [stageOptions],
  );
  const selectedOptions = optionGroupsByCode.get(form.phase_code)?.options ?? [];

  async function loadData(nextProjectFilter = projectFilter, nextPhaseFilter = phaseFilter) {
    const [projectData, optionData, stageData] = await Promise.all([
      masterDataApi.listProjects(),
      masterDataApi.listStageOptions(),
      masterDataApi.listStages(nextProjectFilter, nextPhaseFilter),
    ]);
    setProjects(projectData);
    setStageOptions(optionData);
    setStages(stageData);
    const projectId = form.project_id || nextProjectFilter || projectData[0]?.id || 0;
    const optionCode =
      form.option_code ||
      optionData.find((group) => group.phase_code === nextPhaseFilter)?.options[0]?.option_code ||
      "";
    if (!form.project_id || !form.option_code) {
      setForm((current) => ({
        ...current,
        project_id: projectId,
        phase_code: nextPhaseFilter,
        option_code: optionCode,
      }));
    }
  }

  useEffect(() => {
    async function initialize() {
      const [projectData, optionData, stageData] = await Promise.all([
        masterDataApi.listProjects(),
        masterDataApi.listStageOptions(),
        masterDataApi.listStages(undefined, "STARTUP"),
      ]);
      setProjects(projectData);
      setStageOptions(optionData);
      setStages(stageData);
      setForm((current) => ({
        ...current,
        project_id: projectData[0]?.id ?? 0,
        option_code: optionData.find((group) => group.phase_code === "STARTUP")?.options[0]?.option_code ?? "",
      }));
    }

    void initialize();
  }, []);

  function resetForm() {
    const projectId = form.project_id || projectFilter || projects[0]?.id || 0;
    const optionCode = optionGroupsByCode.get(phaseFilter)?.options[0]?.option_code ?? "";
    setEditingId(null);
    setForm({
      ...defaultForm,
      project_id: projectId,
      phase_code: phaseFilter,
      option_code: optionCode,
    });
  }

  function handlePhaseChange(phaseCode: string) {
    const optionCode = optionGroupsByCode.get(phaseCode)?.options[0]?.option_code ?? "";
    setForm((current) => ({
      ...current,
      phase_code: phaseCode,
      option_code: optionCode,
      sort_order: optionGroupsByCode.get(phaseCode)?.options[0]?.sort_order ?? 0,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.project_id || !form.phase_code || !form.option_code) {
      setMessage("请先选择项目、大阶段和二级阶段");
      return;
    }
    const option = selectedOptions.find((item) => item.option_code === form.option_code);
    const payload = {
      project_id: form.project_id,
      phase_code: form.phase_code,
      option_code: form.option_code,
      sort_order: Number(form.sort_order) || option?.sort_order || 0,
      enabled: form.enabled,
      description: form.description.trim() || null,
    };
    try {
      if (editingId) {
        await masterDataApi.updateStage(editingId, payload);
        setMessage("二级阶段已更新");
      } else {
        await masterDataApi.createStage(payload);
        setMessage("二级阶段已启用");
      }
      resetForm();
      await loadData();
    } catch {
      setMessage("保存失败，请确认二级阶段来自样例库");
    }
  }

  async function handleToggle(stage: Stage) {
    await masterDataApi.updateStage(stage.id, { enabled: !stage.enabled });
    await loadData();
  }

  function handleEdit(stage: Stage) {
    setEditingId(stage.id);
    setForm({
      project_id: stage.project_id,
      phase_code: stage.phase_code ?? "STARTUP",
      option_code: stage.option_code ?? stage.code,
      sort_order: stage.sort_order,
      enabled: stage.enabled,
      description: stage.description ?? "",
    });
  }

  async function handleProjectFilterChange(value: string) {
    const nextProjectId = value ? Number(value) : undefined;
    setProjectFilter(nextProjectId);
    await loadData(nextProjectId, phaseFilter);
  }

  async function handlePhaseFilterChange(value: string) {
    setPhaseFilter(value);
    handlePhaseChange(value);
    await loadData(projectFilter, value);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">二级阶段管理</h1>
          <p className="mt-1 text-sm text-slate-500">按项目维护三大阶段下的二级阶段配置</p>
        </div>
        <Button variant="secondary" onClick={() => void loadData()}>
          <RotateCcw className="size-4" aria-hidden="true" />
          刷新
        </Button>
      </div>

      {message && (
        <Badge tone={message.includes("失败") || message.includes("选择") ? "danger" : "success"}>
          {message}
        </Badge>
      )}

      <section className="grid gap-4 xl:grid-cols-[380px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>{editingId ? "编辑二级阶段" : "添加二级阶段"}</CardTitle>
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
              <Field label="大阶段">
                <SelectField
                  value={form.phase_code}
                  onChange={(event) => handlePhaseChange(event.target.value)}
                  required
                >
                  {stageOptions.map((group) => (
                    <option key={group.phase_code} value={group.phase_code}>
                      {group.phase_name}
                    </option>
                  ))}
                </SelectField>
              </Field>
              <Field label="二级阶段">
                <SelectField
                  value={form.option_code}
                  onChange={(event) => {
                    const option = selectedOptions.find(
                      (item) => item.option_code === event.target.value,
                    );
                    setForm((current) => ({
                      ...current,
                      option_code: event.target.value,
                      sort_order: option?.sort_order ?? current.sort_order,
                      description: option?.description ?? current.description,
                    }));
                  }}
                  disabled={Boolean(editingId)}
                  required
                >
                  <option value="" disabled>
                    从样例库选择
                  </option>
                  {selectedOptions.map((option) => (
                    <option key={option.option_code} value={option.option_code}>
                      {option.name}
                    </option>
                  ))}
                </SelectField>
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="启用状态">
                  <SelectField
                    value={form.enabled ? "true" : "false"}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, enabled: event.target.value === "true" }))
                    }
                  >
                    <option value="true">启用</option>
                    <option value="false">停用</option>
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
                  value={form.description}
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
              <CardTitle>二级阶段列表</CardTitle>
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
                  value={phaseFilter}
                  onChange={(event) => void handlePhaseFilterChange(event.target.value)}
                >
                  {stageOptions.map((group) => (
                    <option key={group.phase_code} value={group.phase_code}>
                      {group.phase_name}
                    </option>
                  ))}
                </SelectField>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <EntityTable
              rows={stages}
              getRowKey={(stage) => stage.id}
              emptyLabel="暂无二级阶段"
              onEdit={handleEdit}
              columns={[
                {
                  key: "project",
                  label: "项目",
                  render: (stage) => projectNameById.get(stage.project_id) ?? "-",
                },
                {
                  key: "phase",
                  label: "大阶段",
                  render: (stage) => phaseNameByCode.get(stage.phase_code ?? "") ?? "-",
                },
                { key: "name", label: "二级阶段", render: (stage) => stage.name },
                { key: "code", label: "样例编码", render: (stage) => stage.option_code ?? stage.code },
                {
                  key: "enabled",
                  label: "状态",
                  render: (stage) => (
                    <Button
                      type="button"
                      size="sm"
                      variant={stage.enabled ? "secondary" : "ghost"}
                      onClick={() => void handleToggle(stage)}
                    >
                      <Power className="size-4" aria-hidden="true" />
                      {stage.enabled ? "启用" : "停用"}
                    </Button>
                  ),
                },
                { key: "sort", label: "排序", render: (stage) => stage.sort_order },
              ]}
            />
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
