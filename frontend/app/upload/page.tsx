"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import GraphView, { type GraphOverview } from "../GraphView";
import { API, deleteDocument, type DocumentItem, type DocumentPage, readError, sourceLocationLabel } from "../lib";

type DocumentDetail = {
  name: string;
  id: string;
  pages: DocumentPage[];
  graph?: GraphOverview;
};

export default function UploadPage() {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [viewer, setViewer] = useState<DocumentDetail | null>(null);
  const [viewerLoading, setViewerLoading] = useState(false);
  const [activePage, setActivePage] = useState<number | null>(null);
  const [deletingId, setDeletingId] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const pageRefs = useRef<Record<number, HTMLElement | null>>({});

  const loadDocuments = useCallback(async () => {
    try {
      const res = await fetch(`${API}/documents`);
      if (!res.ok) return;
      const data = await res.json();
      setDocuments(data.documents || []);
    } catch {
      // backend may be offline
    }
  }, []);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  useEffect(() => {
    if (activePage == null) return;
    pageRefs.current[activePage]?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [viewer, activePage]);

  async function openDocument(documentId: string) {
    setViewerLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/documents/${encodeURIComponent(documentId)}`);
      if (!res.ok) throw new Error(await readError(res));
      const data = (await res.json()) as DocumentDetail;
      setViewer(data);
      setActivePage(data.pages[0]?.page ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "เปิดเอกสารไม่สำเร็จ");
    } finally {
      setViewerLoading(false);
    }
  }

  async function removeDocument(doc: DocumentItem) {
    if (!window.confirm(`ลบ ${doc.name} ออกจากคลัง?`)) return;
    setError("");
    setStatus("");
    setDeletingId(doc.id);
    try {
      await deleteDocument(doc.id);
      if (viewer?.id === doc.id) {
        setViewer(null);
        setActivePage(null);
      }
      await loadDocuments();
      setStatus(`ลบ ${doc.name} แล้ว`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "ลบเอกสารไม่สำเร็จ");
    } finally {
      setDeletingId("");
    }
  }

  async function uploadFile(file: File) {
    const suffix = file.name.toLowerCase();
    if (!suffix.endsWith(".pdf") && !suffix.endsWith(".csv")) {
      setError("กรุณาเลือกไฟล์ PDF หรือ CSV");
      return;
    }

    setError("");
    setStatus("");
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API}/upload`, { method: "POST", body: form });
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      await loadDocuments();
      setStatus(
        `เพิ่ม ${data.filename} เข้าคลังแล้ว (${data.parent_chunks} ช่วง) ถามที่แทบ Chat ได้จากทุกไฟล์ที่อัปไว้`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "อัปโหลดไม่สำเร็จ");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  return (
    <div className="h-dvh overflow-y-auto text-[var(--ink)]">
      <div className="mx-auto flex min-h-full max-w-2xl flex-col justify-center px-5 py-10">
        <div className="text-center">
          <p className="text-[10px] tracking-[0.28em] text-cyan-300">MEDICAL RAG AI</p>
          <h1 className="mt-2 text-3xl font-semibold text-white">อัปโหลดเอกสาร</h1>
          <p className="mt-2 text-sm text-slate-400">
            อัปโหลด PDF หรือ CSV ได้หลายไฟล์ และลบออกจากคลังได้จากรายการด้านล่าง
          </p>
        </div>

        <label
          onDragOver={(event) => {
            event.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(event) => {
            event.preventDefault();
            setDragOver(false);
            const file = event.dataTransfer.files?.[0];
            if (file) void uploadFile(file);
          }}
          className={`mt-8 flex cursor-pointer flex-col items-center rounded-3xl border-2 border-dashed px-6 py-16 text-center transition ${
            dragOver
              ? "border-cyan-300 bg-cyan-300/10"
              : "border-white/15 bg-white/5 hover:border-cyan-300/50"
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept="application/pdf,.pdf,text/csv,.csv"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void uploadFile(file);
            }}
          />
          <span className="text-lg font-medium text-white">
            {uploading ? "กำลัง index เอกสาร..." : "วางไฟล์ PDF หรือ CSV ที่นี่"}
          </span>
          <span className="mt-2 text-sm text-slate-400">หรือคลิกเพื่อเลือกไฟล์</span>
        </label>

        {error && <p className="mt-4 text-center text-sm text-rose-300">{error}</p>}
        {status && <p className="mt-4 text-center text-sm text-cyan-200">{status}</p>}

        <div className="mt-10">
          <p className="mb-3 text-center text-[10px] tracking-[0.22em] text-slate-500">DOCUMENTS</p>
          {documents.length === 0 ? (
            <p className="text-center text-sm text-slate-500">ยังไม่มีไฟล์ที่ index</p>
          ) : (
            <ul className="space-y-2">
              {documents.map((doc) => (
                <li key={doc.id} className="flex items-stretch gap-2">
                  <button
                    type="button"
                    onClick={() => void openDocument(doc.id)}
                    className={`min-w-0 flex-1 rounded-2xl border px-4 py-3 text-left text-sm leading-snug transition hover:border-cyan-300/40 ${
                      viewer?.id === doc.id
                        ? "border-cyan-300/40 bg-cyan-300/10"
                        : "border-white/10 bg-white/5"
                    }`}
                  >
                    <span className="block truncate font-medium text-white">{doc.name}</span>
                    <span className="mt-1 block text-xs text-slate-400">
                      กดเพื่อดูเนื้อหา
                      {typeof doc.chunks === "number" ? ` · ${doc.chunks} ช่วง` : ""}
                    </span>
                  </button>
                  <button
                    type="button"
                    disabled={deletingId === doc.id}
                    onClick={() => void removeDocument(doc)}
                    className="rounded-2xl border border-rose-300/20 px-3 text-sm text-rose-200 hover:bg-rose-400/10 disabled:opacity-50"
                  >
                    {deletingId === doc.id ? "..." : "ลบ"}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {viewerLoading && (
          <p className="mt-6 text-center text-sm text-slate-400">กำลังโหลดเนื้อหา...</p>
        )}
        {viewer?.graph && !viewer.graph.skipped && viewer.graph.nodes.length > 0 && (
          <div className="mt-6 h-[22rem]">
            <GraphView graph={viewer.graph} />
          </div>
        )}
        {viewer?.pages.map((page, index) => (
          <article
            key={`${page.page}-${index}`}
            ref={(node) => {
              if (typeof page.page === "number") pageRefs.current[page.page] = node;
            }}
            className={`mt-4 rounded-2xl border px-4 py-3 ${
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
    </div>
  );
}
