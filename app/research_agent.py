"""
NeuraDeck Research Agent
========================
Enriches the outline with researched, substantive content per slide.
Uses multi-step Tavily research (broad + targeted) with full page content, then LLM for slide content.
"""

import asyncio
import json
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.gemini_client import generate_async

CURRENT_YEAR = "2026"
MIN_SEARCHES_PER_TOPIC = 5

# Expanded to catch brands, markets, and tech terms to trigger financial/deep searches
COMPANY_TOPIC_HINTS = (
    "company", "corp", "inc", "ltd", "startup", "business", "investor", "pitch",
    "revenue", "vc", "funding", "b2b", "b2c", "saas", "enterprise", 
    "apple", "tech", "market", "industry", "brand", "sales"
)

# Expanded to catch generic traps and force a retry
PLACEHOLDER_PHRASES = (
    "details for this section", "coming soon", "information not available",
    "to be filled", "to be added", "content to be researched", "key point",
    "specific details about", "tbd", "n/a", "placeholder", "insert content",
    "add details here", "overview", "history", "introduction", "conclusion"
)


def _topic_looks_like_company(topic: str) -> bool:
    """True if the topic appears to be a company (triggers financial data search)."""
    t = (topic or "").strip().lower()
    if not t or len(t) < 2:
        return False
    return any(hint in t for hint in COMPANY_TOPIC_HINTS)


class TavilyResearchError(Exception):
    """Raised when Tavily is unavailable or returns no results after retries."""


def _is_empty_or_dash(hint: Any) -> bool:
    if hint is None:
        return True
    if isinstance(hint, list):
        return not any(str(x).strip() and str(x).strip() != "—" for x in hint)
    s = str(hint).strip()
    return not s or s == "—"


def _is_placeholder_or_generic(bullets: List[str]) -> bool:
    """True if bullets are empty or contain only placeholder/generic filler text."""
    if not bullets:
        return True
    combined = " ".join(str(b).strip().lower() for b in bullets if b)
    if not combined or len(combined) < 20:
        return True
    for phrase in PLACEHOLDER_PHRASES:
        if phrase in combined:
            return True
    return False


def _filter_recent(results: list, months: int = 24) -> list:
    """Keep only results published within the last N months (if date info available)."""
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
        
        content = (r.get("content") or "").strip()
        if len(content) > 50: 
            filtered.append(r)
    return filtered


def _tavily_search_one(
    client: Any,
    query: str,
    max_results: int = 5,
    include_raw: bool = True,
) -> List[Dict[str, Any]]:
    """Run a single Tavily search with advanced depth and full page content. Returns list of result dicts."""
    kwargs = {
        "query": query,
        "max_results": max_results,
        "search_depth": "advanced",
    }
    if include_raw:
        kwargs["include_raw_content"] = True
    try:
        response = client.search(**kwargs)
    except TypeError:
        kwargs.pop("include_raw_content", None)
        response = client.search(**kwargs)
    return _filter_recent(response.get("results") or [])


def _run_one_tavily_search(api_key: str, query: str, max_results: int = 5, include_raw: bool = True) -> List[Dict[str, Any]]:
    """Run one Tavily search in a thread (creates client inside). Returns list of result dicts."""
    from tavily import TavilyClient  # type: ignore[reportMissingImports]
    client = TavilyClient(api_key=api_key)
    return _tavily_search_one(client, query, max_results=max_results, include_raw=include_raw)


def _content_from_result(r: Dict[str, Any], max_chars: int = 2000) -> str:
    """Extract full content from a result: raw_content (full page) preferred, else content snippet."""
    raw = (r.get("raw_content") or r.get("content") or "").strip()
    if not raw:
        raw = (r.get("content") or r.get("title") or "").strip()
    if not raw:
        return ""
    return raw[:max_chars] if len(raw) > max_chars else raw


async def _fetch_tavily_multistep(topic: str) -> List[str]:
    """
    Multi-step research: 1 broad search, then 4 targeted searches on key findings.
    Uses search_depth=advanced and full page content (include_raw_content). Minimum 5 searches per topic.
    Returns list of content strings for web_context.
    """
    api_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
    if not api_key:
        raise TavilyResearchError(
            "TAVILY_API_KEY is not set. Add it to backend/.env (get a key at https://tavily.com/)."
        )

    topic_short = (topic or "topic")[:80]
    all_contents: List[str] = []
    seen: set[str] = set()

    def add_content(text: str) -> None:
        t = (text or "").strip()
        if not t or len(t) < 30:
            return
        key = t[:200]
        if key not in seen:
            seen.add(key)
            all_contents.append(t[:3000])

    # 1) Broad search with full content (search 1)
    broad_query = f"{topic_short} overview market analysis {CURRENT_YEAR}"
    broad_results = await asyncio.to_thread(
        _run_one_tavily_search, api_key, broad_query, 5, True
    )
    if not broad_results:
        broad_results = await asyncio.to_thread(
            _run_one_tavily_search, api_key, f"{topic_short} business data {CURRENT_YEAR}", 5, True
        )
    for r in broad_results:
        add_content(_content_from_result(r))

    # Dedicated financial data search when topic is a company
    if _topic_looks_like_company(topic_short):
        fin_query = f"{topic_short} quarterly earnings revenue 2025 2026 official results"
        try:
            fin_results = await asyncio.to_thread(
                _run_one_tavily_search, api_key, fin_query, max_results=5, include_raw=True
            )
            for r in fin_results:
                add_content(_content_from_result(r))
        except Exception:
            pass

    # Build summary for key-finding extraction
    broad_summary = "\n\n".join(_content_from_result(r, max_chars=600) for r in broad_results[:5])
    if not broad_summary.strip():
        broad_summary = f"Topic: {topic_short}"

    # 2) Get 4 targeted search queries from broad research (LLM)
    key_finding_queries: List[str] = []
    try:
        prompt = f"""Based on this research summary, output exactly 4 short search queries (each 3-8 words) to find deeper detail on the most important specific aspects. Return ONLY a JSON array of 4 strings. No markdown.

Research summary:
{broad_summary[:2500]}

Example output: ["query one", "query two", "query three", "query four"]"""
        raw_queries = await generate_async(prompt, temperature=0.2, max_output_tokens=300)
        raw_queries = (raw_queries or "").strip()
        if raw_queries.startswith("```"):
            raw_queries = re.sub(r"^```\w*\n?", "", raw_queries)
            raw_queries = re.sub(r"\n?```\s*$", "", raw_queries)
        parsed = json.loads(raw_queries)
        if isinstance(parsed, list):
            key_finding_queries = [str(q).strip()[:80] for q in parsed if str(q).strip()][:4]
    except Exception:
        pass
    if len(key_finding_queries) < 4:
        for r in broad_results[:4]:
            title = (r.get("title") or r.get("content") or "").strip()[:60]
            if title and title not in key_finding_queries:
                key_finding_queries.append(f"{topic_short} {title}")
        key_finding_queries = key_finding_queries[:4]
    while len(key_finding_queries) < 4:
        key_finding_queries.append(f"{topic_short} key facts {CURRENT_YEAR}")

    # 3) Targeted searches (4 more) with full content – 5 total searches minimum
    for q in key_finding_queries:
        q_with_year = f"{q} {CURRENT_YEAR}" if CURRENT_YEAR not in q else q
        targeted_results = await asyncio.to_thread(
            _run_one_tavily_search, api_key, q_with_year, 4, True
        )
        for r in targeted_results:
            add_content(_content_from_result(r))

    if not all_contents:
        raise TavilyResearchError(
            f"Tavily returned no content for topic \"{topic_short[:50]}\". Try a different prompt or check TAVILY_API_KEY."
        )
    return all_contents[:20]


def _fetch_tavily(topic: str, max_results: int = 6, query_override: str | None = None) -> List[str]:
    """Legacy: single-call fetch. Prefer _fetch_tavily_multistep for enrich_outline."""
    api_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
    if not api_key:
        raise TavilyResearchError(
            "TAVILY_API_KEY is not set. Add it to backend/.env (get a key at [https://tavily.com/](https://tavily.com/))."
        )
    base_query = query_override or (f"{topic[:80]} overview" if topic else "overview")
    query = f"{base_query} {CURRENT_YEAR}"
    try:
        from tavily import TavilyClient  # type: ignore[reportMissingImports]
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query,
            max_results=max_results,
            search_depth="advanced",
            include_raw_content=True,
        )
        results = _filter_recent(response.get("results") or [])
        snippets = []
        for r in results:
            content = _content_from_result(r, max_chars=800)
            if content:
                snippets.append(content)
        return snippets[:15]
    except Exception as e:
        raise TavilyResearchError(f"Tavily search failed: {e}") from e


class ResearchAgent:
    def __init__(self, model_name: str = "gemini-2.0-flash"):
        self.model_name = model_name

    def _build_slide_prompt(
        self,
        topic: str,
        slide_title: str,
        content_hint: str,
        web_context: str = "",
        simple: bool = False,
    ) -> str:
        
        escape_hatch = """If the web context does not contain enough specific, hard factual data to write 3 impressive bullets, DO NOT guess. Return exactly: ["PLACEHOLDER"]."""

        if simple:
            return f"""Presentation topic: "{topic}". Slide: "{slide_title}". Write exactly 3 bullet points that are specific to this topic—real facts or insights. {escape_hatch} Return ONLY a JSON array of 3 strings. No markdown."""
        
        web_block = ""
        if web_context.strip():
            web_block = f"\nRelevant web research (use to ground your bullets):\n{web_context[:2500]}\n"
            
        return f"""You are a strict data consultant. Write slide bullets that would impress an investor. Every line must be specific to the topic—nothing generic. 

Topic: {topic}
Slide title: {slide_title}
Context: {content_hint[:350]}
{web_block}

RULES:
- 3–5 bullets. Each MUST contain one concrete fact, number, or specific insight. Max 18 words per bullet.
- Include the year (and quarter when available) for every statistic (e.g., "$3.4B revenue (Q2 {CURRENT_YEAR})", "40% growth (FY2025)").
- FORBIDDEN: General knowledge, Wikipedia summaries, "Key insights", "Important considerations", repeating the title, or vague advice.
- {escape_hatch}

Return ONLY a JSON array of strings. No markdown. Example: ["Closed $1.2M ARR in Q2 {CURRENT_YEAR}.", "Revenue grew 40%."]"""

    def _parse_bullets(self, text: str) -> List[str]:
        text = (text or "").strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        text = text.strip()
        
        # Regex extraction to prevent JSON crashing
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match:
            text = match.group(0)

        try:
            out = json.loads(text)
            if isinstance(out, list):
                return [str(b).strip() for b in out if b and str(b).strip()][:5]
            return [str(out)[:200]] if str(out).strip() else []
        except json.JSONDecodeError:
            lines = [ln.strip().strip('-*• ') for ln in text.split("\n") if ln.strip() and len(ln.strip()) > 10][:5]
            return lines
        return []

    async def _research_slide(
        self, topic: str, slide: Dict[str, Any], web_context: str = ""
    ) -> Optional[List[str]]:
        """Research one slide. Returns list of bullets, or None to skip slide (after retries if content stayed generic)."""
        title = slide.get("title", "Slide")
        raw = slide.get("content", "")
        if isinstance(raw, list):
            hint = " ".join(str(x) for x in raw[:3]) if raw else ""
        else:
            hint = (str(raw).strip() or "")[:400]
        if _is_empty_or_dash(hint):
            hint = f"Write specific content about {title} for {topic}."

        current_context = web_context
        max_retries = 2
        for attempt in range(max_retries + 1):
            prompt = self._build_slide_prompt(topic, title, hint, web_context=current_context, simple=(attempt > 0))
            try:
                text = await generate_async(
                    prompt,
                    model_name=self.model_name,
                    temperature=0.2,
                    max_output_tokens=500,
                )
            except Exception:
                if attempt < max_retries:
                    try:
                        api_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
                        if api_key:
                            query = f"{topic} {title} market data {CURRENT_YEAR}"
                            results = await asyncio.to_thread(
                                _run_one_tavily_search, api_key, query, max_results=5, include_raw=True
                            )
                            extra = "\n\n".join(_content_from_result(r, 1500) for r in results[:4])
                            if extra.strip():
                                current_context = (current_context + "\n\n[Targeted search]\n" + extra)[:8000]
                    except Exception:
                        pass
                    continue
                return None
            bullets = self._parse_bullets(text or "")
            if not _is_placeholder_or_generic(bullets):
                return bullets if bullets else [f"{title}: specific details about {topic}."]
            if attempt < max_retries:
                try:
                    api_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
                    if api_key:
                        query = f"{topic} {title} financials {CURRENT_YEAR}"
                        results = await asyncio.to_thread(
                            _run_one_tavily_search, api_key, query, max_results=5, include_raw=True
                        )
                        extra = "\n\n".join(_content_from_result(r, 1500) for r in results[:4])
                        if extra.strip():
                            current_context = (current_context + "\n\n[Targeted search]\n" + extra)[:8000]
                except Exception:
                    pass
        return None  # still empty or generic after 2 retries: skip this slide

    async def enrich_outline(
        self,
        topic: str,
        outline: Dict[str, Any],
        report: str | None = None,
    ) -> Dict[str, Any]:
        """Enrich each slide using the structured report when provided; otherwise fetch raw research."""
        slides = outline.get("slides", [])
        if not slides:
            return outline

        topic_short = (topic or "Business")[:120]
        if report and report.strip():
            web_context = report.strip()[:12000]
            if _topic_looks_like_company(topic_short):
                try:
                    api_key = (os.environ.get("TAVILY_API_KEY") or "").strip()
                    if api_key:
                        fin_query = f"{topic_short} quarterly earnings revenue 2025 2026 official results"
                        fin_snippets = await asyncio.to_thread(
                            _run_one_tavily_search, api_key, fin_query, max_results=5, include_raw=True
                        )
                        if fin_snippets:
                            fin_text = "\n\n".join(_content_from_result(r) for r in fin_snippets)
                            if fin_text.strip():
                                web_context = web_context + "\n\n[Financial data search]\n" + fin_text[:4000]
                except Exception:
                    pass
        else:
            try:
                web_snippets = await _fetch_tavily_multistep(topic_short)
            except TavilyResearchError:
                web_snippets = await asyncio.to_thread(
                    _fetch_tavily,
                    topic_short,
                    max_results=8,
                    query_override=f"{topic_short[:60]} overview {CURRENT_YEAR}" if topic_short else f"overview {CURRENT_YEAR}",
                )
            if not web_snippets:
                raise TavilyResearchError(
                    f"Tavily returned no web results for topic \"{topic_short[:50]}\". Try a different prompt or check your TAVILY_API_KEY."
                )
            web_context = "\n\n".join(web_snippets)
            
        enriched = []
        for slide in slides:
            bullets = await self._research_slide(topic_short, slide, web_context=web_context)
            if bullets is None:
                continue
            raw = slide.get("content", "")
            if bullets:
                content = bullets
            elif isinstance(raw, list):
                content = [str(b).strip() for b in raw if b and str(b).strip() and str(b).strip() != "—"][:5]
            else:
                content = [str(raw).strip()[:200]] if (raw and str(raw).strip() and str(raw).strip() != "—") else []
            if not content:
                content = [f"{slide.get('title', 'Slide')}: key information for the presentation."]
            enriched.append({**slide, "content": content})

        return {
            **outline,
            "slides": enriched,
            "total_slides": len(enriched),
        }