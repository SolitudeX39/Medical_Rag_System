from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pathlib import Path
import uuid
import hashlib

RAG_NAMESPACE = uuid.UUID("7d5a5286-6df7-4404-b97c-e0938f381c15")


def _split_docs(docs: list[Document]):
    parent_splitter = RecursiveCharacterTextSplitter(chunk_size=2000, chunk_overlap=30)
    child_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=20)
    parent_docs_list = []
    child_docs_list = []

    parent_docs = parent_splitter.split_documents(docs)
    for parent_doc in parent_docs:
        parent_id = uuid.uuid5(RAG_NAMESPACE, parent_doc.page_content)
        parent_doc.metadata["parent_id"] = parent_id
    parent_docs_list.extend(parent_docs)

    for parent_doc in parent_docs:
        child_docs = child_splitter.split_documents([parent_doc])
        for child_doc in child_docs:
            child_id = uuid.uuid5(RAG_NAMESPACE, child_doc.page_content)
            child_doc.metadata["child_id"] = child_id
        child_docs_list.extend(child_docs)

    child_texts = [doc.page_content for doc in child_docs_list]
    return docs, parent_docs_list, child_docs_list, child_texts


def load_and_split_pages(pages: list[str], pdf_name: str, document_id: str | None = None):
    joined = "\n\n".join(pages).encode("utf-8")
    if document_id is None:
        document_id = hashlib.sha256(joined).hexdigest()

    docs = []
    for index, text in enumerate(pages):
        docs.append(
            Document(
                page_content=text,
                metadata={
                    "pdf_name": pdf_name,
                    "document_id": document_id,
                    "page": index,
                },
            )
        )
    return _split_docs(docs)


def load_and_split_pdf(pdf_path: str | Path):
    from langchain_community.document_loaders import PyPDFLoader

    pdf_path = Path(pdf_path)
    loader = PyPDFLoader(str(pdf_path))
    docs = loader.load()

    with open(pdf_path, "rb") as f:
        document_id = hashlib.sha256(f.read()).hexdigest()

    for doc in docs:
        doc.metadata["pdf_name"] = pdf_path.name
        doc.metadata["document_id"] = document_id

    return _split_docs(docs)


def _load_csv_docs(csv_path: Path):
    from langchain_community.document_loaders import CSVLoader

    last_error = None
    for encoding in ("utf-8-sig", "utf-8", "cp874", "cp1252"):
        try:
            loader = CSVLoader(
                file_path=str(csv_path),
                encoding=encoding,
                csv_args={"skipinitialspace": True},
            )
            docs = loader.load()
            if docs:
                return docs
        except Exception as exc:
            last_error = exc
    if last_error:
        raise ValueError(f"อ่านไฟล์ CSV ไม่สำเร็จ: {last_error}") from last_error
    raise ValueError("ไม่พบแถวข้อมูลในไฟล์ CSV")


def load_and_split_csv(csv_path: str | Path):
    csv_path = Path(csv_path)
    docs = _load_csv_docs(csv_path)

    with open(csv_path, "rb") as f:
        document_id = hashlib.sha256(f.read()).hexdigest()

    for index, doc in enumerate(docs):
        row = doc.metadata.get("row", index)
        try:
            row = int(row)
        except (TypeError, ValueError):
            row = index
        parts = []
        for line in (doc.page_content or "").splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                parts.append(f"{key.strip()}: {value.strip()}")
            else:
                parts.append(line)
        if parts:
            doc.page_content = " | ".join(parts)
        doc.metadata["pdf_name"] = csv_path.name
        doc.metadata["document_id"] = document_id
        doc.metadata["page"] = row

    return _split_docs(docs)


def load_and_split_file(path: str | Path):
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return load_and_split_csv(path)
    if suffix == ".pdf":
        return load_and_split_pdf(path)
    raise ValueError("รองรับเฉพาะไฟล์ PDF และ CSV")
