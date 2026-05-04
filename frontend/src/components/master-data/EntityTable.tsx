import { Edit3, Trash2 } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";

type EntityTableProps<T> = {
  columns: Array<{
    key: string;
    label: string;
    render: (item: T) => ReactNode;
  }>;
  rows: T[];
  getRowKey: (item: T) => number;
  onEdit: (item: T) => void;
  onDelete?: (item: T) => void;
  emptyLabel: string;
};

export function EntityTable<T>({
  columns,
  rows,
  getRowKey,
  onEdit,
  onDelete,
  emptyLabel,
}: EntityTableProps<T>) {
  if (rows.length === 0) {
    return (
      <div className="flex h-36 items-center justify-center rounded-md border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-500">
        {emptyLabel}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-left text-sm">
        <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
          <tr>
            {columns.map((column) => (
              <th key={column.key} className="whitespace-nowrap px-3 py-3 font-medium">
                {column.label}
              </th>
            ))}
            <th className="w-24 px-3 py-3 text-right font-medium">操作</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr key={getRowKey(row)} className="bg-white">
              {columns.map((column) => (
                <td key={column.key} className="whitespace-nowrap px-3 py-3 text-slate-700">
                  {column.render(row)}
                </td>
              ))}
              <td className="px-3 py-3">
                <div className="flex justify-end gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => onEdit(row)}
                    title="编辑"
                  >
                    <Edit3 className="size-4" aria-hidden="true" />
                  </Button>
                  {onDelete && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon"
                      onClick={() => onDelete(row)}
                      title="删除"
                    >
                      <Trash2 className="size-4" aria-hidden="true" />
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
