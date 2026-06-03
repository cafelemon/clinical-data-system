import { cn } from "@/lib/utils";

export function inputClassName(className?: string) {
  return cn(
    "h-10 w-full rounded-md border border-[#DDE7F0] bg-white px-3 text-sm text-[#10233F] outline-none transition placeholder:text-slate-400 focus:border-[#0F78D4] focus:ring-2 focus:ring-[#0F78D4]/10",
    className,
  );
}
