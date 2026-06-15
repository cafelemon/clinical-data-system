import { X } from "lucide-react";

import { Button } from "@/components/ui/button";

type PdfPreviewDialogProps = {
  title: string;
  url: string | null;
  loading: boolean;
  error: string | null;
  frameKey?: number;
  onClose: () => void;
  onReload?: () => void;
};

export function PdfPreviewDialog({
  title,
  url,
  loading,
  error,
  frameKey = 0,
  onClose,
  onReload,
}: PdfPreviewDialogProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 p-4">
      <div className="flex max-h-[92vh] w-full max-w-6xl flex-col rounded-md bg-white shadow-xl">
        <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
          <div>
            <h2 className="text-base font-semibold text-slate-950">{title}</h2>
            <p className="mt-1 text-xs text-slate-500">页面内预览</p>
          </div>
          <div className="flex items-center gap-2">
            {url && onReload && (
              <Button size="sm" variant="secondary" onClick={onReload}>
                重新加载
              </Button>
            )}
            <Button
              size="sm"
              variant="ghost"
              onClick={onClose}
              aria-label="关闭预览"
              title="关闭预览"
            >
              <X className="size-4" aria-hidden="true" />
            </Button>
          </div>
        </div>
        <div className="min-h-[420px] flex-1 bg-slate-100 p-3">
          {loading ? (
            <div className="flex h-[72vh] items-center justify-center rounded-md bg-white text-sm text-slate-500">
              PDF 读取中...
            </div>
          ) : error ? (
            <div className="flex h-[72vh] items-center justify-center rounded-md bg-white text-sm text-red-600">
              {error}
            </div>
          ) : url ? (
            <iframe
              key={frameKey}
              title={title}
              src={url}
              className="h-[72vh] w-full rounded-md border border-slate-200 bg-white"
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}
