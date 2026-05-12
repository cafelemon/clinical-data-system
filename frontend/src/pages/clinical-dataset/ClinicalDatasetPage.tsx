import { Database, Eye, FileText, Pencil, Plus, RotateCcw, Save, Trash2, Users } from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { FileActions } from "@/components/files/FileActions";
import { BatchApproveButton } from "@/components/reviews/BatchApproveButton";
import { ReviewActions } from "@/components/reviews/ReviewActions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, SelectField } from "@/components/ui/form";
import { inputClassName } from "@/lib/form-styles";
import { cn } from "@/lib/utils";
import { clinicalDataApi } from "@/services/clinical-data";
import { masterDataApi } from "@/services/master-data";
import { useAuthStore } from "@/stores/auth-store";
import type {
  ClinicalDataset,
  CompletenessSummary,
  StageFile,
  StageFileGroup,
  Subject,
  SubjectArm,
} from "@/types/clinical-data";
import type { Center, Project, Stage } from "@/types/master-data";

const uploadStatusLabels: Record<string, string> = {
  not_uploaded: "未上传",
  uploaded: "已上传",
  supplement_required: "待补充",
  replaced: "已替换",
};

const reviewStatusLabels: Record<string, string> = {
  unreviewed: "未审核",
  pending: "待审核",
  approved: "已通过",
  rejected: "已驳回",
};

const dataStatusLabels: Record<string, string> = {
  incomplete: "资料不全",
  checking: "核查中",
  complete: "资料齐全",
};

const subjectArmLabels: Record<SubjectArm, string> = {
  experimental: "实验组",
  control: "对照组",
};

type SubjectForm = {
  screening_no: string;
  subject_arm: "" | SubjectArm;
  gender: string;
  age: string;
  informed_at: string;
};

const defaultSubjectForm: SubjectForm = {
  screening_no: "",
  subject_arm: "",
  gender: "",
  age: "",
  informed_at: "",
};

const stageConfigs = [
  {
    code: "STARTUP",
    label: "启动阶段",
    title: "启动阶段 - 合作文件",
    description: "管理与中心的合作文件，包括申请表、试验方案、研究手册等",
  },
  {
    code: "TRIAL",
    label: "试验进行阶段",
    title: "试验进行阶段 - 受试者列表",
    description: "跟踪受试者资料完整性",
  },
  {
    code: "CLOSEOUT",
    label: "总结阶段",
    title: "总结阶段 - 归档文件",
    description: "管理总结报告、关闭资料和项目归档文件",
  },
] as const;

type StageCode = (typeof stageConfigs)[number]["code"];

function normalizeStageCode(value: string | null): StageCode {
  return stageConfigs.some((stage) => stage.code === value) ? (value as StageCode) : "STARTUP";
}

function buildDatasetSearchParams(projectId?: number, centerId?: number, stage: StageCode = "STARTUP") {
  const params = new URLSearchParams();
  if (projectId) params.set("project_id", String(projectId));
  if (centerId) params.set("center_id", String(centerId));
  params.set("stage", stage);
  return params;
}

function statusTone(status: string) {
  if (status === "approved" || status === "complete" || status === "uploaded") return "success";
  if (status === "rejected" || status === "incomplete" || status === "supplement_required") return "danger";
  if (status === "checking" || status === "pending" || status === "unreviewed" || status === "replaced") {
    return "warning";
  }
  return "neutral";
}

function statusLabel(labels: Record<string, string>, status: string) {
  return labels[status] ?? status;
}

function pad2(value: number) {
  return String(value).padStart(2, "0");
}

function formatDateTimeMinute(value: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 16).replace("T", " ");
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())} ${pad2(
    date.getHours(),
  )}:${pad2(date.getMinutes())}`;
}

function toDateTimeLocalValue(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 16);
  const localDate = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return localDate.toISOString().slice(0, 16);
}

function fileCompletenessStatus(file: StageFile) {
  if (file.upload_status === "supplement_required" || file.review_status === "rejected") {
    return "incomplete";
  }
  if ((file.upload_status === "uploaded" || file.upload_status === "replaced") && file.review_status === "approved") {
    return "complete";
  }
  if (file.upload_status === "uploaded" || file.upload_status === "replaced") {
    return "checking";
  }
  return "incomplete";
}

function StageFileTable({
  files,
  canReadFiles,
  canWriteFiles,
  canDeleteFiles,
  canSubmitReview,
  canReview,
  canReadReviews,
  onChanged,
}: {
  files: StageFile[];
  canReadFiles: boolean;
  canWriteFiles: boolean;
  canDeleteFiles: boolean;
  canSubmitReview: boolean;
  canReview: boolean;
  canReadReviews: boolean;
  onChanged: () => void;
}) {
  if (files.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
        暂无阶段资料
      </div>
    );
  }
  const batchTargets = files.map((file) => ({
    target_type: "stage_file" as const,
    target_id: file.id,
  }));
  return (
    <div className="space-y-3">
      {canReview && (
        <BatchApproveButton
          targets={batchTargets}
          label="一键审批当前列表"
          confirmText={`确认一键审批当前列表 ${batchTargets.length} 项？已上传未提交的资料会自动提交并通过。`}
          onChanged={onChanged}
        />
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1120px] text-left text-sm">
          <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
            <tr>
              <th className="px-3 py-2 font-medium">资料名称</th>
              <th className="px-3 py-2 font-medium">资料类型</th>
              <th className="px-3 py-2 font-medium">上传人</th>
              <th className="px-3 py-2 font-medium">上传时间</th>
              <th className="px-3 py-2 font-medium">审核人</th>
              <th className="px-3 py-2 font-medium">审核时间</th>
              <th className="px-3 py-2 font-medium">上传状态</th>
              <th className="px-3 py-2 font-medium">审核状态</th>
              <th className="px-3 py-2 font-medium">完整性</th>
              <th className="px-3 py-2 font-medium">文件</th>
              <th className="px-3 py-2 font-medium">审核</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {files.map((file) => (
              <tr key={file.id}>
                <td className="px-3 py-3 font-medium text-slate-900">{file.file_name}</td>
                <td className="px-3 py-3 text-slate-600">{file.file_type || "-"}</td>
                <td className="px-3 py-3 text-slate-600">{file.uploaded_by_name || "-"}</td>
                <td className="px-3 py-3 text-slate-500">
                  {file.uploaded_at ? new Date(file.uploaded_at).toLocaleDateString() : "-"}
                </td>
                <td className="px-3 py-3 text-slate-600">{file.reviewer_name || "-"}</td>
                <td className="px-3 py-3 text-slate-500">
                  {file.reviewed_at ? new Date(file.reviewed_at).toLocaleDateString() : "-"}
                </td>
                <td className="px-3 py-3">
                  <Badge tone={statusTone(file.upload_status)}>
                    {statusLabel(uploadStatusLabels, file.upload_status)}
                  </Badge>
                </td>
                <td className="px-3 py-3">
                  <Badge tone={statusTone(file.review_status)}>
                    {statusLabel(reviewStatusLabels, file.review_status)}
                  </Badge>
                </td>
                <td className="px-3 py-3">
                  <Badge tone={statusTone(fileCompletenessStatus(file))}>
                    {statusLabel(
                      dataStatusLabels,
                      file.completeness_status ?? fileCompletenessStatus(file),
                    )}
                  </Badge>
                </td>
                <td className="px-3 py-3">
                  <FileActions
                    stageFileId={file.id}
                    defaultCategory="clinical_document"
                    canRead={canReadFiles}
                    canWrite={canWriteFiles}
                    canDelete={canDeleteFiles}
                    onChanged={onChanged}
                  />
                </td>
                <td className="px-3 py-3">
                  <ReviewActions
                    targetType="stage_file"
                    targetId={file.id}
                    uploadStatus={file.upload_status}
                    reviewStatus={file.review_status}
                    canSubmit={canSubmitReview}
                    canReview={canReview}
                    canReadRecords={canReadReviews}
                    onChanged={onChanged}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function SubjectTable({
  subjects,
  onEdit,
  onDelete,
  canWrite,
  canDelete,
}: {
  subjects: Subject[];
  onEdit: (subject: Subject) => void;
  onDelete: (subject: Subject) => void;
  canWrite: boolean;
  canDelete: boolean;
}) {
  if (subjects.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
        暂无受试者
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[1380px] text-left text-sm">
        <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-3 py-2 font-medium">筛选号</th>
            <th className="px-3 py-2 font-medium">分组</th>
            <th className="px-3 py-2 font-medium">性别</th>
            <th className="px-3 py-2 font-medium">年龄</th>
            <th className="px-3 py-2 font-medium">知情时间</th>
            <th className="px-3 py-2 font-medium">访视1日期</th>
            <th className="px-3 py-2 font-medium">访视2日期</th>
            <th className="px-3 py-2 font-medium">访视3日期</th>
            <th className="px-3 py-2 font-medium">访视4日期</th>
            <th className="px-3 py-2 font-medium">访视5日期</th>
            <th className="px-3 py-2 font-medium">资料状态</th>
            <th className="px-3 py-2 font-medium">审核状态</th>
            <th className="px-3 py-2 font-medium">操作</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {subjects.map((subject) => (
            <tr key={subject.id}>
              <td className="px-3 py-3 font-medium text-slate-900">{subject.screening_no}</td>
              <td className="px-3 py-3 text-slate-600">
                {subject.subject_arm ? subjectArmLabels[subject.subject_arm] : "未分组"}
              </td>
              <td className="px-3 py-3 text-slate-600">{subject.gender || "-"}</td>
              <td className="px-3 py-3 text-slate-600">{subject.age ?? "-"}</td>
              <td className="px-3 py-3 text-slate-600">{formatDateTimeMinute(subject.informed_at)}</td>
              <td className="px-3 py-3 text-slate-600">{subject.visit1_date || "-"}</td>
              <td className="px-3 py-3 text-slate-600">{subject.visit2_date || "-"}</td>
              <td className="px-3 py-3 text-slate-600">{subject.visit3_date || "-"}</td>
              <td className="px-3 py-3 text-slate-600">{subject.visit4_date || "-"}</td>
              <td className="px-3 py-3 text-slate-600">{subject.visit5_date || "-"}</td>
              <td className="px-3 py-3">
                <Badge tone={statusTone(subject.data_status)}>
                  {statusLabel(dataStatusLabels, subject.data_status)}
                </Badge>
              </td>
              <td className="px-3 py-3">
                <Badge tone={statusTone(subject.review_status)}>
                  {statusLabel(reviewStatusLabels, subject.review_status)}
                </Badge>
              </td>
              <td className="px-3 py-3">
                <div className="flex flex-wrap gap-2">
                  <Button asChild size="sm" variant="secondary">
                    <Link to={`/clinical-dataset/subjects/${subject.id}`}>
                      <Eye className="size-4" aria-hidden="true" />
                      详情
                    </Link>
                  </Button>
                  {canWrite && (
                    <Button size="sm" variant="ghost" onClick={() => onEdit(subject)}>
                      <Pencil className="size-4" aria-hidden="true" />
                      编辑
                    </Button>
                  )}
                  {canDelete && (
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-red-600 hover:bg-red-50"
                      onClick={() => onDelete(subject)}
                    >
                      <Trash2 className="size-4" aria-hidden="true" />
                      删除
                    </Button>
                  )}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CountRow({ label, counts }: { label: string; counts: CompletenessSummary["subjects"] }) {
  return (
    <div className="grid grid-cols-[1fr_auto_auto_auto] items-center gap-2 text-sm">
      <span className="text-slate-600">{label}</span>
      <Badge tone="success">齐全 {counts.complete}</Badge>
      <Badge tone="warning">核查 {counts.checking}</Badge>
      <Badge tone="danger">不全 {counts.incomplete}</Badge>
    </div>
  );
}

function CompletenessOverview({
  summary,
  canRecalculate,
  onRecalculate,
}: {
  summary: CompletenessSummary | null;
  canRecalculate: boolean;
  onRecalculate: () => void;
}) {
  if (!summary) {
    return <p className="text-sm text-slate-500">选择项目和中心后显示完整性</p>;
  }
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <Badge tone={statusTone(summary.status)}>
          {statusLabel(dataStatusLabels, summary.status)}
        </Badge>
        {canRecalculate && (
          <Button size="sm" variant="secondary" onClick={onRecalculate}>
            <RotateCcw className="size-4" aria-hidden="true" />
            重算
          </Button>
        )}
      </div>
      <div className="space-y-2">
        <CountRow label="阶段资料" counts={summary.stage_files} />
        <CountRow label="受试者" counts={summary.subjects} />
      </div>
      {summary.stages.length > 0 && (
        <div className="space-y-2 border-t border-slate-100 pt-3">
          <p className="text-xs font-medium text-slate-500">阶段资料分布</p>
          {summary.stages.map((stage) => (
            <div key={stage.stage_id} className="flex items-center justify-between gap-3 text-sm">
              <span className="min-w-0 truncate text-slate-600">{stage.stage_name}</span>
              <Badge tone={statusTone(stage.status)}>
                {stage.complete_count}/{stage.required_count}
              </Badge>
            </div>
          ))}
        </div>
      )}
      {summary.centers.length > 0 && (
        <div className="space-y-2 border-t border-slate-100 pt-3">
          <p className="text-xs font-medium text-slate-500">中心状态</p>
          {summary.centers.map((center) => (
            <div key={center.center_id} className="flex items-center justify-between gap-3 text-sm">
              <span className="min-w-0 truncate text-slate-600">{center.center_name}</span>
              <Badge tone={statusTone(center.status)}>
                {statusLabel(dataStatusLabels, center.status)}
              </Badge>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function stageFilesForCode(dataset: ClinicalDataset | null, code: StageCode) {
  if (!dataset) return [];
  if (code === "STARTUP") return dataset.startup_files;
  if (code === "TRIAL") return [];
  return dataset.closeout_files;
}

function stageFileGroupsForCode(dataset: ClinicalDataset | null, code: StageCode) {
  if (!dataset) return [];
  if (code === "STARTUP") return dataset.startup_file_groups;
  if (code === "CLOSEOUT") return dataset.closeout_file_groups;
  return [];
}

function SecondaryStageFiles({
  groups,
  activeGroupId,
  onGroupChange,
  canReadFiles,
  canWriteFiles,
  canDeleteFiles,
  canSubmitReview,
  canReview,
  canReadReviews,
  onChanged,
}: {
  groups: StageFileGroup[];
  activeGroupId: number | null;
  onGroupChange: (stageId: number) => void;
  canReadFiles: boolean;
  canWriteFiles: boolean;
  canDeleteFiles: boolean;
  canSubmitReview: boolean;
  canReview: boolean;
  canReadReviews: boolean;
  onChanged: () => void;
}) {
  if (groups.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
        暂无二级阶段资料
      </div>
    );
  }
  const activeGroup =
    groups.find((group) => group.stage.id === activeGroupId) ?? groups[0];
  return (
    <div className="grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
      <div className="space-y-2">
        {groups.map((group) => {
          const isActive = activeGroup.stage.id === group.stage.id;
          return (
            <button
              key={group.stage.id}
              type="button"
              className={cn(
                "flex w-full items-center justify-between gap-2 rounded-md border border-slate-200 px-3 py-2 text-left text-sm text-slate-600 transition hover:border-emerald-200 hover:bg-emerald-50",
                isActive && "border-emerald-600 bg-emerald-50 text-emerald-800",
              )}
              onClick={() => onGroupChange(group.stage.id)}
            >
              <span className="min-w-0 truncate">{group.stage.name}</span>
              <Badge tone={isActive ? "success" : "neutral"}>{group.files.length}</Badge>
            </button>
          );
        })}
      </div>
      <StageFileTable
        files={activeGroup.files}
        canReadFiles={canReadFiles}
        canWriteFiles={canWriteFiles}
        canDeleteFiles={canDeleteFiles}
        canSubmitReview={canSubmitReview}
        canReview={canReview}
        canReadReviews={canReadReviews}
        onChanged={onChanged}
      />
    </div>
  );
}

function StageNavigation({
  activeStage,
  stages,
  dataset,
  onChange,
}: {
  activeStage: StageCode;
  stages: Stage[];
  dataset: ClinicalDataset | null;
  onChange: (stage: StageCode) => void;
}) {
  const stageByCode = new Map(stages.map((stage) => [stage.code, stage]));

  return (
    <div className="space-y-2">
      {stageConfigs.map((config) => {
        const stage = stageByCode.get(config.code);
        const isActive = activeStage === config.code;
        const count =
          config.code === "TRIAL"
            ? dataset?.subject_count ?? 0
            : stageFilesForCode(dataset, config.code).length;
        return (
          <button
            key={config.code}
            type="button"
            className={cn(
              "flex w-full items-center gap-3 rounded-md px-3 py-3 text-left text-sm font-medium text-slate-600 transition hover:bg-slate-100 hover:text-slate-950",
              isActive && "bg-emerald-600 text-white hover:bg-emerald-600 hover:text-white",
            )}
            onClick={() => onChange(config.code)}
          >
            {config.code === "TRIAL" ? (
              <Users className="size-4 shrink-0" aria-hidden="true" />
            ) : (
              <FileText className="size-4 shrink-0" aria-hidden="true" />
            )}
            <span className="min-w-0 flex-1">
              <span className="block truncate">{stage?.name ?? config.label}</span>
              <span
                className={cn(
                  "mt-0.5 block text-xs font-normal",
                  isActive ? "text-emerald-50" : "text-slate-400",
                )}
              >
                {stage ? `${count} 项` : "未配置"}
              </span>
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function ClinicalDatasetPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const currentQuery = searchParams.toString();
  const requestedProjectId = useMemo(
    () => Number(searchParams.get("project_id")) || undefined,
    [searchParams],
  );
  const requestedCenterId = useMemo(
    () => Number(searchParams.get("center_id")) || undefined,
    [searchParams],
  );
  const requestedStage = searchParams.get("stage");
  const [projects, setProjects] = useState<Project[]>([]);
  const [centers, setCenters] = useState<Center[]>([]);
  const [stages, setStages] = useState<Stage[]>([]);
  const [projectId, setProjectId] = useState<number | undefined>();
  const [centerId, setCenterId] = useState<number | undefined>();
  const [activeStage, setActiveStage] = useState<StageCode>(normalizeStageCode(requestedStage));
  const [activeSubStageId, setActiveSubStageId] = useState<number | null>(null);
  const [dataset, setDataset] = useState<ClinicalDataset | null>(null);
  const [completeness, setCompleteness] = useState<CompletenessSummary | null>(null);
  const [form, setForm] = useState<SubjectForm>(defaultSubjectForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canReadClinicalData = hasPermission("clinical_data:read");
  const canWrite = hasPermission("clinical_data:write");
  const canDeleteSubjects = hasPermission("clinical_data:delete");
  const canReadFiles = hasPermission("files:read");
  const canWriteFiles = hasPermission("files:write");
  const canDeleteFiles = hasPermission("files:delete");
  const canReadReviews = hasPermission("reviews:read");
  const canSubmitReview = hasPermission("reviews:submit");
  const canReview = hasPermission("reviews:review");
  const canReadCompleteness = hasPermission("completeness:read");
  const canRecalculateCompleteness = hasPermission("completeness:recalculate");

  const resetForm = useCallback(() => {
    setEditingId(null);
    setForm(defaultSubjectForm);
  }, []);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === projectId),
    [projectId, projects],
  );
  const selectedCenter = useMemo(
    () => centers.find((center) => center.id === centerId),
    [centerId, centers],
  );
  const displayStages = dataset?.stages ?? stages;
  const stageByCode = useMemo(
    () => new Map(displayStages.map((stage) => [stage.code, stage])),
    [displayStages],
  );
  const activeStageModel = stageByCode.get(activeStage);
  const activeStageConfig = stageConfigs.find((stage) => stage.code === activeStage) ?? stageConfigs[0];
  const activeStageFiles = stageFilesForCode(dataset, activeStage);
  const activeFileGroups = useMemo(
    () => stageFileGroupsForCode(dataset, activeStage),
    [activeStage, dataset],
  );
  const subjectReviewCounts = useMemo(() => {
    const subjects = dataset?.subjects ?? [];
    return {
      approved: subjects.filter((subject) => subject.review_status === "approved").length,
      pending: subjects.filter((subject) => subject.review_status === "pending").length,
      unreviewed: subjects.filter((subject) => subject.review_status === "unreviewed").length,
      rejected: subjects.filter((subject) => subject.review_status === "rejected").length,
    };
  }, [dataset?.subjects]);

  const loadCompleteness = useCallback(async () => {
    if (!projectId || !centerId || !canReadCompleteness) {
      setCompleteness(null);
      return;
    }
    const summary = await clinicalDataApi.getCompletenessSummary(projectId, centerId);
    setCompleteness(summary);
  }, [canReadCompleteness, centerId, projectId]);

  const loadDataset = useCallback(async () => {
    if (!canReadClinicalData || !projectId || !centerId) {
      setDataset(null);
      setCompleteness(null);
      return;
    }
    setLoading(true);
    try {
      const [data] = await Promise.all([
        clinicalDataApi.getDataset(projectId, centerId),
        loadCompleteness(),
      ]);
      setDataset(data);
      setMessage(null);
    } catch {
      setDataset(null);
      setMessage("临床数据集加载失败");
    } finally {
      setLoading(false);
    }
  }, [canReadClinicalData, centerId, loadCompleteness, projectId]);

  useEffect(() => {
    setActiveStage(normalizeStageCode(requestedStage));
  }, [requestedStage]);

  useEffect(() => {
    if (activeStage === "TRIAL") {
      setActiveSubStageId(null);
      return;
    }
    if (activeFileGroups.length === 0) {
      setActiveSubStageId(null);
      return;
    }
    if (!activeFileGroups.some((group) => group.stage.id === activeSubStageId)) {
      setActiveSubStageId(activeFileGroups[0].stage.id);
    }
  }, [activeFileGroups, activeStage, activeSubStageId]);

  useEffect(() => {
    if (!canReadClinicalData) return;
    async function initialize() {
      const projectData = await masterDataApi.listProjects();
      setProjects(projectData);
    }
    void initialize();
  }, [canReadClinicalData]);

  useEffect(() => {
    if (!canReadClinicalData) {
      setProjectId(undefined);
      setCenterId(undefined);
      return;
    }
    if (projects.length === 0) {
      setProjectId(undefined);
      setCenterId(undefined);
      return;
    }
    const nextProjectId =
      requestedProjectId && projects.some((project) => project.id === requestedProjectId)
        ? requestedProjectId
        : projects[0].id;
    if (projectId !== nextProjectId) {
      setProjectId(nextProjectId);
      setCenterId(undefined);
      setDataset(null);
      resetForm();
    }
  }, [canReadClinicalData, projectId, projects, requestedProjectId, resetForm]);

  useEffect(() => {
    resetForm();
    setDataset(null);
  }, [projectId, resetForm]);

  useEffect(() => {
    async function loadScope() {
      if (!canReadClinicalData || !projectId) {
        setCenters([]);
        setStages([]);
        setCenterId(undefined);
        return;
      }
      const requestedProjectExists = projects.some((project) => project.id === requestedProjectId);
      if (requestedProjectId && requestedProjectExists && projectId !== requestedProjectId) {
        return;
      }
      const [centerData, stageData] = await Promise.all([
        masterDataApi.listCenters(projectId),
        masterDataApi.listStages(projectId),
      ]);
      setCenters(centerData);
      setStages(stageData);
      const nextCenterId =
        requestedCenterId && centerData.some((center) => center.id === requestedCenterId)
          ? requestedCenterId
          : centerData[0]?.id;
      setCenterId((current) => (current === nextCenterId ? current : nextCenterId));
      const nextParams = buildDatasetSearchParams(projectId, nextCenterId, activeStage);
      if (nextParams.toString() !== currentQuery) {
        setSearchParams(nextParams, { replace: true });
      }
    }
    void loadScope();
  }, [
    activeStage,
    canReadClinicalData,
    currentQuery,
    projectId,
    projects,
    requestedCenterId,
    requestedProjectId,
    setSearchParams,
  ]);

  useEffect(() => {
    void loadDataset();
  }, [loadDataset]);

  function handleProjectChange(value: string) {
    const nextProjectId = value ? Number(value) : undefined;
    setProjectId(nextProjectId);
    setCenterId(undefined);
    setDataset(null);
    resetForm();
    const nextParams = buildDatasetSearchParams(nextProjectId, undefined, activeStage);
    if (nextParams.toString() !== currentQuery) {
      setSearchParams(nextParams, { replace: true });
    }
  }

  function handleCenterChange(value: string) {
    const nextCenterId = Number(value) || undefined;
    setCenterId(nextCenterId);
    setDataset(null);
    const nextParams = buildDatasetSearchParams(projectId, nextCenterId, activeStage);
    if (nextParams.toString() !== currentQuery) {
      setSearchParams(nextParams, { replace: true });
    }
  }

  function handleStageChange(stage: StageCode) {
    setActiveStage(stage);
    const nextParams = buildDatasetSearchParams(projectId, centerId, stage);
    if (nextParams.toString() !== currentQuery) {
      setSearchParams(nextParams, { replace: true });
    }
  }

  function handleEdit(subject: Subject) {
    setEditingId(subject.id);
    setForm({
      screening_no: subject.screening_no,
      subject_arm: subject.subject_arm ?? "",
      gender: subject.gender ?? "",
      age: subject.age === null ? "" : String(subject.age),
      informed_at: toDateTimeLocalValue(subject.informed_at),
    });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId || !centerId) {
      setMessage("请先选择项目和中心");
      return;
    }
    if (!editingId && !form.subject_arm) {
      setMessage("新建受试者必须选择分组");
      return;
    }
    const payload = {
      project_id: projectId,
      center_id: centerId,
      screening_no: form.screening_no.trim(),
      ...(form.subject_arm ? { subject_arm: form.subject_arm } : {}),
      gender: form.gender || null,
      age: form.age ? Number(form.age) : null,
      informed_at: form.informed_at || null,
    };
    try {
      if (editingId) {
        await clinicalDataApi.updateSubject(editingId, payload);
        setMessage("受试者已更新");
      } else {
        await clinicalDataApi.createSubject({
          ...payload,
          subject_arm: form.subject_arm as SubjectArm,
        });
        setMessage("受试者已创建");
      }
      resetForm();
      await loadDataset();
    } catch {
      setMessage("保存失败，请检查筛选号是否重复或权限范围");
    }
  }

  async function handleDelete(subject: Subject) {
    if (!window.confirm(`确认删除受试者 ${subject.screening_no}？`)) return;
    try {
      await clinicalDataApi.deleteSubject(subject.id);
      if (editingId === subject.id) resetForm();
      await loadDataset();
      setMessage("受试者已删除");
    } catch {
      setMessage("删除失败，仅管理员可删除受试者");
    }
  }

  async function handleRecalculateCompleteness() {
    if (!projectId || !centerId) return;
    try {
      const summary = await clinicalDataApi.recalculateCompleteness({
        project_id: projectId,
        center_id: centerId,
      });
      setCompleteness(summary);
      await loadDataset();
      setMessage("完整性已重算");
    } catch {
      setMessage("完整性重算失败");
    }
  }

  if (!canReadClinicalData) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">临床数据集</h1>
          <p className="mt-1 text-sm text-slate-500">项目中心资料与受试者链路</p>
        </div>
        <Card>
          <CardContent className="py-8 text-sm text-slate-600">
            当前账号没有临床数据集查看权限
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex items-start gap-3">
          <div className="flex size-12 shrink-0 items-center justify-center rounded-md bg-emerald-100 text-emerald-700">
            <Database className="size-6" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-normal text-slate-950">临床数据集</h1>
            <p className="mt-1 text-sm text-slate-500">
              {selectedProject?.name ?? "未选择项目"} · {selectedCenter?.name ?? "未选择中心"}
            </p>
          </div>
        </div>
        <div className="grid gap-3 sm:grid-cols-[minmax(180px,260px)_minmax(180px,260px)_auto] sm:items-end">
          <Field label="项目">
            <SelectField
              value={projectId ?? ""}
              onChange={(event) => handleProjectChange(event.target.value)}
            >
              <option value="">选择项目</option>
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </SelectField>
          </Field>
          <Field label="中心">
            <SelectField
              value={centerId ?? ""}
              onChange={(event) => handleCenterChange(event.target.value)}
            >
              <option value="">选择中心</option>
              {centers.map((center) => (
                <option key={center.id} value={center.id}>
                  {center.name}
                </option>
              ))}
            </SelectField>
          </Field>
          <Button variant="secondary" onClick={() => void loadDataset()}>
            <RotateCcw className="size-4" aria-hidden="true" />
            刷新
          </Button>
        </div>
      </div>

      {message && (
        <Badge tone={message.includes("失败") || message.includes("选择") ? "danger" : "success"}>
          {message}
        </Badge>
      )}

      <section className="grid gap-4 xl:grid-cols-[280px_minmax(0,1fr)]">
        <aside className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>阶段导航</CardTitle>
            </CardHeader>
            <CardContent>
              <StageNavigation
                activeStage={activeStage}
                stages={displayStages}
                dataset={dataset}
                onChange={handleStageChange}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>完整性概览</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="mb-4 grid grid-cols-2 gap-3">
                <div className="rounded-md border border-slate-200 p-3">
                  <p className="text-xs text-slate-500">阶段资料</p>
                  <p className="mt-1 text-2xl font-semibold">{dataset?.stage_file_count ?? 0}</p>
                </div>
                <div className="rounded-md border border-slate-200 p-3">
                  <p className="text-xs text-slate-500">受试者</p>
                  <p className="mt-1 text-2xl font-semibold">{dataset?.subject_count ?? 0}</p>
                </div>
              </div>
              {canReadCompleteness && (
                <CompletenessOverview
                  summary={completeness}
                  canRecalculate={canRecalculateCompleteness}
                  onRecalculate={() => void handleRecalculateCompleteness()}
                />
              )}
              {loading && <p className="mt-3 text-sm text-slate-500">正在加载</p>}
            </CardContent>
          </Card>
        </aside>

        <div className="min-w-0 space-y-4">
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <CardTitle>{activeStageConfig.title}</CardTitle>
                  <p className="mt-2 text-sm text-slate-500">
                    {activeStageModel?.description || activeStageConfig.description}
                  </p>
                </div>
                {activeStage === "TRIAL" ? (
                  <div className="flex flex-wrap gap-2">
                    <Badge tone="success">审核通过 {subjectReviewCounts.approved}</Badge>
                    <Badge tone="warning">待审核 {subjectReviewCounts.pending}</Badge>
                    <Badge tone="neutral">未审核 {subjectReviewCounts.unreviewed}</Badge>
                    {subjectReviewCounts.rejected > 0 && (
                      <Badge tone="danger">已驳回 {subjectReviewCounts.rejected}</Badge>
                    )}
                  </div>
                ) : (
                  <Badge tone="neutral">资料 {activeStageFiles.length}</Badge>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-6">
              {!projectId || !centerId ? (
                <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                  请先选择项目和中心
                </div>
              ) : !activeStageModel ? (
                <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                  当前项目未配置{activeStageConfig.label}
                </div>
              ) : activeStage === "TRIAL" ? (
                <>
                  <SubjectTable
                    subjects={dataset?.subjects ?? []}
                    onEdit={handleEdit}
                    onDelete={(subject) => void handleDelete(subject)}
                    canWrite={canWrite}
                    canDelete={canDeleteSubjects}
                  />

                  {canWrite && (
                    <div className="rounded-md border border-slate-200 bg-slate-50 p-4">
                      <h3 className="text-sm font-semibold text-slate-950">
                        {editingId ? "编辑受试者" : "新增受试者"}
                      </h3>
                      <form className="mt-4 grid gap-4 lg:grid-cols-5" onSubmit={handleSubmit}>
                        <Field label="筛选号">
                          <input
                            className={inputClassName()}
                            value={form.screening_no}
                            onChange={(event) =>
                              setForm((current) => ({
                                ...current,
                                screening_no: event.target.value,
                              }))
                            }
                            required
                          />
                        </Field>
                        <Field label="分组">
                          <SelectField
                            value={form.subject_arm}
                            onChange={(event) =>
                              setForm((current) => ({
                                ...current,
                                subject_arm: event.target.value as SubjectForm["subject_arm"],
                              }))
                            }
                            required={!editingId}
                          >
                            <option value="">
                              {editingId ? "未分组（保留）" : "请选择分组"}
                            </option>
                            <option value="experimental">实验组</option>
                            <option value="control">对照组</option>
                          </SelectField>
                        </Field>
                        <Field label="性别">
                          <SelectField
                            value={form.gender}
                            onChange={(event) =>
                              setForm((current) => ({ ...current, gender: event.target.value }))
                            }
                          >
                            <option value="">未填写</option>
                            <option value="男">男</option>
                            <option value="女">女</option>
                          </SelectField>
                        </Field>
                        <Field label="年龄">
                          <input
                            className={inputClassName()}
                            type="number"
                            min={0}
                            max={130}
                            value={form.age}
                            onChange={(event) =>
                              setForm((current) => ({ ...current, age: event.target.value }))
                            }
                          />
                        </Field>
                        <Field label="知情时间">
                          <input
                            className={inputClassName()}
                            type="datetime-local"
                            value={form.informed_at}
                            onChange={(event) =>
                              setForm((current) => ({
                                ...current,
                                informed_at: event.target.value,
                              }))
                            }
                          />
                        </Field>
                        <div className="flex items-end gap-2 lg:col-span-5">
                          <Button type="submit" disabled={!projectId || !centerId}>
                            {editingId ? (
                              <Save className="size-4" aria-hidden="true" />
                            ) : (
                              <Plus className="size-4" aria-hidden="true" />
                            )}
                            保存
                          </Button>
                          {editingId && (
                            <Button type="button" variant="ghost" onClick={resetForm}>
                              取消
                            </Button>
                          )}
                        </div>
                      </form>
                    </div>
                  )}
                </>
              ) : (
                <SecondaryStageFiles
                  groups={activeFileGroups}
                  activeGroupId={activeSubStageId}
                  onGroupChange={setActiveSubStageId}
                  canReadFiles={canReadFiles}
                  canWriteFiles={canWriteFiles}
                  canDeleteFiles={canDeleteFiles}
                  canSubmitReview={canSubmitReview}
                  canReview={canReview}
                  canReadReviews={canReadReviews}
                  onChanged={() => void loadDataset()}
                />
              )}
            </CardContent>
          </Card>
        </div>
      </section>
    </div>
  );
}
