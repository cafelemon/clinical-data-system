import { http } from "@/services/http";
import type { SystemManagementOverview } from "@/types/system-management";

export const systemManagementApi = {
  async getOverview() {
    const response = await http.get<SystemManagementOverview>("/system-management/overview");
    return response.data;
  },
};
