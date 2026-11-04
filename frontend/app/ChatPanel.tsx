"use client";

import { FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import {
  CHAT_EVENT,
  getCurrentThreadId,
  loadThreads,
  newThreadId,
  setCurrentThreadId,
  upsertThread,
  type ChatAction,
  type StoredMessage,
} from "./chatStore";
import { API, readError } from "./lib";

type ChatPanelProps = {
  namespace: string;
  title: string;
  eyebrow: string;
  subtitle: string;
  emptyTitle: string;
  emptyBody: string;
  prompts: string[];
  placeholder: string;
  endpoint: string;
  extraBody?: Record<string, unknown>;
  busyLabel?: string;
  renderExtra?: (message: StoredMessage) => ReactNode;
};

export default function ChatPanel({
  namespace,
  title,
  eyebrow,
  subtitle,
  emptyTitle,
  emptyBody,
  prompts,
  placeholder,
  endpoint,
  extraBody,
  busyLabel = "กำลังคิดคำตอบ...",
  renderExtra,
}: ChatPanelProps) {
  const [threadId, setThreadId] = useState("");
  const [messages, setMessages] = useState<StoredMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [hydrated, setHydrated] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  function startNewChat() {
    const id = newThreadId();
    setThreadId(id);
    setCurrentThreadId(id, namespace);
    setMessages([]);
    setInput("");
    setError("");
  }

  function openThread(id: string) {
    const thread = loadThreads(namespace).find((item) => item.id === id);
    if (!thread) {
      startNewChat();
      return;
    }
    setThreadId(thread.id);
    setCurrentThreadId(thread.id, namespace);
    setMessages(thread.messages);
    setError("");
  }

  useEffect(() => {
    setHydrated(true);
    const current = getCurrentThreadId(namespace);
    const thread = loadThreads(namespace).find((item) => item.id === current);
    if (thread) {
      setThreadId(thread.id);
      setMessages(thread.messages);
    } else {
      const id = newThreadId();
      setThreadId(id);
      setCurrentThreadId(id, namespace);
    }

    function onChat(event: Event) {
      const action = (event as CustomEvent<ChatAction>).detail;
      if (!action) return;
      if (action.type === "new") startNewChat();
      if (action.type === "open") openThread(action.id);
    }
    window.addEventListener(CHAT_EVENT, onChat);
    return () => window.removeEventListener(CHAT_EVENT, onChat);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [namespace]);

  useEffect(() => {
    if (!threadId || messages.length === 0) return;
    upsertThread(threadId, messages, namespace);
  }, [threadId, messages, namespace]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function send(text: string, event?: FormEvent) {
    event?.preventDefault();
    const prompt = text.trim();
    if (!prompt || busy) return;

    const history = messages.map(({ role, content }) => ({ role, content }));
    const nextMessages: StoredMessage[] = [...messages, { role: "user", content: prompt }];
    setMessages(nextMessages);
    setInput("");
    setBusy(true);
    setError("");

    try {
      const res = await fetch(`${API}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: prompt, history, ...extraBody }),
      });
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content: data.answer || "ยังสรุปผลไม่ได้",
          sources: data.sources || [],
          triage: data.ready != null ? data : undefined,
        },
      ]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "ส่งข้อความไม่สำเร็จ";
      setError(message);
      setMessages([
        ...nextMessages,
        { role: "assistant", content: `ส่งข้อความไม่สำเร็จ: ${message}` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  if (!hydrated) {
    return (
      <div className="flex h-full flex-col">
        <header className="border-b border-white/10 px-4 py-3 md:px-6">
          <p className="text-[10px] tracking-[0.24em] text-cyan-300">{eyebrow}</p>
          <p className="font-semibold text-white">{title}</p>
        </header>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b border-white/10 px-4 py-3 md:px-6">
        <div>
          <p className="text-[10px] tracking-[0.24em] text-cyan-300">{eyebrow}</p>
          <p className="font-semibold text-white">{title}</p>
          <p className="text-xs text-slate-400">{subtitle}</p>
        </div>
        <button
          type="button"
          className="rounded-full border border-white/10 px-3 py-1 text-sm text-slate-300 hover:bg-white/5"
          onClick={startNewChat}
        >
          เริ่มใหม่
        </button>
      </header>

      <div className="flex-1 overflow-y-auto px-4 py-6 md:px-10">
        {messages.length === 0 && (
          <div className="glass-panel mx-auto mt-10 max-w-xl rounded-3xl p-8">
            <p className="text-xl font-semibold text-white">{emptyTitle}</p>
            <p className="mt-2 text-sm text-slate-400">{emptyBody}</p>
            <div className="mt-5 flex flex-wrap gap-2">
              {prompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  disabled={busy}
                  onClick={() => void send(prompt)}
                  className="rounded-full border border-white/10 bg-white/5 px-3 py-2 text-left text-sm text-slate-200 hover:border-cyan-300/40 hover:text-cyan-100 disabled:opacity-50"
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="mx-auto flex max-w-3xl flex-col gap-4">
          {messages.map((message, index) => (
            <article
              key={`${message.role}-${index}`}
              className={`max-w-[90%] rounded-3xl px-4 py-3 leading-relaxed ${
                message.role === "user"
                  ? "ml-auto border border-cyan-300/25 bg-cyan-300/15 text-cyan-50"
                  : "glass-panel text-slate-100"
              }`}
            >
              <p className="whitespace-pre-wrap">{message.content.replaceAll("**", "")}</p>
              {message.role === "assistant" && renderExtra?.(message)}
            </article>
          ))}
          {busy && <p className="text-sm text-slate-400">{busyLabel}</p>}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="border-t border-white/10 bg-[#0b1220]/80 px-4 py-4 backdrop-blur md:px-10">
        {error && <p className="mx-auto mb-2 max-w-3xl text-sm text-rose-300">{error}</p>}
        <form onSubmit={(event) => void send(input, event)} className="mx-auto flex max-w-3xl items-stretch gap-2">
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder={placeholder}
            className="flex-1 rounded-2xl border border-white/10 bg-[#070b14] px-4 py-3 text-slate-100 outline-none placeholder:text-slate-500 focus:border-cyan-300/50"
            disabled={busy}
          />
          <button
            type="submit"
            disabled={busy || !input.trim()}
            className="rounded-2xl bg-cyan-400 px-5 py-3 font-medium text-slate-950 disabled:opacity-50"
          >
            ส่ง
          </button>
        </form>
      </div>
    </div>
  );
}
