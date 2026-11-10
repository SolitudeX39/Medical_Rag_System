export const AUTH_EVENT = "rag-auth";
const AUTH_KEY = "rag-auth-session";
const LEGACY_KEY = "rag-auth-user";

export type AuthRole = "staff" | "patient";

export type AuthSession = {
  username: string;
  role: AuthRole;
  name: string;
};

const LOCAL_ACCOUNTS: Record<string, { password: string; role: AuthRole; name: string }> = {
  admin: { password: "test1234", role: "staff", name: "เจ้าหน้าที่คัดกรอง" },
  staff: { password: "test1234", role: "staff", name: "พยาบาลคัดกรอง" },
  somchai: { password: "test1234", role: "patient", name: "สมชาย ใจดี" },
  malee: { password: "test1234", role: "patient", name: "มาลี สุขใจ" },
  nicha: { password: "test1234", role: "patient", name: "ณิชา วงศ์ศิลป์" },
};

export function homePath(role?: AuthRole | null) {
  return role === "patient" ? "/patient" : "/";
}

export function getSession(): AuthSession | null {
  try {
    const raw = localStorage.getItem(AUTH_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as AuthSession;
      if (parsed?.username && (parsed.role === "staff" || parsed.role === "patient")) {
        return parsed;
      }
    }
    const legacy = localStorage.getItem(LEGACY_KEY);
    if (legacy === "admin") {
      return { username: "admin", role: "staff", name: "เจ้าหน้าที่คัดกรอง" };
    }
  } catch {
    return null;
  }
  return null;
}

export function getAuthUser() {
  return getSession()?.username || "";
}

export function getAuthRole(): AuthRole | null {
  return getSession()?.role || null;
}

export function isLoggedIn() {
  return Boolean(getSession());
}

export function saveSession(session: AuthSession) {
  localStorage.setItem(AUTH_KEY, JSON.stringify(session));
  localStorage.removeItem(LEGACY_KEY);
  window.dispatchEvent(new Event(AUTH_EVENT));
}

export function loginLocal(username: string, password: string): AuthSession | null {
  const account = LOCAL_ACCOUNTS[username.trim().toLowerCase()];
  if (!account || account.password !== password) return null;
  const session = {
    username: username.trim().toLowerCase(),
    role: account.role,
    name: account.name,
  };
  saveSession(session);
  return session;
}

export function logout() {
  localStorage.removeItem(AUTH_KEY);
  localStorage.removeItem(LEGACY_KEY);
  window.dispatchEvent(new Event(AUTH_EVENT));
}
