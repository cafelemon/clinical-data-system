import { ScanLine, ShieldCheck } from "lucide-react";
import { FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import fortuneLogo from "@/assets/fortune-logo-compact-light.png";
import systemMark from "@/assets/xunchang-system-mark.png";
import { Button } from "@/components/ui/button";
import { authApi } from "@/services/auth";
import { useAuthStore } from "@/stores/auth-store";

export function LoginPage() {
  const navigate = useNavigate();
  const setToken = useAuthStore((state) => state.setToken);
  const setUser = useAuthStore((state) => state.setUser);
  const setInitialized = useAuthStore((state) => state.setInitialized);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("Admin@123456");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const token = await authApi.login(username.trim(), password);
      setToken(token.access_token);
      const user = await authApi.me();
      setUser(user);
      setInitialized(true);
      navigate("/", { replace: true });
    } catch {
      setError("账号或密码错误");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#F5F8FB] px-4 py-10">
      <section className="grid w-full max-w-5xl overflow-hidden rounded-lg border border-[#DDE7F0] bg-white shadow-xl shadow-sky-950/10 lg:grid-cols-[1.08fr_0.92fr]">
        <div className="relative hidden min-h-[560px] border-r border-[#DDE7F0] bg-[#F7FBFD] p-10 lg:block">
          <div className="flex items-center gap-3">
            <img src={systemMark} alt="巡常系统图标" className="size-16 rounded-lg object-contain" />
            <div>
              <h1 className="text-2xl font-semibold tracking-normal text-[#10233F]">
                巡常临床数据智能管理系统
              </h1>
              <p className="mt-1 text-sm text-[#5D7188]">
                Xunchang Clinical Data Intelligence Management System
              </p>
            </div>
          </div>

          <div className="mt-14 max-w-md">
            <p className="text-xs font-semibold uppercase text-[#0F78D4]">
              Medical SaaS Console
            </p>
            <h2 className="mt-4 text-3xl font-semibold leading-tight tracking-normal text-[#10233F]">
              临床资料、影像数据与智能识别结果的统一工作台
            </h2>
            <p className="mt-4 text-sm leading-6 text-[#5D7188]">
              面向项目、中心、受试者和资料包的闭环管理，保留人工确认入口，让 OCR 与智能识别成为可追溯的数据助手。
            </p>
          </div>

          <div className="mt-10 grid grid-cols-2 gap-3">
            <div className="rounded-lg border border-[#DDE7F0] bg-white p-4">
              <ShieldCheck className="size-5 text-[#0F78D4]" aria-hidden="true" />
              <p className="mt-3 text-sm font-semibold text-[#10233F]">风险强确认</p>
              <p className="mt-1 text-xs leading-5 text-[#5D7188]">关键字段先校验，再进入主数据。</p>
            </div>
            <div className="rounded-lg border border-[#DDE7F0] bg-white p-4">
              <ScanLine className="size-5 text-[#10BFB3]" aria-hidden="true" />
              <p className="mt-3 text-sm font-semibold text-[#10233F]">轻量智能识别</p>
              <p className="mt-1 text-xs leading-5 text-[#5D7188]">保留证据摘要，减少错位风险。</p>
            </div>
          </div>
        </div>

        <div className="p-6 sm:p-10">
          <div className="mb-8 flex items-center justify-between gap-4 lg:justify-end">
            <div className="flex items-center gap-2 lg:hidden">
              <img src={systemMark} alt="巡常系统图标" className="size-11 rounded-md object-contain" />
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-[#10233F]">巡常临床数据智能管理系统</p>
                <p className="text-xs text-[#5D7188]">账号登录</p>
              </div>
            </div>
            <img
              src={fortuneLogo}
              alt="Fortune 势通"
              className="h-5 max-w-28 object-contain sm:h-6 sm:max-w-36 lg:h-7 lg:max-w-52"
            />
          </div>

          <div className="mb-6">
            <p className="text-xs font-semibold uppercase text-[#0F78D4]">
              Secure Sign In
            </p>
            <h2 className="mt-3 text-2xl font-semibold tracking-normal text-[#10233F]">账号登录</h2>
            <p className="mt-2 text-sm text-[#5D7188]">进入巡常临床数据智能管理系统</p>
          </div>

          <form className="space-y-4" onSubmit={handleSubmit}>
            <label className="block text-sm font-medium text-[#39506A]">
              账号
              <input
                className="mt-1 h-11 w-full rounded-md border border-[#DDE7F0] bg-white px-3 text-sm text-[#10233F] outline-none transition placeholder:text-slate-400 focus:border-[#0F78D4] focus:ring-2 focus:ring-[#0F78D4]/10"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                placeholder="admin"
                autoComplete="username"
                required
              />
            </label>
            <label className="block text-sm font-medium text-[#39506A]">
              密码
              <input
                type="password"
                className="mt-1 h-11 w-full rounded-md border border-[#DDE7F0] bg-white px-3 text-sm text-[#10233F] outline-none transition placeholder:text-slate-400 focus:border-[#0F78D4] focus:ring-2 focus:ring-[#0F78D4]/10"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="********"
                autoComplete="current-password"
                required
              />
            </label>
            {error && <p className="text-sm text-rose-600">{error}</p>}
            <Button type="submit" className="h-11 w-full" disabled={loading}>
              {loading ? "登录中" : "进入系统"}
            </Button>
          </form>
        </div>
      </section>
    </main>
  );
}
