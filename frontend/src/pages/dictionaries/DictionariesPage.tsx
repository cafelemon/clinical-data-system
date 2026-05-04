import { RotateCcw, Save } from "lucide-react";
import { FormEvent, useEffect, useState } from "react";

import { EntityTable } from "@/components/master-data/EntityTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, SelectField } from "@/components/ui/form";
import { inputClassName } from "@/lib/form-styles";
import { masterDataApi } from "@/services/master-data";
import type { DictionaryItem, DictionaryPayload } from "@/types/master-data";

const dictTypes = [
  { value: "project_status", label: "项目状态" },
  { value: "center_status", label: "中心状态" },
  { value: "review_status", label: "审核状态" },
  { value: "upload_status", label: "上传状态" },
];

const defaultForm: DictionaryPayload = {
  dict_type: "project_status",
  value: "",
  label: "",
  color: "neutral",
  sort_order: 0,
  enabled: true,
};

export function DictionariesPage() {
  const [items, setItems] = useState<DictionaryItem[]>([]);
  const [dictTypeFilter, setDictTypeFilter] = useState<string>("");
  const [form, setForm] = useState<DictionaryPayload>(defaultForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function loadData(nextDictType = dictTypeFilter) {
    const data = await masterDataApi.listDictionaries(nextDictType || undefined);
    setItems(data);
  }

  useEffect(() => {
    async function initialize() {
      const data = await masterDataApi.listDictionaries();
      setItems(data);
    }

    void initialize();
  }, []);

  function resetForm() {
    setEditingId(null);
    setForm(defaultForm);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = {
      ...form,
      dict_type: form.dict_type.trim(),
      value: form.value.trim(),
      label: form.label.trim(),
      color: form.color?.trim() || null,
      sort_order: Number(form.sort_order) || 0,
    };
    try {
      if (editingId) {
        await masterDataApi.updateDictionary(editingId, payload);
        setMessage("字典项已更新");
      } else {
        await masterDataApi.createDictionary(payload);
        setMessage("字典项已创建");
      }
      resetForm();
      await loadData();
    } catch {
      setMessage("保存失败，请检查同类型 value 是否重复");
    }
  }

  async function handleDelete(item: DictionaryItem) {
    if (!window.confirm(`确认删除字典项：${item.label}？`)) return;
    await masterDataApi.deleteDictionary(item.id);
    await loadData();
  }

  function handleEdit(item: DictionaryItem) {
    setEditingId(item.id);
    setForm({
      dict_type: item.dict_type,
      value: item.value,
      label: item.label,
      color: item.color ?? "neutral",
      sort_order: item.sort_order,
      enabled: item.enabled,
    });
  }

  async function handleFilterChange(value: string) {
    setDictTypeFilter(value);
    await loadData(value);
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">状态字典</h1>
          <p className="mt-1 text-sm text-slate-500">统一维护前端可调用的状态值和标签</p>
        </div>
        <Button variant="secondary" onClick={() => void loadData()}>
          <RotateCcw className="size-4" aria-hidden="true" />
          刷新
        </Button>
      </div>

      {message && <Badge tone={message.includes("失败") ? "danger" : "success"}>{message}</Badge>}

      <section className="grid gap-4 xl:grid-cols-[360px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>{editingId ? "编辑字典项" : "新建字典项"}</CardTitle>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleSubmit}>
              <Field label="字典类型">
                <SelectField
                  value={form.dict_type}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, dict_type: event.target.value }))
                  }
                >
                  {dictTypes.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
                </SelectField>
              </Field>
              <Field label="值">
                <input
                  className={inputClassName()}
                  value={form.value}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, value: event.target.value }))
                  }
                  placeholder="active"
                  required
                />
              </Field>
              <Field label="标签">
                <input
                  className={inputClassName()}
                  value={form.label}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, label: event.target.value }))
                  }
                  placeholder="启用"
                  required
                />
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="颜色">
                  <SelectField
                    value={form.color ?? "neutral"}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, color: event.target.value }))
                    }
                  >
                    <option value="neutral">灰色</option>
                    <option value="success">绿色</option>
                    <option value="warning">黄色</option>
                    <option value="danger">红色</option>
                  </SelectField>
                </Field>
                <Field label="排序">
                  <input
                    className={inputClassName()}
                    type="number"
                    value={form.sort_order}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, sort_order: Number(event.target.value) }))
                    }
                  />
                </Field>
              </div>
              <Field label="是否启用">
                <SelectField
                  value={form.enabled ? "true" : "false"}
                  onChange={(event) =>
                    setForm((current) => ({ ...current, enabled: event.target.value === "true" }))
                  }
                >
                  <option value="true">启用</option>
                  <option value="false">停用</option>
                </SelectField>
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
              <CardTitle>字典列表</CardTitle>
              <SelectField
                className="sm:w-56"
                value={dictTypeFilter}
                onChange={(event) => void handleFilterChange(event.target.value)}
              >
                <option value="">全部类型</option>
                {dictTypes.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </SelectField>
            </div>
          </CardHeader>
          <CardContent>
            <EntityTable
              rows={items}
              getRowKey={(item) => item.id}
              emptyLabel="暂无字典项"
              onEdit={handleEdit}
              onDelete={(item) => void handleDelete(item)}
              columns={[
                { key: "type", label: "类型", render: (item) => item.dict_type },
                { key: "value", label: "值", render: (item) => item.value },
                { key: "label", label: "标签", render: (item) => item.label },
                { key: "color", label: "颜色", render: (item) => item.color || "-" },
                { key: "enabled", label: "启用", render: (item) => (item.enabled ? "是" : "否") },
              ]}
            />
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
