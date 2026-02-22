"""
NeuraDeck Agents - Planning Agent & Combined Research+Outline
==============================================================
Planning Agent: topic-specific slide outline from research.
Combined pipeline: one LLM call takes raw research and returns full outline with
data-rich bullets (replaces Report + Planning + Research).
"""

import asyncio
import json
import re
from typing import Any, Dict, List

from app.gemini_client import generate_async

# --- Combined research + outline (single LLM call) ---

CURRENT_YEAR = "2026"

PLACEHOLDER_LIKE = (
    "content.", "key point", "overview of", "to be filled", "to be researched",
    "details for this section", "bullet", "point one", "point two", "slide 1", "slide 2",
    "summary and next steps", "key points to be researched", "tbd", "n/a",
)


def _outline_looks_like_placeholders(slides: List[Dict[str, Any]]) -> bool:
    """True if a majority of content slides have only placeholder-like content (no real facts)."""
    if not slides or len(slides) < 2:
        return False
    placeholder_count = 0
    for s in slides:
        if (s.get("type") or "").strip().lower() == "section_divider":
            continue
        title = (s.get("title") or "").strip().lower()
        content = s.get("content")
        if isinstance(content, list):
            text = " ".join(str(b).strip().lower() for b in content)
        else:
            text = (str(content) or "").strip().lower()
        combined = (title + " " + text).strip()
        has_placeholder_phrase = any(p in combined for p in PLACEHOLDER_LIKE)
        short_and_no_number = len(combined) < 60 and not any(c.isdigit() for c in combined)
        if has_placeholder_phrase or short_and_no_number:
            placeholder_count += 1
    content_slide_count = sum(1 for s in slides if (s.get("type") or "").strip().lower() != "section_divider")
    if content_slide_count < 2:
        return False
    return placeholder_count > content_slide_count / 2


def _build_outline_prompt(
    research: str,
    topic: str,
    min_slides: int,
    max_slides: int,
    charts_instruction: str,
    retry_placeholder: bool,
) -> str:
    strict = ""
    if retry_placeholder:
        strict = """
CRITICAL: Your previous response contained placeholder or generic text. This time you MUST extract ONLY specific facts, numbers, company names, and concrete claims FROM THE RAW RESEARCH below and put them in every slide. Do NOT output "Key Point 1", "Content.", "Overview of topic", or similar. Copy real data from the research into the bullets. The deck must be production-ready.
"""
    return f"""You are a senior consultant. Create a production-ready presentation outline. Every title and every bullet MUST be taken from or directly supported by the RAW RESEARCH below. The output is for a finished, client-ready deck—no placeholders.
{strict}
{charts_instruction}
RAW RESEARCH:
{research[:14000]}

USER PROMPT / TOPIC: "{topic}"

YOUR TASKS:
1. Decide the number of slides (between {min_slides} and {max_slides}). Cover a wide range of topics from the prompt and research; only include slides that add real value.
2. Choose every slide title yourself—specific to the topic and the research (e.g. "Market Size & Growth", "Technical Architecture", "Risks & Mitigation"). No generic labels like "Slide 3" or "Key Points".
3. For section dividers: insert slides with "type":"section_divider", and YOU choose the "title". Use "content" as a single one-line summary only (no bullet list).
4. Every content slide must have 4 or 5 bullet points. Each bullet MUST contain at least one number, percentage, year, or concrete fact FROM THE RAW RESEARCH. Bad: "Company is growing." Good: "Revenue grew 40% YoY to $2M in 2025." Extract and copy specific facts from the research—do not invent or generalize.
5. Use "content" as a string with bullets separated by \\n (e.g. "• Fact one.\\n• Fact two.\\n• Fact three.\\n• Fact four.") or as an array of strings.
6. FORBIDDEN: no "details for this section", "coming soon", "TBD", "to be filled", "Key Point 1", "Content.", "Overview of [topic]". Use ONLY substantive facts from the research.

Output format (JSON array only):
[{{"slide_number":1,"title":"<topic>","content":"• Subtitle from research."}}, {{"slide_number":2,"title":"<specific title>","content":"• Specific fact with number.\\n• Another fact.\\n• Third.\\n• Fourth."}}, {{"slide_number":3,"title":"<section name>","content":"One-line summary.","type":"section_divider"}}, ..., {{"slide_number":N,"title":"Thank You","content":"• Summary.\\n• ..."}}]
"""


async def generate_research_and_outline(
    raw_research: str,
    user_prompt: str,
    template_id: str = "builtin_1",
    model_name: str = "gemini-2.0-flash",
    charts_enabled: bool = False,
) -> Dict[str, Any]:
    """
    Single LLM call: raw research -> full slide outline with substantive bullets.
    When charts_enabled=True, agent may use more slides so chart slides (Revenue, Funnel, Team, Market) fit naturally.
    """
    tid = (template_id or "").strip().lower()
    min_slides = 6
    base_max = 15 if tid == "corporate" else (10 if tid == "pitch" else 12)
    max_slides = base_max + 4 if charts_enabled else base_max
    topic = (user_prompt or "Topic")[:200]

    research = (raw_research or "").strip()
    if not research:
        research = f"Topic: {topic}. No web research provided."

    charts_instruction = ""
    if charts_enabled:
        charts_instruction = """
CHARTS: If a slide contains multiple numerical data points, the system will automatically generate a custom chart for it. Do NOT force generic slides like "Sales Funnel", "Team Growth", or "Market Opportunity" unless they are highly relevant to the specific topic and research. Focus purely on the data provided in the research."""

    prompt = _build_outline_prompt(
        research=research,
        topic=topic,
        min_slides=min_slides,
        max_slides=max_slides,
        charts_instruction=charts_instruction,
        retry_placeholder=False,
    )

    try:
        raw = await generate_async(
            prompt,
            model_name=model_name,
            temperature=0.2,
            max_output_tokens=4000,
        )
    except Exception:
        planning = PlanningAgent(model_name=model_name)
        return planning._create_fallback_outline(user_prompt, template_id, max_slides)

    raw = (raw or "").strip()
    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1:
        start = raw.find("{")
        end = raw.rfind("}")
    if start == -1:
        planning = PlanningAgent(model_name=model_name)
        return planning._create_fallback_outline(user_prompt, template_id, max_slides)

    json_str = raw[start : end + 1]
    planning = PlanningAgent(model_name=model_name)
    target_slides = min(max_slides, 19)
    slides = planning._parse_outline_json(json_str, user_prompt, template_id, target_slides)
    if not slides:
        slides = planning._repair_truncated_json(json_str, user_prompt, template_id, target_slides).get("slides")
    if not slides:
        return planning._create_fallback_outline(user_prompt, template_id, target_slides)

    if _outline_looks_like_placeholders(slides):
        try:
            retry_prompt = _build_outline_prompt(
                research=research,
                topic=topic,
                min_slides=min_slides,
                max_slides=max_slides,
                charts_instruction=charts_instruction,
                retry_placeholder=True,
            )
            raw2 = await generate_async(retry_prompt, model_name=model_name, temperature=0.15, max_output_tokens=4000)
            raw2 = (raw2 or "").strip()
            start2 = raw2.find("[")
            end2 = raw2.rfind("]")
            if start2 >= 0 and end2 > start2:
                json_str2 = raw2[start2 : end2 + 1]
                slides2 = planning._parse_outline_json(json_str2, user_prompt, template_id, target_slides)
                if slides2 and not _outline_looks_like_placeholders(slides2):
                    slides = slides2
        except Exception:
            pass

    if _outline_has_generic_business_titles(slides, user_prompt) and not _topic_looks_like_business(user_prompt):
        pass  # keep slides
    slides = planning._normalize_slides(slides, user_prompt, target_slides)
    for i, s in enumerate(slides):
        content = s.get("content", "")
        if isinstance(content, list):
            s["content"] = content
        elif isinstance(content, str):
            if "• " in content or "\\n" in content:
                parts = content.replace("\\n", "\n").split("\n")
                bullets = [p.strip().strip("•").strip() for p in parts if p.strip()]
                s["content"] = bullets if bullets else [content.strip()[:200]]
            else:
                s["content"] = [content.strip()[:200]] if content.strip() else []
        else:
            s["content"] = []
    return {
        "slides": slides,
        "total_slides": len(slides),
        "user_prompt": user_prompt,
        "template_id": template_id,
    }

# Import Tavily fetch for research-driven outline (no circular dep: research_agent doesn't import agents)
try:
    from app.research_agent import _fetch_tavily, TavilyResearchError
except ImportError:
    _fetch_tavily = None  # type: ignore[assignment]
    TavilyResearchError = Exception  # type: ignore[assignment, misc]

# Generic business terms that must not appear in outlines for non-business topics
GENERIC_BUSINESS_TERMS = (
    "company introduction", "market context", "products & services", "financial overview",
    "competitive landscape", "growth strategy", "partnerships", "market share",
    "revenue", "funnel", "company ", "business model", "investment opportunity",
    "contact information", "customer testimonials", "team overview", "technology stack",
    "future roadmap", "success stories", "market analysis",
)

# Topic keywords that indicate a business/company context (outline may use business terms)
BUSINESS_TOPIC_HINTS = (
    "company", "corp", "startup", "business", "investor", "pitch", "revenue",
    "vc", "funding", "b2b", "b2c", "saas", "enterprise", "inc", "ltd",
)


def _topic_looks_like_business(topic: str) -> bool:
    t = (topic or "").strip().lower()
    return any(hint in t for hint in BUSINESS_TOPIC_HINTS)


def _outline_has_generic_business_titles(slides: List[Dict[str, Any]], topic: str) -> bool:
    """True if outline uses generic business slide titles but the topic is not business-focused."""
    if _topic_looks_like_business(topic):
        return False
    for s in slides:
        title = (s.get("title") or "").strip().lower()
        if any(term in title for term in GENERIC_BUSINESS_TERMS):
            return True
    return False


class PlanningAgent:
    def __init__(self, model_name: str = "gemini-2.0-flash"):
        self.model_name = model_name

    def _build_research_driven_prompt(
        self,
        research_summary: str,
        user_prompt: str,
        template_id: str,
        avoid_business_jargon: bool = False,
    ) -> str:
        tid = (template_id or "").strip().lower()
        min_slides = 6
        max_slides = 15 if tid == "corporate" else (10 if tid == "pitch" else 12)
        topic = (user_prompt or "Topic")[:200]
        jargon_note = ""
        if avoid_business_jargon:
            jargon_note = (
                "\nCRITICAL: The topic is NOT a company or business pitch. "
                "Do NOT use generic business slide titles (e.g. Company Introduction, Market Context, "
                "Revenue, Funnel, Financial Overview, Competitive Landscape, Partnerships). "
                "Use titles that are specific to the topic (e.g. for anime: Origin & History, "
                "Characters, Story Arcs, Global Fanbase, Manga vs Anime)."
            )
        return f"""You are creating a presentation outline based ONLY on the following research. YOU decide everything: number of slides, every slide title, every section divider title, and all content. Only include what is important—every word must earn its place.

RESEARCH SUMMARY:
{research_summary[:6000]}

TOPIC: "{topic}"

TASK:
1. Decide how many slides make sense (between {min_slides} and {max_slides}). Cover a wide range of topics from the prompt and research, but only include slides that add real value.
2. Choose every slide title yourself—specific to the topic and research (e.g. "Origin & History", "Market Size & Growth", "Risks & Mitigation"). No generic labels.
3. Every content slide: 4 or 5 bullets. Each bullet must be DATA-RICH: at least one number, percentage, year, or concrete fact. Bad: "OpenAI is growing fast." Good: "OpenAI revenue grew 200% YoY to $3.4B in 2024." Use \\n between bullets in content.
4. ONLY two fixed slides: FIRST = title slide (topic as title, one-line subtitle). LAST = "Thank You" or "Key Takeaways" (2–3 summary bullets with data).
5. SECTION DIVIDERS: Between major topic changes, insert a section divider. YOU choose the "title" (e.g. "Market Overview", "Technical Deep Dive"). Use "type":"section_divider" and "content" as a single one-line summary (no bullets). Example: {{"slide_number":3,"title":"Market Overview","content":"Key trends and market size.","type":"section_divider"}}
{jargon_note}

OUTPUT: A single JSON array of objects. No markdown, no explanation. Format exactly:
[
  {{"slide_number":1,"title":"<topic as title>","content":"• Subtitle or key hook.\\n• Optional second line."}},
  {{"slide_number":2,"title":"<specific title>","content":"• Specific fact with number (e.g. 40% growth).\\n• Another fact with data.\\n• Third fact with data."}},
  {{"slide_number":3,"title":"Section Name","content":"One-line summary only.","type":"section_divider"}},
  ...
  {{"slide_number":N,"title":"Thank You","content":"• Summary with data.\\n• Optional."}}
]

RULES: Double quotes only. Use \\n for newlines in content. No trailing commas. Every content slide bullet must contain at least one data point. Section divider slides have "type":"section_divider" and content = one line only, no bullets. Output the JSON array only:"""

    async def generate_outline(
        self,
        user_prompt: str,
        template_id: str = "builtin_1",
        report: str | None = None,
    ) -> Dict[str, Any]:
        """Generate slide outline from a structured report (never from raw search directly). If report is provided, use it; otherwise fetch Tavily and build outline (legacy fallback)."""
        tid = (template_id or "").strip().lower()
        target_slides = 15 if tid == "corporate" else 10
        topic_short = (user_prompt or "Topic")[:120]

        # Use report when provided (pipeline: ReportAgent -> PlanningAgent)
        if report and report.strip():
            research_summary = report.strip()[:8000]
        else:
            # Legacy: fetch research only when no report (e.g. tests)
            research_summary = ""
            if _fetch_tavily is not None:
                try:
                    snippets = await asyncio.to_thread(
                        _fetch_tavily,
                        topic_short,
                        max_results=10,
                        query_override=f"{topic_short[:80]} overview",
                    )
                    research_summary = "\n\n".join(snippets)[:6000] if snippets else ""
                except (TavilyResearchError, Exception):
                    research_summary = ""
            if not research_summary.strip():
                research_summary = f"No report or research for \"{topic_short}\". Generate a minimal, topic-specific outline (e.g. Origin, Key Points, Summary). Do not use generic business slide titles unless the topic is clearly a company or business."

        # 2) Generate outline from research (with optional retry if generic business terms detected)
        avoid_jargon = False
        for attempt in range(2):
            prompt = self._build_research_driven_prompt(
                research_summary, user_prompt, template_id, avoid_business_jargon=avoid_jargon
            )
            try:
                raw = await generate_async(
                    prompt,
                    model_name=self.model_name,
                    temperature=0.3,
                    max_output_tokens=3200,
                )
            except Exception:
                return self._create_fallback_outline(user_prompt, template_id, target_slides)

            raw = (raw or "").strip()
            start = raw.find('[')
            end = raw.rfind(']')
            if start == -1:
                start = raw.find('{')
                end = raw.rfind('}')
            if start == -1:
                return self._create_fallback_outline(user_prompt, template_id, target_slides)

            json_str = raw[start : end + 1]
            slides = self._parse_outline_json(json_str, user_prompt, template_id, target_slides)
            if slides is None:
                slides = self._repair_truncated_json(json_str, user_prompt, template_id, target_slides).get("slides")
            if not slides:
                return self._create_fallback_outline(user_prompt, template_id, target_slides)

            # Validation: reject generic business outline for non-business topics
            if _outline_has_generic_business_titles(slides, user_prompt) and not avoid_jargon:
                avoid_jargon = True
                continue
            break
        else:
            slides = self._create_fallback_outline(user_prompt, template_id, target_slides).get("slides", [])

        # 3) Normalize: ensure first slide = title, last = Thank You / Key Takeaways
        slides = self._normalize_slides(slides, user_prompt, target_slides)
        return {
            "slides": slides,
            "total_slides": len(slides),
            "user_prompt": user_prompt,
            "template_id": template_id,
        }

    def _parse_outline_json(
        self, json_str: str, user_prompt: str, template_id: str, target_slides: int
    ) -> List[Dict[str, Any]] | None:
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, list):
                slides = parsed
            elif isinstance(parsed, dict) and "slides" in parsed:
                slides = parsed["slides"]
            else:
                return None
        except json.JSONDecodeError:
            json_str = json_str.replace("'", '"').replace('True', 'true').replace('False', 'false').replace('None', 'null')
            json_str = re.sub(r'(?<!\\)\n', r'\\n', json_str)
            try:
                parsed = json.loads(json_str)
                slides = parsed if isinstance(parsed, list) else (parsed.get("slides") if isinstance(parsed, dict) else None)
            except json.JSONDecodeError:
                return None
        if not slides or not isinstance(slides, list):
            return None
        fixed = []
        for slide in slides:
            if isinstance(slide, list) and slide and isinstance(slide[0], dict):
                fixed.append(slide[0])
            elif isinstance(slide, dict):
                content = slide.get("content", "")
                if isinstance(content, str):
                    content = content.replace("\\n", "\n")
                    if len(content) > 500:
                        content = content[:500] + "..."
                    slide = {**slide, "content": content}
                elif isinstance(content, list):
                    slide = {**slide, "content": "\n".join(f"• {str(item)}" for item in content[:5])}
                fixed.append(slide)
            else:
                fixed.append({"slide_number": len(fixed) + 1, "title": f"Slide {len(fixed)+1}", "content": "Content"})
        return fixed

    def _repair_truncated_json(self, text: str, user_prompt: str, template_id: str, target_slides: int) -> Dict[str, Any]:
        import re
        start = text.find('[')
        end = text.rfind(']')
        if start >= 0 and end > start:
            try:
                repaired = text[start:end + 1]
                repaired = repaired.replace("'", '"')
                repaired = repaired.replace('True', 'true').replace('False', 'false')
                repaired = repaired.replace('None', 'null')
                slides = json.loads(repaired)
                if isinstance(slides, list) and slides:
                    return {
                        "slides": slides[:target_slides],
                        "total_slides": len(slides[:target_slides]),
                        "user_prompt": user_prompt,
                        "template_id": template_id,
                    }
            except json.JSONDecodeError:
                pass
        last_complete = text.rfind('"},')
        if last_complete >= 0:
            repaired = text[:last_complete + 2] + "]"
            try:
                slides = json.loads(repaired)
                if isinstance(slides, list) and slides:
                    return {
                        "slides": slides[:target_slides],
                        "total_slides": len(slides[:target_slides]),
                        "user_prompt": user_prompt,
                        "template_id": template_id,
                    }
            except json.JSONDecodeError:
                pass
        last_brace = text.rfind('"}')
        if last_brace >= 0:
            repaired = text[:last_brace + 2] + "]"
            try:
                slides = json.loads(repaired)
                if isinstance(slides, list) and slides:
                    return {
                        "slides": slides[:target_slides],
                        "total_slides": len(slides[:target_slides]),
                        "user_prompt": user_prompt,
                        "template_id": template_id,
                    }
            except json.JSONDecodeError:
                pass
        slide_pattern = r'\{"slide_number":\s*(\d+),\s*"title":\s*"([^"]*)",\s*"content":\s*"([^"]*)"\}'
        slide_matches = re.findall(slide_pattern, text)
        if slide_matches:
            slides = []
            for num, title, content in slide_matches:
                slides.append({
                    "slide_number": int(num),
                    "title": title[:80] if title else f"Slide {num}",
                    "content": content[:500] if content else "Content to be researched"
                })
            if slides:
                return {
                    "slides": slides[:target_slides],
                    "total_slides": len(slides[:target_slides]),
                    "user_prompt": user_prompt,
                    "template_id": template_id,
                }
        return self._create_fallback_outline(user_prompt, template_id, target_slides)

    def _normalize_slides(
        self, slides: List[Dict[str, Any]], user_prompt: str, target_slides: int
    ) -> List[Dict[str, Any]]:
        if not slides:
            return self._create_fallback_outline(user_prompt, "", target_slides).get("slides", [])
            
        topic_title = (user_prompt or "Presentation")[:80].strip() or "Title"
        
        # Ensure slide 1 is the Title Slide
        slides[0] = {**slides[0], "title": topic_title, "slide_number": 1}
        
        # Ensure the last slide is a Thank You / Summary slide
        last = slides[-1]
        last_title = (last.get("title") or "").strip().lower()
        if "thank" not in last_title and "key takeaway" not in last_title and "summary" not in last_title:
            slides[-1] = {**last, "title": "Summary & Next Steps", "slide_number": len(slides)}
            
        # FIX: The padding loop has been completely removed. 
        # The AI will now generate natural length presentations instead of filling gaps.
        
        # Recalculate slide numbers just in case the AI messed up the counting
        for idx, s in enumerate(slides):
            s["slide_number"] = idx + 1
            
        return slides[:target_slides]

    def _create_fallback_outline(self, user_prompt: str, template_id: str, target_slides: int) -> Dict[str, Any]:
        """Smarter fallback outline that uses the topic name instead of generic 'Key Points'."""
        topic = (user_prompt or "Presentation")[:80].strip() or "Title"
        
        # If the API crashes, we create a small, sensible 5-slide deck instead of a 15-slide empty deck.
        safe_slide_count = min(target_slides, 5) 
        
        slides = [
            {"slide_number": 1, "title": topic, "content": f"• An overview of {topic}.\n• Executive Summary."},
            {"slide_number": 2, "title": f"Market Context: {topic}", "content": "• Fetching latest market data..."},
            {"slide_number": 3, "title": f"Core Analysis: {topic}", "content": "• Detailed insights currently unavailable.\n• Please try refining the prompt."},
            {"slide_number": 4, "title": "Financials & Metrics", "content": "• Data temporarily unavailable."},
            {"slide_number": 5, "title": "Summary & Conclusion", "content": f"• Concluding thoughts on {topic}."},
        ]
        
        # Trim to target if somehow target is less than 5
        slides = slides[:safe_slide_count]
        
        for idx, s in enumerate(slides):
            s["slide_number"] = idx + 1
            
        return {
            "slides": slides,
            "total_slides": len(slides),
            "user_prompt": user_prompt,
            "template_id": template_id,
        }