import { Plus } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function ProjectsPage() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-normal text-slate-950">项目管理</h1>
          <p className="mt-1 text-sm text-slate-500">项目主数据将在 P1 接入</p>
        </div>
        <Button disabled>
          <Plus className="size-4" aria-hidden="true" />
          新建项目
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>项目列表</CardTitle>
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

