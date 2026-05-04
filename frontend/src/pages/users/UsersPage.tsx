import { RotateCcw, Save } from "lucide-react";
import { FormEvent, useEffect, useMemo, useState } from "react";

import { EntityTable } from "@/components/master-data/EntityTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, SelectField } from "@/components/ui/form";
import { inputClassName } from "@/lib/form-styles";
import { identityApi } from "@/services/identity";
import { masterDataApi } from "@/services/master-data";
import type { Role, User, UserPayload } from "@/types/auth";
import type { Center, Project } from "@/types/master-data";

type UserForm = UserPayload & { password: string };

const defaultForm: UserForm = {
  username: "",
  password: "",
  full_name: "",
  email: "",
  is_active: true,
  role_ids: [],
  project_ids: [],
  center_ids: [],
};

function toggleNumber(values: number[], value: number) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

export function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [projects, setProjects] = useState<Project[]>([]);
  const [centers, setCenters] = useState<Center[]>([]);
  const [form, setForm] = useState<UserForm>(defaultForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const roleNameById = useMemo(() => new Map(roles.map((role) => [role.id, role.label])), [roles]);

  async function loadData() {
    const [userData, roleData, projectData, centerData] = await Promise.all([
      identityApi.listUsers(),
      identityApi.listRoles(),
      masterDataApi.listProjects(),
      masterDataApi.listCenters(),
    ]);
    setUsers(userData);
    setRoles(roleData);
    setProjects(projectData);
    setCenters(centerData);
  }

  useEffect(() => {
    void loadData();
  }, []);

  function resetForm() {
    setEditingId(null);
    setForm(defaultForm);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      if (editingId) {
        const payload: Partial<UserPayload> = {
          full_name: form.full_name?.trim() || null,
          email: form.email?.trim() || null,
          is_active: form.is_active,
          role_ids: form.role_ids,
          project_ids: form.project_ids,
          center_ids: form.center_ids,
        };
        if (form.password) {
          payload.password = form.password;
        }
        await identityApi.updateUser(editingId, payload);
        setMessage("用户已更新");
      } else {
        await identityApi.createUser({
          username: form.username.trim(),
          password: form.password,
          full_name: form.full_name?.trim() || null,
          email: form.email?.trim() || null,
          is_active: form.is_active,
          role_ids: form.role_ids,
          project_ids: form.project_ids,
          center_ids: form.center_ids,
        });
        setMessage("用户已创建");
      }
      resetForm();
      await loadData();
    } catch {
      setMessage("保存失败，请检查用户名、邮箱或权限范围");
    }
  }

  async function handleDelete(user: User) {
    if (!window.confirm(`确认删除用户：${user.username}？`)) return;
    await identityApi.deleteUser(user.id);
    await loadData();
  }

  function handleEdit(user: User) {
    setEditingId(user.id);
    setForm({
      username: user.username,
      password: "",
      full_name: user.full_name ?? "",
      email: user.email ?? "",
      is_active: user.is_active,
      role_ids: user.role_ids,
      project_ids: user.project_ids,
      center_ids: user.center_ids,
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">用户管理</h1>
          <p className="mt-1 text-sm text-slate-500">维护账号、角色和项目/中心数据范围</p>
        </div>
        <Button variant="secondary" onClick={() => void loadData()}>
          <RotateCcw className="size-4" aria-hidden="true" />
          刷新
        </Button>
      </div>

      {message && <Badge tone={message.includes("失败") ? "danger" : "success"}>{message}</Badge>}

      <section className="grid gap-4 xl:grid-cols-[400px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>{editingId ? "编辑用户" : "新建用户"}</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleSubmit}>
              <Field label="用户名">
                <input
                  className={inputClassName()}
                  value={form.username}
                  disabled={Boolean(editingId)}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, username: event.target.value }))
                  }
                  required
                />
              </Field>
              <Field label={editingId ? "新密码" : "密码"}>
                <input
                  type="password"
                  className={inputClassName()}
                  value={form.password}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, password: event.target.value }))
                  }
                  required={!editingId}
                  minLength={editingId && !form.password ? undefined : 8}
                  maxLength={72}
                />
              </Field>
              <Field label="姓名">
                <input
                  className={inputClassName()}
                  value={form.full_name ?? ""}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, full_name: event.target.value }))
                  }
                />
              </Field>
              <Field label="邮箱">
                <input
                  className={inputClassName()}
                  value={form.email ?? ""}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, email: event.target.value }))
                  }
                />
              </Field>
              <Field label="状态">
                <SelectField
                  value={form.is_active ? "true" : "false"}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, is_active: event.target.value === "true" }))
                  }
                >
                  <option value="true">启用</option>
                  <option value="false">停用</option>
                </SelectField>
              </Field>

              <div className="space-y-2">
                <p className="text-sm font-medium text-slate-700">角色</p>
                <div className="grid gap-2 rounded-md border border-slate-200 p-3">
                  {roles.map((role) => (
                    <label key={role.id} className="flex items-center gap-2 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={form.role_ids.includes(role.id)}
                        onChange={() =>
                          setForm((current) => ({
                            ...current,
                            role_ids: toggleNumber(current.role_ids, role.id),
                          }))
                        }
                      />
                      {role.label}
                    </label>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium text-slate-700">授权项目</p>
                <div className="max-h-32 space-y-2 overflow-auto rounded-md border border-slate-200 p-3">
                  {projects.map((project) => (
                    <label key={project.id} className="flex items-center gap-2 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={form.project_ids.includes(project.id)}
                        onChange={() =>
                          setForm((current) => ({
                            ...current,
                            project_ids: toggleNumber(current.project_ids, project.id),
                          }))
                        }
                      />
                      {project.name}
                    </label>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium text-slate-700">授权中心</p>
                <div className="max-h-32 space-y-2 overflow-auto rounded-md border border-slate-200 p-3">
                  {centers.map((center) => (
                    <label key={center.id} className="flex items-center gap-2 text-sm text-slate-700">
                      <input
                        type="checkbox"
                        checked={form.center_ids.includes(center.id)}
                        onChange={() =>
                          setForm((current) => ({
                            ...current,
                            center_ids: toggleNumber(current.center_ids, center.id),
                          }))
                        }
                      />
                      {center.name}
                    </label>
                  ))}
                </div>
              </div>

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
            <CardTitle>用户列表</CardTitle>
          </CardHeader>
          <CardContent>
            <EntityTable
              rows={users}
              getRowKey={(user) => user.id}
              emptyLabel="暂无用户"
              onEdit={handleEdit}
              onDelete={(user) => void handleDelete(user)}
              columns={[
                { key: "username", label: "用户名", render: (user) => user.username },
                { key: "name", label: "姓名", render: (user) => user.full_name || "-" },
                {
                  key: "roles",
                  label: "角色",
                  render: (user) =>
                    user.role_ids.map((roleId) => roleNameById.get(roleId) ?? roleId).join(", "),
                },
                { key: "status", label: "状态", render: (user) => (user.is_active ? "启用" : "停用") },
              ]}
            />
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

