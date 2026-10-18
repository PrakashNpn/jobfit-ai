"""Vector store: local FastEmbed embeddings + PostgreSQL/pgvector via LangChain."""

from typing import Protocol

from .config import settings
from .schemas import Chunk


class VectorStore(Protocol):
    def add(self, chunks: list[Chunk]) -> int: ...

    def search(self, query: str, k: int, doc_type: str | None = None) -> list[Chunk]: ...


class PgVectorStore:
    def __init__(self) -> None:
        # Imported here so the API (and its tests) can load without a database.
        from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
        from langchain_postgres import Column, PGEngine, PGVectorStore

        embeddings = FastEmbedEmbeddings(model_name=settings.embedding_model)
        engine = PGEngine.from_connection_string(url=settings.database_url)
        try:
            engine.init_vectorstore_table(
                table_name=settings.table_name,
                vector_size=settings.embedding_size,
                metadata_columns=[
                    Column("source", "TEXT"),
                    Column("doc_type", "TEXT"),
                    Column("chunk_index", "INTEGER"),
                ],
            )
        except Exception as exc:  # table already exists on every start after the first
            if "already exists" not in str(exc):
                raise
        self._store = PGVectorStore.create_sync(
            engine=engine,
            table_name=settings.table_name,
            embedding_service=embeddings,
            metadata_columns=["source", "doc_type", "chunk_index"],
        )

    def add(self, chunks: list[Chunk]) -> int:
        from langchain_core.documents import Document

        docs = [
            Document(
                page_content=c.text,
                metadata={"source": c.source, "doc_type": c.doc_type, "chunk_index": c.chunk_index},
            )
            for c in chunks
        ]
        self._store.add_documents(docs)
        return len(docs)

    def search(self, query: str, k: int, doc_type: str | None = None) -> list[Chunk]:
        filter_ = {"doc_type": {"$eq": doc_type}} if doc_type else None
        results = self._store.similarity_search_with_score(query, k=k, filter=filter_)
        return [
            Chunk(
                text=doc.page_content,
                source=doc.metadata.get("source", "unknown"),
                doc_type=doc.metadata.get("doc_type", "other"),
                chunk_index=doc.metadata.get("chunk_index", 0),
                score=float(score),
            )
            for doc, score in results
        ]
