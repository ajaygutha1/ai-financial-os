"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch, refreshAccessToken, setAccessToken } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";
import type { TokenResponse, UserPublic } from "@/types/api";

type AuthStatus = "loading" | "authenticated" | "unauthenticated";

interface AuthContextValue {
  user: UserPublic | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>("loading");

  // Access tokens are memory-only, so a hard page reload starts with none.
  // Silently attempt a refresh (using the httpOnly cookie) on first mount to
  // restore the session without ever putting a token in localStorage.
  useEffect(() => {
    let cancelled = false;
    void refreshAccessToken().then((token) => {
      if (!cancelled) setStatus(token ? "authenticated" : "unauthenticated");
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const meQuery = useQuery({
    queryKey: queryKeys.me,
    queryFn: () => apiFetch<UserPublic>("/api/v1/auth/me"),
    enabled: status === "authenticated",
    retry: false,
  });

  const login = async (email: string, password: string) => {
    const data = await apiFetch<TokenResponse>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setAccessToken(data.access_token);
    setStatus("authenticated");
    await queryClient.invalidateQueries({ queryKey: queryKeys.me });
  };

  const register = async (email: string, password: string, fullName?: string) => {
    const data = await apiFetch<TokenResponse>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name: fullName }),
    });
    setAccessToken(data.access_token);
    setStatus("authenticated");
    await queryClient.invalidateQueries({ queryKey: queryKeys.me });
  };

  const logout = async () => {
    await apiFetch("/api/v1/auth/logout", { method: "POST" });
    setAccessToken(null);
    setStatus("unauthenticated");
    queryClient.clear();
  };

  return (
    <AuthContext.Provider
      value={{ user: meQuery.data ?? null, status, login, register, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
