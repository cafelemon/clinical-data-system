import { create } from "zustand";

type AppState = {
  selectedProjectCode: string | null;
  setSelectedProjectCode: (code: string | null) => void;
};

export const useAppStore = create<AppState>((set) => ({
  selectedProjectCode: null,
  setSelectedProjectCode: (code) => set({ selectedProjectCode: code }),
}));

