import { http } from "@/services/http";
import type { HealthResponse, VersionResponse } from "@/types/health";

export async function getHealth() {
  const response = await http.get<HealthResponse>("/health");
  return response.data;
}

export async function getVersion() {
  const response = await http.get<VersionResponse>("/version");
  return response.data;
}

