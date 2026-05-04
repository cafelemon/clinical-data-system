import { RotateCcw, Save } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { EntityTable } from "@/components/master-data/EntityTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, TextAreaField } from "@/components/ui/form";
import { inputClassName } from "@/lib/form-styles";
import { identityApi } from "@/services/identity";
import type { Permission, Role, RolePayload } from "@/types/auth";

const defaultForm: RolePayload = {
  name: "",
  label: "",
  description: "",
  permission_ids: [],
};

function toggleNumber(values: number[], value: number) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

export function RolesPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [form, setForm] = useState<RolePayload>(defaultForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function loadData() {
    const [roleData, permissionData] = await Promise.all([
      identityApi.listRoles(),
      identityApi.listPermissions(),
    ]);
    setRoles(roleData);
    setPermissions(permissionData);
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
        await identityApi.updateRole(editingId, {
          label: form.label.trim(),
          description: form.description?.trim() || null,
          permission_ids: form.permission_ids,
        });
        setMessage("角色已更新");
      } else {
        await identityApi.createRole({
          name: form.name.trim(),
          label: form.label.trim(),
          description: form.description?.trim() || null,
          permission_ids: form.permission_ids,
        });
        setMessage("角色已创建");
      }
      resetForm();
      await loadData();
    } catch {
      setMessage("保存失败，请检查角色编码是否重复");
    }
  }

  function handleEdit(role: Role) {
    setEditingId(role.id);
    setForm({
      name: role.name,
      label: role.label,
      description: role.description ?? "",
      permission_ids: role.permission_ids,
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">角色管理</h1>
          <p className="mt-1 text-sm text-slate-500">维护角色与权限点绑定</p>
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
            <CardTitle>{editingId ? "编辑角色" : "新建角色"}</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleSubmit}>
              <Field label="角色编码">
                <input
                  className={inputClassName()}
                  value={form.name}
                  disabled={Boolean(editingId)}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, name: event.target.value }))
                  }
                  placeholder="custom_role"
                  required
                />
              </Field>
              <Field label="角色名称">
                <input
                  className={inputClassName()}
                  value={form.label}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, label: event.target.value }))
                  }
                  required
                />
              </Field>
              <Field label="说明">
                <TextAreaField
                  value={form.description ?? ""}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, description: event.target.value }))
                  }
                />
              </Field>
              <div className="space-y-2">
                <p className="text-sm font-medium text-slate-700">权限点</p>
                <div className="max-h-64 space-y-2 overflow-auto rounded-md border border-slate-200 p-3">
                  {permissions.map((permission) => (
                    <label
                      key={permission.id}
                      className="flex items-center gap-2 text-sm text-slate-700"
                    >
                      <input
                        type="checkbox"
                        checked={form.permission_ids.includes(permission.id)}
                        onChange={() =>
                          setForm((current) => ({
                            ...current,
                            permission_ids: toggleNumber(current.permission_ids, permission.id),
                          }))
                        }
                      />
                      {permission.label}
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
            <CardTitle>角色列表</CardTitle>
          </CardHeader>
          <CardContent>
            <EntityTable
              rows={roles}
              getRowKey={(role) => role.id}
              emptyLabel="暂无角色"
              onEdit={handleEdit}
              columns={[
                { key: "name", label: "编码", render: (role) => role.name },
                { key: "label", label: "名称", render: (role) => role.label },
                { key: "system", label: "内置", render: (role) => (role.system ? "是" : "否") },
                { key: "permissions", label: "权限数", render: (role) => role.permission_ids.length },
              ]}
            />
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
