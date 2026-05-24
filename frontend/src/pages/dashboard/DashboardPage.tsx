import {
  AlertTriangle,
  Download,
  Edit3,
  FileSpreadsheet,
  Plus,
  RefreshCcw,
  Save,
  Trash2,
  Upload,
  X,
} from "lucide-react";
import { ChangeEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Field, SelectField } from "@/components/ui/form";
import { inputClassName } from "@/lib/form-styles";
import { dashboardApi } from "@/services/dashboard";
import { masterDataApi } from "@/services/master-data";
import { useAuthStore } from "@/stores/auth-store";
import type {
  DashboardV31Kind,
  DashboardV31Overview,
  DashboardV31Record,
  DashboardV31Warning,
} from "@/types/dashboard";
import type { Center, Project } from "@/types/master-data";

type FieldKind = "text" | "number" | "date" | "datetime" | "textarea" | "select";

type ColumnDef = {
  key: string;
  label: string;
  kind?: FieldKind;
  required?: boolean;
  options?: Array<{ value: string; label: string }>;
};

type TableConfig = {
  kind: DashboardV31Kind;
  label: string;
  description: string;
  columns: ColumnDef[];
};

const statusOptions = [
  { value: "not_started", label: "未开始" },
  { value: "in_progress", label: "进行中" },
  { value: "done", label: "已完成" },
  { value: "open", label: "未关闭" },
  { value: "closed", label: "已关闭" },
];

const yesNoOptions = [
  { value: "yes", label: "是" },
  { value: "no", label: "否" },
];

const TABLES: TableConfig[] = [
  {
    kind: "milestones",
    label: "进度甘特图",
    description: "按中心维护伦理批件、合同完成、省局备案、启动时间、方案修正案和入组进度。",
    columns: [
      { key: "milestone_name", label: "里程碑", required: true },
      { key: "planned_date", label: "计划日期", kind: "date" },
      { key: "actual_date", label: "实际日期", kind: "date" },
      { key: "status", label: "状态", kind: "select", options: statusOptions },
      { key: "owner", label: "负责人" },
      { key: "notes", label: "备注", kind: "textarea" },
    ],
  },
  {
    kind: "enrollment-plans",
    label: "入组计划表",
    description: "维护中心级合同例数、筛选、入组、阳性、全结肠完成和下周计划。",
    columns: [
      { key: "contract_count", label: "合同例数", kind: "number" },
      { key: "screening_count", label: "已筛选", kind: "number" },
      { key: "current_enrolled_count", label: "当前入组", kind: "number" },
      { key: "positive_enrolled_count", label: "阳性入组", kind: "number" },
      { key: "identified_polyp_count", label: "识别息肉", kind: "number" },
      { key: "unidentified_polyp_count", label: "未识别息肉", kind: "number" },
      { key: "whole_colon_completed_count", label: "全结肠完成", kind: "number" },
      { key: "whole_colon_incomplete_count", label: "未全结肠完成", kind: "number" },
      { key: "sigmoid_unidentified_count", label: "未识别乙状结肠", kind: "number" },
      { key: "next_week_plan_count", label: "下周计划", kind: "number" },
      { key: "eligible_count", label: "符合入组", kind: "number" },
      { key: "enrollment_arrangement", label: "入组安排", kind: "textarea" },
      { key: "notes", label: "备注", kind: "textarea" },
    ],
  },
  {
    kind: "subject-overviews",
    label: "整体情况表",
    description: "维护受试者筛选号、知情和吞服时间、器械序列号、图像视频信息。",
    columns: [
      { key: "screening_no", label: "筛选号", required: true },
      { key: "informed_at", label: "知情时间", kind: "datetime" },
      { key: "swallow_time", label: "吞服时间", kind: "datetime" },
      { key: "swallow_time_2", label: "吞服时间2", kind: "datetime" },
      { key: "gastric_transit_time", label: "胃转运时间" },
      { key: "colon_entry_duration", label: "进入结肠时长" },
      { key: "capsule_batch_no", label: "胶囊批次号" },
      { key: "capsule_serial_no", label: "胶囊序列号" },
      { key: "recorder_batch_no", label: "记录仪批次号" },
      { key: "recorder_serial_no", label: "记录仪序列号" },
      { key: "image_count", label: "图像数量", kind: "number" },
      { key: "video_duration", label: "视频时长" },
      { key: "colon_work_duration", label: "结肠工作时间" },
      { key: "condition_description", label: "情况描述", kind: "textarea" },
      { key: "capsule_excreted_at", label: "胶囊排出时间", kind: "datetime" },
    ],
  },
  {
    kind: "device-handovers",
    label: "器械交接记录表",
    description: "维护器械交接、归还、批次号、序列号和交接状态。",
    columns: [
      { key: "device_name", label: "器械名称", required: true },
      { key: "batch_no", label: "批次号" },
      { key: "device_serial_no", label: "序列号", required: true },
      { key: "handed_over_at", label: "交接日期", kind: "date" },
      { key: "returned_at", label: "归还日期", kind: "date" },
      { key: "handover_status", label: "交接状态", kind: "select", options: statusOptions },
      { key: "handover_person", label: "交接人" },
      { key: "receiver", label: "接收人" },
      { key: "notes", label: "备注", kind: "textarea" },
    ],
  },
  {
    kind: "subject-results",
    label: "受试者结果统计表",
    description: "维护阅片号、筛选号、全结肠完成判断、息肉统计和匹配结果。",
    columns: [
      { key: "reading_no", label: "阅片号" },
      { key: "screening_no", label: "筛选号", required: true },
      { key: "enrollment_no", label: "入组号" },
      { key: "whole_colon_completed", label: "全结肠完成", kind: "select", options: yesNoOptions },
      { key: "is_positive", label: "是否阳性", kind: "select", options: yesNoOptions },
      { key: "max_polyp_size", label: "最大息肉大小" },
      { key: "capsule_polyp_count", label: "胶囊息肉数", kind: "number" },
      { key: "colonoscopy_polyp_count", label: "肠镜息肉数", kind: "number" },
      { key: "matched_polyp_count", label: "匹配息肉数", kind: "number" },
      { key: "is_fully_matched", label: "完全匹配", kind: "select", options: yesNoOptions },
      { key: "max_polyp_matched", label: "匹配最大息肉", kind: "select", options: yesNoOptions },
      { key: "other_diagnosis", label: "其他疾病诊断", kind: "textarea" },
      { key: "result_notes", label: "结果备注", kind: "textarea" },
    ],
  },
  {
    kind: "clinical-events",
    label: "临床事件记录",
    description: "维护临床事件、发生时间、类型、严重程度和处理状态。",
    columns: [
      { key: "event_name", label: "事件", required: true },
      { key: "occurred_at", label: "发生时间", kind: "datetime" },
      { key: "event_type", label: "事件类型" },
      { key: "severity", label: "严重程度" },
      { key: "status", label: "状态", kind: "select", options: statusOptions },
      { key: "notes", label: "备注", kind: "textarea" },
    ],
  },
  {
    kind: "device-issues",
    label: "器械问题记录表",
    description: "维护器械问题时间、问题描述、解决状态、问题类型和中心机构。",
    columns: [
      { key: "problem_time", label: "问题时间", kind: "datetime" },
      { key: "problem_description", label: "问题描述", required: true, kind: "textarea" },
      { key: "is_resolved", label: "是否解决", kind: "select", options: yesNoOptions },
      { key: "problem_type", label: "问题类型" },
      { key: "center_institution", label: "中心机构" },
      { key: "notes", label: "备注", kind: "textarea" },
    ],
  },
];

const importantTaskConfig: TableConfig = {
  kind: "important-tasks",
  label: "重要紧急事项完成",
  description: "维护事项、负责人、计划完成日期、实际完成日期、状态、重要程度和紧急程度。",
  columns: [
    { key: "title", label: "事项", required: true },
    { key: "owner", label: "负责人" },
    { key: "planned_due_date", label: "计划完成日期", kind: "date" },
    { key: "actual_completed_date", label: "实际完成日期", kind: "date" },
    { key: "status", label: "状态", kind: "select", options: statusOptions },
    {
      key: "importance",
      label: "重要程度",
      kind: "select",
      options: [
        { value: "normal", label: "普通" },
        { value: "important", label: "重要" },
      ],
    },
    {
      key: "urgency",
      label: "紧急程度",
      kind: "select",
      options: [
        { value: "normal", label: "普通" },
        { value: "urgent", label: "紧急" },
      ],
    },
    { key: "notes", label: "备注", kind: "textarea" },
  ],
};

const allTableConfigs = [...TABLES, importantTaskConfig];

function centerName(centers: Center[], centerId: number | null) {
  if (!centerId) return "项目级";
  return centers.find((center) => center.id === centerId)?.name ?? `中心 ${centerId}`;
}

function formatValue(value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  return String(value).replace("T", " ").slice(0, 19);
}

function recordToForm(record: DashboardV31Record | null, columns: ColumnDef[]) {
  const next: Record<string, string> = {};
  columns.forEach((column) => {
    const value = record?.[column.key];
    next[column.key] = value === null || value === undefined ? "" : String(value).slice(0, column.kind === "datetime" ? 16 : undefined);
  });
  return next;
}

function buildPayload(
  form: Record<string, string>,
  config: TableConfig,
  projectId: number,
  centerId: number | undefined,
) {
  const payload: Record<string, unknown> = {
    project_id: projectId,
    center_id: centerId ?? null,
  };
  config.columns.forEach((column) => {
    const rawValue = form[column.key]?.trim() ?? "";
    if (rawValue === "") {
      payload[column.key] = null;
    } else if (column.kind === "number") {
      payload[column.key] = Number(rawValue);
    } else {
      payload[column.key] = rawValue;
    }
  });
  return payload;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function statusBadge(value: unknown) {
  const text = String(value ?? "");
  if (["done", "completed", "complete", "closed", "yes"].includes(text)) {
    return <Badge tone="success">{formatValue(value)}</Badge>;
  }
  if (["in_progress", "open", "not_started", "no"].includes(text)) {
    return <Badge tone="warning">{formatValue(value)}</Badge>;
  }
  return <Badge tone="neutral">{formatValue(value)}</Badge>;
}

function WorkbenchForm({
  config,
  form,
  setForm,
  onSubmit,
  onCancel,
  canWrite,
  editing,
}: {
  config: TableConfig;
  form: Record<string, string>;
  setForm: (value: Record<string, string>) => void;
  onSubmit: () => void;
  onCancel: () => void;
  canWrite: boolean;
  editing: boolean;
}) {
  if (!canWrite) return null;
  return (
    <div className="border-y border-slate-200 bg-slate-50/70 px-4 py-4">
      <div className="grid gap-3 lg:grid-cols-4">
        {config.columns.map((column) => (
          <Field key={column.key} label={`${column.label}${column.required ? " *" : ""}`}>
            {column.kind === "textarea" ? (
              <textarea
                value={form[column.key] ?? ""}
                onChange={(event) => setForm({ ...form, [column.key]: event.target.value })}
                className={inputClassName("min-h-20 py-2")}
              />
            ) : column.kind === "select" ? (
              <SelectField
                value={form[column.key] ?? ""}
                onChange={(event) => setForm({ ...form, [column.key]: event.target.value })}
              >
                <option value="">未填写</option>
                {column.options?.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </SelectField>
            ) : (
              <input
                value={form[column.key] ?? ""}
                type={column.kind === "number" ? "number" : column.kind === "date" ? "date" : column.kind === "datetime" ? "datetime-local" : "text"}
                onChange={(event) => setForm({ ...form, [column.key]: event.target.value })}
                className={inputClassName()}
              />
            )}
          </Field>
        ))}
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button onClick={onSubmit}>
          <Save className="size-4" aria-hidden="true" />
          {editing ? "保存修改" : "新增记录"}
        </Button>
        {editing && (
          <Button variant="secondary" onClick={onCancel}>
            <X className="size-4" aria-hidden="true" />
            取消编辑
          </Button>
        )}
      </div>
    </div>
  );
}

function DataTable({
  config,
  rows,
  centers,
  canWrite,
  onEdit,
  onDelete,
}: {
  config: TableConfig;
  rows: DashboardV31Record[];
  centers: Center[];
  canWrite: boolean;
  onEdit: (record: DashboardV31Record) => void;
  onDelete: (record: DashboardV31Record) => void;
}) {
  if (rows.length === 0) {
    return (
      <div className="px-4 py-10 text-center text-sm text-slate-500">
        当前筛选下暂无数据
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[1120px] text-left text-sm">
        <thead className="sticky top-0 z-10 border-b border-slate-200 bg-white text-xs text-slate-500">
          <tr>
            <th className="sticky left-0 z-20 bg-white px-3 py-2 font-medium">中心</th>
            {config.columns.map((column) => (
              <th key={column.key} className="px-3 py-2 font-medium">
                {column.label}
              </th>
            ))}
            <th className="px-3 py-2 font-medium">更新时间</th>
            {canWrite && <th className="sticky right-0 z-20 bg-white px-3 py-2 font-medium">操作</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr key={row.id} className="hover:bg-slate-50">
              <td className="sticky left-0 bg-white px-3 py-3 font-medium text-slate-900">
                {centerName(centers, row.center_id)}
              </td>
              {config.columns.map((column) => (
                <td key={column.key} className="max-w-60 px-3 py-3 text-slate-600">
                  {column.key === "status" || column.key === "is_resolved" || column.key === "handover_status"
                    ? statusBadge(row[column.key])
                    : formatValue(row[column.key])}
                </td>
              ))}
              <td className="px-3 py-3 text-slate-500">{formatValue(row.updated_at)}</td>
              {canWrite && (
                <td className="sticky right-0 bg-white px-3 py-3">
                  <div className="flex gap-1">
                    <Button variant="ghost" size="sm" onClick={() => onEdit(row)} title="编辑">
                      <Edit3 className="size-4" aria-hidden="true" />
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => onDelete(row)} title="删除">
                      <Trash2 className="size-4" aria-hidden="true" />
                    </Button>
                  </div>
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function GanttView({ rows, centers }: { rows: DashboardV31Record[]; centers: Center[] }) {
  if (rows.length === 0) return null;
  return (
    <div className="border-b border-slate-200 px-4 py-4">
      <div className="mb-3 text-sm font-medium text-slate-900">时间轴预览</div>
      <div className="space-y-2">
        {rows.slice(0, 12).map((row) => (
          <div key={row.id} className="grid gap-2 text-xs text-slate-600 md:grid-cols-[160px_1fr_96px] md:items-center">
            <span className="font-medium text-slate-800">{centerName(centers, row.center_id)}</span>
            <div className="h-3 rounded-full bg-slate-100">
              <div
                className="h-3 rounded-full bg-emerald-500"
                style={{
                  width: row.actual_date || row.status === "done" ? "100%" : row.status === "in_progress" ? "55%" : "18%",
                }}
              />
            </div>
            <span>{formatValue(row.milestone_name)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function WarningList({ warnings, centers }: { warnings: DashboardV31Warning[]; centers: Center[] }) {
  if (warnings.length === 0) {
    return <div className="px-4 py-8 text-sm text-slate-500">当前没有逾期或 7 天内临近事项</div>;
  }
  return (
    <div className="divide-y divide-slate-100">
      {warnings.map((warning) => (
        <div key={`${warning.source}-${warning.id}`} className="grid gap-2 px-4 py-3 text-sm md:grid-cols-[90px_1fr_140px_120px] md:items-center">
          <Badge tone={warning.warning_level === "overdue" ? "danger" : "warning"}>
            {warning.warning_level === "overdue" ? "预警" : "临近"}
          </Badge>
          <div>
            <div className="font-medium text-slate-900">{warning.title}</div>
            <div className="text-xs text-slate-500">{centerName(centers, warning.center_id)}</div>
          </div>
          <span className="text-slate-600">{warning.planned_date}</span>
          {statusBadge(warning.status)}
        </div>
      ))}
    </div>
  );
}

export function DashboardPage() {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canReadDashboard = hasPermission("dashboard:read");
  const canWriteDashboard = hasPermission("dashboard:write");
  const [projects, setProjects] = useState<Project[]>([]);
  const [centers, setCenters] = useState<Center[]>([]);
  const [projectId, setProjectId] = useState<number | undefined>();
  const [centerId, setCenterId] = useState<number | undefined>();
  const [overview, setOverview] = useState<DashboardV31Overview | null>(null);
  const [activeSection, setActiveSection] = useState<"experiment" | "progress">("experiment");
  const [activeKind, setActiveKind] = useState<DashboardV31Kind>("milestones");
  const [rows, setRows] = useState<DashboardV31Record[]>([]);
  const [form, setForm] = useState<Record<string, string>>({});
  const [editingRecord, setEditingRecord] = useState<DashboardV31Record | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const activeConfig = useMemo(
    () => allTableConfigs.find((config) => config.kind === activeKind) ?? TABLES[0],
    [activeKind],
  );

  const resetForm = useCallback(() => {
    setEditingRecord(null);
    setForm(recordToForm(null, activeConfig.columns));
  }, [activeConfig]);

  const refresh = useCallback(async () => {
    if (!projectId || !canReadDashboard) return;
    setLoading(true);
    setMessage(null);
    try {
      const [overviewData, records] = await Promise.all([
        dashboardApi.getV31Overview(projectId),
        dashboardApi.listV31Records(activeKind, projectId, centerId),
      ]);
      setOverview(overviewData);
      setRows(records);
    } catch {
      setRows([]);
      setOverview(null);
      setMessage("看板数据加载失败");
    } finally {
      setLoading(false);
    }
  }, [activeKind, canReadDashboard, centerId, projectId]);

  useEffect(() => {
    if (!canReadDashboard) return;
    async function loadMasterData() {
      try {
        const projectData = await masterDataApi.listProjects();
        setProjects(projectData);
        setProjectId((current) => current ?? projectData[0]?.id);
      } catch {
        setMessage("项目列表加载失败");
      }
    }
    void loadMasterData();
  }, [canReadDashboard]);

  useEffect(() => {
    if (!projectId) {
      setCenters([]);
      return;
    }
    async function loadCenters() {
      const centerData = await masterDataApi.listCenters(projectId);
      setCenters(centerData);
      setCenterId((current) => (current && centerData.some((center) => center.id === current) ? current : undefined));
    }
    void loadCenters();
  }, [projectId]);

  useEffect(() => {
    resetForm();
  }, [resetForm]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function submitForm() {
    if (!projectId) return;
    for (const column of activeConfig.columns) {
      if (column.required && !form[column.key]?.trim()) {
        setMessage(`${column.label}不能为空`);
        return;
      }
    }
    const payload = buildPayload(form, activeConfig, projectId, centerId);
    try {
      if (editingRecord) {
        await dashboardApi.updateV31Record(activeKind, editingRecord.id, payload);
      } else {
        await dashboardApi.createV31Record(activeKind, payload);
      }
      setMessage(editingRecord ? "修改已保存" : "记录已新增");
      resetForm();
      await refresh();
    } catch {
      setMessage("保存失败，请检查字段或权限");
    }
  }

  async function deleteRow(record: DashboardV31Record) {
    if (!window.confirm("确认删除这条记录？")) return;
    try {
      await dashboardApi.deleteV31Record(activeKind, record.id);
      setMessage("记录已删除");
      await refresh();
    } catch {
      setMessage("删除失败，请检查权限");
    }
  }

  async function downloadTemplate() {
    const blob = await dashboardApi.downloadV31Template(activeKind);
    downloadBlob(blob, `dashboard-v31-${activeKind}-template.xlsx`);
  }

  async function exportRecords() {
    if (!projectId) return;
    const blob = await dashboardApi.exportV31Records(activeKind, projectId, centerId);
    downloadBlob(blob, `dashboard-v31-${activeKind}.xlsx`);
  }

  async function importRecords(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || !projectId) return;
    try {
      const result = await dashboardApi.importV31Records(activeKind, projectId, file);
      if (result.errors.length > 0) {
        setMessage(`导入失败：第 ${result.errors[0].row} 行 ${result.errors[0].field} ${result.errors[0].message}`);
      } else {
        setMessage(`导入完成：新增 ${result.created_count}，更新 ${result.updated_count}`);
        await refresh();
      }
    } catch {
      setMessage("导入失败，请确认文件来自当前模板");
    }
  }

  function editRow(record: DashboardV31Record) {
    setEditingRecord(record);
    setForm(recordToForm(record, activeConfig.columns));
  }

  if (!canReadDashboard) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold tracking-normal text-slate-950">数据看板</h1>
        <Card>
          <CardContent className="flex items-center gap-3 py-8 text-sm text-slate-600">
            <AlertTriangle className="size-5 text-slate-400" aria-hidden="true" />
            当前账号没有看板权限
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 border-b border-slate-200 pb-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">数据看板工作台</h1>
          <p className="mt-1 text-sm text-slate-500">V3.1.0 临床项目进度、入组、结果、事件与风险维护</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <SelectField value={projectId ?? ""} onChange={(event) => setProjectId(Number(event.target.value) || undefined)} className="h-10 w-56">
            <option value="">选择项目</option>
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </SelectField>
          <SelectField value={centerId ?? ""} onChange={(event) => setCenterId(Number(event.target.value) || undefined)} className="h-10 w-48">
            <option value="">全部中心/项目级</option>
            {centers.map((center) => (
              <option key={center.id} value={center.id}>
                {center.name}
              </option>
            ))}
          </SelectField>
          <Button variant="secondary" onClick={() => void refresh()} disabled={loading || !projectId}>
            <RefreshCcw className="size-4" aria-hidden="true" />
            刷新
          </Button>
          <Button variant="secondary" onClick={() => void downloadTemplate()} disabled={!projectId}>
            <FileSpreadsheet className="size-4" aria-hidden="true" />
            模板
          </Button>
          <Button variant="secondary" onClick={() => fileInputRef.current?.click()} disabled={!projectId || !canWriteDashboard}>
            <Upload className="size-4" aria-hidden="true" />
            导入
          </Button>
          <Button variant="secondary" onClick={() => void exportRecords()} disabled={!projectId}>
            <Download className="size-4" aria-hidden="true" />
            导出
          </Button>
          <input ref={fileInputRef} type="file" accept=".xlsx" className="hidden" onChange={(event) => void importRecords(event)} />
        </div>
      </div>

      {message && <Badge tone={message.includes("失败") ? "danger" : "neutral"}>{message}</Badge>}

      <div className="grid gap-3 md:grid-cols-4">
        <div className="rounded-md border border-slate-200 bg-white p-3">
          <div className="text-xs text-slate-500">合同例数</div>
          <div className="mt-1 text-2xl font-semibold text-slate-950">{overview?.enrollment.contract_count ?? 0}</div>
        </div>
        <div className="rounded-md border border-slate-200 bg-white p-3">
          <div className="text-xs text-slate-500">系统受试者</div>
          <div className="mt-1 text-2xl font-semibold text-slate-950">{overview?.enrollment.subject_count ?? 0}</div>
        </div>
        <div className="rounded-md border border-slate-200 bg-white p-3">
          <div className="text-xs text-slate-500">下周计划入组</div>
          <div className="mt-1 text-2xl font-semibold text-slate-950">{overview?.enrollment.planned_next_week ?? 0}</div>
        </div>
        <div className="rounded-md border border-slate-200 bg-white p-3">
          <div className="text-xs text-slate-500">预期偏离预警</div>
          <div className="mt-1 text-2xl font-semibold text-rose-700">{overview?.deviation_warnings.length ?? 0}</div>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 border-b border-slate-200">
        <button
          type="button"
          className={`border-b-2 px-3 py-2 text-sm font-medium ${activeSection === "experiment" ? "border-slate-950 text-slate-950" : "border-transparent text-slate-500"}`}
          onClick={() => {
            setActiveSection("experiment");
            setActiveKind("milestones");
          }}
        >
          实验项目
        </button>
        <button
          type="button"
          className={`border-b-2 px-3 py-2 text-sm font-medium ${activeSection === "progress" ? "border-slate-950 text-slate-950" : "border-transparent text-slate-500"}`}
          onClick={() => {
            setActiveSection("progress");
            setActiveKind("important-tasks");
          }}
        >
          整体进度计划达成情况
        </button>
      </div>

      {activeSection === "experiment" ? (
        <div className="flex flex-wrap gap-2">
          {TABLES.map((table) => (
            <Button key={table.kind} size="sm" variant={activeKind === table.kind ? "primary" : "secondary"} onClick={() => setActiveKind(table.kind)}>
              {table.label}
            </Button>
          ))}
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <Button size="sm" variant={activeKind === "milestones" ? "primary" : "secondary"} onClick={() => setActiveKind("milestones")}>
            预期偏离预警
          </Button>
          <Button size="sm" variant={activeKind === "important-tasks" ? "primary" : "secondary"} onClick={() => setActiveKind("important-tasks")}>
            重要紧急事项完成
          </Button>
        </div>
      )}

      <section className="overflow-hidden rounded-md border border-slate-200 bg-white">
        <div className="flex flex-col gap-3 border-b border-slate-200 px-4 py-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-slate-950">{activeConfig.label}</h2>
            <p className="mt-1 text-sm text-slate-500">{activeSection === "progress" && activeKind === "milestones" ? "按计划日期自动判断：早于今天且未完成为预警，7 天内到期且未完成为临近。" : activeConfig.description}</p>
          </div>
          {canWriteDashboard && (
            <Button variant="secondary" onClick={resetForm}>
              <Plus className="size-4" aria-hidden="true" />
              新增
            </Button>
          )}
        </div>

        {activeSection === "progress" && activeKind === "milestones" ? (
          <WarningList warnings={overview?.deviation_warnings ?? []} centers={centers} />
        ) : (
          <>
            {activeKind === "milestones" && <GanttView rows={rows} centers={centers} />}
            <WorkbenchForm
              config={activeConfig}
              form={form}
              setForm={setForm}
              onSubmit={() => void submitForm()}
              onCancel={resetForm}
              canWrite={canWriteDashboard}
              editing={Boolean(editingRecord)}
            />
            <DataTable
              config={activeConfig}
              rows={rows}
              centers={centers}
              canWrite={canWriteDashboard}
              onEdit={editRow}
              onDelete={(record) => void deleteRow(record)}
            />
          </>
        )}
      </section>

      {loading && <p className="text-sm text-slate-500">正在加载</p>}
    </div>
  );
}
