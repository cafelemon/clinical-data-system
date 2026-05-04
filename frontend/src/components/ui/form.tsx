import type { ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/utils";
import { inputClassName } from "@/lib/form-styles";

type FieldProps = {
  label: string;
  children: ReactNode;
  className?: string;
};

export function Field({ label, children, className }: FieldProps) {
  return (
    <label className={cn("block text-sm font-medium text-slate-700", className)}>
      <span className="mb-1 block">{label}</span>
      {children}
    </label>
  );
}

export function SelectField(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={inputClassName(props.className)} />;
}

export function TextAreaField(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...props}
      className={cn(inputClassName("min-h-20 py-2"), props.className)}
    />
  );
}
