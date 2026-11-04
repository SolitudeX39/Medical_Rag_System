import os
import re
from pathlib import Path

import psycopg2
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from components.chat_prompt import CHAT_SYSTEM_PROMPT
from components.chunking_process import load_and_split_file, load_and_split_pages
from components.env import load_project_env
from components.gemini_embedding import GeminiEmbeddings
from components.graph import format_graph_context, graph_overview, related_terms, replace_graph
from components.medical_graph import MEDICAL_GRAPH_NODES, MEDICAL_GRAPH_RELATIONSHIPS
from components.mock_pdf_data import MOCK_PDF_NAME, MOCK_PDF_PAGES
from components.openrouter_rerank import OpenRouterRerank

load_project_env()

_gemini_embeddings = None
_reranker = None


def _embeddings():
    global _gemini_embeddings
    if _gemini_embeddings is None:
        _gemini_embeddings = GeminiEmbeddings()
    return _gemini_embeddings


def _get_reranker():
    global _reranker
    if _reranker is None:
        _reranker = OpenRouterRerank()
    return _reranker


def get_connection():
    return psycopg2.connect(
        database=os.getenv("POSTGRES_DB", "vectordb3"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "newpassword"),
        host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
        port=os.getenv("POSTGRES_PORT", "5432"),
    )


def _to_vector(values) -> str:
    return "[" + ",".join(str(float(v)) for v in values) + "]"


def _store_split_documents(docs_list, parent_docs_list, child_docs_list, child_texts) -> dict:
    if not docs_list:
        raise ValueError("ไม่พบเนื้อหาในไฟล์ที่อัปโหลด")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        embedded_contents = _embeddings().embed_documents(child_texts)
        doc = docs_list[0]
        pdf_id = doc.metadata["document_id"]
        pdf_name = doc.metadata["pdf_name"]

        cursor.execute(
            """
            INSERT INTO documents (file_hash, pdf_name)
            VALUES (%s, %s)
            ON CONFLICT (file_hash) DO NOTHING
            """,
            (pdf_id, pdf_name),
        )
        conn.commit()

        for parent_doc in parent_docs_list:
            parent_docs_id = parent_doc.metadata["parent_id"]
            hash_id = parent_doc.metadata["document_id"]
            parent_pages = parent_doc.metadata.get("page", 0)
            parent_texts = parent_doc.page_content
            cursor.execute(
                """
                INSERT INTO parent_chunks (parent_id, file_hash, page, parent_texts)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (parent_id) DO NOTHING
                """,
                (str(parent_docs_id), hash_id, parent_pages, parent_texts),
            )
        conn.commit()

        for child_doc, embedded_content in zip(child_docs_list, embedded_contents):
            child_id = child_doc.metadata["child_id"]
            child_parent_id = child_doc.metadata["parent_id"]
            child_text = child_doc.page_content
            cursor.execute(
                """
                INSERT INTO child_chunks (child_id, parent_id, child_text, embeddings)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (child_id) DO NOTHING
                """,
                (
                    str(child_id),
                    str(child_parent_id),
                    child_text,
                    _to_vector(embedded_content),
                ),
            )
        conn.commit()

        result = {
            "filename": pdf_name,
            "document_id": pdf_id,
            "parent_chunks": len(parent_docs_list),
            "child_chunks": len(child_docs_list),
        }
    finally:
        conn.close()

    result["graph"] = replace_graph(
        MEDICAL_GRAPH_NODES, MEDICAL_GRAPH_RELATIONSHIPS, pdf_name
    )
    return result


def insert_into_database(file_path: str | Path) -> dict:
    file_path = Path(file_path)
    docs_list, parent_docs_list, child_docs_list, child_texts = load_and_split_file(
        file_path
    )
    return _store_split_documents(
        docs_list, parent_docs_list, child_docs_list, child_texts
    )


def seed_mock_pdf_data() -> dict:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM child_chunks")
        cursor.execute("DELETE FROM parent_chunks")
        cursor.execute("DELETE FROM documents")
        conn.commit()
    finally:
        conn.close()

    docs_list, parent_docs_list, child_docs_list, child_texts = load_and_split_pages(
        MOCK_PDF_PAGES, MOCK_PDF_NAME
    )
    return _store_split_documents(
        docs_list, parent_docs_list, child_docs_list, child_texts
    )


def list_documents() -> list[dict]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                d.pdf_name,
                d.file_hash,
                COUNT(DISTINCT p.parent_id) AS parents,
                COUNT(c.child_id) AS children
            FROM documents d
            LEFT JOIN parent_chunks p ON p.file_hash = d.file_hash
            LEFT JOIN child_chunks c ON c.parent_id = p.parent_id
            GROUP BY d.pdf_name, d.file_hash
            ORDER BY d.pdf_name
            """
        )
        documents = []
        for row in cursor.fetchall():
            name = row[0]
            lower = (name or "").lower()
            kind = "csv" if lower.endswith(".csv") else "pdf" if lower.endswith(".pdf") else "file"
            documents.append(
                {
                    "name": name,
                    "id": row[1],
                    "chunks": row[2],
                    "children": row[3],
                    "kind": kind,
                }
            )
        return documents
    finally:
        conn.close()


def delete_document(document_id: str) -> dict | None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT pdf_name, file_hash FROM documents WHERE file_hash = %s",
            (document_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        cursor.execute(
            """
            DELETE FROM child_chunks
            WHERE parent_id IN (
                SELECT parent_id FROM parent_chunks WHERE file_hash = %s
            )
            """,
            (document_id,),
        )
        children = cursor.rowcount
        cursor.execute("DELETE FROM parent_chunks WHERE file_hash = %s", (document_id,))
        parents = cursor.rowcount
        cursor.execute("DELETE FROM documents WHERE file_hash = %s", (document_id,))
        conn.commit()
        return {
            "name": row[0],
            "id": row[1],
            "parent_chunks": parents,
            "child_chunks": children,
        }
    finally:
        conn.close()


def get_document(document_id: str) -> dict | None:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT pdf_name, file_hash FROM documents WHERE file_hash = %s",
            (document_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        cursor.execute(
            """
            SELECT page, parent_texts
            FROM parent_chunks
            WHERE file_hash = %s
            ORDER BY page ASC, parent_id ASC
            """,
            (document_id,),
        )
        pages = [
            {"page": item[0], "text": item[1]}
            for item in cursor.fetchall()
        ]
        return {
            "name": row[0],
            "id": row[1],
            "pages": pages,
            "graph": graph_overview(),
        }
    finally:
        conn.close()


def _source_label(filename: str | None, page) -> str:
    name = filename or "เอกสาร"
    if page is None:
        return name
    kind = "แถว" if name.lower().endswith(".csv") else "หน้า"
    try:
        number = int(page) + 1
    except (TypeError, ValueError):
        return name
    return f"{name} · {kind} {number}"


_STOP_WORDS = {
    "the", "and", "for", "with", "from", "that", "this", "what", "how",
    "คือ", "อะไร", "ของ", "ใน", "ที่", "และ", "หรือ", "มี", "ไหม", "ได้",
    "จาก", "ให้", "ว่า", "เป็น", "บ้าง",
}


def _search_terms(query: str) -> list[str]:
    terms = []
    cleaned = (query or "").strip()
    if cleaned:
        terms.append(cleaned)
    for token in re.findall(r"[\w\u0E00-\u0E7F-]{3,}", cleaned):
        if token.lower() not in _STOP_WORDS and token not in terms:
            terms.append(token)
    return terms[:8]


def _vector_search_per_document(query: str, per_doc: int = 4) -> list[tuple]:
    conn = get_connection()
    try:
        cursor = conn.cursor()
        embed_query = _to_vector(_embeddings().embed_query(query))
        cursor.execute(
            """
            WITH scored AS (
                SELECT
                    p.parent_id,
                    p.parent_texts,
                    p.page,
                    d.pdf_name,
                    d.file_hash,
                    (c.embeddings <=> %s::vector) AS distance,
                    ROW_NUMBER() OVER (
                        PARTITION BY d.file_hash
                        ORDER BY c.embeddings <=> %s::vector ASC
                    ) AS rn
                FROM child_chunks c
                JOIN parent_chunks p ON p.parent_id = c.parent_id
                JOIN documents d ON d.file_hash = p.file_hash
                WHERE length(trim(p.parent_texts)) > 0
            )
            SELECT parent_id, parent_texts, page, pdf_name, file_hash
            FROM scored
            WHERE rn <= %s
            ORDER BY distance ASC
            """,
            (embed_query, embed_query, per_doc),
        )
        return cursor.fetchall()
    finally:
        conn.close()


def _lexical_search(query: str, limit: int = 16) -> list[tuple]:
    terms = _search_terms(query)
    if not terms:
        return []
    patterns = [f"%{term}%" for term in terms]
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT p.parent_id, p.parent_texts, p.page, d.pdf_name, d.file_hash
            FROM parent_chunks p
            LEFT JOIN documents d ON d.file_hash = p.file_hash
            LEFT JOIN child_chunks c ON c.parent_id = p.parent_id
            WHERE p.parent_texts ILIKE ANY(%s)
               OR c.child_text ILIKE ANY(%s)
            LIMIT %s
            """,
            (patterns, patterns, limit),
        )
        return cursor.fetchall()
    finally:
        conn.close()


def _merge_search_rows(*groups: list[tuple], limit: int = 12) -> list[tuple]:
    seen = set()
    merged = []
    for group in groups:
        for row in group:
            key = str(row[0])
            if key in seen:
                continue
            seen.add(key)
            merged.append(row)
    return _diversify_rows(merged, limit)


def _diversify_rows(rows: list[tuple], limit: int = 12, per_file: int = 5) -> list[tuple]:
    by_file: dict[str, list[tuple]] = {}
    for row in rows:
        by_file.setdefault(str(row[4] or row[3] or "doc"), []).append(row)
    picked = []
    while len(picked) < limit and any(by_file.values()):
        progressed = False
        for key, items in list(by_file.items()):
            if not items or len(picked) >= limit:
                continue
            used = sum(1 for item in picked if str(item[4] or item[3] or "doc") == key)
            if used >= per_file:
                by_file[key] = []
                continue
            picked.append(items.pop(0))
            progressed = True
        if not progressed:
            break
    return picked


def _search_all_documents(query: str, limit: int = 12) -> list[tuple]:
    vector_rows = []
    try:
        vector_rows = _vector_search_per_document(query, per_doc=4)
    except Exception:
        vector_rows = []
    lexical_rows = []
    try:
        lexical_rows = _lexical_search(query, limit=16)
    except Exception:
        lexical_rows = []
    return _merge_search_rows(vector_rows, lexical_rows, limit=limit)


def search_parent_chunks(query: str, limit: int = 12) -> list[tuple]:
    try:
        return _search_all_documents(query, limit=limit)
    except Exception:
        return []


def context_from_rows(rows: list[tuple]) -> str:
    grouped: dict[str, list[str]] = {}
    for row in rows:
        label = _source_label(row[3], row[2])
        grouped.setdefault(row[3] or "เอกสาร", []).append(f"{label}\n{row[1]}")
    blocks = []
    for filename, items in grouped.items():
        blocks.append(f"## {filename}\n" + "\n\n".join(items))
    return "\n\n".join(blocks)


def query_database(query: str, history: list | None = None) -> dict:
    sql_result = _search_all_documents(query, limit=12)

    graph_facts = related_terms(query)
    graph_text = format_graph_context(graph_facts)

    if not sql_result and not graph_facts:
        return {
            "answer": "ไม่พบเนื้อหาที่เกี่ยวข้องในเอกสารหรือกราฟศัพท์",
            "sources": [],
            "graph": [],
        }

    context_text = context_from_rows(sql_result)

    llm = ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )

    user_content = f"""Context จากเอกสารทั้งหมดที่เคยอัปโหลด แยกตามไฟล์ PDF และ CSV:
{context_text}

กราฟศัพท์จาก Neo4j:
{graph_text or "ไม่พบโหนดที่เกี่ยวข้อง"}

คำถามของผู้ใช้:
{query}"""

    messages = [SystemMessage(content=CHAT_SYSTEM_PROMPT)]
    if history:
        for item in history[-8:]:
            role = item.get("role")
            content = item.get("content", "")
            if not content:
                continue
            if role == "user":
                messages.append(HumanMessage(content=content))
            elif role == "assistant":
                messages.append(AIMessage(content=content))
    messages.append(HumanMessage(content=user_content))

    response = llm.invoke(messages)
    sources = [
        {
            "page": row[2],
            "text": row[1],
            "filename": row[3],
            "document_id": row[4],
        }
        for row in sql_result
    ]
    return {
        "answer": response.content,
        "sources": sources,
        "graph": graph_facts,
    }
