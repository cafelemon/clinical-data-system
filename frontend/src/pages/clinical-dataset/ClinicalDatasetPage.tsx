import {
  ClipboardList,
  Database,
  Eye,
  FileText,
  Pencil,
  Plus,
  RotateCcw,
  Save,
  Trash2,
  Users,
} from "lucide-react";
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
  ClinicalSsuProgress,
  ClinicalSsuProgressPayload,
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

const ssuStatusLabels: Record<string, string> = {
  not_started: "未开始",
  in_progress: "进行中",
  submitted: "已提交",
  approved: "已批准",
  completed: "已完成",
  blocked: "受阻",
};

const subjectArmLabels: Record<SubjectArm, string> = {
  experimental: "实验组",
  control: "对照组",
};

const ssuStageMeta = [
  {
    code: "SSU_PROJECT_APPROVAL",
    label: "立项",
    fileTypes: [
      "STARTUP_001_APPLICATION",
      "STARTUP_002_PROTOCOL",
      "STARTUP_003_INVESTIGATOR_BROCHURE",
      "STARTUP_008_PRECLINICAL_MATERIALS",
      "STARTUP_010_QMS_DECLARATION",
    ],
  },
  {
    code: "SSU_ETHICS",
    label: "伦理",
    fileTypes: [
      "STARTUP_004_ICF_TEXT",
      "STARTUP_005_RECRUITMENT_DOCUMENTS",
      "STARTUP_006_CRF_TEXT",
      "STARTUP_011_SUBJECT_INSURANCE",
      "STARTUP_012_ETHICS_OPINION",
      "STARTUP_013_ETHICS_MEMBER_LIST",
    ],
  },
  {
    code: "SSU_AGREEMENT_SIGNING",
    label: "协议签署",
    fileTypes: [
      "STARTUP_009_INVESTIGATOR_QUALIFICATION",
      "STARTUP_014_CONTRACT",
      "STARTUP_018_SIGNATURE_AUTHORIZATION",
    ],
  },
  {
    code: "SSU_PROVINCIAL_FILING",
    label: "省局备案",
    fileTypes: [
      "STARTUP_007_PRODUCT_TEST_REPORT",
      "STARTUP_015_TRIAL_APPROVAL",
      "STARTUP_016_REGULATORY_FILING",
    ],
  },
  {
    code: "SSU_STARTUP_MEETING",
    label: "启动会",
    fileTypes: [
      "STARTUP_017_STARTUP_TRAINING",
      "STARTUP_019_LAB_NORMAL_RANGE",
      "STARTUP_020_LAB_QC_CERTIFICATE",
      "STARTUP_021_DEVICE_LABEL_TEXT",
      "STARTUP_022_DEVICE_HANDOVER",
      "STARTUP_023_UNBLINDING_PROCEDURE",
      "STARTUP_024_RANDOMIZATION_LIST",
      "STARTUP_025_MONITORING_PLAN",
      "STARTUP_026_STARTUP_MONITORING_REPORT",
    ],
  },
] as const;

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
    label: "试验准备阶段",
    title: "试验准备阶段",
    description: "中心级资料准备和 SSU 进展维护",
  },
  {
    code: "TRIAL",
    label: "试验进行阶段",
    title: "试验进行阶段 - 受试者列表",
    description: "跟踪受试者资料完整性",
  },
  {
    code: "CLOSEOUT",
    label: "试验结束阶段",
    title: "试验结束阶段",
    description: "中心级结束资料准备和归档",
  },
] as const;

type StageCode = (typeof stageConfigs)[number]["code"];
type StartupView = "ssu" | "materials";

function normalizeStageCode(value: string | null): StageCode {
  return stageConfigs.some((stage) => stage.code === value) ? (value as StageCode) : "STARTUP";
}

function normalizeStartupView(value: string | null): StartupView {
  return value === "materials" ? "materials" : "ssu";
}

function buildDatasetSearchParams(
  projectId?: number,
  centerId?: number,
  stage: StageCode = "STARTUP",
  startupView: StartupView = "ssu",
) {
  const params = new URLSearchParams();
  if (projectId) params.set("project_id", String(projectId));
  if (centerId) params.set("center_id", String(centerId));
  params.set("stage", stage);
  if (stage === "STARTUP") params.set("view", startupView);
  if (stage === "CLOSEOUT") params.set("view", "materials");
  return params;
}

function statusTone(status: string) {
  if (status === "approved" || status === "complete" || status === "uploaded" || status === "completed") {
    return "success";
  }
  if (
    status === "rejected" ||
    status === "incomplete" ||
    status === "supplement_required" ||
    status === "blocked"
  ) {
    return "danger";
  }
  if (
    status === "checking" ||
    status === "pending" ||
    status === "unreviewed" ||
    status === "replaced" ||
    status === "in_progress" ||
    status === "submitted"
  ) {
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
  if (!file.required && file.not_applicable) return "complete";
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
  canUpdateApplicability,
  canSubmitReview,
  canReview,
  canReadReviews,
  onChanged,
}: {
  files: StageFile[];
  canReadFiles: boolean;
  canWriteFiles: boolean;
  canDeleteFiles: boolean;
  canUpdateApplicability: boolean;
  canSubmitReview: boolean;
  canReview: boolean;
  canReadReviews: boolean;
  onChanged: () => void;
}) {
  const [applicabilityDrafts, setApplicabilityDrafts] = useState<
    Record<number, { not_applicable: boolean; reason: string }>
  >({});
  const [savingApplicabilityId, setSavingApplicabilityId] = useState<number | null>(null);

  useEffect(() => {
    setApplicabilityDrafts(
      Object.fromEntries(
        files.map((file) => [
          file.id,
          {
            not_applicable: file.not_applicable,
            reason: file.not_applicable_reason ?? "",
          },
        ]),
      ),
    );
  }, [files]);

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
        <table className="w-full min-w-[980px] text-left text-sm">
          <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
            <tr>
              <th className="w-[34%] px-3 py-2 font-medium">资料名称</th>
              <th className="px-3 py-2 font-medium">上传/审核</th>
              <th className="px-3 py-2 font-medium">上传状态</th>
              <th className="px-3 py-2 font-medium">审核状态</th>
              <th className="px-3 py-2 font-medium">完整性</th>
              <th className="px-3 py-2 font-medium">材料情况</th>
              <th className="px-3 py-2 font-medium">文件</th>
              <th className="px-3 py-2 font-medium">审核</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {files.map((file) => {
              const completenessStatus = file.completeness_status ?? fileCompletenessStatus(file);
              const draft = applicabilityDrafts[file.id] ?? {
                not_applicable: file.not_applicable,
                reason: file.not_applicable_reason ?? "",
              };
              const applicabilityChanged =
                draft.not_applicable !== file.not_applicable ||
                draft.reason !== (file.not_applicable_reason ?? "");
              const hasUploadedFile =
                file.upload_status === "uploaded" || file.upload_status === "replaced";

              async function saveApplicability() {
                setSavingApplicabilityId(file.id);
                try {
                  await clinicalDataApi.updateStageFileApplicability(file.id, {
                    not_applicable: draft.not_applicable,
                    reason: draft.reason.trim() || null,
                  });
                  onChanged();
                } finally {
                  setSavingApplicabilityId(null);
                }
              }

              return (
                <tr key={file.id} className="align-top">
                  <td className="px-3 py-3 font-medium text-slate-900">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="whitespace-normal break-words leading-6">{file.file_name}</span>
                      {!file.required && <Badge tone="neutral">若有</Badge>}
                    </div>
                    {file.not_applicable && (
                      <p className="mt-1 text-xs text-slate-500">
                        已声明无此材料
                        {file.not_applicable_by_name ? ` · ${file.not_applicable_by_name}` : ""}
                      </p>
                    )}
                  </td>
                  <td className="px-3 py-3 text-xs text-slate-600">
                    <div className="space-y-1">
                      <p>上传：{file.uploaded_by_name || "-"}</p>
                      <p className="text-slate-500">
                        {file.uploaded_at ? new Date(file.uploaded_at).toLocaleDateString() : "-"}
                      </p>
                      <p>审核：{file.reviewer_name || "-"}</p>
                      <p className="text-slate-500">
                        {file.reviewed_at ? new Date(file.reviewed_at).toLocaleDateString() : "-"}
                      </p>
                    </div>
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
                    <Badge tone={statusTone(completenessStatus)}>
                      {statusLabel(dataStatusLabels, completenessStatus)}
                    </Badge>
                  </td>
                  <td className="min-w-[220px] px-3 py-3">
                    {!file.required ? (
                      <div className="space-y-2">
                        <label className="flex items-center gap-2 text-xs text-slate-700">
                          <input
                            type="checkbox"
                            className="size-4 rounded border-slate-300"
                            checked={draft.not_applicable}
                            disabled={!canUpdateApplicability || hasUploadedFile}
                            onChange={(event) =>
                              setApplicabilityDrafts((current) => ({
                                ...current,
                                [file.id]: {
                                  ...draft,
                                  not_applicable: event.target.checked,
                                },
                              }))
                            }
                          />
                          无此材料
                        </label>
                        {draft.not_applicable && (
                          <textarea
                            className={inputClassName("min-h-16 resize-y text-xs")}
                            placeholder="备注（可选）"
                            value={draft.reason}
                            disabled={!canUpdateApplicability || hasUploadedFile}
                            onChange={(event) =>
                              setApplicabilityDrafts((current) => ({
                                ...current,
                                [file.id]: {
                                  ...draft,
                                  reason: event.target.value,
                                },
                              }))
                            }
                          />
                        )}
                        {hasUploadedFile && (
                          <p className="text-xs text-slate-400">已有上传文件，不能声明无此材料</p>
                        )}
                        {canUpdateApplicability && applicabilityChanged && !hasUploadedFile && (
                          <Button
                            size="sm"
                            variant="secondary"
                            disabled={savingApplicabilityId === file.id}
                            onClick={() => void saveApplicability()}
                          >
                            <Save className="size-4" aria-hidden="true" />
                            保存
                          </Button>
                        )}
                      </div>
                    ) : (
                      <Badge tone="neutral">必备</Badge>
                    )}
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
              );
            })}
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
  canUpdateApplicability,
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
  canUpdateApplicability: boolean;
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
        canUpdateApplicability={canUpdateApplicability}
        canSubmitReview={canSubmitReview}
        canReview={canReview}
        canReadReviews={canReadReviews}
        onChanged={onChanged}
      />
    </div>
  );
}

function ssuMeta(stageCode: string) {
  return ssuStageMeta.find((item) => item.code === stageCode);
}

function ssuDraft(record: ClinicalSsuProgress): Required<ClinicalSsuProgressPayload> {
  return {
    status: record.status,
    submitted_at: record.submitted_at ?? "",
    approved_at: record.approved_at ?? "",
    completed_at: record.completed_at ?? "",
    version_info: record.version_info ?? "",
    file_checklist: record.file_checklist ?? "",
    summary: record.summary ?? "",
    fee_detail: record.fee_detail ?? "",
    notes: record.notes ?? "",
  };
}

function cleanSsuDraft(draft: Required<ClinicalSsuProgressPayload>): ClinicalSsuProgressPayload {
  return {
    status: draft.status,
    submitted_at: draft.submitted_at || null,
    approved_at: draft.approved_at || null,
    completed_at: draft.completed_at || null,
    version_info: draft.version_info?.trim() || null,
    file_checklist: draft.file_checklist?.trim() || null,
    summary: draft.summary?.trim() || null,
    fee_detail: draft.fee_detail?.trim() || null,
    notes: draft.notes?.trim() || null,
  };
}

function SsuProgressPanel({
  records,
  startupFiles,
  canWrite,
  onChanged,
}: {
  records: ClinicalSsuProgress[];
  startupFiles: StageFile[];
  canWrite: boolean;
  onChanged: () => void;
}) {
  const [drafts, setDrafts] = useState<Record<number, Required<ClinicalSsuProgressPayload>>>({});
  const [savingId, setSavingId] = useState<number | null>(null);

  useEffect(() => {
    setDrafts(
      Object.fromEntries(records.map((record) => [record.id, ssuDraft(record)])),
    );
  }, [records]);

  const fileByType = useMemo(
    () => new Map(startupFiles.map((file) => [file.file_type ?? "", file])),
    [startupFiles],
  );

  function updateDraft(
    recordId: number,
    key: keyof Required<ClinicalSsuProgressPayload>,
    value: string,
  ) {
    setDrafts((current) => ({
      ...current,
      [recordId]: {
        ...(current[recordId] ?? ssuDraft(records.find((record) => record.id === recordId)!)),
        [key]: value,
      },
    }));
  }

  async function saveRecord(record: ClinicalSsuProgress) {
    const draft = drafts[record.id] ?? ssuDraft(record);
    setSavingId(record.id);
    try {
      await clinicalDataApi.updateSsuProgress(record.id, cleanSsuDraft(draft));
      await onChanged();
    } finally {
      setSavingId(null);
    }
  }

  if (records.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
        暂无 SSU 进展
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {records.map((record) => {
        const meta = ssuMeta(record.stage_code);
        const draft = drafts[record.id] ?? ssuDraft(record);
        const relatedFiles =
          meta?.fileTypes
            .map((fileType) => fileByType.get(fileType))
            .filter((file): file is StageFile => Boolean(file)) ?? [];
        return (
          <div key={record.id} className="rounded-md border border-slate-200 p-4">
            <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <ClipboardList className="size-4 text-emerald-700" aria-hidden="true" />
                  <h3 className="text-sm font-semibold text-slate-950">
                    {meta?.label ?? record.stage_code}
                  </h3>
                  <Badge tone={statusTone(draft.status)}>
                    {statusLabel(ssuStatusLabels, draft.status)}
                  </Badge>
                </div>
                <div className="mt-3 flex flex-wrap gap-2">
	                  {relatedFiles.map((file) => (
	                    <Badge key={file.id} tone={statusTone(file.completeness_status ?? fileCompletenessStatus(file))}>
	                      {file.file_name}
	                      {file.not_applicable ? " · 无此材料" : ""}
	                    </Badge>
	                  ))}
                  {relatedFiles.length === 0 && <Badge tone="neutral">暂无关联资料</Badge>}
                </div>
              </div>
              {canWrite && (
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={savingId === record.id}
                  onClick={() => void saveRecord(record)}
                >
                  <Save className="size-4" aria-hidden="true" />
                  保存
                </Button>
              )}
            </div>
            <div className="mt-4 grid gap-3 lg:grid-cols-4">
              <Field label="状态">
                <SelectField
                  value={draft.status}
                  disabled={!canWrite}
                  onChange={(event) => updateDraft(record.id, "status", event.target.value)}
                >
                  {Object.entries(ssuStatusLabels).map(([value, label]) => (
                    <option key={value} value={value}>
                      {label}
                    </option>
                  ))}
                </SelectField>
              </Field>
              <Field label="提交日期">
                <input
                  className={inputClassName()}
                  type="date"
                  disabled={!canWrite}
                  value={draft.submitted_at ?? ""}
                  onChange={(event) => updateDraft(record.id, "submitted_at", event.target.value)}
                />
              </Field>
              <Field label="批准日期">
                <input
                  className={inputClassName()}
                  type="date"
                  disabled={!canWrite}
                  value={draft.approved_at ?? ""}
                  onChange={(event) => updateDraft(record.id, "approved_at", event.target.value)}
                />
              </Field>
              <Field label="完成日期">
                <input
                  className={inputClassName()}
                  type="date"
                  disabled={!canWrite}
                  value={draft.completed_at ?? ""}
                  onChange={(event) => updateDraft(record.id, "completed_at", event.target.value)}
                />
              </Field>
              <Field label="版本信息">
                <input
                  className={inputClassName()}
                  disabled={!canWrite}
                  value={draft.version_info ?? ""}
                  onChange={(event) => updateDraft(record.id, "version_info", event.target.value)}
                />
              </Field>
              <Field label="资料清单">
                <textarea
                  className={inputClassName("min-h-20 resize-y")}
                  disabled={!canWrite}
                  value={draft.file_checklist ?? ""}
                  onChange={(event) => updateDraft(record.id, "file_checklist", event.target.value)}
                />
              </Field>
              <Field label="摘要">
                <textarea
                  className={inputClassName("min-h-20 resize-y")}
                  disabled={!canWrite}
                  value={draft.summary ?? ""}
                  onChange={(event) => updateDraft(record.id, "summary", event.target.value)}
                />
              </Field>
              <Field label="费用明细">
                <textarea
                  className={inputClassName("min-h-20 resize-y")}
                  disabled={!canWrite}
                  value={draft.fee_detail ?? ""}
                  onChange={(event) => updateDraft(record.id, "fee_detail", event.target.value)}
                />
              </Field>
              <div className="lg:col-span-4">
                <Field label="备注">
                  <textarea
                    className={inputClassName("min-h-20 resize-y")}
                    disabled={!canWrite}
                    value={draft.notes ?? ""}
                    onChange={(event) => updateDraft(record.id, "notes", event.target.value)}
                  />
                </Field>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function StageNavigation({
  activeStage,
  startupView,
  stages,
  dataset,
  onChange,
  onStartupViewChange,
}: {
  activeStage: StageCode;
  startupView: StartupView;
  stages: Stage[];
  dataset: ClinicalDataset | null;
  onChange: (stage: StageCode) => void;
  onStartupViewChange: (view: StartupView) => void;
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
          <div key={config.code} className="space-y-1">
            <button
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
                  {stage
                    ? config.code === "STARTUP"
                      ? `SSU ${dataset?.ssu_progress.length ?? 0} · 资料 ${count}`
                      : `${count} 项`
                    : "未配置"}
                </span>
              </span>
            </button>
            {config.code === "STARTUP" && isActive && (
              <div className="ml-7 space-y-1 border-l border-slate-200 pl-3">
                {[
                  { value: "ssu" as const, label: "SSU进展", count: dataset?.ssu_progress.length ?? 0 },
                  { value: "materials" as const, label: "资料准备", count },
                ].map((item) => {
                  const isViewActive = startupView === item.value;
                  return (
                    <button
                      key={item.value}
                      type="button"
                      className={cn(
                        "flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-xs text-slate-500 transition hover:bg-slate-100 hover:text-slate-900",
                        isViewActive && "bg-emerald-50 font-medium text-emerald-800",
                      )}
                      onClick={() => onStartupViewChange(item.value)}
                    >
                      <span>{item.label}</span>
                      <Badge tone={isViewActive ? "success" : "neutral"}>{item.count}</Badge>
                    </button>
                  );
                })}
              </div>
            )}
            {config.code === "CLOSEOUT" && isActive && (
              <div className="ml-7 space-y-1 border-l border-slate-200 pl-3">
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-2 rounded-md bg-emerald-50 px-3 py-2 text-left text-xs font-medium text-emerald-800 transition hover:bg-emerald-50"
                  onClick={() => onChange("CLOSEOUT")}
                >
                  <span>资料准备</span>
                  <Badge tone="success">{count}</Badge>
                </button>
              </div>
            )}
          </div>
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
  const requestedStartupView = searchParams.get("view");
  const [projects, setProjects] = useState<Project[]>([]);
  const [centers, setCenters] = useState<Center[]>([]);
  const [stages, setStages] = useState<Stage[]>([]);
  const [projectId, setProjectId] = useState<number | undefined>();
  const [centerId, setCenterId] = useState<number | undefined>();
  const [activeStage, setActiveStage] = useState<StageCode>(normalizeStageCode(requestedStage));
  const [startupView, setStartupView] = useState<StartupView>(
    normalizeStartupView(requestedStartupView),
  );
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
  const activePanelTitle =
    activeStage === "STARTUP"
      ? startupView === "ssu"
        ? "试验准备阶段 - SSU进展"
        : "试验准备阶段 - 资料准备"
      : activeStageConfig.title;
  const activePanelDescription =
    activeStage === "STARTUP"
      ? startupView === "ssu"
        ? "维护立项、伦理、协议签署、省局备案和启动会进展"
        : "维护试验准备阶段中心级资料清单"
      : activeStageModel?.description || activeStageConfig.description;
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
    const nextStage = normalizeStageCode(requestedStage);
    setActiveStage(nextStage);
    if (nextStage === "STARTUP") {
      setStartupView(normalizeStartupView(requestedStartupView));
    }
  }, [requestedStage, requestedStartupView]);

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
      const nextParams = buildDatasetSearchParams(projectId, nextCenterId, activeStage, startupView);
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
	    startupView,
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
    const nextParams = buildDatasetSearchParams(nextProjectId, undefined, activeStage, startupView);
    if (nextParams.toString() !== currentQuery) {
      setSearchParams(nextParams, { replace: true });
    }
  }

  function handleCenterChange(value: string) {
    const nextCenterId = Number(value) || undefined;
    setCenterId(nextCenterId);
    setDataset(null);
    const nextParams = buildDatasetSearchParams(projectId, nextCenterId, activeStage, startupView);
    if (nextParams.toString() !== currentQuery) {
      setSearchParams(nextParams, { replace: true });
    }
  }

  function handleStageChange(stage: StageCode) {
    setActiveStage(stage);
    const nextStartupView = stage === "STARTUP" ? "ssu" : startupView;
    if (stage === "STARTUP") {
      setStartupView(nextStartupView);
    }
    const nextParams = buildDatasetSearchParams(projectId, centerId, stage, nextStartupView);
    if (nextParams.toString() !== currentQuery) {
      setSearchParams(nextParams, { replace: true });
    }
  }

  function handleStartupViewChange(view: StartupView) {
    setActiveStage("STARTUP");
    setStartupView(view);
    const nextParams = buildDatasetSearchParams(projectId, centerId, "STARTUP", view);
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
                startupView={startupView}
                stages={displayStages}
                dataset={dataset}
                onChange={handleStageChange}
                onStartupViewChange={handleStartupViewChange}
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
	                  <CardTitle>{activePanelTitle}</CardTitle>
	                  <p className="mt-2 text-sm text-slate-500">{activePanelDescription}</p>
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
	                  <Badge tone="neutral">
	                    {activeStage === "STARTUP" && startupView === "ssu"
	                      ? `节点 ${dataset?.ssu_progress.length ?? 0}`
	                      : `资料 ${activeStageFiles.length}`}
	                  </Badge>
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
              ) : activeStage === "STARTUP" ? (
                startupView === "ssu" ? (
                  <section className="space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h2 className="text-base font-semibold text-slate-950">SSU进展</h2>
                      <Badge tone="neutral">节点 {dataset?.ssu_progress.length ?? 0}</Badge>
                    </div>
                    <SsuProgressPanel
                      records={dataset?.ssu_progress ?? []}
                      startupFiles={dataset?.startup_files ?? []}
                      canWrite={canWrite}
                      onChanged={() => void loadDataset()}
                    />
                  </section>
                ) : (
                  <section className="space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <h2 className="text-base font-semibold text-slate-950">资料准备</h2>
                      <Badge tone="neutral">资料 {dataset?.startup_files.length ?? 0}</Badge>
                    </div>
                    <StageFileTable
                      files={dataset?.startup_files ?? []}
                      canReadFiles={canReadFiles}
                      canWriteFiles={canWriteFiles}
                      canDeleteFiles={canDeleteFiles}
                      canUpdateApplicability={canWrite}
                      canSubmitReview={canSubmitReview}
                      canReview={canReview}
                      canReadReviews={canReadReviews}
                      onChanged={() => void loadDataset()}
                    />
                  </section>
                )
              ) : activeStage === "CLOSEOUT" ? (
                <section className="space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h2 className="text-base font-semibold text-slate-950">试验结束阶段资料准备</h2>
                    <Badge tone="neutral">资料 {dataset?.closeout_files.length ?? 0}</Badge>
                  </div>
                  <StageFileTable
                    files={dataset?.closeout_files ?? []}
                    canReadFiles={canReadFiles}
                    canWriteFiles={canWriteFiles}
                    canDeleteFiles={canDeleteFiles}
                    canUpdateApplicability={canWrite}
                    canSubmitReview={canSubmitReview}
                    canReview={canReview}
                    canReadReviews={canReadReviews}
                    onChanged={() => void loadDataset()}
                  />
                </section>
              ) : (
                <SecondaryStageFiles
                  groups={activeFileGroups}
                  activeGroupId={activeSubStageId}
                  onGroupChange={setActiveSubStageId}
                  canReadFiles={canReadFiles}
                  canWriteFiles={canWriteFiles}
                  canDeleteFiles={canDeleteFiles}
                  canUpdateApplicability={canWrite}
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
