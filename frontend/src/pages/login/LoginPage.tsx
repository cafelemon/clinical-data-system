import { Activity } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";

export function LoginPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-100 px-4">
      <section className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex size-10 items-center justify-center rounded-lg bg-emerald-600 text-white">
            <Activity className="size-5" aria-hidden="true" />
          </div>
          <div>
            <h1 className="text-base font-semibold text-slate-950">临床数据收集系统</h1>
            <p className="text-sm text-slate-500">账号登录</p>
          </div>
        </div>

        <div className="space-y-4">
          <label className="block text-sm font-medium text-slate-700">
            账号
            <input
              className="mt-1 h-10 w-full rounded-md border border-slate-200 px-3 text-sm outline-none focus:border-slate-400"
              placeholder="admin"
            />
          </label>
          <label className="block text-sm font-medium text-slate-700">
            密码
            <input
              type="password"
              className="mt-1 h-10 w-full rounded-md border border-slate-200 px-3 text-sm outline-none focus:border-slate-400"
              placeholder="••••••••"
            />
          </label>
          <Button asChild className="w-full">
            <Link to="/">进入系统</Link>
          </Button>
        </div>
      </section>
    </main>
  );
}

