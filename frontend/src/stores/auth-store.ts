import { create } from "zustand";

import type { CurrentUser } from "@/types/auth";

const TOKEN_KEY = "clinical_data_system_token";

function readStoredToken() {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

type AuthState = {
  token: string | null;
  user: CurrentUser | null;
  initialized: boolean;
  setToken: (token: string) => void;
  setUser: (user: CurrentUser | null) => void;
  setInitialized: (initialized: boolean) => void;
  clearSession: () => void;
  hasPermission: (permission: string) => boolean;
  hasAnyPermission: (permissions: string[]) => boolean;
};

export const useAuthStore = create<AuthState>((set, get) => ({
  token: readStoredToken(),
  user: null,
  initialized: false,
  setToken: (token) => {
    window.localStorage.setItem(TOKEN_KEY, token);
    set({ token });
  },
  setUser: (user) => set({ user }),
  setInitialized: (initialized) => set({ initialized }),
  clearSession: () => {
    window.localStorage.removeItem(TOKEN_KEY);
    set({ token: null, user: null, initialized: true });
  },
  hasPermission: (permission) => {
    const user = get().user;
    return Boolean(user?.is_admin || user?.permissions?.includes(permission));
  },
  hasAnyPermission: (permissions) => {
    const user = get().user;
    return Boolean(user?.is_admin || permissions.some((permission) => user?.permissions?.includes(permission)));
  },
}));
