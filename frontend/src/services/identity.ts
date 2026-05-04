import { http } from "@/services/http";
import type { Permission, Role, RolePayload, User, UserPayload } from "@/types/auth";

export const identityApi = {
  async listUsers() {
    const response = await http.get<User[]>("/users");
    return response.data;
  },

  async createUser(payload: UserPayload & { password: string }) {
    const response = await http.post<User>("/users", payload);
    return response.data;
  },

  async updateUser(id: number, payload: Partial<UserPayload>) {
    const response = await http.put<User>(`/users/${id}`, payload);
    return response.data;
  },

  async deleteUser(id: number) {
    await http.delete(`/users/${id}`);
  },

  async listRoles() {
    const response = await http.get<Role[]>("/roles");
    return response.data;
  },

  async createRole(payload: RolePayload) {
    const response = await http.post<Role>("/roles", payload);
    return response.data;
  },

  async updateRole(id: number, payload: Partial<Omit<RolePayload, "name">>) {
    const response = await http.put<Role>(`/roles/${id}`, payload);
    return response.data;
  },

  async listPermissions() {
    const response = await http.get<Permission[]>("/permissions");
    return response.data;
  },
};

