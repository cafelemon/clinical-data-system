import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

type Tone = "blue" | "teal" | "amber" | "red" | "slate";
type BadgeTone = "neutral" | "success" | "warning" | "danger";

function toneClass(tone: Tone) {
  if (tone === "teal") return "bg-teal-50 text-teal-700";
  if (tone === "amber") return "bg-amber-50 text-amber-700";
  if (tone === "red") return "bg-rose-50 text-rose-700";
  if (tone === "slate") return "bg-slate-100 text-slate-600";
  return "bg-blue-50 text-[#0B2E63]";
}

export function ManagementPageHeader({
  title,
  description,
  icon: Icon,
  badge,
  badgeTone = "neutral",
  actions,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
  badge?: string;
  badgeTone?: BadgeTone;
  actions?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex min-w-0 items-start gap-3">
        <div className="flex size-12 shrink-0 items-center justify-center rounded-md bg-blue-50 text-[#0B2E63]">
          <Icon className="size-6" aria-hidden="true" />
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-normal text-slate-950">{title}</h1>
            {badge && <Badge tone={badgeTone}>{badge}</Badge>}
          </div>
          <p className="mt-1 text-sm text-slate-500">{description}</p>
        </div>
      </div>
      {actions && <div className="flex shrink-0 flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function ManagementStatCard({
  label,
  value,
  detail,
  icon: Icon,
  tone = "blue",
}: {
  label: string;
  value: string | number;
  detail: string;
  icon: LucideIcon;
  tone?: Tone;
}) {
  return (
    <div className="rounded-md border border-[#DDE7F0] bg-white p-4 shadow-sm shadow-sky-950/5">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-500">{label}</p>
          <p className="mt-2 text-2xl font-semibold tracking-normal text-slate-950">{value}</p>
        </div>
        <div className={cn("flex size-9 shrink-0 items-center justify-center rounded-md", toneClass(tone))}>
          <Icon className="size-4" aria-hidden="true" />
        </div>
      </div>
      <p className="mt-3 truncate text-xs text-slate-500">{detail}</p>
    </div>
  );
}

export function ManagementNotice({
  title,
  description,
  tone = "slate",
}: {
  title: string;
  description: string;
  tone?: Tone;
}) {
  return (
    <div className="rounded-md border border-[#DDE7F0] bg-white p-4">
      <div className="flex flex-col gap-1">
        <p className={cn("text-sm font-semibold", tone === "red" ? "text-rose-700" : "text-[#10233F]")}>{title}</p>
        <p className="text-sm text-slate-500">{description}</p>
      </div>
    </div>
  );
}
