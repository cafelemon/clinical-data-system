import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuthStore } from "@/stores/auth-store";

export function SettingsPage() {
  const hasPermission = useAuthStore((state) => state.hasPermission);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-normal text-slate-950">系统设置</h1>
        <p className="mt-1 text-sm text-slate-500">字典、权限和系统参数将在后续阶段接入</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>配置项</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 rounded-md border border-dashed border-slate-300 bg-slate-50 p-4 sm:grid-cols-3">
            {hasPermission("dictionaries:read") && (
              <Button asChild variant="secondary">
                <Link to="/dictionaries">状态字典</Link>
              </Button>
            )}
            {hasPermission("users:read") && (
              <Button asChild variant="secondary">
                <Link to="/users">用户管理</Link>
              </Button>
            )}
            {hasPermission("roles:read") && (
              <Button asChild variant="secondary">
                <Link to="/roles">角色管理</Link>
              </Button>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
