import { ArrowLeft, AlertTriangle, CheckCircle2, ClipboardList, RotateCcw, Users } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { RemarkAutosaveCell } from "@/components/clinical-data/RemarkAutosaveCell";
import { UpdateRecordCell } from "@/components/clinical-data/UpdateRecordCell";
import { DocumentExtractedFieldsPanel } from "@/components/document-fields/DocumentExtractedFieldsPanel";
import { FileActions } from "@/components/files/FileActions";
import { ReviewEntrypoints } from "@/components/files/ReviewEntrypoints";
import { BatchApproveButton } from "@/components/reviews/BatchApproveButton";
import { ReviewActions } from "@/components/reviews/ReviewActions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { restoreScrollPosition, saveScrollPosition } from "@/lib/navigation-origin";
import { cn } from "@/lib/utils";
import { clinicalDataApi } from "@/services/clinical-data";
import { useAuthStore } from "@/stores/auth-store";
import type { Subject, SubjectItem, SubjectItemRemarkResponse, SubjectSection } from "@/types/clinical-data";
import type { FileRecord } from "@/types/files";

const uploadStatusLabels: Record<string, string> = {
  not_uploaded: "未上传",
  uploaded: "已上传",
  supplement_required: "待补充",
  replaced: "已重新上传",
};

const reviewStatusLabels: Record<string, string> = {
  unreviewed: "待审核",
  pending: "待审核",
  approved: "已通过",
  rejected: "已驳回",
};

const dataStatusLabels: Record<string, string> = {
  incomplete: "资料不全",
  checking: "核查中",
  complete: "资料齐全",
};

const subjectArmLabels = {
  experimental: "实验组",
  control: "对照组",
};

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

function formatDateTime(value: string | null) {
  return value ? new Date(value).toLocaleDateString() : "-";
}

function formatDateTimeMinute(value: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 16).replace("T", " ");
  const pad = (input: number) => String(input).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`;
}

function itemCompletenessStatus(item: SubjectItem) {
  if (item.completeness_status) return item.completeness_status;
  if (item.upload_status === "supplement_required" || item.review_status === "rejected") {
    return "incomplete";
  }
  if ((item.upload_status === "uploaded" || item.upload_status === "replaced") && item.review_status === "approved") {
    return "complete";
  }
  if (item.upload_status === "uploaded" || item.upload_status === "replaced") {
    return "checking";
  }
  return "incomplete";
}

function percent(numerator: number, denominator: number) {
  if (denominator <= 0) return 0;
  return Math.round((numerator / denominator) * 100);
}

function ProgressBar({ value, tone = "blue" }: { value: number; tone?: "blue" | "teal" | "amber" | "red" }) {
  const colorClass =
    tone === "teal"
      ? "bg-[#10BFB3]"
      : tone === "amber"
        ? "bg-amber-500"
        : tone === "red"
          ? "bg-rose-500"
          : "bg-[#0F78D4]";
  return (
    <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
      <div className={cn("h-full rounded-full", colorClass)} style={{ width: `${Math.min(value, 100)}%` }} />
    </div>
  );
}

function DetailMetric({
  label,
  value,
  detail,
  tone = "blue",
  icon: Icon,
}: {
  label: string;
  value: number | string;
  detail: string;
  tone?: "blue" | "teal" | "amber" | "red";
  icon: typeof ClipboardList;
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
        <div>
          <p className="text-xs font-medium text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-semibold text-slate-950">{value}</p>
        </div>
        <div className={cn("flex size-9 shrink-0 items-center justify-center rounded-md", toneClass)}>
          <Icon className="size-4" aria-hidden="true" />
        </div>
      </div>
      <p className="mt-3 truncate text-xs text-slate-500">{detail}</p>
    </div>
  );
}

export function SubjectDetailPage() {
  const params = useParams();
  const location = useLocation();
  const subjectId = Number(params.subjectId);
  const restoredScrollKeyRef = useRef<string | null>(null);
  const [subject, setSubject] = useState<Subject | null>(null);
  const [sections, setSections] = useState<SubjectSection[]>([]);
  const [items, setItems] = useState<SubjectItem[]>([]);
  const [detailRefreshKey, setDetailRefreshKey] = useState(0);
  const [expandedFieldItemId, setExpandedFieldItemId] = useState(0);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canWrite = hasPermission("clinical_data:write");
  const canReadFiles = hasPermission("files:read");
  const canWriteFiles = hasPermission("files:write");
  const canDeleteFiles = hasPermission("files:delete");
  const canReadReviews = hasPermission("reviews:read");
  const canSubmitReview = hasPermission("reviews:submit");
  const canReview = hasPermission("reviews:review");

  const groupedSections = useMemo(
    () =>
      sections.map((section) => ({
        section,
        items: items.filter((item) => item.section_id === section.id),
      })),
    [items, sections],
  );
  const batchTargets = useMemo(
    () =>
      items.map((item) => ({
        target_type: "subject_item" as const,
        target_id: item.id,
      })),
    [items],
  );
  const latestItem = useMemo(
    () =>
      [...items].sort(
        (first, second) =>
          new Date(second.updated_at).getTime() - new Date(first.updated_at).getTime(),
      )[0],
    [items],
  );
  const itemSummary = useMemo(() => {
    const counts = items.reduce(
      (current, item) => {
        const completeness = itemCompletenessStatus(item);
        if (completeness === "complete") current.complete += 1;
        if (completeness === "checking") current.checking += 1;
        if (completeness === "incomplete") current.incomplete += 1;
        if (item.review_status === "pending" || item.review_status === "rejected") {
          current.reviewRisk += 1;
        }
        return current;
      },
      { complete: 0, checking: 0, incomplete: 0, reviewRisk: 0 },
    );
    return {
      ...counts,
      total: items.length,
      completeRate: percent(counts.complete, items.length),
    };
  }, [items]);
  const backPath = subject
    ? `/clinical-dataset?project_id=${subject.project_id}&center_id=${subject.center_id}&stage=TRIAL&view=visits`
    : "/clinical-dataset";
  const restoreState = location.state as
    | { restoreScrollKey?: string; restoreItemId?: number }
    | null;

  const loadData = useCallback(async () => {
    if (!subjectId) {
      setMessage("受试者不存在");
      return;
    }
    setLoading(true);
    try {
      const [subjectData, sectionData, itemData] = await Promise.all([
        clinicalDataApi.getSubject(subjectId),
        clinicalDataApi.listSubjectSections(subjectId),
        clinicalDataApi.listSubjectItems(subjectId),
      ]);
      setSubject(subjectData);
      setSections(sectionData);
      setItems(itemData);
      setMessage(null);
    } catch {
      setMessage("受试者详情加载失败");
    } finally {
      setLoading(false);
    }
  }, [subjectId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    const restoreScrollKey = restoreState?.restoreScrollKey;
    if (loading || !restoreScrollKey) return;
    if (restoredScrollKeyRef.current === restoreScrollKey) return;
    restoreScrollPosition(restoreScrollKey, restoreState?.restoreItemId);
    restoredScrollKeyRef.current = restoreScrollKey;
  }, [items, loading, restoreState?.restoreItemId, restoreState?.restoreScrollKey]);

  function reviewOriginForItem(itemId: number) {
    const scrollKey = `subject-detail:${subjectId}:${itemId}`;
    return {
      origin: {
        from: `${location.pathname}${location.search}`,
        backLabel: "返回详情页",
        scrollKey,
        itemId,
      },
    };
  }

  function handleReviewNavigate(itemId: number) {
    saveScrollPosition(`subject-detail:${subjectId}:${itemId}`, itemId);
  }

  const handleDataChanged = useCallback((file?: FileRecord) => {
    if (file?.subject_item_id) {
      setExpandedFieldItemId(file.subject_item_id);
    }
    setDetailRefreshKey((current) => current + 1);
    void loadData();
  }, [loadData]);

  function handleRemarkSaved(itemId: number, response: SubjectItemRemarkResponse) {
    setItems((current) =>
      current.map((item) =>
        item.id === itemId
          ? {
              ...item,
              remark: response.remark,
              updated_at: response.updated_at,
            }
          : item,
      ),
    );
    setDetailRefreshKey((current) => current + 1);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <Button asChild variant="ghost" className="mb-3 px-0 text-slate-600">
            <Link to={backPath}>
              <ArrowLeft className="size-4" aria-hidden="true" />
              返回数据集
            </Link>
          </Button>
          <div className="flex flex-col gap-3 md:flex-row md:items-center">
            <div className="flex size-12 shrink-0 items-center justify-center rounded-md bg-blue-50 text-[#0B2E63]">
              <Users className="size-6" aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <h1 className="truncate text-2xl font-semibold tracking-normal text-slate-950">
                {subject?.screening_no ?? "受试者详情"}
              </h1>
              {subject && (
                <div className="mt-2 flex flex-wrap gap-2">
                  <Badge tone={statusTone(subject.data_status)}>
                    {statusLabel(dataStatusLabels, subject.data_status)}
                  </Badge>
                  <Badge tone={statusTone(subject.review_status)}>
                    {statusLabel(reviewStatusLabels, subject.review_status)}
                  </Badge>
                  <Badge tone="neutral">
                    {subject.subject_arm
                      ? subjectArmLabels[subject.subject_arm] ?? subject.subject_arm
                      : "未分组"}
                  </Badge>
                  <Badge tone="neutral">更新 {formatDateTimeMinute(subject.updated_at)}</Badge>
                  {latestItem && (
                    <Badge tone="neutral">
                      最近：{latestItem.item_name} · {formatDateTime(latestItem.updated_at)}
                    </Badge>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {canReview && batchTargets.length > 0 && (
            <BatchApproveButton
              targets={batchTargets}
              label="一键审批当前受试者资料"
              confirmText={`确认一键审批当前受试者 ${batchTargets.length} 项资料？已上传未提交的资料会自动提交并通过。`}
              onChanged={handleDataChanged}
            />
          )}
          <Button variant="secondary" onClick={() => void loadData()}>
            <RotateCcw className="size-4" aria-hidden="true" />
            刷新
          </Button>
        </div>
      </div>

      {message && (
        <Badge tone={message.includes("失败") || message.includes("不存在") ? "danger" : "success"}>
          {message}
        </Badge>
      )}

      {subject && (
        <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <DetailMetric
              label="总资料项"
              value={itemSummary.total}
              detail={`完成率 ${itemSummary.completeRate}%`}
              icon={ClipboardList}
              tone="blue"
            />
            <DetailMetric
              label="资料齐全"
              value={itemSummary.complete}
              detail={`核查中 ${itemSummary.checking}`}
              icon={CheckCircle2}
              tone="teal"
            />
            <DetailMetric
              label="资料不全"
              value={itemSummary.incomplete}
              detail={`待补齐 ${itemSummary.incomplete}`}
              icon={AlertTriangle}
              tone={itemSummary.incomplete > 0 ? "amber" : "blue"}
            />
            <DetailMetric
              label="待处理审核"
              value={itemSummary.reviewRisk}
              detail="pending / rejected"
              icon={AlertTriangle}
              tone={itemSummary.reviewRisk > 0 ? "red" : "blue"}
            />
          </div>
          <div className="rounded-md border border-slate-200 bg-white p-4">
            <h2 className="text-sm font-semibold text-slate-950">受试者资料页头</h2>
            <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
              <div>
                <p className="text-xs text-slate-500">记录分组</p>
                <p className="mt-1 font-medium text-slate-900">
                  {subject.subject_arm
                    ? subjectArmLabels[subject.subject_arm] ?? subject.subject_arm
                    : "未分组"}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500">性别/年龄</p>
                <p className="mt-1 font-medium text-slate-900">
                  {subject.gender || "-"} · {subject.age ?? "-"}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500">入组日期</p>
                <p className="mt-1 font-medium text-slate-900">{subject.enrolled_at || "-"}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">知情时间</p>
                <p className="mt-1 font-medium text-slate-900">
                  {formatDateTimeMinute(subject.informed_at)}
                </p>
              </div>
            </div>
          </div>
        </section>
      )}

      {loading && <p className="text-sm text-slate-500">正在加载</p>}

      <div className="space-y-4">
        {groupedSections.map(({ section, items: sectionItems }) => {
          const completeCount = sectionItems.filter((item) => itemCompletenessStatus(item) === "complete").length;
          const checkingCount = sectionItems.filter((item) => itemCompletenessStatus(item) === "checking").length;
          const incompleteCount = sectionItems.filter((item) => itemCompletenessStatus(item) === "incomplete").length;
          const completeRate = percent(completeCount, sectionItems.length);
          return (
          <Card key={section.id} className="overflow-hidden">
            <CardHeader>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <CardTitle>{section.name}</CardTitle>
                  <p className="mt-1 text-xs text-slate-500">
                    {section.visit_name || "-"} · {section.time_window || "-"}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Badge>{section.section_code}</Badge>
                  <Badge tone="success">齐全 {completeCount}</Badge>
                  <Badge tone="warning">核查 {checkingCount}</Badge>
                  <Badge tone="danger">不全 {incompleteCount}</Badge>
                </div>
              </div>
              <div className="mt-3">
                <ProgressBar value={completeRate} tone={incompleteCount > 0 ? "amber" : "teal"} />
              </div>
            </CardHeader>
            <CardContent>
              <div className="divide-y divide-slate-100">
                {sectionItems.map((item) => {
                  const completeness = itemCompletenessStatus(item);
                  return (
                    <div
                      key={item.id}
                      id={`subject-item-${item.id}`}
                      className="py-3"
                    >
                      <div className="rounded-md border border-slate-200 bg-white px-4 py-3">
                        <div className="grid min-h-32 gap-4 xl:grid-cols-[minmax(180px,1fr)_minmax(170px,0.9fr)_minmax(260px,1.25fr)_minmax(180px,0.9fr)_minmax(220px,1fr)]">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="min-w-0 break-words text-sm font-semibold leading-6 text-slate-950">
                                {item.item_name}
                              </p>
                              <Badge tone={item.required ? "warning" : "neutral"}>
                                {item.required ? "必填" : "非必填"}
                              </Badge>
                            </div>
                            <p className="mt-2 break-all text-xs font-medium text-slate-500">
                              {item.item_code}
                            </p>
                          </div>

                          <div className="space-y-2">
                            <div className="flex flex-wrap gap-1.5">
                              <Badge tone={statusTone(completeness)}>
                                {statusLabel(dataStatusLabels, completeness)}
                              </Badge>
                              <Badge tone={statusTone(item.upload_status)}>
                                {statusLabel(uploadStatusLabels, item.upload_status)}
                              </Badge>
                              <Badge tone={statusTone(item.review_status)}>
                                {statusLabel(reviewStatusLabels, item.review_status)}
                              </Badge>
                            </div>
                            <p className="text-xs leading-5 text-slate-500">
                              上传 {item.uploaded_by_name || "-"} · 审核 {item.reviewer_name || "-"}
                            </p>
                          </div>

                          <FileActions
                            subjectItemId={item.id}
                            defaultCategory="clinical_document"
                            canRead={canReadFiles}
                            canWrite={canWriteFiles}
                            canDelete={canDeleteFiles}
                            onChanged={handleDataChanged}
                          />

                          <div className="space-y-2">
                            <UpdateRecordCell itemId={item.id} refreshKey={detailRefreshKey} />
                            <ReviewActions
                              targetType="subject_item"
                              targetId={item.id}
                              uploadStatus={item.upload_status}
                              reviewStatus={item.review_status}
                              canSubmit={canSubmitReview}
                              canReview={canReview}
                              canReadRecords={canReadReviews}
                              showLatest={false}
                              showRecordsButton={false}
                              onChanged={handleDataChanged}
                            />
                            <ReviewEntrypoints
                              subjectItemId={item.id}
                              canReadFiles={canReadFiles}
                              refreshKey={detailRefreshKey}
                              linkState={reviewOriginForItem(item.id)}
                              onNavigate={() => handleReviewNavigate(item.id)}
                            />
                          </div>

                          <RemarkAutosaveCell
                            item={item}
                            canWrite={canWrite}
                            onSaved={handleRemarkSaved}
                          />
                        </div>

                        <div className="mt-3 border-t border-slate-100 pt-3">
                          <DocumentExtractedFieldsPanel
                            subjectItemId={item.id}
                            canWrite={canWriteFiles}
                            defaultOpen={expandedFieldItemId === item.id}
                            refreshKey={detailRefreshKey}
                            onChanged={handleDataChanged}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}
                {sectionItems.length === 0 && (
                  <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                    暂无资料项
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        );
        })}
      </div>
    </div>
  );
}
