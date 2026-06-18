import {
  Building2,
  CheckCircle2,
  FileCheck2,
  FileText,
  Gauge,
  Layers3,
  Plus,
  RotateCcw,
  Save,
  Sparkles,
  Trash2,
  Upload,
  type LucideIcon,
} from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

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

type ProjectProtocolOverview = {
  latest: TrialProtocolVersionSummary;
  riskCenterCount: number;
  pendingCenterConfirmations: number;
  visitCount: number;
  itemCount: number;
  centerCount: number;
};

type DraftStats = {
  visitCount: number;
  enabledVisitCount: number;
  itemCount: number;
  requiredItemCount: number;
  optionalItemCount: number;
  centerCount: number;
  riskCenterCount: number;
  pendingCenterConfirmations: number;
};

const emptyDraftStats: DraftStats = {
  visitCount: 0,
  enabledVisitCount: 0,
  itemCount: 0,
  requiredItemCount: 0,
  optionalItemCount: 0,
  centerCount: 0,
  riskCenterCount: 0,
  pendingCenterConfirmations: 0,
};

const protocolStatusLabels: Record<string, string> = {
  parsed: "已解析",
  parse_failed: "解析失败",
  uploaded: "已上传",
  applied: "已应用",
};

function protocolStatusLabel(status: string) {
  return protocolStatusLabels[status] ?? status;
}

function protocolStatusTone(status: string) {
  if (status === "parse_failed") return "danger" as const;
  if (status === "parsed" || status === "applied") return "success" as const;
  return "neutral" as const;
}

function centerNeedsConfirmationValue(center: TrialProtocolCenterDraft) {
  return Boolean(center.requires_confirmation && !center.confirmed);
}

function draftStats(draft: TrialProtocolDraft | null | undefined): DraftStats {
  if (!draft) return emptyDraftStats;
  const itemCount = draft.visits.reduce((total, visit) => total + visit.items.length, 0);
  const requiredItemCount = draft.visits.reduce(
    (total, visit) => total + visit.items.filter((item) => item.required).length,
    0,
  );
  const riskCenterCount = draft.centers.filter((center) => center.requires_confirmation).length;
  return {
    visitCount: draft.visits.length,
    enabledVisitCount: draft.visits.filter((visit) => visit.enabled).length,
    itemCount,
    requiredItemCount,
    optionalItemCount: itemCount - requiredItemCount,
    centerCount: draft.centers.length,
    riskCenterCount,
    pendingCenterConfirmations: draft.centers.filter(centerNeedsConfirmationValue).length,
  };
}

function parseSourceLabel(source?: string | null) {
  if (!source) return "-";
  if (source === "ocr_api") return "OCR API";
  if (source === "pdf_text") return "PDF 文本";
  if (source === "empty") return "空文本";
  return source;
}

function applyStatus(version: TrialProtocolVersion | null) {
  if (!version) return { label: "未选择", tone: "neutral" as const };
  if (version.applied_at) return { label: "已应用", tone: "success" as const };
  if (version.parsing_status === "parse_failed") return { label: "需手动维护", tone: "danger" as const };
  return { label: "待确认应用", tone: "warning" as const };
}

function MetricCard({
  label,
  value,
  detail,
  icon: Icon,
  tone = "blue",
}: {
  label: string;
  value: string | number;
  detail: string;
  icon: LucideIcon;
  tone?: "blue" | "teal" | "amber" | "red";
}) {
  const toneClass =
    tone === "teal"
      ? "bg-teal-50 text-teal-700"
      : tone === "amber"
        ? "bg-amber-50 text-amber-700"
        : tone === "red"
          ? "bg-rose-50 text-rose-700"
          : "bg-blue-50 text-[#0B2E63]";
  return (
    <div className="rounded-md border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-semibold tracking-normal text-slate-950">{value}</p>
        </div>
        <div className={`flex size-9 shrink-0 items-center justify-center rounded-md ${toneClass}`}>
          <Icon className="size-4" aria-hidden="true" />
        </div>
      </div>
      <p className="mt-3 truncate text-xs text-slate-500">{detail}</p>
    </div>
  );
}

function WorkflowStep({
  index,
  title,
  detail,
  tone = "neutral",
}: {
  index: number;
  title: string;
  detail: string;
  tone?: "success" | "warning" | "danger" | "neutral";
}) {
  const toneClass =
    tone === "success"
      ? "border-teal-200 bg-teal-50 text-teal-800"
      : tone === "warning"
        ? "border-amber-200 bg-amber-50 text-amber-800"
        : tone === "danger"
          ? "border-rose-200 bg-rose-50 text-rose-800"
          : "border-slate-200 bg-slate-50 text-slate-700";
  return (
    <div className={`rounded-md border p-3 ${toneClass}`}>
      <div className="flex items-center gap-2">
        <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-white text-xs font-semibold">
          {index}
        </span>
        <p className="text-sm font-semibold">{title}</p>
      </div>
      <p className="mt-2 text-xs opacity-80">{detail}</p>
    </div>
  );
}

export function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [statuses, setStatuses] = useState<DictionaryItem[]>(fallbackStatuses);
  const [protocolSummaries, setProtocolSummaries] = useState<
    Record<number, ProjectProtocolOverview | null>
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
            const latest = versions[0] ?? null;
            if (!latest) return [project.id, null] as const;
            const detail = await trialProtocolApi.getVersion(project.id, latest.id);
            const stats = draftStats(detail.draft_json);
            return [
              project.id,
              {
                latest,
                riskCenterCount: stats.riskCenterCount,
                pendingCenterConfirmations: stats.pendingCenterConfirmations,
                visitCount: stats.visitCount,
                itemCount: stats.itemCount,
                centerCount: stats.centerCount,
              },
            ] as const;
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
      if (draft && draft.centers.some(centerNeedsConfirmation)) {
        setMessage("存在未确认的高风险中心字段，请确认后再应用");
        return;
      }
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
      const fieldChanged =
        "code" in patch ||
        "name" in patch ||
        "filing_no" in patch ||
        "principal_investigator" in patch;
      return {
        ...current,
        centers: current.centers.map((center, itemIndex) => {
          if (itemIndex !== index) return center;
          const confirmedPatch =
            fieldChanged && center.requires_confirmation ? { confirmed: false } : {};
          return { ...center, ...confirmedPatch, ...patch };
        }),
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
        confidence: null,
        requires_confirmation: false,
        confirmed: true,
        evidence: null,
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

  function centerNeedsConfirmation(center: TrialProtocolCenterDraft) {
    return Boolean(center.requires_confirmation && !center.confirmed);
  }

  function centerStatus(center: TrialProtocolCenterDraft) {
    if (centerNeedsConfirmation(center)) {
      return { label: "需确认", tone: "warning" as const };
    }
    if (center.requires_confirmation && center.confirmed) {
      return { label: "已确认", tone: "success" as const };
    }
    return { label: "正常", tone: "neutral" as const };
  }

  function confirmCenter(index: number) {
    updateCenter(index, { confirmed: true });
  }

  const selectedProject = projects.find((project) => project.id === selectedProjectId) ?? null;
  const selectedProjectOverview = selectedProject ? protocolSummaries[selectedProject.id] ?? null : null;
  const activeStats = useMemo(() => draftStats(draft), [draft]);
  const pendingCenterConfirmations = activeStats.pendingCenterConfirmations;
  const activeApplyStatus = applyStatus(activeProtocol);
  const workflowSteps = [
    {
      title: "上传解析",
      detail: activeProtocol ? `v${activeProtocol.version_number} · ${activeProtocol.original_name}` : "选择项目后上传 PDF",
      tone: activeProtocol ? ("success" as const) : ("neutral" as const),
    },
    {
      title: "解析证据",
      detail: draft
        ? `${parseSourceLabel(draft.parse_meta?.text_source)} · ${activeProtocol?.page_count ?? draft.parse_meta?.page_count ?? 0} 页`
        : "等待解析草稿",
      tone: draft ? ("success" as const) : ("neutral" as const),
    },
    {
      title: "人工确认",
      detail: draft ? `待确认中心 ${pendingCenterConfirmations} · 风险中心 ${activeStats.riskCenterCount}` : "暂无可确认内容",
      tone: pendingCenterConfirmations > 0 ? ("warning" as const) : draft ? ("success" as const) : ("neutral" as const),
    },
    {
      title: "确认应用",
      detail: activeProtocol?.applied_at ? `应用于 ${new Date(activeProtocol.applied_at).toLocaleDateString()}` : "写入访视、资料模板和中心",
      tone: activeApplyStatus.tone,
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex size-12 shrink-0 items-center justify-center rounded-md bg-blue-50 text-[#0B2E63]">
            <Sparkles className="size-6" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-normal text-slate-950">
              项目与方案智能识别
            </h1>
            <p className="mt-1 text-sm text-slate-500">
              项目基础口径、方案版本解析、证据确认和应用结果
            </p>
          </div>
        </div>
        <Button variant="secondary" onClick={() => void loadData()} disabled={loading}>
          <RotateCcw className="size-4" aria-hidden="true" />
          刷新
        </Button>
      </div>

      {message && <Badge tone={message.includes("失败") ? "danger" : "success"}>{message}</Badge>}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <MetricCard
          label="方案版本"
          value={protocolVersions.length}
          detail={activeProtocol ? `当前 v${activeProtocol.version_number}` : "未选择方案"}
          icon={FileText}
          tone="blue"
        />
        <MetricCard
          label="访视 / 资料项"
          value={`${activeStats.visitCount}/${activeStats.itemCount}`}
          detail={`启用访视 ${activeStats.enabledVisitCount} · 必填 ${activeStats.requiredItemCount}`}
          icon={Layers3}
          tone="teal"
        />
        <MetricCard
          label="试验中心"
          value={activeStats.centerCount}
          detail={`风险 ${activeStats.riskCenterCount} · 待确认 ${pendingCenterConfirmations}`}
          icon={Building2}
          tone={pendingCenterConfirmations > 0 ? "amber" : "blue"}
        />
        <MetricCard
          label="解析来源"
          value={parseSourceLabel(draft?.parse_meta?.text_source)}
          detail={`页数 ${activeProtocol?.page_count ?? draft?.parse_meta?.page_count ?? 0}`}
          icon={Gauge}
          tone="blue"
        />
        <MetricCard
          label="应用状态"
          value={activeApplyStatus.label}
          detail={activeProtocol?.applied_at ? new Date(activeProtocol.applied_at).toLocaleDateString() : "等待确认应用"}
          icon={FileCheck2}
          tone={activeApplyStatus.tone === "danger" ? "red" : activeApplyStatus.tone === "warning" ? "amber" : "teal"}
        />
      </section>

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
                    const overview = protocolSummaries[project.id];
                    return overview ? (
                      <div className="space-y-1">
                        <div className="flex flex-wrap items-center gap-1.5">
                          <Badge tone={protocolStatusTone(overview.latest.parsing_status)}>
                            v{overview.latest.version_number} · {protocolStatusLabel(overview.latest.parsing_status)}
                          </Badge>
                          {overview.latest.applied_at && <Badge tone="success">已应用</Badge>}
                        </div>
                        <p className="text-xs text-slate-500">
                          访视 {overview.visitCount} · 资料 {overview.itemCount} · 中心 {overview.centerCount}
                        </p>
                        <p className="text-xs text-slate-500">
                          风险 {overview.riskCenterCount} · 待确认 {overview.pendingCenterConfirmations}
                        </p>
                      </div>
                    ) : (
                      <span className="text-slate-400">未上传</span>
                    );
                  },
                },
                {
                  key: "protocol_action",
                  label: "方案维护",
                  render: (project) => (
                    <Button
                      size="sm"
                      variant={selectedProjectId === project.id ? "secondary" : "ghost"}
                      onClick={() => selectProject(project)}
                    >
                      <FileText className="size-4" aria-hidden="true" />
                      选择
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
          <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
            <div>
              <CardTitle>临床试验方案智能识别</CardTitle>
              <p className="mt-2 text-sm text-slate-500">
                上传解析、证据核查、人工确认和确认应用保持同一条可追溯链路
              </p>
            </div>
            <Badge tone={activeApplyStatus.tone}>{activeApplyStatus.label}</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(280px,420px)]">
            <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-slate-950">
                    {selectedProject ? selectedProject.name : "请选择一个项目"}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {selectedProjectOverview
                      ? `最新 v${selectedProjectOverview.latest.version_number} · 风险中心 ${selectedProjectOverview.riskCenterCount}`
                      : "选择项目后可上传方案 PDF 并进入解析草稿"}
                  </p>
                </div>
                {activeProtocol && (
                  <Badge tone={protocolStatusTone(activeProtocol.parsing_status)}>
                    {protocolStatusLabel(activeProtocol.parsing_status)}
                  </Badge>
                )}
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div>
                  <p className="text-xs text-slate-500">方案编号</p>
                  <p className="mt-1 truncate text-sm font-medium text-slate-900">
                    {activeProtocol?.protocol_no || "-"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">方案版本</p>
                  <p className="mt-1 truncate text-sm font-medium text-slate-900">
                    {activeProtocol?.protocol_version || "-"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">方案日期</p>
                  <p className="mt-1 truncate text-sm font-medium text-slate-900">
                    {activeProtocol?.protocol_date || "-"}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-slate-500">解析来源</p>
                  <p className="mt-1 truncate text-sm font-medium text-slate-900">
                    {parseSourceLabel(draft?.parse_meta?.text_source)}
                  </p>
                </div>
              </div>
            </div>
            <div className="rounded-md border border-slate-200 bg-white p-4">
              <div className="flex flex-wrap items-center gap-2">
                <input
                  className={inputClassName("h-9 min-w-0 flex-1 text-xs")}
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
              {selectedProject && protocolVersions.length > 0 && (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <span className="text-xs text-slate-500">历史版本</span>
                  <SelectField
                    value={String(activeProtocol?.id ?? protocolVersions[0]?.id ?? "")}
                    onChange={(event) => void openProtocolVersion(Number(event.target.value))}
                    className="h-9 min-w-0 flex-1"
                  >
                    {protocolVersions.map((version) => (
                      <option key={version.id} value={version.id}>
                        v{version.version_number} · {version.original_name}
                      </option>
                    ))}
                  </SelectField>
                </div>
              )}
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            {workflowSteps.map((step, index) => (
              <WorkflowStep
                key={step.title}
                index={index + 1}
                title={step.title}
                detail={step.detail}
                tone={step.tone}
              />
            ))}
          </div>

          {draft ? (
            <div className="space-y-6">
              <section className="rounded-md border border-slate-200 bg-white p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h2 className="text-base font-semibold text-slate-950">访视与资料项</h2>
                    <p className="mt-1 text-xs text-slate-500">
                      访视 {activeStats.visitCount} · 资料项 {activeStats.itemCount} · 必填 {activeStats.requiredItemCount} · 若有 {activeStats.optionalItemCount}
                    </p>
                  </div>
                  <Button type="button" size="sm" variant="secondary" onClick={addVisit}>
                    <Plus className="size-4" aria-hidden="true" />
                    访视
                  </Button>
                </div>
                <div className="mt-4 grid gap-3">
                  {draft.visits.map((visit, visitIndex) => {
                    const requiredCount = visit.items.filter((item) => item.required).length;
                    return (
                      <div key={`${visit.ordinal}-${visitIndex}`} className="rounded-md border border-slate-200 p-3">
                        <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge tone={visit.enabled ? "success" : "neutral"}>
                                {visit.enabled ? "启用" : "停用"}
                              </Badge>
                              <Badge tone="neutral">资料 {visit.items.length}</Badge>
                              <Badge tone="warning">必填 {requiredCount}</Badge>
                              <Badge tone="neutral">若有 {visit.items.length - requiredCount}</Badge>
                            </div>
                            <p className="mt-2 text-sm font-semibold text-slate-950">{visit.name}</p>
                            <p className="mt-1 text-xs text-slate-500">
                              {visit.source_visit_code || `V${visit.ordinal}`} · {visit.window || "无窗口期"}
                            </p>
                          </div>
                          <div className="grid min-w-0 gap-2 sm:grid-cols-[76px_minmax(160px,1fr)_minmax(120px,180px)_auto_auto]">
                            <input
                              className={inputClassName("h-9")}
                              type="number"
                              min={1}
                              value={visit.ordinal}
                              onChange={(event) => updateVisit(visitIndex, { ordinal: Number(event.target.value) })}
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
                            <label className="flex h-9 items-center gap-2 text-xs text-slate-600">
                              <input
                                type="checkbox"
                                checked={visit.enabled}
                                onChange={(event) => updateVisit(visitIndex, { enabled: event.target.checked })}
                              />
                              启用
                            </label>
                            <Button type="button" size="sm" variant="ghost" onClick={() => removeVisit(visitIndex)}>
                              <Trash2 className="size-4" aria-hidden="true" />
                            </Button>
                          </div>
                        </div>
                        <div className="mt-3 divide-y divide-slate-100">
                          {visit.items.map((item, itemIndex) => (
                            <div
                              key={`${item.ordinal}-${itemIndex}`}
                              className="grid gap-2 py-2 md:grid-cols-[76px_minmax(0,1fr)_auto_auto_auto]"
                            >
                              <input
                                className={inputClassName("h-9")}
                                type="number"
                                min={1}
                                value={item.ordinal}
                                onChange={(event) =>
                                  updateVisitItem(visitIndex, itemIndex, { ordinal: Number(event.target.value) })
                                }
                              />
                              <input
                                className={inputClassName("h-9")}
                                value={item.name}
                                onChange={(event) => updateVisitItem(visitIndex, itemIndex, { name: event.target.value })}
                              />
                              <label className="flex h-9 items-center gap-2 text-xs text-slate-600">
                                <input
                                  type="checkbox"
                                  checked={item.required}
                                  onChange={(event) =>
                                    updateVisitItem(visitIndex, itemIndex, { required: event.target.checked })
                                  }
                                />
                                必填
                              </label>
                              <label className="flex h-9 items-center gap-2 text-xs text-slate-600">
                                <input
                                  type="checkbox"
                                  checked={item.enabled}
                                  onChange={(event) =>
                                    updateVisitItem(visitIndex, itemIndex, { enabled: event.target.checked })
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
                        </div>
                        <Button type="button" size="sm" variant="ghost" onClick={() => addVisitItem(visitIndex)}>
                          <Plus className="size-4" aria-hidden="true" />
                          资料项
                        </Button>
                      </div>
                    );
                  })}
                </div>
              </section>

              <section className="rounded-md border border-slate-200 bg-white p-4">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <h2 className="text-base font-semibold text-slate-950">试验中心证据确认</h2>
                    <p className="mt-1 text-xs text-slate-500">
                      风险中心优先展示，逐行确认后才能应用到中心主数据
                    </p>
                  </div>
                  <Button type="button" size="sm" variant="secondary" onClick={addCenter}>
                    <Plus className="size-4" aria-hidden="true" />
                    中心
                  </Button>
                </div>
                <div className="mt-4 space-y-3">
                  {draft.centers
                    .map((center, centerIndex) => ({ center, centerIndex }))
                    .sort((first, second) => {
                      const firstRisk = centerNeedsConfirmation(first.center) ? 0 : first.center.requires_confirmation ? 1 : 2;
                      const secondRisk = centerNeedsConfirmation(second.center) ? 0 : second.center.requires_confirmation ? 1 : 2;
                      return firstRisk - secondRisk;
                    })
                    .map(({ center, centerIndex }) => (
                      <div
                        key={`${center.code}-${centerIndex}`}
                        className="rounded-md border border-slate-200 p-3"
                      >
                        <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <Badge tone={centerStatus(center).tone}>{centerStatus(center).label}</Badge>
                              {typeof center.confidence === "number" && (
                                <Badge tone={center.confidence < 0.7 ? "warning" : "neutral"}>
                                  置信度 {Math.round(center.confidence * 100)}%
                                </Badge>
                              )}
                              {center.evidence?.page_no && (
                                <Badge tone="neutral">来源页 {center.evidence.page_no}</Badge>
                              )}
                              {center.evidence?.source && (
                                <Badge tone="neutral">{parseSourceLabel(center.evidence.source)}</Badge>
                              )}
                            </div>
                            <p className="mt-2 text-sm font-semibold text-slate-950">{center.name || "未命名中心"}</p>
                            {center.evidence?.risk_reasons && center.evidence.risk_reasons.length > 0 && (
                              <p className="mt-1 text-xs text-amber-700">
                                风险：{center.evidence.risk_reasons.join("、")}
                              </p>
                            )}
                          </div>
                          {centerNeedsConfirmation(center) && (
                            <Button type="button" size="sm" variant="secondary" onClick={() => confirmCenter(centerIndex)}>
                              <CheckCircle2 className="size-4" aria-hidden="true" />
                              确认本行
                            </Button>
                          )}
                        </div>
                        <div className="mt-3 grid gap-2 lg:grid-cols-[90px_minmax(0,1fr)_minmax(120px,180px)_minmax(120px,180px)_auto_auto]">
                          <input
                            className={inputClassName("h-9")}
                            value={center.code}
                            onChange={(event) => updateCenter(centerIndex, { code: event.target.value })}
                            placeholder="代号"
                          />
                          <input
                            className={inputClassName(centerNeedsConfirmation(center) ? "h-9 border-amber-300" : "h-9")}
                            value={center.name}
                            onChange={(event) => updateCenter(centerIndex, { name: event.target.value })}
                          />
                          <input
                            className={inputClassName(centerNeedsConfirmation(center) ? "h-9 border-amber-300" : "h-9")}
                            value={center.filing_no ?? ""}
                            onChange={(event) => updateCenter(centerIndex, { filing_no: event.target.value })}
                            placeholder="备案号"
                          />
                          <input
                            className={inputClassName(centerNeedsConfirmation(center) ? "h-9 border-amber-300" : "h-9")}
                            value={center.principal_investigator ?? ""}
                            onChange={(event) =>
                              updateCenter(centerIndex, { principal_investigator: event.target.value })
                            }
                            placeholder="研究者"
                          />
                          <label className="flex h-9 items-center gap-2 text-xs text-slate-600">
                            <input
                              type="checkbox"
                              checked={center.enabled}
                              onChange={(event) => updateCenter(centerIndex, { enabled: event.target.checked })}
                            />
                            启用
                          </label>
                          <Button type="button" size="sm" variant="ghost" onClick={() => removeCenter(centerIndex)}>
                            <Trash2 className="size-4" aria-hidden="true" />
                          </Button>
                        </div>
                        {center.evidence?.lines && center.evidence.lines.length > 0 && (
                          <div className="mt-3 rounded-md bg-slate-50 p-3 text-xs text-slate-600">
                            {center.evidence.lines.slice(0, 3).map((line, lineIndex) => (
                              <p key={`${line.page_no}-${lineIndex}`} className="break-words leading-5">
                                P{line.page_no} · {parseSourceLabel(line.source)}：{line.text}
                              </p>
                            ))}
                          </div>
                        )}
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
                  {pendingCenterConfirmations > 0
                    ? `确认应用（${pendingCenterConfirmations}项待确认）`
                    : "确认应用"}
                </Button>
              </div>
            </div>
          ) : (
            <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 p-6 text-sm text-slate-500">
              {selectedProject ? "暂无方案草稿" : "请选择项目后上传或选择方案版本"}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
