"""
NeuraDeck Projects Research Agent
==================================
Uses Tavily web search to find case studies and success stories, then
Google Gemini to produce bullet points for the "Success Stories" slide.
"""

import asyncio
import json
import os
import re
from typing import List
from datetime import datetime, timedelta, timezone

from app.gemini_client import generate_async
from app.research_agent import TavilyResearchError

CURRENT_YEAR = "2026"

def _filter_recent_results(results: list, months: int = 36) -> list:
    """
    FIX 1: Expanded to 36 months (3 years). Case studies don't expire as fast as daily news.
    Keep only results published within the last N months (if date info available).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)
    filtered = []
    
    for r in results:
        pub = r.get("published_date") or r.get("publishedDate") or ""
        if pub:
            try:
                pub_clean = pub.replace("Z", "+00:00")
                dt = datetime.fromisoformat(pub_clean.split("T")[0])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt < cutoff:
                    continue
            except (ValueError, TypeError):
                pass
                
        # Only keep results that actually have some text to read
        content = (r.get("content") or "").strip()
        if len(content) > 50:
            filtered.append(r)
            
    return filtered


def _fetch_tavily_search(query: str, max_results: int = 8) -> List[str]:
    """Web search via Tavily with advanced depth and recency filter."""
    api_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
    if not api_key:
        raise TavilyResearchError(
            "TAVILY_API_KEY is not set. Add it to backend/.env (get a key at https://tavily.com/)."
        )
    try:
        from tavily import TavilyClient  # type: ignore[reportMissingImports]
        client = TavilyClient(api_key=api_key)
        
        # FIX 2: Broadened the search to focus on ROI and Case Studies instead of just "2026"
        primary_query = f"{query} case study ROI results"
        response = client.search(primary_query, max_results=max_results, search_depth="advanced")
        results = _filter_recent_results(response.get("results") or [])
        snippets = []
        
        for r in results:
            content = (r.get("content") or r.get("title") or "").strip()
            if content:
                snippets.append(content[:800]) # Give Gemini more context to read

        if len(snippets) < 3:
            news_query = f"{query} customer success story metrics"
            news_response = client.search(news_query, max_results=max_results, search_depth="advanced")
            news_results = _filter_recent_results(news_response.get("results") or [])
            for r in news_results:
                content = (r.get("content") or r.get("title") or "").strip()
                if content and content not in snippets:
                    snippets.append(content[:800])

        return snippets[:15]
    except Exception as e:
        raise TavilyResearchError(f"Tavily web search failed: {e}") from e


class ProjectsResearchAgent:
    def __init__(self, model_name: str = "gemini-2.0-flash"):
        self.model_name = model_name
        self._api_key = (os.environ.get("TAVILY_API_KEY") or "").strip()

    def _web_search_serpapi(self, query: str) -> List[str]:
        if not self._api_key:
            return []
        return _fetch_tavily_search(query)

    async def _summarize_to_bullets(self, topic: str, raw_snippets: List[str]) -> List[str]:
        context = "\n\n".join(raw_snippets[:15]) if raw_snippets else ""
        
        # FIX 3: Removed the "plausible success stories" hallucination instruction.
        escape_hatch = """If the provided text does not contain real, specific case studies or metrics, DO NOT invent them. Return exactly: ["PLACEHOLDER"]."""
        
        if context:
            prompt = f"""You are a strict data analyst. Write 3-5 bullet points about real success stories and case studies for "{topic}" based ONLY on these search results. 

RULES:
1. Extract HARD METRICS (e.g., "$2M saved", "40% increase in Q1").
2. Include the client name and year if available.
3. {escape_hatch}

CONTEXT:
{context[:4000]}

Return ONLY a valid JSON array of 3-5 strings. Example: ["Company X increased revenue 40% in Q1 2025."]"""
        else:
            prompt = f"""You are a strict data analyst searching for success stories for "{topic}". 
{escape_hatch}
Return ONLY a valid JSON array of strings."""

        try:
            text = await generate_async(
                prompt,
                model_name=self.model_name,
                temperature=0.2, # FIX 4: Lower temperature to stop creative lying
                max_output_tokens=400,
            )
        except Exception:
            raise
            
        if not text:
            raise ValueError("Gemini returned no text for success stories. Please try again.")
            
        # FIX 5: Bulletproof JSON parsing with Regex
        text = text.strip()
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            text = match.group(0)
            
        try:
            out = json.loads(text)
            if isinstance(out, list):
                return [str(b).strip() for b in out if b][:5]
            return [str(out)[:200]]
        except json.JSONDecodeError:
            lines = [ln.strip().strip('-*• ') for ln in text.split("\n") if ln.strip()][:5]
            if not lines:
                raise ValueError("Gemini success stories response was not valid JSON. Please try again.")
            return lines

    async def fetch_success_stories(self, topic: str) -> List[str]:
        topic_clean = (topic or "Projects")[:80]
        query = f"{topic_clean} specific case study metrics" if topic_clean != "Projects" else f"business case study ROI"
        
        snippets = await asyncio.to_thread(_fetch_tavily_search, query)
        
        if not snippets:
            alt_query = f"{topic_clean} enterprise customer success metrics" if topic_clean != "Projects" else f"company case studies achievements"
            snippets = await asyncio.to_thread(_fetch_tavily_search, alt_query, max_results=10)
            
        if not snippets:
            raise TavilyResearchError(
                f"Tavily returned no results for \"{topic_clean}\" success stories. Try a different prompt or check TAVILY_API_KEY."
            )
            
        return await self._summarize_to_bullets(topic or "Projects", snippets)