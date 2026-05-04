import { cn } from "@/lib/utils";

export function inputClassName(className?: string) {
  return cn(
    "h-10 w-full rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-950 outline-none transition placeholder:text-slate-400 focus:border-slate-400 focus:ring-2 focus:ring-slate-100",
    className,
  );
}

