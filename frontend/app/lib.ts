export const API = "/rag";

export type Source = {
  page?: number | null;
  text: string;
  filename?: string | null;
  document_id?: string | null;
};

export type DocumentItem = {
  name: string;
  id: string;
  chunks?: number;
  children?: number;
  kind?: "pdf" | "csv" | "file";
};

export type DocumentPage = {
  page: number | null;
  text: string;
};

export function isCsvFile(filename?: string | null) {
  return (filename || "").toLowerCase().endsWith(".csv");
}

export function datasetKind(doc: Pick<DocumentItem, "name" | "kind">) {
  if (doc.kind) return doc.kind;
  const name = (doc.name || "").toLowerCase();
  if (name.endsWith(".csv")) return "csv";
  if (name.endsWith(".pdf")) return "pdf";
  return "file";
}

export function sourceLocationLabel(
  filename?: string | null,
  page?: number | null,
  fallbackIndex = 0,
) {
  const number = typeof page === "number" ? page + 1 : fallbackIndex + 1;
  return isCsvFile(filename) ? `แถว ${number}` : `หน้า ${number}`;
}

export async function deleteDocument(documentId: string) {
  const res = await fetch(`${API}/documents/${encodeURIComponent(documentId)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json() as Promise<{ name?: string }>;
}

export async function readError(res: Response) {
  try {
    const data = await res.json();
    const detail = data.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail.map((item) => item.msg || JSON.stringify(item)).join(", ");
    }
    return data.message || res.statusText;
  } catch {
    return res.statusText;
  }
}
