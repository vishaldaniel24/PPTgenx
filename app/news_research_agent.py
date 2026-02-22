"""
NeuraDeck News Research Agent
=============================
Fetches recent news via Tavily and uses Google Gemini to produce bullet points
for the "Market Context" slide.
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

def _filter_recent_results(results: list, months: int = 24) -> list:
    """
    FIX 1: Expanded from 12 to 24 months to prevent the agent from starving for data.
    Keep only results published within the last N months (if date info available).
    """
    # Use timezone-aware datetime for accurate comparison
    cutoff = datetime.now(timezone.utc) - timedelta(days=months * 30)
    filtered = []
    
    for r in results:
        pub = r.get("published_date") or r.get("publishedDate") or ""
        if pub:
            try:
                # Robust parsing for various ISO formats
                pub_clean = pub.replace("Z", "+00:00")
                dt = datetime.fromisoformat(pub_clean)
                
                # Make naive datetimes aware so they can be compared
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                    
                if dt < cutoff:
                    continue # Skip old news
            except (ValueError, TypeError):
                pass # If date is unreadable, keep it rather than throwing it away
                
        # FIX 2: Check for substantive content so we don't feed Gemini empty SEO pages
        content = (r.get("content") or "").strip()
        if len(content) > 50: 
            filtered.append(r)
            
    return filtered


def _fetch_tavily_news(query: str, max_results: int = 8) -> List[str]:
    """Fetch news via Tavily with advanced depth, current-year bias, and recency filter."""
    api_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
    if not api_key:
        raise TavilyResearchError(
            "TAVILY_API_KEY is not set. Add it to backend/.env (get a key at https://tavily.com/)."
        )
    try:
        from tavily import TavilyClient  # type: ignore[reportMissingImports]
        client = TavilyClient(api_key=api_key)
        
        # FIX 3: Added "market analysis" to force actual business data, not just generic info
        primary_query = f"{query} market analysis financials {CURRENT_YEAR}"
        response = client.search(primary_query, max_results=max_results, search_depth="advanced")
        results = _filter_recent_results(response.get("results") or [])
        snippets = []
        
        for r in results:
            content = (r.get("content") or r.get("title") or "").strip()
            if content:
                snippets.append(content[:800]) # Increased context window for better facts

        # Fallback search if the first one doesn't yield enough
        if len(snippets) < 3:
            news_query = f"{query} business news {CURRENT_YEAR}"
            news_response = client.search(news_query, max_results=max_results, search_depth="advanced")
            news_results = _filter_recent_results(news_response.get("results") or [])
            for r in news_results:
                content = (r.get("content") or r.get("title") or "").strip()
                if content and content not in snippets:
                    snippets.append(content[:800])

        return snippets[:15]
    except Exception as e:
        raise TavilyResearchError(f"Tavily news search failed: {e}") from e


class NewsResearchAgent:
    def __init__(self, model_name: str = "gemini-2.0-flash"):
        self.model_name = model_name
        self._api_key = (os.environ.get("TAVILY_API_KEY") or "").strip()

    def _fetch_news_serpapi(self, query: str) -> List[str]:
        """Legacy name for tests; uses Tavily when API key is set."""
        if not self._api_key:
            return []
        return _fetch_tavily_news(query)

    async def _summarize_to_bullets(self, topic: str, raw_snippets: List[str]) -> List[str]:
        context = "\n\n".join(raw_snippets[:15]) if raw_snippets else ""
        
        # FIX 4: Drastically improved the prompt to reject generic statements
        if context:
            prompt = f"""You are a strict financial analyst. Write 3-5 high-impact bullet points about the market context for "{topic}" based ONLY on these news snippets. 

RULES:
1. Extract HARD NUMBERS, percentages, and specific data points.
2. DO NOT write generic statements like "Apple is a technology company" or "It has health benefits."
3. Prioritize the most recent data from {CURRENT_YEAR} and 2025. 
4. Always mention the year for every statistic.

CONTEXT:
{context[:4000]}

Return ONLY a valid JSON array of strings. Example: ["Market grew 15% in Q1 {CURRENT_YEAR}.", "Revenue hit $50B in 2025."]"""
        else:
            prompt = f"""You are a financial analyst. Write 3-5 specific bullet points about the market context for "{topic}" as of {CURRENT_YEAR}.
Include specific details like market size, growth rates, key players, or recent developments. Do NOT use generic placeholder text.
Return ONLY a valid JSON array of 3-5 strings."""
            
        try:
            text = await generate_async(
                prompt,
                model_name=self.model_name,
                temperature=0.2, # Lowered temperature to stop hallucination
                max_output_tokens=400,
            )
        except Exception:
            raise
            
        if not text:
            raise ValueError("Gemini returned no text for market context. Please try again.")
            
        # FIX 5: Bulletproof JSON extraction using Regex
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
            # Absolute fallback if Gemini fails JSON formatting
            lines = [ln.strip().strip('-*• ') for ln in text.split("\n") if ln.strip()][:5]
            if not lines:
                raise ValueError("Gemini market context response was not valid JSON. Please try again.")
            return lines

    async def fetch_market_context(self, topic: str) -> List[str]:
        topic_clean = (topic or "Market")[:80]
        query = f"{topic_clean} market context {CURRENT_YEAR}" if topic_clean != "Market" else f"business market news {CURRENT_YEAR}"
        snippets = await asyncio.to_thread(_fetch_tavily_news, query)
        
        if not snippets:
            alt_query = f"{topic_clean} financials {CURRENT_YEAR}" if topic_clean != "Market" else f"market news trends {CURRENT_YEAR}"
            snippets = await asyncio.to_thread(_fetch_tavily_news, alt_query, max_results=10)
            
        if not snippets:
            raise TavilyResearchError(
                f"Tavily returned no news results for \"{topic_clean}\". Try a different prompt or check TAVILY_API_KEY."
            )
        return await self._summarize_to_bullets(topic or "Market", snippets)