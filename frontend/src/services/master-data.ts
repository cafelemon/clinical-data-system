import { http } from "@/services/http";
import type {
  Center,
  CenterPayload,
  DictionaryItem,
  DictionaryPayload,
  Project,
  ProjectPayload,
  Stage,
  StageOptionGroup,
  StagePayload,
  StageTemplate,
  StageTemplatePayload,
} from "@/types/master-data";

async function read<T>(url: string, params?: Record<string, unknown>) {
  const response = await http.get<T>(url, { params });
  return response.data;
}

async function create<T, P>(url: string, payload: P) {
  const response = await http.post<T>(url, payload);
  return response.data;
}

async function update<T, P>(url: string, payload: Partial<P>) {
  const response = await http.put<T>(url, payload);
  return response.data;
}

async function remove(url: string) {
  await http.delete(url);
}

export const masterDataApi = {
  listProjects: () => read<Project[]>("/projects"),
  createProject: (payload: ProjectPayload) => create<Project, ProjectPayload>("/projects", payload),
  updateProject: (id: number, payload: Partial<ProjectPayload>) =>
    update<Project, ProjectPayload>(`/projects/${id}`, payload),
  deleteProject: (id: number) => remove(`/projects/${id}`),

  listCenters: (projectId?: number) => read<Center[]>("/centers", { project_id: projectId }),
  createCenter: (payload: CenterPayload) => create<Center, CenterPayload>("/centers", payload),
  updateCenter: (id: number, payload: Partial<CenterPayload>) =>
    update<Center, CenterPayload>(`/centers/${id}`, payload),
  deleteCenter: (id: number) => remove(`/centers/${id}`),

  listStageOptions: () => read<StageOptionGroup[]>("/stage-options"),
  listStages: (projectId?: number, phaseCode?: string, includeSystem = false, enabled?: boolean) =>
    read<Stage[]>("/stages", {
      project_id: projectId,
      phase_code: phaseCode,
      include_system: includeSystem,
      enabled,
    }),
  createStage: (payload: StagePayload) => create<Stage, StagePayload>("/stages", payload),
  updateStage: (id: number, payload: Partial<StagePayload>) =>
    update<Stage, StagePayload>(`/stages/${id}`, payload),
  deleteStage: (id: number) => remove(`/stages/${id}`),

  listStageTemplates: (projectId?: number, stageId?: number, templateScope?: string) =>
    read<StageTemplate[]>("/stage-templates", {
      project_id: projectId,
      stage_id: stageId,
      template_scope: templateScope,
    }),
  createStageTemplate: (payload: StageTemplatePayload) =>
    create<StageTemplate, StageTemplatePayload>("/stage-templates", payload),
  updateStageTemplate: (id: number, payload: Partial<StageTemplatePayload>) =>
    update<StageTemplate, StageTemplatePayload>(`/stage-templates/${id}`, payload),
  deleteStageTemplate: (id: number) => remove(`/stage-templates/${id}`),

  listDictionaries: (dictType?: string) =>
    read<DictionaryItem[]>("/dictionaries", { dict_type: dictType }),
  createDictionary: (payload: DictionaryPayload) =>
    create<DictionaryItem, DictionaryPayload>("/dictionaries", payload),
  updateDictionary: (id: number, payload: Partial<DictionaryPayload>) =>
    update<DictionaryItem, DictionaryPayload>(`/dictionaries/${id}`, payload),
  deleteDictionary: (id: number) => remove(`/dictionaries/${id}`),
};
