import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function SettingsPage() {
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
          <div className="flex h-36 items-center justify-center rounded-md border border-dashed border-slate-300 bg-slate-50">
            <Badge>等待 P1/P2 模块</Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

