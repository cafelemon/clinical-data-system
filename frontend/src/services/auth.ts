import { http } from "@/services/http";
import type { CurrentUser, LoginResponse } from "@/types/auth";

export const authApi = {
  async login(username: string, password: string) {
    const response = await http.post<LoginResponse>("/auth/login", { username, password });
    return response.data;
  },

  async logout() {
    await http.post("/auth/logout");
  },

  async me() {
    const response = await http.get<CurrentUser>("/auth/me");
    return response.data;
  },

  async changePassword(currentPassword: string, newPassword: string) {
    await http.post("/auth/change-password", {
      current_password: currentPassword,
      new_password: newPassword,
    });
  },
};

