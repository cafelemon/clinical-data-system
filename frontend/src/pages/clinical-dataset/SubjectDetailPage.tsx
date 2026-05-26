import { ArrowLeft, RotateCcw } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { RemarkAutosaveCell } from "@/components/clinical-data/RemarkAutosaveCell";
import { UpdateRecordCell } from "@/components/clinical-data/UpdateRecordCell";
import { FileActions } from "@/components/files/FileActions";
import { ReviewEntrypoints } from "@/components/files/ReviewEntrypoints";
import { BatchApproveButton } from "@/components/reviews/BatchApproveButton";
import { ReviewActions } from "@/components/reviews/ReviewActions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { restoreScrollPosition, saveScrollPosition } from "@/lib/navigation-origin";
import { clinicalDataApi } from "@/services/clinical-data";
import { useAuthStore } from "@/stores/auth-store";
import type { Subject, SubjectItem, SubjectItemRemarkResponse, SubjectSection } from "@/types/clinical-data";

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

export function SubjectDetailPage() {
  const params = useParams();
  const location = useLocation();
  const subjectId = Number(params.subjectId);
  const restoredScrollKeyRef = useRef<string | null>(null);
  const [subject, setSubject] = useState<Subject | null>(null);
  const [sections, setSections] = useState<SubjectSection[]>([]);
  const [items, setItems] = useState<SubjectItem[]>([]);
  const [detailRefreshKey, setDetailRefreshKey] = useState(0);
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

  const handleDataChanged = useCallback(() => {
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
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Button asChild variant="ghost" className="mb-3 px-0">
            <Link to={backPath}>
              <ArrowLeft className="size-4" aria-hidden="true" />
              返回数据集
            </Link>
          </Button>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">
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
              {latestItem && (
                <Badge tone="neutral">
                  最近：{latestItem.item_name} · {formatDateTime(latestItem.updated_at)}
                </Badge>
              )}
            </div>
          )}
        </div>
        <Button variant="secondary" onClick={() => void loadData()}>
          <RotateCcw className="size-4" aria-hidden="true" />
          刷新
        </Button>
      </div>

      {message && (
        <Badge tone={message.includes("失败") || message.includes("不存在") ? "danger" : "success"}>
          {message}
        </Badge>
      )}

      {subject && (
        <Card>
          <CardHeader>
            <CardTitle>基本信息</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
              <div>
                <p className="text-xs text-slate-500">性别</p>
                <p className="mt-1 font-medium">{subject.gender || "-"}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">年龄</p>
                <p className="mt-1 font-medium">{subject.age ?? "-"}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">入组日期</p>
                <p className="mt-1 font-medium">{subject.enrolled_at || "-"}</p>
              </div>
              <div>
                <p className="text-xs text-slate-500">分组</p>
                <p className="mt-1 font-medium">
                  {subject.subject_arm
                    ? subjectArmLabels[subject.subject_arm] ?? subject.subject_arm
                    : "未分组"}
                </p>
              </div>
              <div>
                <p className="text-xs text-slate-500">更新时间</p>
                <p className="mt-1 font-medium">
                  {new Date(subject.updated_at).toLocaleDateString()}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {loading && <p className="text-sm text-slate-500">正在加载</p>}

      <div className="space-y-4">
        {canReview && batchTargets.length > 0 && (
          <BatchApproveButton
            targets={batchTargets}
            label="一键审批当前受试者资料"
            confirmText={`确认一键审批当前受试者 ${batchTargets.length} 项资料？已上传未提交的资料会自动提交并通过。`}
            onChanged={handleDataChanged}
          />
        )}
        {groupedSections.map(({ section, items: sectionItems }) => (
          <Card key={section.id}>
            <CardHeader>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <CardTitle>{section.name}</CardTitle>
                  <p className="mt-1 text-xs text-slate-500">
                    {section.visit_name || "-"} · {section.time_window || "-"}
                  </p>
                </div>
                <Badge>{section.section_code}</Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1260px] text-left text-sm">
                  <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2 font-medium">数据项</th>
                      <th className="px-3 py-2 font-medium">上传人</th>
                      <th className="px-3 py-2 font-medium">审核人</th>
                      <th className="px-3 py-2 font-medium">必填</th>
                      <th className="px-3 py-2 font-medium">上传状态</th>
                      <th className="px-3 py-2 font-medium">审核状态</th>
                      <th className="px-3 py-2 font-medium">文件</th>
                      <th className="px-3 py-2 font-medium">审阅</th>
                      <th className="px-3 py-2 font-medium">更新记录</th>
                      <th className="px-3 py-2 font-medium">备注</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {sectionItems.map((item) => (
                      <tr key={item.id} id={`subject-item-${item.id}`} className="align-top">
                        <td className="max-w-56 px-3 py-3 font-medium text-slate-900">
                          <span className="block leading-5" title={item.item_name}>
                            {item.item_name}
                          </span>
                        </td>
                        <td className="px-3 py-3 text-slate-600">
                          {item.uploaded_by_name || "-"}
                        </td>
                        <td className="px-3 py-3 text-slate-600">
                          {item.reviewer_name || "-"}
                        </td>
                        <td className="px-3 py-3">
                          <Badge tone={item.required ? "warning" : "neutral"}>
                            {item.required ? "必填" : "非必填"}
                          </Badge>
                        </td>
                        <td className="px-3 py-3">
                          <Badge tone={statusTone(item.upload_status)}>
                            {statusLabel(uploadStatusLabels, item.upload_status)}
                          </Badge>
                        </td>
                        <td className="px-3 py-3">
                          <div className="space-y-2">
                            <Badge tone={statusTone(item.review_status)}>
                              {statusLabel(reviewStatusLabels, item.review_status)}
                            </Badge>
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
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          <FileActions
                            subjectItemId={item.id}
                            defaultCategory="clinical_document"
                            canRead={canReadFiles}
                            canWrite={canWriteFiles}
                            canDelete={canDeleteFiles}
                            onChanged={handleDataChanged}
                          />
                        </td>
                        <td className="px-3 py-3">
                          <ReviewEntrypoints
                            subjectItemId={item.id}
                            canReadFiles={canReadFiles}
                            refreshKey={detailRefreshKey}
                            linkState={reviewOriginForItem(item.id)}
                            onNavigate={() => handleReviewNavigate(item.id)}
                          />
                        </td>
                        <td className="px-3 py-3">
                          <UpdateRecordCell itemId={item.id} refreshKey={detailRefreshKey} />
                        </td>
                        <td className="px-3 py-3">
                          <RemarkAutosaveCell
                            item={item}
                            canWrite={canWrite}
                            onSaved={handleRemarkSaved}
                          />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
