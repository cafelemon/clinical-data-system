import { Eye, Pencil, Plus, RotateCcw, Save } from "lucide-react";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { FileActions } from "@/components/files/FileActions";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, SelectField } from "@/components/ui/form";
import { inputClassName } from "@/lib/form-styles";
import { clinicalDataApi } from "@/services/clinical-data";
import { masterDataApi } from "@/services/master-data";
import { useAuthStore } from "@/stores/auth-store";
import type { ClinicalDataset, StageFile, Subject } from "@/types/clinical-data";
import type { Center, Project, Stage } from "@/types/master-data";

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

type SubjectForm = {
  screening_no: string;
  gender: string;
  age: string;
  enrolled_at: string;
  review_status: string;
  data_status: string;
};

const defaultSubjectForm: SubjectForm = {
  screening_no: "",
  gender: "",
  age: "",
  enrolled_at: "",
  review_status: "pending_review",
  data_status: "not_started",
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

function StageFileTable({
  files,
  canReadFiles,
  canWriteFiles,
  canDeleteFiles,
  onChanged,
}: {
  files: StageFile[];
  canReadFiles: boolean;
  canWriteFiles: boolean;
  canDeleteFiles: boolean;
  onChanged: () => void;
}) {
  if (files.length === 0) {
    return (
      <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
        暂无阶段资料
      </div>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[620px] text-left text-sm">
        <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-3 py-2 font-medium">资料名称</th>
            <th className="px-3 py-2 font-medium">资料类型</th>
            <th className="px-3 py-2 font-medium">上传状态</th>
            <th className="px-3 py-2 font-medium">审核状态</th>
            <th className="px-3 py-2 font-medium">更新时间</th>
            <th className="px-3 py-2 font-medium">文件</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {files.map((file) => (
            <tr key={file.id}>
              <td className="px-3 py-3 font-medium text-slate-900">{file.file_name}</td>
              <td className="px-3 py-3 text-slate-600">{file.file_type || "-"}</td>
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
              <td className="px-3 py-3 text-slate-500">
                {new Date(file.updated_at).toLocaleDateString()}
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
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SubjectTable({
  subjects,
  onEdit,
  canWrite,
}: {
  subjects: Subject[];
  onEdit: (subject: Subject) => void;
  canWrite: boolean;
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
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-3 py-2 font-medium">筛选号</th>
            <th className="px-3 py-2 font-medium">性别</th>
            <th className="px-3 py-2 font-medium">年龄</th>
            <th className="px-3 py-2 font-medium">入组日期</th>
            <th className="px-3 py-2 font-medium">资料状态</th>
            <th className="px-3 py-2 font-medium">审核状态</th>
            <th className="px-3 py-2 font-medium">操作</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {subjects.map((subject) => (
            <tr key={subject.id}>
              <td className="px-3 py-3 font-medium text-slate-900">{subject.screening_no}</td>
              <td className="px-3 py-3 text-slate-600">{subject.gender || "-"}</td>
              <td className="px-3 py-3 text-slate-600">{subject.age ?? "-"}</td>
              <td className="px-3 py-3 text-slate-600">{subject.enrolled_at || "-"}</td>
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
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ClinicalDatasetPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [centers, setCenters] = useState<Center[]>([]);
  const [stages, setStages] = useState<Stage[]>([]);
  const [projectId, setProjectId] = useState<number | undefined>();
  const [centerId, setCenterId] = useState<number | undefined>();
  const [dataset, setDataset] = useState<ClinicalDataset | null>(null);
  const [form, setForm] = useState<SubjectForm>(defaultSubjectForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const hasPermission = useAuthStore((state) => state.hasPermission);
  const canWrite = hasPermission("clinical_data:write");
  const canReadFiles = hasPermission("files:read");
  const canWriteFiles = hasPermission("files:write");
  const canDeleteFiles = hasPermission("files:delete");

  const stageByCode = useMemo(
    () => new Map((dataset?.stages ?? stages).map((stage) => [stage.code, stage])),
    [dataset?.stages, stages],
  );
  const startupStage = stageByCode.get("STARTUP");
  const trialStage = stageByCode.get("TRIAL");
  const closeoutStage = stageByCode.get("CLOSEOUT");

  const loadDataset = useCallback(async () => {
    if (!projectId || !centerId) {
      setDataset(null);
      return;
    }
    setLoading(true);
    try {
      const data = await clinicalDataApi.getDataset(projectId, centerId);
      setDataset(data);
      setMessage(null);
    } catch {
      setDataset(null);
      setMessage("临床数据集加载失败");
    } finally {
      setLoading(false);
    }
  }, [centerId, projectId]);

  useEffect(() => {
    async function initialize() {
      const projectData = await masterDataApi.listProjects();
      setProjects(projectData);
      setProjectId(projectData[0]?.id);
    }
    void initialize();
  }, []);

  useEffect(() => {
    async function loadScope() {
      if (!projectId) {
        setCenters([]);
        setStages([]);
        setCenterId(undefined);
        return;
      }
      const [centerData, stageData] = await Promise.all([
        masterDataApi.listCenters(projectId),
        masterDataApi.listStages(projectId),
      ]);
      setCenters(centerData);
      setStages(stageData);
      setCenterId((current) =>
        centerData.some((center) => center.id === current) ? current : centerData[0]?.id,
      );
    }
    void loadScope();
  }, [projectId]);

  useEffect(() => {
    void loadDataset();
  }, [loadDataset]);

  function resetForm() {
    setEditingId(null);
    setForm(defaultSubjectForm);
  }

  function handleProjectChange(value: string) {
    setProjectId(value ? Number(value) : undefined);
    setCenterId(undefined);
    setDataset(null);
    resetForm();
  }

  function handleEdit(subject: Subject) {
    setEditingId(subject.id);
    setForm({
      screening_no: subject.screening_no,
      gender: subject.gender ?? "",
      age: subject.age === null ? "" : String(subject.age),
      enrolled_at: subject.enrolled_at ?? "",
      review_status: subject.review_status,
      data_status: subject.data_status,
    });
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectId || !centerId) {
      setMessage("请先选择项目和中心");
      return;
    }
    const payload = {
      project_id: projectId,
      center_id: centerId,
      screening_no: form.screening_no.trim(),
      gender: form.gender || null,
      age: form.age ? Number(form.age) : null,
      enrolled_at: form.enrolled_at || null,
      review_status: form.review_status,
      data_status: form.data_status,
    };
    try {
      if (editingId) {
        await clinicalDataApi.updateSubject(editingId, payload);
        setMessage("受试者已更新");
      } else {
        await clinicalDataApi.createSubject(payload);
        setMessage("受试者已创建");
      }
      resetForm();
      await loadDataset();
    } catch {
      setMessage("保存失败，请检查筛选号是否重复或权限范围");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">临床数据集</h1>
          <p className="mt-1 text-sm text-slate-500">项目中心资料与受试者链路</p>
        </div>
        <Button variant="secondary" onClick={() => void loadDataset()}>
          <RotateCcw className="size-4" aria-hidden="true" />
          刷新
        </Button>
      </div>

      {message && (
        <Badge tone={message.includes("失败") || message.includes("选择") ? "danger" : "success"}>
          {message}
        </Badge>
      )}

      <section className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>数据范围</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 sm:grid-cols-2">
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
                    onChange={(event) => setCenterId(Number(event.target.value) || undefined)}
                  >
                    <option value="">选择中心</option>
                    {centers.map((center) => (
                      <option key={center.id} value={center.id}>
                        {center.name}
                      </option>
                    ))}
                  </SelectField>
                </Field>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>启动阶段资料</CardTitle>
            </CardHeader>
            <CardContent>
              {startupStage ? (
                <StageFileTable
                  files={dataset?.startup_files ?? []}
                  canReadFiles={canReadFiles}
                  canWriteFiles={canWriteFiles}
                  canDeleteFiles={canDeleteFiles}
                  onChanged={() => void loadDataset()}
                />
              ) : (
                <p className="text-sm text-slate-500">未配置 STARTUP 阶段</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>试验进行阶段受试者</CardTitle>
            </CardHeader>
            <CardContent>
              {trialStage ? (
                <SubjectTable
                  subjects={dataset?.subjects ?? []}
                  onEdit={handleEdit}
                  canWrite={canWrite}
                />
              ) : (
                <p className="text-sm text-slate-500">未配置 TRIAL 阶段</p>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>总结阶段资料</CardTitle>
            </CardHeader>
            <CardContent>
              {closeoutStage ? (
                <StageFileTable
                  files={dataset?.closeout_files ?? []}
                  canReadFiles={canReadFiles}
                  canWriteFiles={canWriteFiles}
                  canDeleteFiles={canDeleteFiles}
                  onChanged={() => void loadDataset()}
                />
              ) : (
                <p className="text-sm text-slate-500">未配置 CLOSEOUT 阶段</p>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>概览</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-md border border-slate-200 p-3">
                  <p className="text-xs text-slate-500">阶段资料</p>
                  <p className="mt-1 text-2xl font-semibold">{dataset?.stage_file_count ?? 0}</p>
                </div>
                <div className="rounded-md border border-slate-200 p-3">
                  <p className="text-xs text-slate-500">受试者</p>
                  <p className="mt-1 text-2xl font-semibold">{dataset?.subject_count ?? 0}</p>
                </div>
              </div>
              {loading && <p className="mt-3 text-sm text-slate-500">正在加载</p>}
            </CardContent>
          </Card>

          {canWrite && (
            <Card>
              <CardHeader>
                <CardTitle>{editingId ? "编辑受试者" : "新增受试者"}</CardTitle>
              </CardHeader>
              <CardContent>
                <form className="space-y-4" onSubmit={handleSubmit}>
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
                  <div className="grid grid-cols-2 gap-3">
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
                  </div>
                  <Field label="入组日期">
                    <input
                      className={inputClassName()}
                      type="date"
                      value={form.enrolled_at}
                      onChange={(event) =>
                        setForm((current) => ({
                          ...current,
                          enrolled_at: event.target.value,
                        }))
                      }
                    />
                  </Field>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="资料状态">
                      <SelectField
                        value={form.data_status}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            data_status: event.target.value,
                          }))
                        }
                      >
                        <option value="not_started">未开始</option>
                        <option value="in_progress">进行中</option>
                        <option value="complete">已完成</option>
                      </SelectField>
                    </Field>
                    <Field label="审核状态">
                      <SelectField
                        value={form.review_status}
                        onChange={(event) =>
                          setForm((current) => ({
                            ...current,
                            review_status: event.target.value,
                          }))
                        }
                      >
                        <option value="pending_review">待审核</option>
                        <option value="approved">已通过</option>
                        <option value="rejected">已驳回</option>
                      </SelectField>
                    </Field>
                  </div>
                  <div className="flex gap-2">
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
              </CardContent>
            </Card>
          )}
        </div>
      </section>
    </div>
  );
}
