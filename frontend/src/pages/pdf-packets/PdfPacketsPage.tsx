import { Eye, FileSearch, Plus, RefreshCw, Save, Trash2, Upload } from "lucide-react";
import { ChangeEvent, FormEvent, useEffect, useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, SelectField, TextAreaField } from "@/components/ui/form";
import { inputClassName } from "@/lib/form-styles";
import { clinicalDataApi } from "@/services/clinical-data";
import { masterDataApi } from "@/services/master-data";
import { pdfPacketsApi } from "@/services/pdf-packets";
import { useAuthStore } from "@/stores/auth-store";
import type { Subject, SubjectItem } from "@/types/clinical-data";
import type { Center, Project } from "@/types/master-data";
import type { PdfPacket, PdfPacketSegment } from "@/types/pdf-packets";

type EditableSegment = {
  page_start: number;
  page_end: number;
  detected_name: string;
  subject_item_id: number;
};
type BadgeTone = "neutral" | "success" | "warning" | "danger";

const emptySegment = {
  page_start: 1,
  page_end: 1,
  detected_name: "",
  subject_item_id: 0,
};

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    uploaded: "已上传",
    processing: "处理中",
    ready: "已识别",
    failed: "失败",
    pending: "待确认",
  };
  return labels[status] ?? status;
}

function statusTone(status: string): BadgeTone {
  if (status === "ready" || status === "uploaded") return "success";
  if (status === "failed") return "danger";
  return "neutral";
}

function formatDateTime(value: string) {
  return value ? value.replace("T", " ").slice(0, 16) : "-";
}

function openBlob(blob: Blob, page?: number) {
  const url = window.URL.createObjectURL(blob);
  window.open(`${url}${page ? `#page=${page}` : ""}`, "_blank", "noopener,noreferrer");
  window.setTimeout(() => window.URL.revokeObjectURL(url), 60_000);
}

export function PdfPacketsPage() {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canRead = hasPermission("pdf_packets:read");
  const canWrite = hasPermission("pdf_packets:write");
  const canDelete = hasPermission("pdf_packets:delete");
  const [projects, setProjects] = useState<Project[]>([]);
  const [centers, setCenters] = useState<Center[]>([]);
  const [subjects, setSubjects] = useState<Subject[]>([]);
  const [subjectItems, setSubjectItems] = useState<SubjectItem[]>([]);
  const [packets, setPackets] = useState<PdfPacket[]>([]);
  const [segments, setSegments] = useState<PdfPacketSegment[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState(0);
  const [selectedCenterId, setSelectedCenterId] = useState(0);
  const [selectedSubjectId, setSelectedSubjectId] = useState(0);
  const [selectedPacketId, setSelectedPacketId] = useState(0);
  const [segmentForms, setSegmentForms] = useState<Record<number, EditableSegment>>({});
  const [newSegment, setNewSegment] = useState<EditableSegment>(emptySegment);
  const [message, setMessage] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);

  const selectedSubject = subjects.find((subject) => subject.id === selectedSubjectId);
  const selectedPacket = packets.find((packet) => packet.id === selectedPacketId);
  const centersForProject = centers.filter((center) => center.project_id === selectedProjectId);

  const subjectItemNameById = useMemo(
    () => new Map(subjectItems.map((item) => [item.id, item.item_name])),
    [subjectItems],
  );

  async function loadProjects() {
    const data = await masterDataApi.listProjects();
    setProjects(data);
    if (!selectedProjectId && data.length > 0) {
      setSelectedProjectId(data[0].id);
    }
  }

  async function loadCenters(projectId: number) {
    const data = await masterDataApi.listCenters(projectId || undefined);
    setCenters(data);
    const firstCenter = data.find((center) => center.project_id === projectId);
    setSelectedCenterId((current) =>
      current && data.some((center) => center.id === current) ? current : firstCenter?.id ?? 0,
    );
  }

  async function loadSubjects(projectId: number, centerId: number) {
    if (!projectId || !centerId) {
      setSubjects([]);
      setSelectedSubjectId(0);
      return;
    }
    const data = await clinicalDataApi.listSubjects(projectId, centerId);
    setSubjects(data);
    setSelectedSubjectId((current) =>
      current && data.some((subject) => subject.id === current) ? current : data[0]?.id ?? 0,
    );
  }

  async function loadPackets(
    projectId = selectedProjectId,
    centerId = selectedCenterId,
    subjectId = selectedSubjectId,
  ) {
    if (!canRead || !projectId || !centerId) {
      setPackets([]);
      setSelectedPacketId(0);
      return;
    }
    const data = await pdfPacketsApi.listPackets({
      project_id: projectId,
      center_id: centerId,
      subject_id: subjectId || undefined,
    });
    setPackets(data);
    setSelectedPacketId((current) =>
      current && data.some((packet) => packet.id === current) ? current : data[0]?.id ?? 0,
    );
  }

  async function loadSegments(packetId = selectedPacketId) {
    if (!packetId) {
      setSegments([]);
      setSegmentForms({});
      return;
    }
    const data = await pdfPacketsApi.listSegments(packetId);
    setSegments(data);
    setSegmentForms(
      Object.fromEntries(
        data.map((segment) => [
          segment.id,
          {
            page_start: segment.page_start,
            page_end: segment.page_end,
            detected_name: segment.detected_name ?? "",
            subject_item_id: segment.subject_item_id ?? segment.suggested_subject_item_id ?? 0,
          },
        ]),
      ),
    );
  }

  async function loadSubjectItems(subjectId = selectedSubjectId) {
    if (!subjectId) {
      setSubjectItems([]);
      return;
    }
    const data = await clinicalDataApi.listSubjectItems(subjectId);
    setSubjectItems(data);
  }

  useEffect(() => {
    if (!canRead) return;
    void loadProjects();
  }, [canRead]);

  useEffect(() => {
    if (!selectedProjectId) return;
    void loadCenters(selectedProjectId);
  }, [selectedProjectId]);

  useEffect(() => {
    void loadSubjects(selectedProjectId, selectedCenterId);
    void loadPackets(selectedProjectId, selectedCenterId);
  }, [selectedProjectId, selectedCenterId]);

  useEffect(() => {
    void loadSubjectItems(selectedSubjectId);
    void loadPackets(selectedProjectId, selectedCenterId, selectedSubjectId);
  }, [selectedSubjectId]);

  useEffect(() => {
    void loadSegments(selectedPacketId);
  }, [selectedPacketId]);

  async function handleUpload(event: ChangeEvent<HTMLInputElement>) {
    const selectedFile = event.target.files?.[0];
    event.target.value = "";
    if (!selectedFile || !selectedProjectId || !selectedCenterId || !selectedSubjectId) return;
    const filenameStem = selectedFile.name.replace(/\.pdf$/i, "");
    if (selectedSubject && filenameStem !== selectedSubject.screening_no) {
      const confirmed = window.confirm(
        `文件名为 ${filenameStem}，当前筛选号为 ${selectedSubject.screening_no}，确认继续？`,
      );
      if (!confirmed) return;
    }
    setBusyKey("upload");
    try {
      const packet = await pdfPacketsApi.uploadPacket({
        file: selectedFile,
        projectId: selectedProjectId,
        centerId: selectedCenterId,
        subjectId: selectedSubjectId,
      });
      setMessage("资料包已上传并完成识别");
      await loadPackets(selectedProjectId, selectedCenterId, selectedSubjectId);
      setSelectedPacketId(packet.id);
      await loadSegments(packet.id);
    } catch {
      setMessage("资料包上传失败");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleAnalyze() {
    if (!selectedPacketId) return;
    setBusyKey(`analyze:${selectedPacketId}`);
    try {
      const packet = await pdfPacketsApi.analyzePacket(selectedPacketId);
      setMessage("识别已完成");
      await loadPackets(selectedProjectId, selectedCenterId, selectedSubjectId);
      setSelectedPacketId(packet.id);
      await loadSegments(packet.id);
    } catch {
      setMessage("识别失败或已有片段入库");
    } finally {
      setBusyKey(null);
    }
  }

  async function handlePreview(page?: number) {
    if (!selectedPacketId) return;
    try {
      const blob = await pdfPacketsApi.previewPacket(selectedPacketId);
      openBlob(blob, page);
    } catch {
      setMessage("预览失败");
    }
  }

  async function handleSaveSegment(segment: PdfPacketSegment) {
    const form = segmentForms[segment.id];
    if (!form) return;
    setBusyKey(`save:${segment.id}`);
    try {
      await pdfPacketsApi.updateSegment(segment.id, {
        page_start: Number(form.page_start),
        page_end: Number(form.page_end),
        detected_name: form.detected_name.trim() || null,
        subject_item_id: form.subject_item_id || null,
      });
      setMessage("片段已保存");
      await loadSegments();
    } catch {
      setMessage("片段保存失败");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleUploadSegment(segment: PdfPacketSegment) {
    const form = segmentForms[segment.id];
    const subjectItemId = form?.subject_item_id || segment.suggested_subject_item_id;
    if (!subjectItemId) {
      setMessage("请选择资料项");
      return;
    }
    setBusyKey(`segment:${segment.id}`);
    try {
      await pdfPacketsApi.uploadSegment(segment.id, subjectItemId);
      setMessage("片段已上传到资料项");
      await loadSegments();
      await loadSubjectItems();
    } catch {
      setMessage("片段上传失败");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleDeleteSegment(segment: PdfPacketSegment) {
    if (!window.confirm(`确认删除片段 p${segment.page_start}-${segment.page_end}？`)) return;
    setBusyKey(`delete:${segment.id}`);
    try {
      await pdfPacketsApi.deleteSegment(segment.id);
      setMessage("片段已删除");
      await loadSegments();
    } catch {
      setMessage("片段删除失败");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleCreateSegment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedPacketId) return;
    setBusyKey("new-segment");
    try {
      await pdfPacketsApi.createSegment(selectedPacketId, {
        page_start: Number(newSegment.page_start),
        page_end: Number(newSegment.page_end),
        detected_name: newSegment.detected_name.trim() || null,
        detected_code: null,
        confidence: 0,
        suggested_subject_item_id: newSegment.subject_item_id || null,
        subject_item_id: newSegment.subject_item_id || null,
        status: "pending",
        ocr_text: null,
      });
      setNewSegment(emptySegment);
      setMessage("片段已新增");
      await loadSegments();
    } catch {
      setMessage("新增片段失败");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleDeletePacket(packet: PdfPacket) {
    if (!window.confirm(`确认删除资料包：${packet.original_name}？`)) return;
    setBusyKey(`packet-delete:${packet.id}`);
    try {
      await pdfPacketsApi.deletePacket(packet.id);
      setMessage("资料包已删除");
      await loadPackets(selectedProjectId, selectedCenterId, selectedSubjectId);
    } catch {
      setMessage("资料包删除失败");
    } finally {
      setBusyKey(null);
    }
  }

  if (!canRead) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-semibold tracking-normal text-slate-950">PDF资料包</h1>
        <Card>
          <CardContent className="py-8 text-sm text-slate-600">
            当前账号没有PDF资料包查看权限
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">PDF资料包</h1>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={() => void loadPackets()}>
            <RefreshCw className="size-4" aria-hidden="true" />
            刷新
          </Button>
          {canWrite && (
            <Button asChild disabled={!selectedSubjectId || busyKey === "upload"}>
              <label>
                <Upload className="size-4" aria-hidden="true" />
                上传资料包
                <input
                  type="file"
                  accept="application/pdf,.pdf"
                  className="hidden"
                  onChange={handleUpload}
                />
              </label>
            </Button>
          )}
        </div>
      </div>

      {message && <Badge tone={message.includes("失败") ? "danger" : "success"}>{message}</Badge>}

      <section className="grid gap-4 xl:grid-cols-[360px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>资料包筛选</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Field label="项目">
              <SelectField
                value={selectedProjectId || ""}
                onChange={(event) => setSelectedProjectId(Number(event.target.value))}
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
            <Field label="中心">
              <SelectField
                value={selectedCenterId || ""}
                onChange={(event) => setSelectedCenterId(Number(event.target.value))}
              >
                <option value="" disabled>
                  选择中心
                </option>
                {centersForProject.map((center) => (
                  <option key={center.id} value={center.id}>
                    {center.name}
                  </option>
                ))}
              </SelectField>
            </Field>
            <Field label="筛选号">
              <SelectField
                value={selectedSubjectId || ""}
                onChange={(event) => setSelectedSubjectId(Number(event.target.value))}
              >
                <option value="" disabled>
                  选择筛选号
                </option>
                {subjects.map((subject) => (
                  <option key={subject.id} value={subject.id}>
                    {subject.screening_no}
                  </option>
                ))}
              </SelectField>
            </Field>
            <div className="space-y-2">
              {packets.length === 0 ? (
                <div className="rounded-md border border-dashed border-slate-200 px-3 py-3 text-sm text-slate-500">
                  暂无资料包
                </div>
              ) : (
                packets.map((packet) => (
                  <button
                    key={packet.id}
                    type="button"
                    onClick={() => setSelectedPacketId(packet.id)}
                    className={`w-full rounded-md border px-3 py-3 text-left text-sm transition ${
                      selectedPacketId === packet.id
                        ? "border-slate-900 bg-slate-50"
                        : "border-slate-200 bg-white hover:bg-slate-50"
                    }`}
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="truncate font-medium text-slate-900">
                        <FileSearch className="mr-1 inline size-4" aria-hidden="true" />
                        {packet.original_name}
                      </span>
                      <Badge tone={statusTone(packet.status)}>{statusLabel(packet.status)}</Badge>
                    </span>
                    <span className="mt-2 block text-xs text-slate-500">
                      {packet.page_count}页 · {formatDateTime(packet.uploaded_at)}
                    </span>
                  </button>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <CardTitle>识别片段</CardTitle>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    onClick={() => void handlePreview()}
                    disabled={!selectedPacketId}
                  >
                    <Eye className="size-4" aria-hidden="true" />
                    预览原包
                  </Button>
                  {canWrite && (
                    <Button
                      variant="secondary"
                      onClick={() => void handleAnalyze()}
                      disabled={!selectedPacketId || busyKey === `analyze:${selectedPacketId}`}
                    >
                      <RefreshCw className="size-4" aria-hidden="true" />
                      重新识别
                    </Button>
                  )}
                  {canDelete && selectedPacket && (
                    <Button
                      variant="secondary"
                      className="border-rose-200 text-rose-700 hover:bg-rose-50"
                      onClick={() => void handleDeletePacket(selectedPacket)}
                      disabled={busyKey === `packet-delete:${selectedPacket.id}`}
                    >
                      <Trash2 className="size-4" aria-hidden="true" />
                      删除资料包
                    </Button>
                  )}
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {selectedPacket && (
                <div className="mb-4 grid gap-3 text-sm text-slate-600 md:grid-cols-3">
                  <div>
                    <span className="text-slate-400">筛选号</span>
                    <p className="mt-1 font-medium text-slate-900">{selectedPacket.screening_no}</p>
                  </div>
                  <div>
                    <span className="text-slate-400">文件名筛选号</span>
                    <p className="mt-1 font-medium text-slate-900">
                      {selectedPacket.filename_screening_no || "-"}
                    </p>
                  </div>
                  <div>
                    <span className="text-slate-400">识别结果</span>
                    <p className="mt-1 font-medium text-slate-900">
                      {selectedPacket.analysis_summary || "-"}
                    </p>
                  </div>
                </div>
              )}

              {segments.length === 0 ? (
                <div className="rounded-md border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-500">
                  暂无识别片段
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-slate-200 text-sm">
                    <thead>
                      <tr className="text-left text-xs font-medium uppercase text-slate-500">
                        <th className="px-2 py-2">页码</th>
                        <th className="px-2 py-2">识别名称</th>
                        <th className="px-2 py-2">资料项</th>
                        <th className="px-2 py-2">状态</th>
                        <th className="px-2 py-2">操作</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {segments.map((segment) => {
                        const form = segmentForms[segment.id] ?? {
                          page_start: segment.page_start,
                          page_end: segment.page_end,
                          detected_name: segment.detected_name ?? "",
                          subject_item_id:
                            segment.subject_item_id ?? segment.suggested_subject_item_id ?? 0,
                        };
                        return (
                          <tr key={segment.id} className="align-top">
                            <td className="px-2 py-3">
                              <div className="flex items-center gap-1">
                                <input
                                  className={inputClassName("h-9 w-16")}
                                  type="number"
                                  min={1}
                                  value={form.page_start}
                                  disabled={Boolean(segment.file_asset_id)}
                                  onChange={(event) =>
                                    setSegmentForms((current) => ({
                                      ...current,
                                      [segment.id]: {
                                        ...form,
                                        page_start: Number(event.target.value),
                                      },
                                    }))
                                  }
                                />
                                <span className="text-slate-400">-</span>
                                <input
                                  className={inputClassName("h-9 w-16")}
                                  type="number"
                                  min={1}
                                  value={form.page_end}
                                  disabled={Boolean(segment.file_asset_id)}
                                  onChange={(event) =>
                                    setSegmentForms((current) => ({
                                      ...current,
                                      [segment.id]: {
                                        ...form,
                                        page_end: Number(event.target.value),
                                      },
                                    }))
                                  }
                                />
                              </div>
                              <button
                                type="button"
                                className="mt-2 text-xs text-slate-500 hover:text-slate-900"
                                onClick={() => void handlePreview(segment.page_start)}
                              >
                                预览
                              </button>
                            </td>
                            <td className="px-2 py-3">
                              <input
                                className={inputClassName("h-9 min-w-40")}
                                value={form.detected_name}
                                disabled={Boolean(segment.file_asset_id)}
                                onChange={(event) =>
                                  setSegmentForms((current) => ({
                                    ...current,
                                    [segment.id]: {
                                      ...form,
                                      detected_name: event.target.value,
                                    },
                                  }))
                                }
                              />
                              <p className="mt-2 text-xs text-slate-500">
                                置信度 {(segment.confidence * 100).toFixed(0)}%
                              </p>
                            </td>
                            <td className="px-2 py-3">
                              <SelectField
                                value={form.subject_item_id || ""}
                                disabled={Boolean(segment.file_asset_id)}
                                onChange={(event) =>
                                  setSegmentForms((current) => ({
                                    ...current,
                                    [segment.id]: {
                                      ...form,
                                      subject_item_id: Number(event.target.value),
                                    },
                                  }))
                                }
                              >
                                <option value="">选择资料项</option>
                                {subjectItems.map((item) => (
                                  <option key={item.id} value={item.id}>
                                    {item.item_name}
                                  </option>
                                ))}
                              </SelectField>
                              {segment.suggested_subject_item_id && (
                                <p className="mt-2 text-xs text-slate-500">
                                  建议：{subjectItemNameById.get(segment.suggested_subject_item_id)}
                                </p>
                              )}
                            </td>
                            <td className="px-2 py-3">
                              <Badge tone={statusTone(segment.status)}>
                                {statusLabel(segment.status)}
                              </Badge>
                              {segment.file_asset_id && (
                                <p className="mt-2 text-xs text-slate-500">
                                  文件 #{segment.file_asset_id}
                                </p>
                              )}
                            </td>
                            <td className="px-2 py-3">
                              <div className="flex flex-wrap gap-1">
                                {canWrite && !segment.file_asset_id && (
                                  <>
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => void handleSaveSegment(segment)}
                                      disabled={busyKey === `save:${segment.id}`}
                                    >
                                      <Save className="size-4" aria-hidden="true" />
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => void handleUploadSegment(segment)}
                                      disabled={busyKey === `segment:${segment.id}`}
                                    >
                                      <Upload className="size-4" aria-hidden="true" />
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="ghost"
                                      onClick={() => void handleDeleteSegment(segment)}
                                      disabled={busyKey === `delete:${segment.id}`}
                                    >
                                      <Trash2 className="size-4" aria-hidden="true" />
                                    </Button>
                                  </>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>

          {canWrite && selectedPacket && (
            <Card>
              <CardHeader>
                <CardTitle>新增片段</CardTitle>
              </CardHeader>
              <CardContent>
                <form
                  className="grid gap-3 md:grid-cols-[120px_120px_1fr_1fr_auto]"
                  onSubmit={handleCreateSegment}
                >
                  <Field label="起始页">
                    <input
                      className={inputClassName()}
                      type="number"
                      min={1}
                      value={newSegment.page_start}
                      onChange={(event) =>
                        setNewSegment((current) => ({
                          ...current,
                          page_start: Number(event.target.value),
                        }))
                      }
                    />
                  </Field>
                  <Field label="结束页">
                    <input
                      className={inputClassName()}
                      type="number"
                      min={1}
                      value={newSegment.page_end}
                      onChange={(event) =>
                        setNewSegment((current) => ({
                          ...current,
                          page_end: Number(event.target.value),
                        }))
                      }
                    />
                  </Field>
                  <Field label="识别名称">
                    <input
                      className={inputClassName()}
                      value={newSegment.detected_name}
                      onChange={(event) =>
                        setNewSegment((current) => ({
                          ...current,
                          detected_name: event.target.value,
                        }))
                      }
                    />
                  </Field>
                  <Field label="资料项">
                    <SelectField
                      value={newSegment.subject_item_id || ""}
                      onChange={(event) =>
                        setNewSegment((current) => ({
                          ...current,
                          subject_item_id: Number(event.target.value),
                        }))
                      }
                    >
                      <option value="">选择资料项</option>
                      {subjectItems.map((item) => (
                        <option key={item.id} value={item.id}>
                          {item.item_name}
                        </option>
                      ))}
                    </SelectField>
                  </Field>
                  <div className="flex items-end">
                    <Button type="submit" disabled={busyKey === "new-segment"}>
                      <Plus className="size-4" aria-hidden="true" />
                      新增
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          )}

          {selectedPacket?.error_message && (
            <Card>
              <CardHeader>
                <CardTitle>失败原因</CardTitle>
              </CardHeader>
              <CardContent>
                <TextAreaField value={selectedPacket.error_message} readOnly />
              </CardContent>
            </Card>
          )}
        </div>
      </section>
    </div>
  );
}
