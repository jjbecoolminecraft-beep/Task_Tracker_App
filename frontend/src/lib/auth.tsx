import { create } from "zustand";
import { api, setAccessToken } from "./api";
import type { SessionInfo } from "./types";

/**
 * Local dev auth stub. The access token lives in memory only; we remember *which*
 * seeded user was chosen (not the token) in sessionStorage so a page reload can
 * silently re-mint one. Production swaps this for MSAL + Entra ID (docs/adr/0002).
 */
const DEV_USER_KEY = "tt.devUserId";

interface AuthState {
  session: SessionInfo | null;
  status: "loading" | "authenticated" | "anonymous";
  loginAs: (userId: string) => Promise<void>;
  logout: () => void;
  bootstrap: () => Promise<void>;
}

async function mintToken(userId: string): Promise<SessionInfo> {
  const { data } = await api<{ access_token: string }>("/auth/dev-login", {
    method: "POST",
    body: { user_id: userId },
  });
  setAccessToken(data.access_token);
  const me = await api<SessionInfo>("/auth/me");
  return me.data;
}

export const useAuth = create<AuthState>((set) => ({
  session: null,
  status: "loading",

  loginAs: async (userId) => {
    const session = await mintToken(userId);
    try {
      sessionStorage.setItem(DEV_USER_KEY, userId);
    } catch {
      /* private mode */
    }
    set({ session, status: "authenticated" });
  },

  logout: () => {
    setAccessToken(null);
    try {
      sessionStorage.removeItem(DEV_USER_KEY);
    } catch {
      /* ignore */
    }
    set({ session: null, status: "anonymous" });
  },

  bootstrap: async () => {
    let remembered: string | null = null;
    try {
      remembered = sessionStorage.getItem(DEV_USER_KEY);
    } catch {
      /* ignore */
    }
    if (!remembered) {
      set({ status: "anonymous" });
      return;
    }
    try {
      const session = await mintToken(remembered);
      set({ session, status: "authenticated" });
    } catch {
      setAccessToken(null);
      set({ status: "anonymous" });
    }
  },
}));

export function hasRole(session: SessionInfo | null, ...roles: string[]): boolean {
  return !!session?.roles.some((r) => roles.includes(r.role));
}
