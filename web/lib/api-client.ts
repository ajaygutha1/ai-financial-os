import type { TokenResponse } from "@/types/api";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

// Access tokens live only in memory (never localStorage) to limit XSS blast
// radius; the refresh token is an httpOnly cookie the browser attaches
// automatically. Losing the in-memory token on a hard refresh is expected --
// AuthProvider re-derives it via a silent /auth/refresh call on mount.
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string
  ) {
    super(message);
    this.name = "ApiError";
  }
}

// Double-submit CSRF cookie (Milestone 8) -- set by the backend alongside
// the refresh token cookie, deliberately not httpOnly so it can be read
// here and echoed back as a header. A cross-site attacker's page can
// trigger a request with the cookie attached automatically, but can't read
// this cookie's value to put it in the header too.
const CSRF_COOKIE_NAME = "finos_csrf_token";

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

async function refreshAccessToken(): Promise<string | null> {
  const csrfToken = readCookie(CSRF_COOKIE_NAME);
  const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
    method: "POST",
    credentials: "include",
    headers: csrfToken ? { "X-CSRF-Token": csrfToken } : undefined,
  });
  if (!response.ok) {
    setAccessToken(null);
    return null;
  }
  const data = (await response.json()) as TokenResponse;
  setAccessToken(data.access_token);
  return data.access_token;
}

function buildHeaders(token: string | null, options: RequestInit): HeadersInit {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const csrfToken = readCookie(CSRF_COOKIE_NAME);
  if (csrfToken) {
    headers.set("X-CSRF-Token", csrfToken);
  }
  return headers;
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const doFetch = (token: string | null) =>
    fetch(`${API_BASE_URL}${path}`, {
      ...options,
      credentials: "include",
      headers: buildHeaders(token, options),
    });

  let response = await doFetch(accessToken);

  if (response.status === 401 && accessToken !== null) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      response = await doFetch(refreshed);
    }
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({ detail: response.statusText }));
    throw new ApiError(response.status, body.detail ?? response.statusText);
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export { refreshAccessToken };
