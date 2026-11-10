export type StoredMessage = {
  role: "user" | "assistant";
  content: string;
  sources?: unknown[];
  graph?: unknown[];
  triage?: unknown;
};

export type ChatThread = {
  id: string;
  title: string;
  updatedAt: number;
  messages: StoredMessage[];
};

export type ChatAction = { type: "new" } | { type: "open"; id: string } | { type: "refresh" };

export const CHAT_EVENT = "rag-chat";
export const DEFAULT_CHAT_NS = "triage-chat";

function threadsKey(namespace: string) {
  return `${namespace}-threads`;
}

function currentKey(namespace: string) {
  return `${namespace}-current`;
}

export function loadThreads(namespace = DEFAULT_CHAT_NS): ChatThread[] {
  try {
    const raw = localStorage.getItem(threadsKey(namespace));
    const parsed = raw ? (JSON.parse(raw) as ChatThread[]) : [];
    return Array.isArray(parsed)
      ? parsed.sort((a, b) => b.updatedAt - a.updatedAt)
      : [];
  } catch {
    return [];
  }
}

export function saveThreads(threads: ChatThread[], namespace = DEFAULT_CHAT_NS) {
  localStorage.setItem(threadsKey(namespace), JSON.stringify(threads.slice(0, 40)));
  window.dispatchEvent(new CustomEvent(CHAT_EVENT, { detail: { type: "refresh" } }));
}

export function getCurrentThreadId(namespace = DEFAULT_CHAT_NS) {
  return localStorage.getItem(currentKey(namespace)) || "";
}

export function setCurrentThreadId(id: string, namespace = DEFAULT_CHAT_NS) {
  if (id) localStorage.setItem(currentKey(namespace), id);
  else localStorage.removeItem(currentKey(namespace));
}

export function titleFromMessages(messages: StoredMessage[]) {
  const first = messages.find((item) => item.role === "user")?.content.trim() || "แชทใหม่";
  return first.length > 36 ? `${first.slice(0, 36)}…` : first;
}

export function upsertThread(id: string, messages: StoredMessage[], namespace = DEFAULT_CHAT_NS) {
  if (messages.length === 0) return;
  const threads = loadThreads(namespace).filter((item) => item.id !== id);
  threads.unshift({
    id,
    title: titleFromMessages(messages),
    updatedAt: Date.now(),
    messages,
  });
  setCurrentThreadId(id, namespace);
  saveThreads(threads, namespace);
}

export function deleteThread(id: string, namespace = DEFAULT_CHAT_NS) {
  const threads = loadThreads(namespace).filter((item) => item.id !== id);
  saveThreads(threads, namespace);
  if (getCurrentThreadId(namespace) === id) setCurrentThreadId("", namespace);
}

export function emitChat(action: ChatAction) {
  window.dispatchEvent(new CustomEvent(CHAT_EVENT, { detail: action }));
}

export function newThreadId() {
  return `chat-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

export function chatNamespace(role: string | null, username = "") {
  if (role === "patient") return `patient-chat-${username || "guest"}`;
  return DEFAULT_CHAT_NS;
}
