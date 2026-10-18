"""Turn uploaded files into text chunks ready for the vector store."""

import io

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader

from .config import settings
from .schemas import Chunk


class UnsupportedFileError(ValueError):
    pass


def extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    if name.endswith((".txt", ".md")):
        return data.decode("utf-8", errors="replace")
    raise UnsupportedFileError("Only .pdf, .txt and .md files are supported")


def split_into_chunks(text: str, source: str, doc_type: str) -> list[Chunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
    )
    pieces = [p for p in splitter.split_text(text) if p.strip()]
    return [
        Chunk(text=piece, source=source, doc_type=doc_type, chunk_index=i)
        for i, piece in enumerate(pieces)
    ]
