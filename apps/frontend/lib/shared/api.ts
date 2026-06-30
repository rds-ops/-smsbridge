const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

type AuthPayload = {
  access_token: string;
  refresh_token: string;
  user?: unknown;
};

export class ApiClientError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
  }
}

export function getToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("access_token") || "";
}

export function getRefreshToken() {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("refresh_token") || "";
}

export function notifyAuthChanged() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event("smsbridge-auth-changed"));
}

export function notifyDataChanged() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event("smsbridge-data-changed"));
}

export function saveAuthTokens(payload: AuthPayload) {
  localStorage.setItem("access_token", payload.access_token);
  localStorage.setItem("refresh_token", payload.refresh_token);
  notifyAuthChanged();
}

export function clearAuthTokens() {
  if (typeof window === "undefined") return;
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  notifyAuthChanged();
}

export function logout() {
  const refreshToken = getRefreshToken();
  if (refreshToken) {
    void fetch(`${API_BASE}/auth/logout`, {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({refresh_token: refreshToken}),
      cache: "no-store"
    }).catch(() => null);
  }
  clearAuthTokens();
}

export async function logoutAll() {
  const token = getToken();
  try {
    if (!token) return {status: "ok", revoked_sessions: 0};
    const response = await fetch(`${API_BASE}/auth/logout-all`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`
      },
      cache: "no-store"
    });
    if (!response.ok) throw await parseApiError(response);
    return response.json() as Promise<{status: string; revoked_sessions: number}>;
  } finally {
    clearAuthTokens();
  }
}

function isAuthEndpoint(path: string) {
  return path === "/auth/login" || path === "/auth/register" || path === "/auth/refresh";
}

function readableError(payload: unknown, fallback: string) {
  if (!payload || typeof payload !== "object") return fallback;
  const detail = (payload as {detail?: unknown}).detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object" && "message" in detail) {
    return String((detail as {message: unknown}).message);
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (!item || typeof item !== "object") return String(item);
        const msg = "msg" in item ? String((item as {msg: unknown}).msg) : "Invalid value";
        const loc = "loc" in item && Array.isArray((item as {loc: unknown}).loc)
          ? (item as {loc: unknown[]}).loc.join(".")
          : "";
        return loc ? `${loc}: ${msg}` : msg;
      })
      .join("; ");
  }
  return fallback;
}

async function parseApiError(response: Response): Promise<ApiClientError> {
  const fallback = response.statusText || `Request failed with ${response.status}`;
  try {
    const payload = await response.clone().json();
    return new ApiClientError(readableError(payload, fallback), response.status);
  } catch {
    const text = await response.text();
    return new ApiClientError(text || fallback, response.status);
  }
}

async function refreshAccessToken() {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return false;
  const response = await fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({refresh_token: refreshToken}),
    cache: "no-store"
  });
  if (!response.ok) {
    clearAuthTokens();
    return false;
  }
  saveAuthTokens(await response.json());
  return true;
}

function redirectToLoginOnAuthFailure() {
  if (typeof window === "undefined") return;
  if (!window.location.pathname.startsWith("/login")) {
    window.location.href = "/login";
  }
}

function localizedClientMessage(key: "session" | "network") {
  const locale = typeof window !== "undefined" ? localStorage.getItem("locale") : "en";
  const messages = {
    session: {
      en: "Your session expired. Please log in again.",
      ru: "Сессия истекла. Войдите снова."
    },
    network: {
      en: "Could not reach the API. Please check that the backend is running and try again.",
      ru: "Не удалось подключиться к API. Проверьте, что backend запущен, и попробуйте снова."
    }
  };
  return locale === "ru" ? messages[key].ru : messages[key].en;
}

export async function apiFetch<T>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) headers.set("Content-Type", "application/json");
  if (token && !isAuthEndpoint(path)) headers.set("Authorization", `Bearer ${token}`);
  const method = (options.method || "GET").toUpperCase();
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {...options, headers, cache: "no-store"});
  } catch {
    throw new ApiClientError(localizedClientMessage("network"), 0);
  }
  if (response.status === 401 && retry && !isAuthEndpoint(path)) {
    const refreshed = await refreshAccessToken();
    if (refreshed) return apiFetch<T>(path, options, false);
  }
  if (!response.ok) {
    const error = await parseApiError(response);
    if (error.status === 401 && !isAuthEndpoint(path)) {
      clearAuthTokens();
      redirectToLoginOnAuthFailure();
      throw new ApiClientError(localizedClientMessage("session"), 401);
    }
    throw error;
  }
  const data = await response.json();
  if (method !== "GET" && !isAuthEndpoint(path)) notifyDataChanged();
  return data;
}

export async function auth(path: string, payload: unknown) {
  const data = await apiFetch<AuthPayload>(path, {
    method: "POST",
    body: JSON.stringify(payload)
  });
  saveAuthTokens(data);
  return data;
}

export async function currentUser() {
  return apiFetch<{id: number; email: string; role: "user" | "admin"; status: string; tier: string; locale: "en" | "ru"}>("/auth/me");
}
