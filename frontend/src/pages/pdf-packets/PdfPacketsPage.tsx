import {
  CheckCircle2,
  Eye,
  FileSearch,
  GitMerge,
  Plus,
  RefreshCw,
  RotateCcw,
  Scissors,
  Trash2,
  Upload,
} from "lucide-react";
import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";

import { PdfPreviewDialog } from "@/components/files/PdfPreviewDialog";
import { ManagementPageHeader, ManagementStatCard } from "@/components/management/ManagementPage";
import { DocumentExtractedFieldsPanel } from "@/components/document-fields/DocumentExtractedFieldsPanel";
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
import type {
  PdfPacket,
  PdfPacketAnalysisReport,
  PdfPacketSegment,
  PdfPacketSegmentSplitItem,
} from "@/types/pdf-packets";

type EditableSegment = {
  page_start: number;
  page_end: number;
  detected_name: string;
  subject_item_id: number;
};
type BadgeTone = "neutral" | "success" | "warning" | "danger";
type PreviewDialog = {
  title: string;
  url: string | null;
  loading: boolean;
  error: string | null;
};

const emptySegment = {
  page_start: 1,
  page_end: 1,
  detected_name: "",
  subject_item_id: 0,
};

function editableFromSegment(segment: PdfPacketSegment): EditableSegment {
  return {
    page_start: segment.page_start,
    page_end: segment.page_end,
    detected_name: segment.detected_name ?? "",
    subject_item_id: segment.subject_item_id ?? segment.suggested_subject_item_id ?? 0,
  };
}

function segmentFormChanged(segment: PdfPacketSegment, form: EditableSegment) {
  const current = editableFromSegment(segment);
  return (
    Number(form.page_start) !== current.page_start ||
    Number(form.page_end) !== current.page_end ||
    form.detected_name.trim() !== current.detected_name ||
    Number(form.subject_item_id || 0) !== current.subject_item_id
  );
}

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    uploaded: "已入库",
    processing: "处理中",
    ready: "已识别",
    failed: "失败",
    pending: "待确认",
    auto_confirmed_candidate: "高置信候选",
    pending_review: "需核对",
    manually_confirmed: "人工已确认",
    manually_modified: "人工已修改",
    unknown: "未识别",
  };
  return labels[status] ?? status;
}

function statusTone(status: string): BadgeTone {
  if (status === "ready" || status === "uploaded") return "success";
  if (status === "failed") return "danger";
  if (status === "pending_review" || status === "unknown") return "warning";
  if (status === "manually_confirmed" || status === "auto_confirmed_candidate") return "success";
  return "neutral";
}

function confidenceTone(confidence: number): BadgeTone {
  if (confidence >= 0.85) return "success";
  if (confidence >= 0.6) return "warning";
  return "danger";
}

export function PdfPacketsPage() {
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canRead = hasPermission("pdf_packets:read");
  const canWrite = hasPermission("pdf_packets:write");
  const canDelete = hasPermission("pdf_packets:delete");
  const canWriteFiles = hasPermission("files:write");
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
  const selectedPacketIdRef = useRef(0);
  const [segmentForms, setSegmentForms] = useState<Record<number, EditableSegment>>({});
  const [newSegment, setNewSegment] = useState<EditableSegment>(emptySegment);
  const [selectedSegmentIds, setSelectedSegmentIds] = useState<number[]>([]);
  const [splitSegmentId, setSplitSegmentId] = useState(0);
  const [splitRows, setSplitRows] = useState<PdfPacketSegmentSplitItem[]>([]);
  const [mergeSubjectItemId, setMergeSubjectItemId] = useState(0);
  const [analysisReport, setAnalysisReport] = useState<PdfPacketAnalysisReport | null>(null);
  const [reasonSegmentId, setReasonSegmentId] = useState(0);
  const [undoSnapshots, setUndoSnapshots] = useState<Record<number, EditableSegment>>({});
  const [message, setMessage] = useState<string | null>(null);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [previewDialog, setPreviewDialog] = useState<PreviewDialog | null>(null);
  const [previewFrameKey, setPreviewFrameKey] = useState(0);
  const previewUrlRef = useRef<string | null>(null);

  const selectedSubject = subjects.find((subject) => subject.id === selectedSubjectId);
  const selectedPacket = packets.find((packet) => packet.id === selectedPacketId);
  const centersForProject = centers.filter((center) => center.project_id === selectedProjectId);

  const subjectItemNameById = useMemo(
    () => new Map(subjectItems.map((item) => [item.id, item.item_name])),
    [subjectItems],
  );
  const selectedSegment = segments.find((segment) => segment.id === splitSegmentId);
  const reasonSegment = segments.find((segment) => segment.id === reasonSegmentId);
  const reasonReportSegment = reasonSegment
    ? analysisReport?.segments.find(
        (segment) =>
          segment.page_start === reasonSegment.page_start && segment.page_end === reasonSegment.page_end,
      )
    : null;
  const reasonPages = reasonSegment
    ? (analysisReport?.pages ?? []).filter(
        (page) => page.page_no >= reasonSegment.page_start && page.page_no <= reasonSegment.page_end,
      )
    : [];

  useEffect(() => {
    return () => {
      if (previewUrlRef.current) {
        window.URL.revokeObjectURL(previewUrlRef.current);
      }
    };
  }, []);

  function clearPreviewUrl() {
    if (previewUrlRef.current) {
      window.URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
  }

  function closePreviewDialog() {
    clearPreviewUrl();
    setPreviewDialog(null);
  }

  function showPreviewLoading(title: string) {
    clearPreviewUrl();
    setPreviewDialog({ title, url: null, loading: true, error: null });
  }

  function showPreviewBlob(title: string, blob: Blob, page?: number) {
    clearPreviewUrl();
    const url = `${window.URL.createObjectURL(blob)}${page ? `#page=${page}` : ""}`;
    previewUrlRef.current = url.split("#")[0];
    setPreviewFrameKey((current) => current + 1);
    setPreviewDialog({ title, url, loading: false, error: null });
  }

  function showPreviewError(title: string, error: string) {
    clearPreviewUrl();
    setPreviewDialog({ title, url: null, loading: false, error });
  }

  function selectPacketId(packetId: number) {
    selectedPacketIdRef.current = packetId;
    setSelectedPacketId(packetId);
  }

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
      selectPacketId(0);
      return;
    }
    const data = await pdfPacketsApi.listPackets({
      project_id: projectId,
      center_id: centerId,
      subject_id: subjectId || undefined,
    });
    setPackets(data);
    const nextPacketId =
      selectedPacketIdRef.current && data.some((packet) => packet.id === selectedPacketIdRef.current)
        ? selectedPacketIdRef.current
        : data[0]?.id ?? 0;
    selectPacketId(nextPacketId);
  }

  async function loadSegments(packetId = selectedPacketId) {
    if (!packetId) {
      setSegments([]);
      setSegmentForms({});
      setSelectedSegmentIds([]);
      setReasonSegmentId(0);
      setSplitSegmentId(0);
      return;
    }
    const data = await pdfPacketsApi.listSegments(packetId);
    if (selectedPacketIdRef.current !== packetId) return;
    setSegments(data);
    setSelectedSegmentIds((current) =>
      current.filter((id) => data.some((segment) => segment.id === id)),
    );
    setUndoSnapshots((current) =>
      Object.fromEntries(
        Object.entries(current).filter(([id]) =>
          data.some((segment) => segment.id === Number(id) && segment.file_asset_id == null),
        ),
      ),
    );
    setReasonSegmentId((current) => (data.some((segment) => segment.id === current) ? current : 0));
    setSplitSegmentId((current) => (data.some((segment) => segment.id === current) ? current : 0));
    setSegmentForms(
      Object.fromEntries(
        data.map((segment) => [segment.id, editableFromSegment(segment)]),
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
    selectedPacketIdRef.current = selectedPacketId;
  }, [selectedPacketId]);

  useEffect(() => {
    void loadSegments(selectedPacketId);
    setAnalysisReport(null);
    setUndoSnapshots({});
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
      selectPacketId(packet.id);
      await loadSegments(packet.id);
    } catch {
      setMessage("资料包上传失败");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleAnalyze(force = false) {
    if (!selectedPacketId) return;
    if (
      force &&
      !window.confirm("强制重新识别会覆盖人工确认/人工修改片段，确认继续？")
    ) {
      return;
    }
    setBusyKey(`analyze:${selectedPacketId}`);
    try {
      const packet = await pdfPacketsApi.reanalyzePacket(selectedPacketId, force);
      setMessage(force ? "强制重新识别已完成" : "识别已完成，人工确认片段已保留");
      await loadPackets(selectedProjectId, selectedCenterId, selectedSubjectId);
      selectPacketId(packet.id);
      await loadSegments(packet.id);
      await loadAnalysisReport(packet.id);
    } catch {
      setMessage("识别失败或已有片段入库");
    } finally {
      setBusyKey(null);
    }
  }

  async function loadAnalysisReport(packetId = selectedPacketId) {
    if (!packetId) return;
    try {
      const report = await pdfPacketsApi.getAnalysisReport(packetId);
      setAnalysisReport(report);
    } catch {
      setAnalysisReport(null);
      setMessage("暂无识别原因报告");
    }
  }

  async function handlePreview(page?: number) {
    if (!selectedPacketId) return;
    showPreviewLoading(page ? `原包预览 · 第 ${page} 页` : "原包预览");
    try {
      const blob = await pdfPacketsApi.previewPacket(selectedPacketId);
      showPreviewBlob(page ? `原包预览 · 第 ${page} 页` : "原包预览", blob, page);
    } catch {
      showPreviewError("原包预览", "预览失败，请稍后重试");
      setMessage("预览失败");
    }
  }

  async function handleSegmentPreview(segment: PdfPacketSegment) {
    const title = `片段预览 · p${segment.page_start}-${segment.page_end}`;
    showPreviewLoading(title);
    try {
      const blob = await pdfPacketsApi.previewSegment(segment.id);
      showPreviewBlob(title, blob);
    } catch {
      showPreviewError(title, "片段预览失败，请确认切分页范围和文件是否存在");
      setMessage("片段预览失败");
    }
  }

  async function saveSegmentForm(
    segment: PdfPacketSegment,
    form: EditableSegment,
    options: { undoSnapshot?: EditableSegment; message?: string; clearUndo?: boolean } = {},
  ) {
    if (segment.file_asset_id) return false;
    if (!segmentFormChanged(segment, form)) return true;
    setBusyKey(`auto-save:${segment.id}`);
    try {
      await pdfPacketsApi.updateSegment(segment.id, {
        page_start: Number(form.page_start),
        page_end: Number(form.page_end),
        detected_name: form.detected_name.trim() || null,
        subject_item_id: form.subject_item_id || null,
      });
      if (options.clearUndo) {
        setUndoSnapshots((current) => {
          const next = { ...current };
          delete next[segment.id];
          return next;
        });
      } else {
        setUndoSnapshots((current) => ({
          ...current,
          [segment.id]: options.undoSnapshot ?? editableFromSegment(segment),
        }));
      }
      setMessage(options.message ?? "片段已自动保存，可撤回");
      await loadSegments();
      return true;
    } catch {
      setMessage("自动保存失败，请检查页码是否冲突");
      return false;
    } finally {
      setBusyKey(null);
    }
  }

  async function handleAutoSaveSegment(segment: PdfPacketSegment, form = segmentForms[segment.id]) {
    if (!form || segment.file_asset_id) return;
    await saveSegmentForm(segment, form);
  }

  async function handleUndoSegment(segment: PdfPacketSegment) {
    const snapshot = undoSnapshots[segment.id];
    if (!snapshot || segment.file_asset_id) return;
    await saveSegmentForm(segment, snapshot, {
      undoSnapshot: editableFromSegment(segment),
      message: "片段已撤回到上次保存前",
      clearUndo: true,
    });
  }

  async function handleConfirmAndUploadSegment(segment: PdfPacketSegment) {
    const form = segmentForms[segment.id];
    const subjectItemId = form?.subject_item_id || segment.subject_item_id || segment.suggested_subject_item_id;
    if (!subjectItemId) {
      setMessage("请选择资料项");
      return;
    }
    if (form && segmentFormChanged(segment, form)) {
      const saved = await saveSegmentForm(segment, form, { message: "片段已自动保存" });
      if (!saved) return;
    }
    setBusyKey(`confirm-upload:${segment.id}`);
    try {
      await pdfPacketsApi.confirmSegment(selectedPacketId, segment.id, {
        subject_item_id: subjectItemId,
        detected_name: form?.detected_name?.trim() || segment.detected_name,
      });
      await pdfPacketsApi.uploadSegment(segment.id, subjectItemId);
      setMessage("片段已确认并上传");
      setUndoSnapshots((current) => {
        const next = { ...current };
        delete next[segment.id];
        return next;
      });
      await loadSegments();
      await loadSubjectItems();
    } catch {
      setMessage("确认上传失败");
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

  function toggleSelectedSegment(segmentId: number) {
    setSelectedSegmentIds((current) =>
      current.includes(segmentId)
        ? current.filter((id) => id !== segmentId)
        : [...current, segmentId],
    );
  }

  function startSplit(segment: PdfPacketSegment) {
    if (segment.page_start === segment.page_end) {
      setMessage("单页片段不能继续拆分");
      return;
    }
    const midpoint = Math.floor((segment.page_start + segment.page_end) / 2);
    const subjectItemId = segment.subject_item_id ?? segment.suggested_subject_item_id ?? null;
    setSplitSegmentId(segment.id);
    setSplitRows([
      {
        page_start: segment.page_start,
        page_end: midpoint,
        subject_item_id: subjectItemId,
        detected_name: segment.detected_name,
      },
      {
        page_start: midpoint + 1,
        page_end: segment.page_end,
        subject_item_id: subjectItemId,
        detected_name: segment.detected_name,
      },
    ]);
  }

  async function handleSplitSegment() {
    if (!selectedPacketId || !splitSegmentId) return;
    setBusyKey(`split:${splitSegmentId}`);
    try {
      await pdfPacketsApi.splitSegment(selectedPacketId, splitSegmentId, {
        splits: splitRows.map((row) => ({
          page_start: Number(row.page_start),
          page_end: Number(row.page_end),
          subject_item_id: row.subject_item_id || null,
          detected_name: row.detected_name?.trim() || null,
        })),
      });
      setMessage("片段已拆分");
      setSplitSegmentId(0);
      setSplitRows([]);
      await loadSegments();
      await loadAnalysisReport();
    } catch {
      setMessage("片段拆分失败，请检查页码是否连续且未越界");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleMergeSegments() {
    if (!selectedPacketId || selectedSegmentIds.length < 2) return;
    setBusyKey("merge-segments");
    try {
      await pdfPacketsApi.mergeSegments(selectedPacketId, {
        segment_ids: selectedSegmentIds,
        subject_item_id: mergeSubjectItemId || null,
      });
      setMessage("片段已合并");
      setSelectedSegmentIds([]);
      setMergeSubjectItemId(0);
      await loadSegments();
      await loadAnalysisReport();
    } catch {
      setMessage("片段合并失败，只能合并连续且未入库的片段");
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
      <div className="space-y-6">
        <ManagementPageHeader
          title="PDF资料包"
          description="页级识别、片段校正和确认入库"
          icon={FileSearch}
          badge="无权限"
          badgeTone="warning"
        />
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
      <ManagementPageHeader
        title="PDF资料包识别工作台"
        description="资料包筛选、页级识别、片段人工校正和确认入库"
        icon={FileSearch}
        badge="流程工具"
      />

      {message && <Badge tone={message.includes("失败") ? "danger" : "success"}>{message}</Badge>}

      <section className="grid gap-3 sm:grid-cols-4">
        <ManagementStatCard label="资料包" value={packets.length} detail={selectedSubject?.screening_no ?? "未选择筛选号"} icon={FileSearch} />
        <ManagementStatCard label="识别片段" value={segments.length} detail={selectedPacket ? statusLabel(selectedPacket.status) : "未选择资料包"} icon={Scissors} tone="teal" />
        <ManagementStatCard label="待确认" value={segments.filter((segment) => segment.status === "pending_review" || segment.status === "unknown").length} detail="需核对或未识别片段" icon={Eye} tone="amber" />
        <ManagementStatCard label="已入库" value={segments.filter((segment) => segment.file_asset_id).length} detail={selectedPacket?.analysis_summary ?? "等待识别"} icon={CheckCircle2} tone="slate" />
      </section>

      <Card>
        <CardHeader>
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <CardTitle>资料包筛选</CardTitle>
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
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 lg:grid-cols-4">
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
            <Field label="当前资料包">
              <SelectField
                value={selectedPacketId || ""}
                onChange={(event) => selectPacketId(Number(event.target.value))}
                disabled={packets.length === 0}
              >
                <option value="">{packets.length === 0 ? "暂无资料包" : "选择资料包"}</option>
                {packets.map((packet) => (
                  <option key={packet.id} value={packet.id}>
                    {packet.original_name} · {packet.page_count}页 · {statusLabel(packet.status)}
                  </option>
                ))}
              </SelectField>
            </Field>
          </div>
        </CardContent>
      </Card>

      <section className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1fr)_300px]">
        <div className="min-w-0 space-y-4">
          <Card>
            <CardHeader>
              <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                <CardTitle>识别片段</CardTitle>
                <div className="grid gap-2 sm:flex sm:flex-wrap sm:justify-end">
                  <Button
                    variant="secondary"
                    className="w-full justify-center sm:w-auto"
                    onClick={() => void handlePreview()}
                    disabled={!selectedPacketId}
                  >
                    <Eye className="size-4" aria-hidden="true" />
                    预览原包
                  </Button>
                  {canWrite && (
                    <Button
                      variant="secondary"
                      className="w-full justify-center sm:w-auto"
                      onClick={() => void handleAnalyze(false)}
                      disabled={!selectedPacketId || busyKey === `analyze:${selectedPacketId}`}
                    >
                      <RefreshCw className="size-4" aria-hidden="true" />
                      重新识别
                    </Button>
                  )}
                  {canWrite && (
                    <Button
                      variant="secondary"
                      className="w-full justify-center sm:w-auto"
                      onClick={() => void handleAnalyze(true)}
                      disabled={!selectedPacketId || busyKey === `analyze:${selectedPacketId}`}
                    >
                      <RefreshCw className="size-4" aria-hidden="true" />
                      强制重新识别
                    </Button>
                  )}
                  {canDelete && selectedPacket && (
                    <Button
                      variant="secondary"
                      className="w-full justify-center border-rose-200 text-rose-700 hover:bg-rose-50 sm:w-auto"
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

	              {canWrite && selectedPacket && (
	                <div className="mb-4 space-y-3 rounded-md border border-slate-200 bg-slate-50 p-3">
	                  {segments.length > 0 && (
                    <div className="grid min-w-0 gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
                      <Field label="合并后资料项">
                        <SelectField
                          value={mergeSubjectItemId || ""}
	                          onChange={(event) => setMergeSubjectItemId(Number(event.target.value))}
	                        >
	                          <option value="">沿用首个片段</option>
	                          {subjectItems.map((item) => (
	                            <option key={item.id} value={item.id}>
	                              {item.item_name}
	                            </option>
	                          ))}
	                        </SelectField>
	                      </Field>
                      <Button
                        type="button"
                        variant="secondary"
                        className="w-full justify-center md:w-auto"
                        onClick={() => void handleMergeSegments()}
                        disabled={selectedSegmentIds.length < 2 || busyKey === "merge-segments"}
                      >
	                        <GitMerge className="size-4" aria-hidden="true" />
	                        合并已选{selectedSegmentIds.length > 0 ? ` ${selectedSegmentIds.length} 段` : ""}
	                      </Button>
	                    </div>
	                  )}

	                  <div className="rounded-md border border-slate-200 bg-white p-3">
	                    <p className="mb-3 text-sm font-medium text-slate-900">新增片段</p>
	                    <form
	                      className="grid gap-3 md:grid-cols-[100px_100px_1fr_1fr_auto]"
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
	                  </div>

	                  {selectedSegment && (
                    <div className="space-y-3 rounded-md border border-slate-200 bg-white p-3">
                      <div className="flex flex-col gap-1 text-sm text-slate-600 md:flex-row md:items-center md:justify-between">
                        <span>
                          拆分 p{selectedSegment.page_start}-{selectedSegment.page_end}
                        </span>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() =>
                            setSplitRows((current) => [
                              ...current,
                              {
                                page_start: current[current.length - 1]?.page_end + 1 || selectedSegment.page_end,
                                page_end: selectedSegment.page_end,
                                subject_item_id:
                                  selectedSegment.subject_item_id ??
                                  selectedSegment.suggested_subject_item_id ??
                                  null,
                                detected_name: selectedSegment.detected_name,
                              },
                            ])
                          }
                        >
                          <Plus className="size-4" aria-hidden="true" />
                          增加行
                        </Button>
                      </div>
                      <div className="space-y-2">
                        {splitRows.map((row, index) => (
                          <div
                            key={`${index}-${row.page_start}-${row.page_end}`}
                            className="grid gap-2 md:grid-cols-[90px_90px_1fr_1fr_auto]"
                          >
                            <input
                              className={inputClassName("h-9")}
                              type="number"
                              min={selectedSegment.page_start}
                              max={selectedSegment.page_end}
                              value={row.page_start}
                              onChange={(event) =>
                                setSplitRows((current) =>
                                  current.map((item, itemIndex) =>
                                    itemIndex === index
                                      ? { ...item, page_start: Number(event.target.value) }
                                      : item,
                                  ),
                                )
                              }
                            />
                            <input
                              className={inputClassName("h-9")}
                              type="number"
                              min={selectedSegment.page_start}
                              max={selectedSegment.page_end}
                              value={row.page_end}
                              onChange={(event) =>
                                setSplitRows((current) =>
                                  current.map((item, itemIndex) =>
                                    itemIndex === index
                                      ? { ...item, page_end: Number(event.target.value) }
                                      : item,
                                  ),
                                )
                              }
                            />
                            <input
                              className={inputClassName("h-9")}
                              value={row.detected_name ?? ""}
                              onChange={(event) =>
                                setSplitRows((current) =>
                                  current.map((item, itemIndex) =>
                                    itemIndex === index
                                      ? { ...item, detected_name: event.target.value }
                                      : item,
                                  ),
                                )
                              }
                            />
                            <SelectField
                              value={row.subject_item_id || ""}
                              onChange={(event) =>
                                setSplitRows((current) =>
                                  current.map((item, itemIndex) =>
                                    itemIndex === index
                                      ? { ...item, subject_item_id: Number(event.target.value) || null }
                                      : item,
                                  ),
                                )
                              }
                            >
                              <option value="">选择资料项</option>
                              {subjectItems.map((item) => (
                                <option key={item.id} value={item.id}>
                                  {item.item_name}
                                </option>
                              ))}
                            </SelectField>
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              onClick={() =>
                                setSplitRows((current) =>
                                  current.filter((_, itemIndex) => itemIndex !== index),
                                )
                              }
                              disabled={splitRows.length <= 2}
                              title="删除拆分行"
                            >
                              <Trash2 className="size-4" aria-hidden="true" />
                            </Button>
                          </div>
                        ))}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Button
                          type="button"
                          onClick={() => void handleSplitSegment()}
                          disabled={splitRows.length < 2 || busyKey === `split:${splitSegmentId}`}
                        >
                          <Scissors className="size-4" aria-hidden="true" />
                          提交拆分
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          onClick={() => {
                            setSplitSegmentId(0);
                            setSplitRows([]);
                          }}
                        >
                          取消
                        </Button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {segments.length === 0 ? (
                <div className="rounded-md border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-500">
                  暂无识别片段
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="min-w-[840px] divide-y divide-slate-200 text-sm">
                    <thead>
                      <tr className="text-left text-xs font-medium uppercase text-slate-500">
                        <th className="px-2 py-2">选择</th>
                        <th className="px-2 py-2">页码</th>
                        <th className="px-2 py-2">识别名称</th>
                        <th className="px-2 py-2">资料项</th>
	                        <th className="px-2 py-2">置信度</th>
	                        <th className="px-2 py-2 whitespace-nowrap">状态</th>
	                        <th className="sticky right-20 z-10 w-32 bg-white px-2 py-2 shadow-[-8px_0_12px_-12px_rgba(15,23,42,0.35)]">
	                          确认上传
	                        </th>
	                        <th className="sticky right-0 z-10 w-20 bg-white px-2 py-2">操作</th>
	                      </tr>
	                    </thead>
	                    <tbody className="divide-y divide-slate-100">
	                      {segments.map((segment) => {
	                        const form = segmentForms[segment.id] ?? editableFromSegment(segment);
	                        const hasSubjectItem = Boolean(
	                          form.subject_item_id || segment.subject_item_id || segment.suggested_subject_item_id,
	                        );
	                        return (
                          <tr key={segment.id} className="align-top">
	                            <td className="px-2 py-3 whitespace-nowrap">
                              <input
                                type="checkbox"
                                checked={selectedSegmentIds.includes(segment.id)}
                                disabled={Boolean(segment.file_asset_id)}
                                onChange={() => toggleSelectedSegment(segment.id)}
                              />
                            </td>
	                            <td className="px-2 py-3 whitespace-nowrap">
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
	                                  onBlur={() => void handleAutoSaveSegment(segment)}
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
	                                  onBlur={() => void handleAutoSaveSegment(segment)}
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
	                                onBlur={() => void handleAutoSaveSegment(segment)}
	                              />
                              <p className="mt-2 text-xs text-slate-500">
                                编码：{segment.detected_code || "-"}
                              </p>
                            </td>
                            <td className="px-2 py-3">
                              <SelectField
	                                value={form.subject_item_id || ""}
	                                disabled={Boolean(segment.file_asset_id)}
	                                onChange={(event) => {
	                                  const nextForm = {
	                                    ...form,
	                                    subject_item_id: Number(event.target.value),
	                                  };
	                                  setSegmentForms((current) => ({
	                                    ...current,
	                                    [segment.id]: nextForm,
	                                  }));
	                                  void handleAutoSaveSegment(segment, nextForm);
	                                }}
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
                              <Badge tone={confidenceTone(segment.confidence)}>
                                {(segment.confidence * 100).toFixed(0)}%
                              </Badge>
                              <button
                                type="button"
                                className="mt-2 block text-xs text-slate-500 hover:text-slate-900"
                                onClick={() => {
                                  setReasonSegmentId(
                                    reasonSegmentId === segment.id ? 0 : segment.id,
                                  );
                                  if (!analysisReport) void loadAnalysisReport();
                                }}
                              >
                                识别原因
                              </button>
                            </td>
	                            <td className="px-2 py-3 whitespace-nowrap">
	                              <Badge tone={statusTone(segment.status)}>
                                {statusLabel(segment.status)}
                              </Badge>
                              {segment.file_asset_id && (
                                <p className="mt-2 text-xs text-slate-500">
                                  文件 #{segment.file_asset_id}
                                </p>
	                              )}
	                            </td>
		                            <td className="sticky right-20 bg-white px-2 py-3 shadow-[-8px_0_12px_-12px_rgba(15,23,42,0.35)]">
		                              {segment.file_asset_id ? (
		                                <Badge tone="success">已入库</Badge>
		                              ) : (
		                                <Button
		                                  size="sm"
		                                  className="min-w-28 whitespace-nowrap"
		                                  onClick={() => void handleConfirmAndUploadSegment(segment)}
	                                  disabled={
	                                    !canWrite ||
	                                    !hasSubjectItem ||
	                                    busyKey === `confirm-upload:${segment.id}` ||
	                                    busyKey === `auto-save:${segment.id}`
	                                  }
	                                  title={hasSubjectItem ? "确认并上传" : "请选择资料项"}
	                                >
	                                  <CheckCircle2 className="size-4" aria-hidden="true" />
	                                  确认并上传
	                                </Button>
	                              )}
	                            </td>
		                            <td className="sticky right-0 bg-white px-2 py-3">
	                              <div className="flex flex-wrap gap-1">
	                                {canWrite && !segment.file_asset_id && (
	                                  <>
	                                    <Button
	                                      size="sm"
	                                      variant="ghost"
                                      onClick={() => startSplit(segment)}
                                      disabled={
                                        segment.page_start === segment.page_end ||
                                        busyKey === `split:${segment.id}`
                                      }
                                      title="拆分"
	                                    >
	                                      <Scissors className="size-4" aria-hidden="true" />
	                                    </Button>
	                                    {undoSnapshots[segment.id] && (
	                                      <Button
	                                        size="sm"
	                                        variant="ghost"
	                                        onClick={() => void handleUndoSegment(segment)}
	                                        disabled={busyKey === `auto-save:${segment.id}`}
	                                        title="撤回到上次保存前"
	                                      >
	                                        <RotateCcw className="size-4" aria-hidden="true" />
	                                      </Button>
	                                    )}
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
        <Card className="min-w-0 xl:sticky xl:top-4 xl:max-h-[calc(100vh-2rem)] xl:overflow-auto">
	          <CardHeader>
	            <div className="flex items-center justify-between gap-2">
	              <CardTitle>识别原因</CardTitle>
	              <Button
	                type="button"
	                size="sm"
	                variant="secondary"
	                onClick={() => void loadAnalysisReport()}
	                disabled={!selectedPacketId}
	              >
	                <RefreshCw className="size-4" aria-hidden="true" />
	                刷新
	              </Button>
	            </div>
	          </CardHeader>
	          <CardContent>
	            {!reasonSegment ? (
	              <div className="rounded-md border border-dashed border-slate-200 px-3 py-8 text-center text-sm text-slate-500">
	                点击片段表中的“识别原因”查看匹配依据
	              </div>
	            ) : (
	              <div className="space-y-3 text-sm">
	                <div>
	                  <p className="font-medium text-slate-900">
	                    p{reasonSegment.page_start}-{reasonSegment.page_end} ·{" "}
	                    {reasonSegment.detected_name || "-"}
	                  </p>
	                  <p className="mt-1 text-slate-500">
	                    置信度 {(reasonSegment.confidence * 100).toFixed(0)}% ·{" "}
	                    {statusLabel(reasonSegment.status)}
	                  </p>
	                </div>

                    <div className="rounded-md border border-slate-200 bg-white p-3">
                      <div className="mb-3 flex aspect-[4/3] items-center justify-center rounded-md border border-dashed border-slate-200 bg-slate-50 text-slate-400">
                        <div className="text-center">
                          <FileSearch className="mx-auto size-8" aria-hidden="true" />
                          <p className="mt-2 text-xs">
                            p{reasonSegment.page_start}-{reasonSegment.page_end}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center justify-between gap-2">
                        <div>
                          <p className="font-medium text-slate-900">片段预览</p>
                          <p className="mt-1 text-xs text-slate-500">
                            仅打开 p{reasonSegment.page_start}-{reasonSegment.page_end} 切分页
                          </p>
                        </div>
                        <Button
                          type="button"
                          size="sm"
                          variant="secondary"
                          onClick={() => void handleSegmentPreview(reasonSegment)}
                        >
                          <Eye className="size-4" aria-hidden="true" />
                          放大
                        </Button>
                      </div>
                    </div>

                    <DocumentExtractedFieldsPanel
                      title="字段核查"
                      segmentId={reasonSegment.id}
                      canWrite={canWriteFiles}
                      defaultOpen
                      refreshKey={reasonSegment.id}
                      onChanged={() => void loadSegments()}
                    />

	                {!analysisReport ? (
	                  <div className="rounded-md border border-dashed border-slate-200 bg-white px-3 py-3 text-slate-500">
	                    暂无调试报告
	                  </div>
	                ) : (
	                  <>
	                    <div className="rounded-md border border-slate-200 bg-white p-3">
	                      <p className="font-medium text-slate-900">片段结论</p>
	                      <p className="mt-2 text-slate-600">
	                        {reasonReportSegment?.reason || "未记录片段级原因"}
	                      </p>
	                      {reasonReportSegment?.page_reasons?.length ? (
	                        <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-600">
	                          {reasonReportSegment.page_reasons.map((reason, index) => (
	                            <li key={`${index}-${reason}`}>{reason}</li>
	                          ))}
	                        </ul>
	                      ) : null}
	                    </div>

	                    <div className="space-y-2">
	                      {reasonPages.map((page) => (
	                        <details
	                          key={page.page_no}
	                          className="rounded-md border border-slate-200 bg-white p-3"
	                          open={reasonPages.length === 1}
	                        >
	                          <summary className="cursor-pointer font-medium text-slate-900">
	                            第 {page.page_no} 页 · {page.display_name || page.doc_type || "未识别"} ·{" "}
	                            {(page.confidence * 100).toFixed(0)}%
	                          </summary>
	                          <div className="mt-3 space-y-3">
	                            <div>
	                              <p className="text-xs font-medium text-slate-500">标题命中</p>
	                              <p className="mt-1 text-slate-700">
	                                {page.matched_title?.join("、") || "-"}
	                              </p>
	                            </div>
	                            <div>
	                              <p className="text-xs font-medium text-slate-500">特征命中</p>
	                              <p className="mt-1 text-slate-700">
	                                {page.matched_features?.join("、") || "-"}
	                              </p>
	                            </div>
	                            <div>
	                              <p className="text-xs font-medium text-slate-500">负向命中</p>
	                              <p className="mt-1 text-slate-700">
	                                {page.negative_hits?.join("、") || "-"}
	                              </p>
	                            </div>
	                            <div>
	                              <p className="text-xs font-medium text-slate-500">原因</p>
	                              <p className="mt-1 text-slate-700">{page.reason || "-"}</p>
	                            </div>
	                            <div>
	                              <p className="text-xs font-medium text-slate-500">页首/页尾</p>
	                              <pre className="mt-1 max-h-40 overflow-auto rounded bg-slate-100 p-2 text-xs text-slate-700">
	                                {[...(page.head_lines ?? []), "...", ...(page.tail_lines ?? [])].join(
	                                  "\n",
	                                )}
	                              </pre>
	                            </div>
	                            <div>
	                              <p className="text-xs font-medium text-slate-500">归一化文本</p>
	                              <pre className="mt-1 max-h-40 overflow-auto rounded bg-slate-100 p-2 text-xs text-slate-700">
	                                {page.normalized_text || page.raw_text || "-"}
	                              </pre>
	                            </div>
	                          </div>
	                        </details>
	                      ))}
	                    </div>
	                  </>
	                )}
	              </div>
	            )}
	          </CardContent>
	        </Card>
	      </section>
      {previewDialog && (
        <PdfPreviewDialog
          title={previewDialog.title}
          url={previewDialog.url}
          loading={previewDialog.loading}
          error={previewDialog.error}
          frameKey={previewFrameKey}
          onClose={closePreviewDialog}
          onReload={() => setPreviewFrameKey((current) => current + 1)}
        />
      )}
    </div>
  );
}
