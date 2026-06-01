import { CheckCircle2, FileText, Plus, RotateCcw, Save, Trash2, Upload } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { EntityTable } from "@/components/master-data/EntityTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, SelectField, TextAreaField } from "@/components/ui/form";
import { inputClassName } from "@/lib/form-styles";
import { masterDataApi } from "@/services/master-data";
import { trialProtocolApi } from "@/services/trial-protocols";
import type { DictionaryItem, Project, ProjectPayload } from "@/types/master-data";
import type {
  TrialProtocolCenterDraft,
  TrialProtocolDraft,
  TrialProtocolVersion,
  TrialProtocolVersionSummary,
  TrialProtocolVisitDraft,
} from "@/types/trial-protocol";

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
  const [protocolSummaries, setProtocolSummaries] = useState<
    Record<number, TrialProtocolVersionSummary | null>
  >({});
  const [form, setForm] = useState<ProjectPayload>(defaultForm);
  const [newProjectProtocolFile, setNewProjectProtocolFile] = useState<File | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [protocolVersions, setProtocolVersions] = useState<TrialProtocolVersionSummary[]>([]);
  const [activeProtocol, setActiveProtocol] = useState<TrialProtocolVersion | null>(null);
  const [draft, setDraft] = useState<TrialProtocolDraft | null>(null);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [protocolLoading, setProtocolLoading] = useState(false);
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
      const versionEntries = await Promise.all(
        projectData.map(async (project) => {
          try {
            const versions = await trialProtocolApi.listVersions(project.id);
            return [project.id, versions[0] ?? null] as const;
          } catch {
            return [project.id, null] as const;
          }
        }),
      );
      setProtocolSummaries(Object.fromEntries(versionEntries));
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
    setNewProjectProtocolFile(null);
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
        const project = await masterDataApi.createProject(payload);
        setSelectedProjectId(project.id);
        if (newProjectProtocolFile) {
          const version = await trialProtocolApi.uploadVersion(project.id, newProjectProtocolFile);
          setActiveProtocol(version);
          setDraft(version.draft_json);
          setMessage("项目已创建，试验方案已解析");
          await loadProtocolVersions(project.id);
        } else {
          setMessage("项目已创建");
        }
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
    setSelectedProjectId(project.id);
    setForm({
      name: project.name,
      code: project.code,
      description: project.description ?? "",
      status: project.status,
    });
    void loadProtocolVersions(project.id);
  }

  async function loadProtocolVersions(projectId: number) {
    setProtocolLoading(true);
    try {
      const versions = await trialProtocolApi.listVersions(projectId);
      setProtocolVersions(versions);
      if (versions.length > 0) {
        const detail = await trialProtocolApi.getVersion(projectId, versions[0].id);
        setActiveProtocol(detail);
        setDraft(detail.draft_json);
      } else {
        setActiveProtocol(null);
        setDraft(null);
      }
    } catch {
      setMessage("试验方案版本加载失败");
    } finally {
      setProtocolLoading(false);
    }
  }

  async function handleProtocolUpload() {
    if (!selectedProjectId || !uploadFile) {
      setMessage("请先选择项目并选择PDF方案文件");
      return;
    }
    setProtocolLoading(true);
    try {
      const version = await trialProtocolApi.uploadVersion(selectedProjectId, uploadFile);
      setActiveProtocol(version);
      setDraft(version.draft_json);
      setUploadFile(null);
      await loadProtocolVersions(selectedProjectId);
      await loadData();
      setMessage(version.parsing_status === "parse_failed" ? "方案已上传，解析失败，请手动维护草稿" : "方案已上传并解析");
    } catch {
      setMessage("方案上传失败");
    } finally {
      setProtocolLoading(false);
    }
  }

  async function openProtocolVersion(versionId: number) {
    if (!selectedProjectId) return;
    setProtocolLoading(true);
    try {
      const version = await trialProtocolApi.getVersion(selectedProjectId, versionId);
      setActiveProtocol(version);
      setDraft(version.draft_json);
    } catch {
      setMessage("方案详情加载失败");
    } finally {
      setProtocolLoading(false);
    }
  }

  async function saveProtocolDraft() {
    if (!selectedProjectId || !activeProtocol || !draft) return;
    try {
      const version = await trialProtocolApi.updateDraft(selectedProjectId, activeProtocol.id, draft);
      setActiveProtocol(version);
      setDraft(version.draft_json);
      await loadProtocolVersions(selectedProjectId);
      setMessage("方案草稿已保存");
    } catch {
      setMessage("方案草稿保存失败");
    }
  }

  async function applyProtocol() {
    if (!selectedProjectId || !activeProtocol) return;
    try {
      if (draft) {
        await trialProtocolApi.updateDraft(selectedProjectId, activeProtocol.id, draft);
      }
      const result = await trialProtocolApi.applyVersion(selectedProjectId, activeProtocol.id);
      setActiveProtocol(result.version);
      setDraft(result.version.draft_json);
      await loadProtocolVersions(selectedProjectId);
      await loadData();
      setMessage("方案已应用到访视、资料模板和中心");
    } catch {
      setMessage("方案应用失败");
    }
  }

  function selectProject(project: Project) {
    setSelectedProjectId(project.id);
    void loadProtocolVersions(project.id);
  }

  function updateVisit(index: number, patch: Partial<TrialProtocolVisitDraft>) {
    setDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        visits: current.visits.map((visit, itemIndex) =>
          itemIndex === index ? { ...visit, ...patch } : visit,
        ),
      };
    });
  }

  function updateVisitItem(
    visitIndex: number,
    itemIndex: number,
    patch: Partial<TrialProtocolVisitDraft["items"][number]>,
  ) {
    setDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        visits: current.visits.map((visit, currentVisitIndex) =>
          currentVisitIndex === visitIndex
            ? {
                ...visit,
                items: visit.items.map((item, currentItemIndex) =>
                  currentItemIndex === itemIndex ? { ...item, ...patch } : item,
                ),
              }
            : visit,
        ),
      };
    });
  }

  function addVisitItem(visitIndex: number) {
    setDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        visits: current.visits.map((visit, currentVisitIndex) =>
          currentVisitIndex === visitIndex
            ? {
                ...visit,
                items: [
                  ...visit.items,
                  {
                    ordinal: visit.items.length + 1,
                    name: "新增资料项",
                    required: true,
                    enabled: true,
                  },
                ],
              }
            : visit,
        ),
      };
    });
  }

  function removeVisitItem(visitIndex: number, itemIndex: number) {
    setDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        visits: current.visits.map((visit, currentVisitIndex) =>
          currentVisitIndex === visitIndex
            ? {
                ...visit,
                items: visit.items.filter((_, currentItemIndex) => currentItemIndex !== itemIndex),
              }
            : visit,
        ),
      };
    });
  }

  function addVisit() {
    setDraft((current) => {
      const nextOrdinal = (current?.visits.length ?? 0) + 1;
      const nextVisit: TrialProtocolVisitDraft = {
        ordinal: nextOrdinal,
        source_visit_code: `V${nextOrdinal}`,
        name: `访视${nextOrdinal}`,
        window: null,
        enabled: true,
        items: [],
      };
      return current
        ? { ...current, visits: [...current.visits, nextVisit] }
        : { visits: [nextVisit], centers: [], deactivate_missing: { visits: false, items: false, centers: false } };
    });
  }

  function updateCenter(index: number, patch: Partial<TrialProtocolCenterDraft>) {
    setDraft((current) => {
      if (!current) return current;
      return {
        ...current,
        centers: current.centers.map((center, itemIndex) =>
          itemIndex === index ? { ...center, ...patch } : center,
        ),
      };
    });
  }

  function addCenter() {
    setDraft((current) => {
      const nextCenter: TrialProtocolCenterDraft = {
        code: "",
        name: "新增中心",
        filing_no: null,
        principal_investigator: null,
        enabled: true,
      };
      return current
        ? { ...current, centers: [...current.centers, nextCenter] }
        : { visits: [], centers: [nextCenter], deactivate_missing: { visits: false, items: false, centers: false } };
    });
  }

  function removeVisit(index: number) {
    setDraft((current) =>
      current ? { ...current, visits: current.visits.filter((_, itemIndex) => itemIndex !== index) } : current,
    );
  }

  function removeCenter(index: number) {
    setDraft((current) =>
      current ? { ...current, centers: current.centers.filter((_, itemIndex) => itemIndex !== index) } : current,
    );
  }

  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;

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
              {!editingId && (
                <Field label="临床试验方案PDF">
                  <input
                    className={inputClassName("text-xs")}
                    type="file"
                    accept="application/pdf,.pdf"
                    onChange={(event) => setNewProjectProtocolFile(event.target.files?.[0] ?? null)}
                  />
                </Field>
              )}
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
                {
                  key: "protocol",
                  label: "方案",
                  render: (project) => {
                    const latest = protocolSummaries[project.id];
                    return latest ? (
                      <span className="text-slate-600">
                        v{latest.version_number} · {latest.parsing_status}
                      </span>
                    ) : (
                      <span className="text-slate-400">未上传</span>
                    );
                  },
                },
                {
                  key: "protocol_action",
                  label: "方案维护",
                  render: (project) => (
                    <Button size="sm" variant="ghost" onClick={() => selectProject(project)}>
                      <FileText className="size-4" aria-hidden="true" />
                    </Button>
                  ),
                },
              ]}
            />
          </CardContent>
        </Card>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>临床试验方案</CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-sm font-medium text-slate-900">
                {selectedProject ? selectedProject.name : "请选择一个项目"}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                上传方案后先进入可编辑草稿，确认应用后生成试验进行阶段访视、资料模板和中心。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <input
                className={inputClassName("h-9 max-w-72 text-xs")}
                type="file"
                accept="application/pdf,.pdf"
                disabled={!selectedProjectId || protocolLoading}
                onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)}
              />
              <Button
                type="button"
                variant="secondary"
                onClick={() => void handleProtocolUpload()}
                disabled={!selectedProjectId || !uploadFile || protocolLoading}
              >
                <Upload className="size-4" aria-hidden="true" />
                上传解析
              </Button>
            </div>
          </div>

          {selectedProject && protocolVersions.length > 0 && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-slate-500">历史版本</span>
              <SelectField
                value={String(activeProtocol?.id ?? protocolVersions[0]?.id ?? "")}
                onChange={(event) => void openProtocolVersion(Number(event.target.value))}
                className="h-9 w-64"
              >
                {protocolVersions.map((version) => (
                  <option key={version.id} value={version.id}>
                    v{version.version_number} · {version.original_name}
                  </option>
                ))}
              </SelectField>
              {activeProtocol && (
                <Badge tone={activeProtocol.parsing_status === "parse_failed" ? "danger" : "neutral"}>
                  {activeProtocol.parsing_status}
                </Badge>
              )}
            </div>
          )}

          {activeProtocol && (
            <div className="grid gap-3 text-sm md:grid-cols-4">
              <div className="rounded-md border border-slate-200 p-3">
                <span className="block text-xs text-slate-500">方案编号</span>
                <span className="mt-1 block font-medium text-slate-900">
                  {activeProtocol.protocol_no || "-"}
                </span>
              </div>
              <div className="rounded-md border border-slate-200 p-3">
                <span className="block text-xs text-slate-500">方案版本</span>
                <span className="mt-1 block font-medium text-slate-900">
                  {activeProtocol.protocol_version || "-"}
                </span>
              </div>
              <div className="rounded-md border border-slate-200 p-3">
                <span className="block text-xs text-slate-500">方案日期</span>
                <span className="mt-1 block font-medium text-slate-900">
                  {activeProtocol.protocol_date || "-"}
                </span>
              </div>
              <div className="rounded-md border border-slate-200 p-3">
                <span className="block text-xs text-slate-500">页数</span>
                <span className="mt-1 block font-medium text-slate-900">
                  {activeProtocol.page_count || "-"}
                </span>
              </div>
            </div>
          )}

          {draft ? (
            <div className="space-y-6">
              <section className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <h2 className="text-sm font-semibold text-slate-900">访视与资料项</h2>
                  <Button type="button" size="sm" variant="secondary" onClick={addVisit}>
                    <Plus className="size-4" aria-hidden="true" />
                    访视
                  </Button>
                </div>
                <div className="space-y-3">
                  {draft.visits.map((visit, visitIndex) => (
                    <div key={`${visit.ordinal}-${visitIndex}`} className="rounded-md border border-slate-200 p-3">
                      <div className="grid gap-2 lg:grid-cols-[80px_1fr_160px_90px_auto]">
                        <input
                          className={inputClassName("h-9")}
                          type="number"
                          min={1}
                          value={visit.ordinal}
                          onChange={(event) =>
                            updateVisit(visitIndex, { ordinal: Number(event.target.value) })
                          }
                        />
                        <input
                          className={inputClassName("h-9")}
                          value={visit.name}
                          onChange={(event) => updateVisit(visitIndex, { name: event.target.value })}
                        />
                        <input
                          className={inputClassName("h-9")}
                          value={visit.window ?? ""}
                          onChange={(event) => updateVisit(visitIndex, { window: event.target.value })}
                          placeholder="窗口期"
                        />
                        <label className="flex items-center gap-2 text-xs text-slate-600">
                          <input
                            type="checkbox"
                            checked={visit.enabled}
                            onChange={(event) =>
                              updateVisit(visitIndex, { enabled: event.target.checked })
                            }
                          />
                          启用
                        </label>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => removeVisit(visitIndex)}
                        >
                          <Trash2 className="size-4" aria-hidden="true" />
                        </Button>
                      </div>
                      <div className="mt-3 space-y-2">
                        {visit.items.map((item, itemIndex) => (
                          <div
                            key={`${item.ordinal}-${itemIndex}`}
                            className="grid gap-2 lg:grid-cols-[80px_1fr_90px_90px_auto]"
                          >
                            <input
                              className={inputClassName("h-9")}
                              type="number"
                              min={1}
                              value={item.ordinal}
                              onChange={(event) =>
                                updateVisitItem(visitIndex, itemIndex, {
                                  ordinal: Number(event.target.value),
                                })
                              }
                            />
                            <input
                              className={inputClassName("h-9")}
                              value={item.name}
                              onChange={(event) =>
                                updateVisitItem(visitIndex, itemIndex, { name: event.target.value })
                              }
                            />
                            <label className="flex items-center gap-2 text-xs text-slate-600">
                              <input
                                type="checkbox"
                                checked={item.required}
                                onChange={(event) =>
                                  updateVisitItem(visitIndex, itemIndex, {
                                    required: event.target.checked,
                                  })
                                }
                              />
                              必需
                            </label>
                            <label className="flex items-center gap-2 text-xs text-slate-600">
                              <input
                                type="checkbox"
                                checked={item.enabled}
                                onChange={(event) =>
                                  updateVisitItem(visitIndex, itemIndex, {
                                    enabled: event.target.checked,
                                  })
                                }
                              />
                              启用
                            </label>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() => removeVisitItem(visitIndex, itemIndex)}
                            >
                              <Trash2 className="size-4" aria-hidden="true" />
                            </Button>
                          </div>
                        ))}
                        <Button type="button" size="sm" variant="ghost" onClick={() => addVisitItem(visitIndex)}>
                          <Plus className="size-4" aria-hidden="true" />
                          资料项
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              <section className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <h2 className="text-sm font-semibold text-slate-900">试验中心</h2>
                  <Button type="button" size="sm" variant="secondary" onClick={addCenter}>
                    <Plus className="size-4" aria-hidden="true" />
                    中心
                  </Button>
                </div>
                <div className="space-y-2">
                  {draft.centers.map((center, centerIndex) => (
                    <div
                      key={`${center.code}-${centerIndex}`}
                      className="grid gap-2 rounded-md border border-slate-200 p-3 lg:grid-cols-[80px_1fr_120px_120px_90px_auto]"
                    >
                      <input
                        className={inputClassName("h-9")}
                        value={center.code}
                        onChange={(event) => updateCenter(centerIndex, { code: event.target.value })}
                        placeholder="代号"
                      />
                      <input
                        className={inputClassName("h-9")}
                        value={center.name}
                        onChange={(event) => updateCenter(centerIndex, { name: event.target.value })}
                      />
                      <input
                        className={inputClassName("h-9")}
                        value={center.filing_no ?? ""}
                        onChange={(event) => updateCenter(centerIndex, { filing_no: event.target.value })}
                        placeholder="备案号"
                      />
                      <input
                        className={inputClassName("h-9")}
                        value={center.principal_investigator ?? ""}
                        onChange={(event) =>
                          updateCenter(centerIndex, { principal_investigator: event.target.value })
                        }
                        placeholder="研究者"
                      />
                      <label className="flex items-center gap-2 text-xs text-slate-600">
                        <input
                          type="checkbox"
                          checked={center.enabled}
                          onChange={(event) =>
                            updateCenter(centerIndex, { enabled: event.target.checked })
                          }
                        />
                        启用
                      </label>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        onClick={() => removeCenter(centerIndex)}
                      >
                        <Trash2 className="size-4" aria-hidden="true" />
                      </Button>
                    </div>
                  ))}
                </div>
              </section>

              <div className="flex flex-wrap gap-2">
                <Button type="button" variant="secondary" onClick={() => void saveProtocolDraft()}>
                  <Save className="size-4" aria-hidden="true" />
                  保存草稿
                </Button>
                <Button type="button" onClick={() => void applyProtocol()}>
                  <CheckCircle2 className="size-4" aria-hidden="true" />
                  确认应用
                </Button>
              </div>
            </div>
          ) : (
            <p className="rounded-md border border-dashed border-slate-200 p-6 text-sm text-slate-500">
              暂无方案草稿
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
