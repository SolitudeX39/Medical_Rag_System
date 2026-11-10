"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { API, datasetKind, deleteDocument, type DocumentItem, type DocumentPage, readError, sourceLocationLabel } from "../lib";

type DocumentDetail = {
  name: string;
  id: string;
  pages: DocumentPage[];
};

function DatasetPageInner() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const selectedId = searchParams.get("id") || "";
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [deletingId, setDeletingId] = useState("");

  const loadDocuments = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API}/documents`);
      if (!res.ok) throw new Error(await readError(res));
      const data = await res.json();
      setDocuments(data.documents || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "โหลดคลังข้อมูลไม่สำเร็จ");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadDocuments();
  }, [loadDocuments]);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }
    let cancelled = false;
    setDetailLoading(true);
    setError("");
    void (async () => {
      try {
        const res = await fetch(`${API}/documents/${encodeURIComponent(selectedId)}`);
        if (!res.ok) throw new Error(await readError(res));
        const data = (await res.json()) as DocumentDetail;
        if (!cancelled) setDetail(data);
      } catch (err) {
        if (!cancelled) {
          setDetail(null);
          setError(err instanceof Error ? err.message : "เปิด dataset ไม่สำเร็จ");
        }
      } finally {
        if (!cancelled) setDetailLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  async function removeDocument(doc: DocumentItem) {
    if (!window.confirm(`ลบ ${doc.name} ออกจากคลัง?`)) return;
    setDeletingId(doc.id);
    setError("");
    try {
      await deleteDocument(doc.id);
      if (selectedId === doc.id) router.push("/datasets");
      await loadDocuments();
    } catch (err) {
      setError(err instanceof Error ? err.message : "ลบเอกสารไม่สำเร็จ");
    } finally {
      setDeletingId("");
    }
  }

  const totals = useMemo(() => {
    return documents.reduce(
      (acc, doc) => {
        acc.datasets += 1;
        acc.parents += doc.chunks || 0;
        acc.children += doc.children || 0;
        const kind = datasetKind(doc);
        if (kind === "csv") acc.csv += 1;
        else if (kind === "pdf") acc.pdf += 1;
        return acc;
      },
      { datasets: 0, parents: 0, children: 0, pdf: 0, csv: 0 },
    );
  }, [documents]);

  const selected = documents.find((doc) => doc.id === selectedId) || null;
  const showingAll = !selectedId;

  return (
    <div className="h-dvh overflow-y-auto text-[var(--ink)]">
      <div className="mx-auto max-w-5xl px-5 py-8 md:px-8">
        <p className="text-[10px] tracking-[0.28em] text-cyan-300">MEDICAL RAG AI</p>
        <h1 className="mt-2 text-3xl font-semibold text-white">Dataset</h1>
        <p className="mt-2 text-sm text-slate-400">
          {showingAll
            ? "สรุปคลังข้อมูลทั้งหมดที่เคยอัปโหลด ทั้ง PDF และ CSV"
            : `กำลังดู ${selected?.name || detail?.name || "dataset ที่เลือก"}`}
        </p>

        {error && <p className="mt-4 text-sm text-rose-300">{error}</p>}
        {loading && <p className="mt-6 text-sm text-slate-400">กำลังโหลดสรุปคลังข้อมูล...</p>}

        {!loading && (
          <>
            <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <SummaryCard label="Dataset" value={showingAll ? totals.datasets : 1} />
              <SummaryCard
                label={showingAll ? "PDF / CSV" : "ชนิดไฟล์"}
                value={
                  showingAll
                    ? `${totals.pdf} / ${totals.csv}`
                    : datasetKind(selected || { name: detail?.name || "" }).toUpperCase()
                }
              />
              <SummaryCard
                label="ช่วงเนื้อหา"
                value={showingAll ? totals.parents : selected?.chunks || detail?.pages.length || 0}
              />
              <SummaryCard
                label="ชิ้นสำหรับค้น"
                value={showingAll ? totals.children : selected?.children || 0}
              />
            </div>

            <div className="mt-8">
              <div className="flex items-end justify-between gap-3">
                <div>
                  <p className="text-[10px] tracking-[0.22em] text-slate-500">เลือกชื่อ DATASET</p>
                  <p className="mt-1 text-sm text-slate-400">
                    กดชื่อเพื่อดูสรุปไฟล์นั้น หรือดูรวมทั้งหมด
                  </p>
                </div>
                {!showingAll && (
                  <Link
                    href="/datasets"
                    className="rounded-full border border-cyan-300/25 bg-cyan-300/10 px-3 py-1 text-sm text-cyan-100 hover:bg-cyan-300/20"
                  >
                    ดูทั้งหมด
                  </Link>
                )}
              </div>

              {documents.length === 0 ? (
                <p className="mt-4 text-sm text-slate-500">
                  ยังไม่มี dataset ไปแทบอัปโหลดเพื่อเพิ่ม PDF หรือ CSV
                </p>
              ) : (
                <ul className="mt-4 grid gap-2 md:grid-cols-2">
                  {documents.map((doc) => {
                    const active = doc.id === selectedId;
                    return (
                      <li key={doc.id} className="flex items-stretch gap-2">
                        <Link
                          href={`/datasets?id=${encodeURIComponent(doc.id)}`}
                          className={`min-w-0 flex-1 rounded-2xl border px-4 py-3 transition ${
                            active
                              ? "border-cyan-300/40 bg-cyan-300/10"
                              : "border-white/10 bg-white/5 hover:border-cyan-300/30"
                          }`}
                        >
                          <span className="block truncate font-medium text-white">{doc.name}</span>
                          <span className="mt-1 block text-xs text-slate-400">
                            {datasetKind(doc).toUpperCase()}
                            {typeof doc.chunks === "number" ? ` · ${doc.chunks} ช่วง` : ""}
                            {typeof doc.children === "number" ? ` · ${doc.children} ชิ้นค้น` : ""}
                          </span>
                        </Link>
                        <button
                          type="button"
                          disabled={deletingId === doc.id}
                          onClick={() => void removeDocument(doc)}
                          className="rounded-2xl border border-rose-300/20 px-3 text-sm text-rose-200 hover:bg-rose-400/10 disabled:opacity-50"
                        >
                          {deletingId === doc.id ? "..." : "ลบ"}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {showingAll && documents.length > 0 && (
              <div className="glass-panel mt-8 overflow-hidden rounded-3xl">
                <div className="border-b border-white/10 px-5 py-4">
                  <p className="text-[10px] tracking-[0.22em] text-cyan-300">สรุปรวมทั้งหมด</p>
                  <p className="mt-1 text-lg font-semibold text-white">คลังข้อมูล Medical RAG AI</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[36rem] text-left text-sm">
                    <thead className="text-[11px] tracking-[0.16em] text-slate-500">
                      <tr>
                        <th className="px-5 py-3 font-medium">ชื่อ dataset</th>
                        <th className="px-5 py-3 font-medium">ชนิด</th>
                        <th className="px-5 py-3 font-medium">ช่วงเนื้อหา</th>
                        <th className="px-5 py-3 font-medium">ชิ้นสำหรับค้น</th>
                        <th className="px-5 py-3 font-medium">จัดการ</th>
                      </tr>
                    </thead>
                    <tbody>
                      {documents.map((doc) => (
                        <tr key={doc.id} className="border-t border-white/5 text-slate-200">
                          <td className="px-5 py-3">
                            <Link
                              href={`/datasets?id=${encodeURIComponent(doc.id)}`}
                              className="text-cyan-100 hover:underline"
                            >
                              {doc.name}
                            </Link>
                          </td>
                          <td className="px-5 py-3 uppercase text-slate-400">{datasetKind(doc)}</td>
                          <td className="px-5 py-3">{doc.chunks ?? 0}</td>
                          <td className="px-5 py-3">{doc.children ?? 0}</td>
                          <td className="px-5 py-3">
                            <button
                              type="button"
                              disabled={deletingId === doc.id}
                              onClick={() => void removeDocument(doc)}
                              className="text-rose-200 hover:underline disabled:opacity-50"
                            >
                              ลบ
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {!showingAll && (
              <div className="mt-8">
                <p className="text-[10px] tracking-[0.22em] text-slate-500">ตัวอย่างเนื้อหา</p>
                {detailLoading && <p className="mt-3 text-sm text-slate-400">กำลังโหลดเนื้อหา...</p>}
                {detail?.pages.slice(0, 12).map((page, index) => (
                  <article
                    key={`${page.page}-${index}`}
                    className="mt-3 rounded-2xl border border-white/10 bg-white/5 px-4 py-3"
                  >
                    <p className="text-xs font-medium text-cyan-300">
                      {sourceLocationLabel(detail.name, page.page, index)}
                    </p>
                    <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed text-slate-300">
                      {page.text}
                    </p>
                  </article>
                ))}
                {detail && detail.pages.length > 12 && (
                  <p className="mt-3 text-xs text-slate-500">แสดง 12 ช่วงแรก จากทั้งหมด {detail.pages.length} ช่วง</p>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function SummaryCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-4">
      <p className="text-[10px] tracking-[0.2em] text-slate-500">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-white">{value}</p>
    </div>
  );
}

export default function DatasetPage() {
  return (
    <Suspense fallback={<div className="p-8 text-sm text-slate-400">กำลังเปิดหน้า dataset...</div>}>
      <DatasetPageInner />
    </Suspense>
  );
}
