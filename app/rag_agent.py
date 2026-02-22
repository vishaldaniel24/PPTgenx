"""
NeuraDeck RAG Agent
===================
Queries ChromaDB for brand guidelines/templates and uses Google Gemini
to produce a short style/brand context string for consistent deck formatting.
"""

import asyncio
import os
from pathlib import Path

from app.gemini_client import generate_async


class RAGAgent:
    """
    Queries ChromaDB for brand guidelines; optionally uses Gemini to summarize
    into a style context string. Output is passed to the Formatter for consistent style.
    """

    def __init__(self, model_name: str = "gemini-2.0-flash"):
        self.model_name = model_name
        self._chroma_path = os.environ.get("CHROMA_DB_PATH", "").strip() or None
        self._collection_name = os.environ.get("CHROMA_COLLECTION", "brand_guidelines").strip()

    def _query_chroma(self, query_text: str, n_results: int = 5) -> list:
        """Query ChromaDB for relevant chunks. Returns list of document strings."""
        if not self._chroma_path or not Path(self._chroma_path).exists():
            return []
        try:
            import chromadb  # type: ignore[reportMissingImports]
            client = chromadb.PersistentClient(path=self._chroma_path)
            col = client.get_or_create_collection(self._collection_name)
            result = col.query(query_texts=[query_text[:500]], n_results=n_results)
            docs = result.get("documents") or []
            return [doc for sub in docs for doc in (sub if isinstance(sub, list) else [sub])]
        except Exception:
            return []

    async def _summarize_style(self, topic: str, chunks: list) -> str:
        """Use Gemini to turn RAG chunks into a short style/brand context."""
        if not chunks:
            return ""
        context = "\n".join(str(c)[:500] for c in chunks[:10])
        prompt = f"""You are a RAG Agent. Below are brand/guideline excerpts. Write 2–4 short sentences that describe tone, style, and formatting rules to apply consistently in a business presentation. Be very concise.

Topic/prompt: {topic[:150]}

Excerpts:
{context[:2500]}

Return ONLY the style summary, no JSON, no bullet list header. Plain text only."""
        try:
            text = await generate_async(
                prompt,
                model_name=self.model_name,
                temperature=0.3,
                max_output_tokens=200,
            )
        except Exception:
            return " ".join(str(c)[:200] for c in chunks[:2])
        return (text or "").strip()[:800]

    async def get_style_context(self, topic: str, use_llm: bool = False) -> str:
        """
        Query ChromaDB for brand/style chunks. By default returns concatenated chunks (no LLM).
        Set use_llm=True to summarize with Gemini (extra LLM call).
        """
        query = f"{topic[:100]} brand guidelines style tone" if topic else "brand guidelines presentation style"
        chunks = await asyncio.to_thread(self._query_chroma, query, n_results=5)
        if not chunks:
            return ""
        if use_llm:
            return await self._summarize_style(topic or "Presentation", chunks)
        return " ".join(str(c)[:500] for c in chunks[:5])[:800]
