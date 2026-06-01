import { http } from "@/services/http";
import type {
  TrialProtocolApplyResult,
  TrialProtocolDraft,
  TrialProtocolVersion,
  TrialProtocolVersionSummary,
} from "@/types/trial-protocol";

export const trialProtocolApi = {
  listVersions: async (projectId: number) => {
    const response = await http.get<TrialProtocolVersionSummary[]>(
      `/projects/${projectId}/protocol-versions`,
    );
    return response.data;
  },
  uploadVersion: async (projectId: number, file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const response = await http.post<TrialProtocolVersion>(
      `/projects/${projectId}/protocol-versions`,
      formData,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return response.data;
  },
  getVersion: async (projectId: number, versionId: number) => {
    const response = await http.get<TrialProtocolVersion>(
      `/projects/${projectId}/protocol-versions/${versionId}`,
    );
    return response.data;
  },
  updateDraft: async (projectId: number, versionId: number, draft: TrialProtocolDraft) => {
    const response = await http.patch<TrialProtocolVersion>(
      `/projects/${projectId}/protocol-versions/${versionId}/draft`,
      draft,
    );
    return response.data;
  },
  applyVersion: async (projectId: number, versionId: number) => {
    const response = await http.post<TrialProtocolApplyResult>(
      `/projects/${projectId}/protocol-versions/${versionId}/apply`,
    );
    return response.data;
  },
};
