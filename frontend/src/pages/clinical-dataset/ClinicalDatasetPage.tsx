import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ClinicalDatasetPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-normal text-slate-950">临床数据集</h1>
        <p className="mt-1 text-sm text-slate-500">受试者资料链路将在 P3 接入</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>数据集概览</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex h-36 items-center justify-center rounded-md border border-dashed border-slate-300 bg-slate-50">
            <Badge>等待主数据与资料模板</Badge>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

