import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function CentersPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-normal text-slate-950">中心管理</h1>
        <p className="mt-1 text-sm text-slate-500">中心主数据将在 P1 接入</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>中心列表</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex h-36 items-center justify-center rounded-md border border-dashed border-slate-300 bg-slate-50">
            <Badge>等待 P1 数据模型</Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

