import { Building2, MapPinned, RotateCcw, Save } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { EntityTable } from "@/components/master-data/EntityTable";
import { ManagementPageHeader, ManagementStatCard } from "@/components/management/ManagementPage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, SelectField, TextAreaField } from "@/components/ui/form";
import { inputClassName } from "@/lib/form-styles";
import { masterDataApi } from "@/services/master-data";
import type { Center, CenterPayload, Project } from "@/types/master-data";

const defaultForm: CenterPayload = {
  project_id: 0,
  name: "",
  code: "",
  contact_person: "",
  status: "active",
  description: "",
};

export function CentersPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [centers, setCenters] = useState<Center[]>([]);
  const [projectFilter, setProjectFilter] = useState<number | undefined>();
  const [form, setForm] = useState<CenterPayload>(defaultForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const projectNameById = useMemo(
    () => new Map(projects.map((project) => [project.id, project.name])),
    [projects],
  );
  const activeCenterCount = centers.filter((center) => center.status === "active").length;
  const pausedCenterCount = centers.filter((center) => center.status === "paused").length;

  async function loadData(nextProjectFilter = projectFilter) {
    const [projectData, centerData] = await Promise.all([
      masterDataApi.listProjects(),
      masterDataApi.listCenters(nextProjectFilter),
    ]);
    setProjects(projectData);
    setCenters(centerData);
    if (!form.project_id && projectData.length > 0) {
      setForm((current) => ({ ...current, project_id: projectData[0].id }));
    }
  }

  useEffect(() => {
    async function initialize() {
      const [projectData, centerData] = await Promise.all([
        masterDataApi.listProjects(),
        masterDataApi.listCenters(),
      ]);
      setProjects(projectData);
      setCenters(centerData);
      if (projectData.length > 0) {
        setForm((current) => ({ ...current, project_id: projectData[0].id }));
      }
    }

    void initialize();
  }, []);

  function resetForm() {
    setEditingId(null);
    setForm((current) => ({
      ...defaultForm,
      project_id: current.project_id || projects[0]?.id || 0,
    }));
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form.project_id) {
      setMessage("请先选择项目");
      return;
    }
    const payload = {
      ...form,
      name: form.name.trim(),
      code: form.code.trim(),
      contact_person: form.contact_person?.trim() || null,
      description: form.description?.trim() || null,
    };
    try {
      if (editingId) {
        await masterDataApi.updateCenter(editingId, payload);
        setMessage("中心已更新");
      } else {
        await masterDataApi.createCenter(payload);
        setMessage("中心已创建");
      }
      resetForm();
      await loadData();
    } catch {
      setMessage("保存失败，请检查中心编码是否重复");
    }
  }

  async function handleDelete(center: Center) {
    if (!window.confirm(`确认删除中心：${center.name}？`)) return;
    await masterDataApi.deleteCenter(center.id);
    await loadData();
  }

  function handleEdit(center: Center) {
    setEditingId(center.id);
    setForm({
      project_id: center.project_id,
      name: center.name,
      code: center.code,
      contact_person: center.contact_person ?? "",
      status: center.status,
      description: center.description ?? "",
    });
  }

  async function handleFilterChange(value: string) {
    const nextProjectId = value ? Number(value) : undefined;
    setProjectFilter(nextProjectId);
    await loadData(nextProjectId);
  }

  return (
    <div className="space-y-6">
      <ManagementPageHeader
        title="中心管理"
        description="为项目维护研究中心、联系人和启用状态"
        icon={Building2}
        badge="后台配置"
        actions={
          <Button variant="secondary" onClick={() => void loadData()}>
            <RotateCcw className="size-4" aria-hidden="true" />
            刷新
          </Button>
        }
      />

      {message && <Badge tone={message.includes("失败") || message.includes("选择") ? "danger" : "success"}>{message}</Badge>}

      <section className="grid gap-3 sm:grid-cols-3">
        <ManagementStatCard label="中心总数" value={centers.length} detail={`项目 ${projects.length}`} icon={Building2} />
        <ManagementStatCard label="启用中心" value={activeCenterCount} detail={`暂停 ${pausedCenterCount}`} icon={MapPinned} tone="teal" />
        <ManagementStatCard
          label="当前范围"
          value={projectFilter ? "单项目" : "全部"}
          detail={projectFilter ? projectNameById.get(projectFilter) ?? "指定项目" : "全部项目"}
          icon={RotateCcw}
          tone="slate"
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-[360px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>{editingId ? "编辑中心" : "新建中心"}</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleSubmit}>
              <Field label="所属项目">
                <SelectField
                  value={form.project_id || ""}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, project_id: Number(event.target.value) }))
                  }
                  required
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
              <Field label="中心名称">
                <input
                  className={inputClassName()}
                  value={form.name}
                  onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))}
                  placeholder="北京一中心"
                  required
                />
              </Field>
              <Field label="中心编码">
                <input
                  className={inputClassName()}
                  value={form.code}
                  onChange={(event) => setForm((current) => ({ ...current, code: event.target.value }))}
                  placeholder="BJ-01"
                  required
                />
              </Field>
              <Field label="联系人">
                <input
                  className={inputClassName()}
                  value={form.contact_person ?? ""}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, contact_person: event.target.value }))
                  }
                  placeholder="张三"
                />
              </Field>
              <Field label="状态">
                <SelectField
                  value={form.status}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, status: event.target.value }))
                  }
                >
                  <option value="active">启用</option>
                  <option value="paused">暂停</option>
                  <option value="closed">关闭</option>
                </SelectField>
              </Field>
              <Field label="说明">
                <TextAreaField
                  value={form.description ?? ""}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, description: event.target.value }))
                  }
                />
              </Field>
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
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <CardTitle>中心列表</CardTitle>
              <SelectField
                className="sm:w-56"
                value={projectFilter ?? ""}
                onChange={(event) => void handleFilterChange(event.target.value)}
              >
                <option value="">全部项目</option>
                {projects.map((project) => (
                  <option key={project.id} value={project.id}>
                    {project.name}
                  </option>
                ))}
              </SelectField>
            </div>
          </CardHeader>
          <CardContent>
            <EntityTable
              rows={centers}
              getRowKey={(center) => center.id}
              emptyLabel="暂无中心"
              emptyDescription="选择项目后可新增研究中心"
              onEdit={handleEdit}
              onDelete={(center) => void handleDelete(center)}
              columns={[
                { key: "project", label: "项目", render: (center) => projectNameById.get(center.project_id) ?? "-" },
                { key: "name", label: "中心", render: (center) => center.name },
                { key: "code", label: "编码", render: (center) => center.code },
                { key: "contact", label: "联系人", render: (center) => center.contact_person || "-" },
                {
                  key: "status",
                  label: "状态",
                  render: (center) => (
                    <Badge tone={center.status === "active" ? "success" : center.status === "paused" ? "warning" : "neutral"}>
                      {center.status === "active" ? "启用" : center.status === "paused" ? "暂停" : center.status}
                    </Badge>
                  ),
                },
              ]}
            />
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
