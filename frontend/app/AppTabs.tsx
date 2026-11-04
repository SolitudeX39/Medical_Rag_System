"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  CHAT_EVENT,
  deleteThread,
  emitChat,
  getCurrentThreadId,
  loadThreads,
  type ChatThread,
} from "./chatStore";
import { getAuthUser, logout } from "./authStore";

const TABS = [
  { href: "/", label: "Chat", hint: "ถามเอกสาร" },
  { href: "/upload", label: "อัปโหลด", hint: "ใส่ PDF หรือ CSV" },
  { href: "/datasets", label: "Dataset", hint: "สรุปคลังข้อมูล" },
];

export default function AppTabs() {
  const pathname = usePathname();
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [currentId, setCurrentId] = useState("");

  function refreshHistory() {
    setThreads(loadThreads());
    setCurrentId(getCurrentThreadId());
  }

  useEffect(() => {
    refreshHistory();
    function onChat() {
      refreshHistory();
    }
    window.addEventListener(CHAT_EVENT, onChat);
    return () => window.removeEventListener(CHAT_EVENT, onChat);
  }, []);

  return (
    <>
      {open && (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-black/40 md:hidden"
          aria-label="ปิดเมนู"
          onClick={() => setOpen(false)}
        />
      )}

      <nav
        className={`relative z-40 flex h-full shrink-0 flex-col border-r border-white/10 bg-[#060910]/95 text-slate-200 backdrop-blur transition-[width] duration-200 ${
          open ? "w-64" : "w-14"
        }`}
      >
        <button
          type="button"
          className="mx-2 mt-3 flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 text-slate-200 hover:bg-white/5"
          aria-expanded={open}
          aria-label={open ? "ย่อเมนู" : "เปิดเมนู"}
          onClick={() => setOpen((current) => !current)}
        >
          <span className="flex flex-col gap-1">
            <span className="block h-0.5 w-4 bg-current" />
            <span className="block h-0.5 w-4 bg-current" />
            <span className="block h-0.5 w-4 bg-current" />
          </span>
        </button>

        {open && (
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="px-3 pb-4 pt-5">
              <p className="text-[10px] tracking-[0.28em] text-cyan-300">MEDICAL RAG AI</p>
              <p className="mt-1 text-xs text-slate-500">ถามเอกสารการแพทย์</p>
              <p className="mt-2 text-xs text-slate-400">{getAuthUser() || "admin"}</p>
            </div>
            {TABS.map((tab) => {
              const active = tab.href === "/" ? pathname === "/" : pathname.startsWith(tab.href);
              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  className={`mx-2 mb-2 rounded-2xl px-3 py-3 transition ${
                    active
                      ? "bg-cyan-300/15 font-semibold text-white shadow-[0_0_24px_rgba(34,211,238,0.12)]"
                      : "text-slate-400 hover:bg-white/5 hover:text-slate-100"
                  }`}
                >
                  <span className="block text-sm">{tab.label}</span>
                  <span className="mt-1 block text-[11px] font-normal text-slate-500">{tab.hint}</span>
                </Link>
              );
            })}

            <div className="mx-2 mt-2 border-t border-white/10 pt-3">
              <button
                type="button"
                className="w-full rounded-2xl border border-cyan-300/25 bg-cyan-300/10 px-3 py-2 text-left text-sm text-cyan-100 hover:bg-cyan-300/20"
                onClick={() => {
                  router.push("/");
                  emitChat({ type: "new" });
                  setOpen(false);
                }}
              >
                + New chat
              </button>
              <p className="mt-3 px-1 text-[10px] tracking-[0.18em] text-slate-500">ประวัติการแชท</p>
            </div>

            <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2 pt-2">
              {threads.length === 0 ? (
                <p className="px-2 text-xs text-slate-500">ยังไม่มีประวัติ</p>
              ) : (
                <ul className="space-y-1">
                  {threads.map((thread) => (
                    <li key={thread.id} className="flex items-stretch gap-1">
                      <button
                        type="button"
                        onClick={() => {
                          router.push("/");
                          emitChat({ type: "open", id: thread.id });
                          setOpen(false);
                        }}
                        className={`min-w-0 flex-1 rounded-xl px-3 py-2 text-left text-sm leading-snug hover:bg-white/5 ${
                          currentId === thread.id ? "bg-white/10 text-white" : "text-slate-300"
                        }`}
                      >
                        <span className="block truncate">{thread.title}</span>
                      </button>
                      <button
                        type="button"
                        className="rounded-lg px-2 text-xs text-slate-500 hover:bg-white/5 hover:text-rose-300"
                        aria-label="ลบแชท"
                        onClick={() => {
                          deleteThread(thread.id);
                          if (currentId === thread.id) emitChat({ type: "new" });
                          refreshHistory();
                        }}
                      >
                        ×
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className="border-t border-white/10 px-2 py-3">
              <button
                type="button"
                className="w-full rounded-2xl px-3 py-2 text-left text-sm text-slate-400 hover:bg-white/5 hover:text-rose-200"
                onClick={() => {
                  logout();
                  router.replace("/login");
                }}
              >
                ออกจากระบบ
              </button>
            </div>
          </div>
        )}
      </nav>
    </>
  );
}
