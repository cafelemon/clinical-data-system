import { http } from "@/services/http";
import type { OperationLogFilters, OperationLogList } from "@/types/operation-log";

export const operationLogsApi = {
  list: async (params: OperationLogFilters) => {
    const response = await http.get<OperationLogList>("/operation-logs", { params });
    return response.data;
  },
};
