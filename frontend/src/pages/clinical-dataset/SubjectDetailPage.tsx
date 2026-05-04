import { ArrowLeft, RotateCcw, Save } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { FileActions } from "@/components/files/FileActions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SelectField, TextAreaField } from "@/components/ui/form";
import { clinicalDataApi } from "@/services/clinical-data";
import { useAuthStore } from "@/stores/auth-store";
import type { Subject, SubjectItem, SubjectSection } from "@/types/clinical-data";

const uploadStatusLabels: Record<string, string> = {
  not_uploaded: "未上传",
  uploaded: "已上传",
  not_applicable: "不适用",
};

const reviewStatusLabels: Record<string, string> = {
  pending_review: "待审核",
  approved: "已通过",
  rejected: "已驳回",
};

const dataStatusLabels: Record<string, string> = {
  not_started: "未开始",
  in_progress: "进行中",
  complete: "已完成",
};

type ItemDraft = {
  upload_status: string;
  review_status: string;
  remark: string;
};

function statusTone(status: string) {
  if (status === "approved" || status === "complete" || status === "uploaded") return "success";
  if (status === "rejected") return "danger";
  if (status === "in_progress" || status === "pending_review") return "warning";
  return "neutral";
}

function statusLabel(labels: Record<string, string>, status: string) {
  return labels[status] ?? status;
}

export function SubjectDetailPage() {
  const params = useParams();
  const subjectId = Number(params.subjectId);
  const [subject, setSubject] = useState<Subject | null>(null);
  const [sections, setSections] = useState<SubjectSection[]>([]);
  const [items, setItems] = useState<SubjectItem[]>([]);
  const [drafts, setDrafts] = useState<Record<number, ItemDraft>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canWrite = hasPermission("clinical_data:write");
  const canReadFiles = hasPermission("files:read");
  const canWriteFiles = hasPermission("files:write");
  const canDeleteFiles = hasPermission("files:delete");

  const groupedSections = useMemo(
    () =>
      sections.map((section) => ({
        section,
        items: items.filter((item) => item.section_id === section.id),
      })),
    [items, sections],
  );

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
      setDrafts(
        Object.fromEntries(
          itemData.map((item) => [
            item.id,
            {
              upload_status: item.upload_status,
              review_status: item.review_status,
              remark: item.remark ?? "",
            },
          ]),
        ),
      );
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

  function updateDraft(itemId: number, patch: Partial<ItemDraft>) {
    setDrafts((current) => ({
      ...current,
      [itemId]: {
        ...current[itemId],
        ...patch,
      },
    }));
  }

  async function handleSaveItem(item: SubjectItem) {
    const draft = drafts[item.id];
    if (!draft) return;
    try {
      await clinicalDataApi.updateSubjectItem(item.id, {
        upload_status: draft.upload_status,
        review_status: draft.review_status,
        remark: draft.remark.trim() || null,
      });
      setMessage("数据项已更新");
      await loadData();
    } catch {
      setMessage("数据项更新失败");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Button asChild variant="ghost" className="mb-3 px-0">
            <Link to="/clinical-dataset">
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
                <table className="w-full min-w-[860px] text-left text-sm">
                  <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="px-3 py-2 font-medium">数据项</th>
                      <th className="px-3 py-2 font-medium">编码</th>
                      <th className="px-3 py-2 font-medium">上传状态</th>
                      <th className="px-3 py-2 font-medium">审核状态</th>
                      <th className="px-3 py-2 font-medium">备注</th>
                      <th className="px-3 py-2 font-medium">文件</th>
                      {canWrite && <th className="px-3 py-2 font-medium">操作</th>}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {sectionItems.map((item) => {
                      const draft = drafts[item.id];
                      return (
                        <tr key={item.id}>
                          <td className="px-3 py-3 font-medium text-slate-900">
                            {item.item_name}
                          </td>
                          <td className="px-3 py-3 text-slate-500">{item.item_code}</td>
                          <td className="px-3 py-3">
                            {canWrite && draft ? (
                              <SelectField
                                value={draft.upload_status}
                                onChange={(event) =>
                                  updateDraft(item.id, { upload_status: event.target.value })
                                }
                              >
                                <option value="not_uploaded">未上传</option>
                                <option value="uploaded">已上传</option>
                                <option value="not_applicable">不适用</option>
                              </SelectField>
                            ) : (
                              <Badge tone={statusTone(item.upload_status)}>
                                {statusLabel(uploadStatusLabels, item.upload_status)}
                              </Badge>
                            )}
                          </td>
                          <td className="px-3 py-3">
                            {canWrite && draft ? (
                              <SelectField
                                value={draft.review_status}
                                onChange={(event) =>
                                  updateDraft(item.id, { review_status: event.target.value })
                                }
                              >
                                <option value="pending_review">待审核</option>
                                <option value="approved">已通过</option>
                                <option value="rejected">已驳回</option>
                              </SelectField>
                            ) : (
                              <Badge tone={statusTone(item.review_status)}>
                                {statusLabel(reviewStatusLabels, item.review_status)}
                              </Badge>
                            )}
                          </td>
                          <td className="px-3 py-3">
                            {canWrite && draft ? (
                              <TextAreaField
                                value={draft.remark}
                                onChange={(event) =>
                                  updateDraft(item.id, { remark: event.target.value })
                                }
                              />
                            ) : (
                              <span className="text-slate-600">{item.remark || "-"}</span>
                            )}
                          </td>
                          <td className="px-3 py-3">
                            <FileActions
                              subjectItemId={item.id}
                              defaultCategory="clinical_document"
                              canRead={canReadFiles}
                              canWrite={canWriteFiles}
                              canDelete={canDeleteFiles}
                              onChanged={() => void loadData()}
                            />
                          </td>
                          {canWrite && (
                            <td className="px-3 py-3">
                              <Button
                                size="sm"
                                variant="secondary"
                                onClick={() => void handleSaveItem(item)}
                              >
                                <Save className="size-4" aria-hidden="true" />
                                保存
                              </Button>
                            </td>
                          )}
                        </tr>
                      );
                    })}
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
