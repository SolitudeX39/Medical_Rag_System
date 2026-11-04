"use client";

import { FormEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import GraphView, { factsToGraph, type GraphOverview } from "./GraphView";
import {
  CHAT_EVENT,
  getCurrentThreadId,
  loadThreads,
  newThreadId,
  setCurrentThreadId,
  upsertThread,
  type ChatAction,
} from "./chatStore";
import { API, type DocumentPage, type Source, readError, sourceLocationLabel } from "./lib";

type ChatMode = "ask" | "graph";

type GraphFact = {
  name: string;
  thai?: string;
  kind?: string;
  definition?: string;
  relation?: string;
  related_name?: string;
  related_thai?: string;
  related_definition?: string;
  relation_detail?: string;
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  graph?: GraphFact[];
};

type DocumentDetail = {
  name: string;
  id: string;
  pages: DocumentPage[];
  graph?: GraphOverview;
};

const FALLBACK_PROMPTS = [
  "Diagnosis ต่างจาก Prognosis อย่างไร?",
  "Hyper- กับ Hypo- แปลว่าอะไร?",
  "Myocardial infarction คืออะไร?",
  "คำย่อ NPO และ PRN หมายถึงอะไร?",
  "Hypertension เกี่ยวกับอะไรในกราฟ?",
];

const FALLBACK_GRAPH_PROMPTS = [
  "สร้างกราฟจากศัพท์ความดันโลหิตและความเสี่ยงโรคหัวใจ",
  "ดึงความสัมพันธ์ของ Hyper- Hypo- Brady- Tachy- จากเอกสาร",
  "เชื่อม Hypertension กับ Stroke และ Myocardial infarction",
];

function relationLabel(relation?: string) {
  return relation?.match(/-\[(.+)\]->/)?.[1] || "เกี่ยวข้อง";
}

function MessageSources({
  sources,
  defaultOpen = false,
  onOpen,
}: {
  sources: Source[];
  defaultOpen?: boolean;
  onOpen: (documentId: string, page?: number | null) => void;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="mt-3 border-t border-white/10 pt-2">
      <button
        type="button"
        className="flex w-full items-center justify-between text-left text-sm text-cyan-200 hover:text-white"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
      >
        <span>เอกสาร · {sources.length} แหล่ง</span>
        <span className="text-xs text-slate-400">{open ? "ซ่อน" : "แสดง"}</span>
      </button>
      {open && (
        <div className="mt-2 space-y-2">
          {sources.map((source, sourceIndex) => (
            <div key={sourceIndex} className="text-sm">
              <button
                type="button"
                className="cursor-pointer text-left text-cyan-300 underline-offset-2 hover:underline"
                onClick={() => {
                  if (source.document_id) {
                    onOpen(source.document_id, source.page);
                  }
                }}
              >
                ดูเอกสาร
                {source.filename ? ` · ${source.filename}` : ""}
                {typeof source.page === "number"
                  ? ` · ${sourceLocationLabel(source.filename, source.page)}`
                  : ""}
              </button>
              <p className="mt-2 max-h-28 overflow-y-auto whitespace-pre-wrap text-slate-400">
                {source.text}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function MessageGraph({ facts }: { facts: GraphFact[] }) {
  const graph = useMemo(() => factsToGraph(facts), [facts]);
  const highlight = useMemo(() => facts.map((fact) => fact.name), [facts]);
  const relations = useMemo(() => {
    const seen = new Set<string>();
    const items: Array<{
      from: string;
      to: string;
      fromThai?: string;
      toThai?: string;
      label: string;
      detail?: string;
      fromDefinition?: string;
      toDefinition?: string;
    }> = [];
    for (const fact of facts) {
      if (!fact.related_name) continue;
      const outgoing = !fact.relation || fact.relation.startsWith(fact.name);
      const from = outgoing ? fact.name : fact.related_name;
      const to = outgoing ? fact.related_name : fact.name;
      const key = `${from}->${to}:${relationLabel(fact.relation)}`;
      if (seen.has(key)) continue;
      seen.add(key);
      items.push({
        from,
        to,
        fromThai: outgoing ? fact.thai : fact.related_thai,
        toThai: outgoing ? fact.related_thai : fact.thai,
        label: relationLabel(fact.relation),
        detail: fact.relation_detail,
        fromDefinition: outgoing ? fact.definition : fact.related_definition,
        toDefinition: outgoing ? fact.related_definition : fact.definition,
      });
    }
    return items;
  }, [facts]);

  return (
    <div>
      <GraphView compact graph={graph} highlight={highlight} />
      {relations.length > 0 && (
        <div className="mt-3 space-y-3">
          <p className="text-[10px] tracking-[0.18em] text-cyan-300">ความสัมพันธ์</p>
          {relations.map((rel) => (
            <div key={`${rel.from}-${rel.label}-${rel.to}`} className="rounded-2xl border border-white/10 bg-white/5 px-3 py-3">
              <p className="text-sm font-medium text-white">
                {rel.from}
                {rel.fromThai ? ` (${rel.fromThai})` : ""}
                <span className="mx-2 text-cyan-300">{rel.label}</span>
                {rel.to}
                {rel.toThai ? ` (${rel.toThai})` : ""}
              </p>
              {rel.fromDefinition && (
                <p className="mt-2 text-sm leading-relaxed text-slate-300">
                  <span className="text-slate-500">{rel.from}: </span>
                  {rel.fromDefinition}
                </p>
              )}
              {rel.toDefinition && (
                <p className="mt-1 text-sm leading-relaxed text-slate-300">
                  <span className="text-slate-500">{rel.to}: </span>
                  {rel.toDefinition}
                </p>
              )}
              {rel.detail && (
                <p className="mt-2 text-sm leading-relaxed text-slate-200">{rel.detail}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function Home() {
  const [threadId, setThreadId] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<ChatMode>("ask");
  const [modeMenuOpen, setModeMenuOpen] = useState(false);
  const [prompts, setPrompts] = useState<string[]>(FALLBACK_PROMPTS);
  const [graphPrompts, setGraphPrompts] = useState<string[]>(FALLBACK_GRAPH_PROMPTS);
  const [error, setError] = useState("");
  const [viewer, setViewer] = useState<DocumentDetail | null>(null);
  const [viewerLoading, setViewerLoading] = useState(false);
  const [activePage, setActivePage] = useState<number | null>(null);
  const [graphOpen, setGraphOpen] = useState(false);
  const [graphFullscreen, setGraphFullscreen] = useState(false);
  const [graph, setGraph] = useState<GraphOverview | null>(null);
  const [graphLoading, setGraphLoading] = useState(false);
  const [hydrated, setHydrated] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const pageRefs = useRef<Record<number, HTMLElement | null>>({});
  const modeMenuRef = useRef<HTMLDivElement>(null);

  const loadGraph = useCallback(async () => {
    setGraphLoading(true);
    try {
      const res = await fetch(`${API}/graph`);
      if (!res.ok) return;
      const data = (await res.json()) as GraphOverview;
      setGraph(data);
    } catch {
      setGraph({ nodes: [], links: [], skipped: true });
    } finally {
      setGraphLoading(false);
    }
  }, []);

  function startNewChat() {
    const id = newThreadId();
    setThreadId(id);
    setCurrentThreadId(id);
    setMessages([]);
    setInput("");
    setError("");
    setViewer(null);
  }

  function openThread(id: string) {
    const thread = loadThreads().find((item) => item.id === id);
    if (!thread) {
      startNewChat();
      return;
    }
    setThreadId(thread.id);
    setCurrentThreadId(thread.id);
    setMessages(thread.messages as ChatMessage[]);
    setError("");
  }

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    const current = getCurrentThreadId();
    const thread = loadThreads().find((item) => item.id === current);
    if (thread) {
      setThreadId(thread.id);
      setMessages(thread.messages as ChatMessage[]);
    } else {
      const id = newThreadId();
      setThreadId(id);
      setCurrentThreadId(id);
    }

    function onChat(event: Event) {
      const action = (event as CustomEvent<ChatAction>).detail;
      if (!action) return;
      if (action.type === "new") startNewChat();
      if (action.type === "open") openThread(action.id);
    }
    window.addEventListener(CHAT_EVENT, onChat);
    return () => window.removeEventListener(CHAT_EVENT, onChat);
  }, []);

  useEffect(() => {
    if (!threadId || messages.length === 0) return;
    upsertThread(threadId, messages);
  }, [threadId, messages]);

  useEffect(() => {
    void loadGraph();
    fetch(`${API}/prompts`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data?.prompts?.length) setPrompts(data.prompts);
        if (data?.graph_prompts?.length) setGraphPrompts(data.graph_prompts);
      })
      .catch(() => undefined);
  }, [loadGraph]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  useEffect(() => {
    if (!modeMenuOpen) return;
    function onPointerDown(event: MouseEvent) {
      if (!modeMenuRef.current?.contains(event.target as Node)) {
        setModeMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [modeMenuOpen]);

  useEffect(() => {
    if (activePage == null) return;
    pageRefs.current[activePage]?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [viewer, activePage]);

  useEffect(() => {
    if (!graphFullscreen) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setGraphFullscreen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [graphFullscreen]);

  async function openDocument(documentId: string, page?: number | null) {
    setViewerLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/documents/${encodeURIComponent(documentId)}`);
      if (!res.ok) throw new Error(await readError(res));
      const data = (await res.json()) as DocumentDetail;
      setViewer(data);
      if (data.graph) setGraph(data.graph);
      setActivePage(typeof page === "number" ? page : data.pages[0]?.page ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "เปิดเอกสารไม่สำเร็จ");
    } finally {
      setViewerLoading(false);
    }
  }

  async function send(text: string, event?: FormEvent) {
    event?.preventDefault();
    const prompt = text.trim();
    if (!prompt || busy) return;

    const history = messages.map(({ role, content }) => ({ role, content }));
    const nextMessages: ChatMessage[] = [...messages, { role: "user", content: prompt }];
    setMessages(nextMessages);
    setInput("");
    setBusy(true);
    setError("");

    try {
      const path = mode === "graph" ? "/graph/build" : "/chat";
      const res = await fetch(`${API}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: prompt, history }),
      });
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      if (data.overview) {
        setGraph(data.overview);
        setGraphOpen(true);
      }
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content: data.answer || "ไม่พบคำตอบ",
          sources: data.sources || [],
          graph: data.graph || [],
        },
      ]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "ส่งคำถามไม่สำเร็จ";
      setError(message);
      setMessages([
        ...nextMessages,
        {
          role: "assistant",
          content: `ส่งคำถามไม่สำเร็จ: ${message}`,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  if (!hydrated) {
    return (
      <div className="flex h-dvh overflow-hidden text-[var(--ink)]">
        <main className="flex min-w-0 flex-1 flex-col">
          <header className="flex items-center justify-between border-b border-white/10 px-4 py-3 md:px-6">
            <div>
              <p className="text-[10px] tracking-[0.24em] text-cyan-300">MEDICAL RAG AI</p>
              <p className="font-semibold text-white">Chat</p>
              <p className="text-xs text-slate-400">คุยจากเอกสารที่อัปโหลดไว้</p>
            </div>
          </header>
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-dvh overflow-hidden text-[var(--ink)]">
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-white/10 px-4 py-3 md:px-6">
          <div>
            <p className="text-[10px] tracking-[0.24em] text-cyan-300">MEDICAL RAG AI</p>
            <p className="font-semibold text-white">Chat</p>
            <p className="text-xs text-slate-400">
              {mode === "graph" ? "โหมดสร้างกราฟ Neo4j จากข้อความหรือเอกสาร" : "คุยจากเอกสารที่อัปโหลดไว้"}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1 text-sm text-cyan-100 hover:bg-cyan-300/20"
              onClick={() => {
                setGraphOpen((open) => {
                  if (open) setGraphFullscreen(false);
                  return !open;
                });
                if (!graph) void loadGraph();
              }}
            >
              กราฟ
            </button>
            <button
              type="button"
              className="rounded-full border border-white/10 px-3 py-1 text-sm text-slate-300 hover:bg-white/5"
              onClick={startNewChat}
            >
              New chat
            </button>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-4 py-6 md:px-10">
          {messages.length === 0 && (
            <div className="glass-panel mx-auto mt-10 max-w-xl rounded-3xl p-8">
              <p className="text-[10px] tracking-[0.24em] text-cyan-300">
                {mode === "graph" ? "GRAPH MODE" : "ASK MODE"}
              </p>
              <p className="mt-2 text-xl font-semibold text-white">
                {mode === "graph" ? "สร้างกราฟศัพท์ใน Neo4j" : "เริ่มคุยจากเอกสารได้เลย"}
              </p>
              <p className="mt-2 text-sm text-slate-400">
                {mode === "graph"
                  ? "บอกศัพท์และความสัมพันธ์ หรือให้ดึงจากเอกสารที่อัปโหลดไว้"
                  : "ระบบค้นจากทุกไฟล์ PDF และ CSV ที่เคยอัปโหลดไว้ รวมกันในคลังเดียว"}
              </p>
              <div className="mt-5 flex flex-wrap gap-2">
                {(mode === "graph" ? graphPrompts : prompts).map((prompt) => (
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
                {message.sources && message.sources.length > 0 && (
                  <MessageSources
                    sources={message.sources}
                    defaultOpen={!(message.graph && message.graph.length > 0)}
                    onOpen={(documentId, page) => void openDocument(documentId, page)}
                  />
                )}
                {message.graph && message.graph.length > 0 && (
                  <div className="mt-3 border-t border-white/10 pt-2">
                    <p className="mb-2 text-[10px] tracking-[0.18em] text-cyan-300">NEO4J GRAPH</p>
                    <MessageGraph facts={message.graph} />
                  </div>
                )}
              </article>
            ))}
            {busy && (
              <p className="text-sm text-slate-400">
                {mode === "graph" ? "กำลังอ่านเอกสาร แล้วสร้างกราฟความสัมพันธ์..." : "กำลังค้นเอกสารและร่างคำตอบ..."}
              </p>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        <div className="border-t border-white/10 bg-[#0b1220]/80 px-4 py-4 backdrop-blur md:px-10">
          {error && <p className="mx-auto mb-2 max-w-3xl text-sm text-rose-300">{error}</p>}
          <form onSubmit={(event) => void send(input, event)} className="mx-auto flex max-w-3xl items-stretch gap-2">
            <div ref={modeMenuRef} className="relative shrink-0">
              <button
                type="button"
                className={`flex h-12 w-12 items-center justify-center rounded-2xl border text-2xl leading-none transition ${
                  mode === "graph"
                    ? "border-violet-300/40 bg-violet-400/20 text-violet-100"
                    : "border-white/10 bg-white/5 text-slate-200 hover:border-cyan-300/40"
                }`}
                onClick={() => setModeMenuOpen((open) => !open)}
                aria-haspopup="menu"
                aria-expanded={modeMenuOpen}
                aria-label="เลือกโหมด"
              >
                +
              </button>
              {modeMenuOpen && (
                <div
                  role="menu"
                  className="absolute bottom-14 left-0 z-20 w-56 overflow-hidden rounded-2xl border border-white/10 bg-[#101827] py-1 shadow-2xl"
                >
                  <p className="px-3 py-2 text-[10px] tracking-[0.18em] text-slate-500">เลือกการใช้งาน</p>
                  <button
                    type="button"
                    role="menuitem"
                    className={`flex w-full flex-col px-3 py-2 text-left text-sm hover:bg-white/5 ${
                      mode === "ask" ? "bg-cyan-300/10 text-cyan-100" : "text-slate-200"
                    }`}
                    onClick={() => {
                      setMode("ask");
                      setModeMenuOpen(false);
                      setError("");
                    }}
                  >
                    <span className="font-medium">ถามเอกสาร</span>
                    <span className="text-xs text-slate-500">ค้นจากทุกไฟล์ที่เคยอัปโหลด</span>
                  </button>
                  <button
                    type="button"
                    role="menuitem"
                    className={`flex w-full flex-col px-3 py-2 text-left text-sm hover:bg-white/5 ${
                      mode === "graph" ? "bg-violet-400/15 text-violet-100" : "text-slate-200"
                    }`}
                    onClick={() => {
                      setMode("graph");
                      setModeMenuOpen(false);
                      setError("");
                    }}
                  >
                    <span className="font-medium">สร้างกราฟ Neo4j</span>
                    <span className="text-xs text-slate-500">สกัดศัพท์แล้วบันทึกลงกราฟ</span>
                  </button>
                </div>
              )}
            </div>
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder={
                mode === "graph"
                  ? "เช่น เชื่อม Hypertension กับ Stroke..."
                  : "ถามเอกสารได้เลย เช่น สรุปหน้านี้ให้หน่อย..."
              }
              className="flex-1 rounded-2xl border border-white/10 bg-[#070b14] px-4 py-3 text-slate-100 outline-none placeholder:text-slate-500 focus:border-cyan-300/50"
              disabled={busy}
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              className="rounded-2xl bg-cyan-400 px-5 py-3 font-medium text-slate-950 disabled:opacity-50"
            >
              {mode === "graph" ? "สร้าง" : "ส่ง"}
            </button>
          </form>
        </div>
      </main>

      {(viewer || viewerLoading) && (
        <section className="fixed inset-y-0 right-0 z-40 flex w-full max-w-2xl flex-col border-l border-white/10 bg-[#0b1220] shadow-2xl md:static md:z-0 md:w-[min(36rem,42vw)] md:shadow-none">
          <header className="flex items-start justify-between gap-3 border-b border-white/10 px-5 py-4">
            <div>
              <p className="text-[10px] tracking-[0.2em] text-cyan-300">DOCUMENT</p>
              <h2 className="mt-1 text-lg font-semibold leading-snug text-white">
                {viewer?.name || "กำลังเปิดเอกสาร..."}
              </h2>
            </div>
            <button
              type="button"
              className="rounded-full border border-white/15 px-3 py-1 text-sm text-slate-200"
              onClick={() => {
                setViewer(null);
                setActivePage(null);
              }}
            >
              ปิด
            </button>
          </header>
          <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
            {viewerLoading && <p className="text-sm text-slate-400">กำลังโหลดเนื้อหา...</p>}
            {viewer?.graph && !viewer.graph.skipped && viewer.graph.nodes.length > 0 && (
              <div className="mb-5 h-[22rem]">
                <GraphView graph={viewer.graph} />
              </div>
            )}
            {viewer?.pages.map((page, index) => (
              <article
                key={`${page.page}-${index}`}
                ref={(node) => {
                  if (typeof page.page === "number") pageRefs.current[page.page] = node;
                }}
                className={`mb-4 rounded-2xl border px-4 py-3 ${
                  activePage === page.page
                    ? "border-cyan-300/40 bg-cyan-300/10"
                    : "border-white/10 bg-white/5"
                }`}
              >
                <p className="text-xs font-medium text-cyan-300">
                  {sourceLocationLabel(viewer.name, page.page, index)}
                </p>
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-300">
                  {page.text}
                </p>
              </article>
            ))}
          </div>
        </section>
      )}

      {graphOpen && !viewer && (
        <section
          className={`flex flex-col bg-[#050814] text-slate-200 ${
            graphFullscreen
              ? "fixed inset-0 z-50"
              : "fixed inset-y-0 right-0 z-40 w-full max-w-3xl border-l border-cyan-300/15 shadow-[0_0_80px_rgba(8,47,73,0.45)] md:static md:z-0 md:w-[min(44rem,48vw)] md:shadow-none"
          }`}
        >
          <header className="flex items-start justify-between gap-3 border-b border-cyan-300/10 px-5 py-4">
            <div>
              <p className="flex items-center gap-2 text-[10px] tracking-[0.28em] text-cyan-300">
                <span className="h-1.5 w-1.5 rounded-full bg-cyan-300 shadow-[0_0_10px_#67e8f9]" />
                NEO4J
              </p>
              <h2 className="mt-1 text-lg font-semibold leading-snug text-white">กราฟศัพท์การแพทย์</h2>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                className="rounded-full border border-cyan-300/30 px-3 py-1 text-sm text-cyan-100 hover:bg-cyan-300/10"
                onClick={() => setGraphFullscreen((current) => !current)}
              >
                {graphFullscreen ? "ย่อ" : "ขยายเต็มจอ"}
              </button>
              <button
                type="button"
                className="rounded-full border border-white/15 px-3 py-1 text-sm text-slate-200 hover:border-cyan-300/40"
                onClick={() => {
                  setGraphOpen(false);
                  setGraphFullscreen(false);
                }}
              >
                ปิด
              </button>
            </div>
          </header>
          <div className="flex min-h-0 flex-1 flex-col px-5 py-4">
            {graphLoading && <p className="text-sm text-slate-400">กำลังซิงก์กราฟ...</p>}
            {!graphLoading && graph?.skipped && (
              <p className="text-sm text-slate-400">
                ยังเชื่อม Neo4j ไม่ได้ เปิด Docker แล้วกดเติมกราฟอีกครั้ง
              </p>
            )}
            {graph && !graph.skipped && Array.isArray(graph.nodes) && (
              <GraphView graph={graph} />
            )}
            <button
              type="button"
              className="mt-3 self-start rounded-full border border-cyan-300/30 bg-cyan-300/10 px-3 py-1 text-sm text-cyan-100 hover:bg-cyan-300/20"
              onClick={async () => {
                setGraphLoading(true);
                setError("");
                try {
                  const res = await fetch(`${API}/graph/seed`, { method: "POST" });
                  if (!res.ok) throw new Error(await readError(res));
                  await loadGraph();
                } catch (err) {
                  setError(err instanceof Error ? err.message : "เติมกราฟไม่สำเร็จ");
                } finally {
                  setGraphLoading(false);
                }
              }}
            >
              เติมกราฟศัพท์
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
