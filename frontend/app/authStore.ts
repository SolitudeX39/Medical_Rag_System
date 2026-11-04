export const AUTH_EVENT = "rag-auth";
const AUTH_KEY = "rag-auth-user";

const DEMO_USER = "admin";
const DEMO_PASS = "test1234";

export function getAuthUser() {
  try {
    return localStorage.getItem(AUTH_KEY) || "";
  } catch {
    return "";
  }
}

export function isLoggedIn() {
  return getAuthUser() === DEMO_USER;
}

export function login(username: string, password: string) {
  if (username.trim() === DEMO_USER && password === DEMO_PASS) {
    localStorage.setItem(AUTH_KEY, DEMO_USER);
    window.dispatchEvent(new Event(AUTH_EVENT));
    return true;
  }
  return false;
}

export function logout() {
  localStorage.removeItem(AUTH_KEY);
  window.dispatchEvent(new Event(AUTH_EVENT));
}
