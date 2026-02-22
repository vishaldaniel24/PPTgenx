"""
ChartMaster Agent - Universal Business Charts
=============================================
Generates 4 business charts (Revenue, Sales Funnel, Team Growth, Market Opportunity)
for ANY company. Uses Google Gemini to generate realistic data when not provided.
Output: ['revenue.png', 'funnel.png', 'team.png', 'market.png'] in the given output folder.

Also supports auto-detection: scan outline slides for numerical data (2+ data points),
extract chart spec via LLM, render theme-aware line/bar/pie/gauge and return slide index -> path.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from app.charts import generate_all_charts, render_dynamic_chart
from app.gemini_client import generate_async

# Module-level logger (must be before any function or class definition)
logger = logging.getLogger(__name__)

# Default structure when LLM is not used
DEFAULT_COMPANY_DATA = {
    "revenue": {"periods": ["2024", "2025", "2026", "2027"], "values": [10, 25, 50, 100], "unit": "M"},
    "funnel": {
        "stages": ["Leads", "MQL", "SQL", "Deal", "Closed"],
        "percentages": [100, 50, 20, 10, 5],
    },
    "team_growth": {"months": None, "headcount": None},  # None -> charts.py uses default
    "market": {"labels": ["Enterprise", "Mid-market", "SMB"], "sizes": [45, 35, 20]},
}


class ChartMasterAgent:
    """
    Generates 4 universal business charts. If company_data is missing or partial,
    calls Gemini to generate realistic data for the given topic, then renders charts.
    """

    def __init__(self, model_name: str = "gemini-2.0-flash"):
        self.model_name = model_name

    def _build_data_prompt(self, topic: str, research_context: str | None = None) -> str:
        context_block = ""
        if research_context and research_context.strip():
            context_block = f"""
RESEARCH CONTEXT:
{research_context[:2500].strip()}

"""
        # FIX: Added strict instruction to prioritize REAL data from research
        return f"""You are a data analyst. For the company/topic "{topic}", return ONLY valid JSON with meaningful business metrics. 
You MUST use real numbers from the RESEARCH CONTEXT if available. If no real data is available, generate highly realistic estimates.
{context_block}
Use this exact structure:
{{
  "revenue": {{
    "periods": ["2024", "2025", "2026", "2027"],
    "values": [realistic values in M or B],
    "unit": "M" or "B"
  }},
  "funnel": {{
    "stages": [stage names relevant to the topic, e.g. "Leads", "MQL", "SQL", "Deal", "Closed"],
    "percentages": [100, then declining conversion %]
  }},
  "team_growth": {{
    "months": ["Jan 2025", "Feb 2025", "Mar 2025", "Apr 2025"],
    "headcount": [realistic headcount growth]
  }},
  "market": {{
    "labels": [segment names relevant to the topic, e.g. "Enterprise", "Mid-market", "SMB"],
    "sizes": [market share or TAM % that sum to 100]
  }}
}}

Return ONLY the JSON object, no markdown or explanation."""

    def _parse_llm_json(self, raw: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks and malformed JSON."""
        raw = raw.strip()
        
        # FIX: Bulletproof Regex JSON extraction
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            raw = match.group(0)
            
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    async def generate_charts(
        self,
        topic: str,
        company_data: Dict[str, Any] | None = None,
        output_dir: str | Path = "/tmp/charts",
        accent_color: str | None = None,
        research_context: str | None = None,
    ) -> tuple[List[Path], Dict[str, Any]]:
        output_dir = Path(output_dir)
        data = dict(company_data) if company_data else {}

        if not _has_chart_data(data):
            try:
                text = await generate_async(
                    self._build_data_prompt(topic, research_context=research_context),
                    model_name=self.model_name,
                    temperature=0.2, # Lowered to reduce wild hallucinations
                    max_output_tokens=800,
                )
                if text:
                    llm_data = self._parse_llm_json(text)
                    if llm_data:
                        for key in ("revenue", "funnel", "team_growth", "market"):
                            if key not in data or not data[key]:
                                data[key] = llm_data.get(key) or DEFAULT_COMPANY_DATA[key]
            except Exception:
                pass
                
        for key in ("revenue", "funnel", "team_growth", "market"):
            if key not in data or not data[key]:
                data[key] = DEFAULT_COMPANY_DATA.get(key, {})

        output_dir = Path(output_dir).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = generate_all_charts(output_dir, company_data=data, accent_color=accent_color)
        return paths, data

    async def detect_and_generate_charts(
        self,
        outline: Dict[str, Any],
        output_dir: str | Path,
        theme_hex_dict: Dict[str, str] | None = None,
    ) -> Dict[int, Path]:
        """Auto-detect numerical data per slide, extract spec, render charts. Returns slide_index -> path."""
        return await detect_and_generate_charts(
            outline, output_dir, theme_hex_dict=theme_hex_dict, model_name=self.model_name
        )


def _has_chart_data(data: Dict[str, Any]) -> bool:
    """True if data has at least one chart section with usable content."""
    if data.get("revenue", {}).get("values"): return True
    if data.get("funnel", {}).get("percentages"): return True
    if data.get("team_growth", {}).get("headcount"): return True
    if data.get("market", {}).get("sizes"): return True
    return False


def _count_data_points(bullets: List[str]) -> int:
    """Count data points in slide bullets."""
    if not bullets: return 0
    text = " ".join(str(b) for b in bullets).lower()
    count = 0
    count += len(re.findall(r"\$?\s*[\d,]+(?:\.\d+)?\s*%?", text))
    return count


def _extract_chart_spec_heuristic(slide_title: str, bullets: List[str]) -> Dict[str, Any] | None:
    """Extract chart type and data from slide content using heuristics."""
    text = " ".join(str(b) for b in (bullets or []))
    combined = (slide_title + " " + text).lower()
    
    values: List[float] = []
    
    # Extract explicit percentage/money values first (high priority)
    for m in re.findall(r"\$?\s*([\d.]+)\s*(?:%|million|M|billion|B|k)", text, re.I):
        try: values.append(float(m))
        except ValueError: pass

    # Extract plain numbers, but SKIP years and quarters!
    if not values:
        for m in re.finditer(r"[\d,]+(?:\.\d+)?", text):
            s = m.group(0).replace(",", "")
            try:
                val = float(s)
                # FIX: Skip Years (e.g., 2024, 2025)
                if 1900 <= val <= 2100 and "." not in s:
                    continue
                # FIX: Skip Quarters (e.g., Q1, Q2, Q3, Q4)
                if val in [1.0, 2.0, 3.0, 4.0] and re.search(rf"q{int(val)}\b", text, re.I):
                    continue
                values.append(val)
            except ValueError:
                pass
                
    if len(values) < 2:
        return None
        
    values = values[:8] # Don't crowd the chart
    
    # Infer labels
    labels: List[str] = []
    years = re.findall(r"\b(20[12]\d)\b", text)
    if len(years) >= len(values):
        labels = list(dict.fromkeys(years))[: len(values)]
    if not labels and re.search(r"q[1-4]|quarter", combined):
        labels = [f"Q{(i % 4) + 1}" for i in range(len(values))]
    if len(labels) < len(values):
        labels = [f"Data {i+1}" for i in range(len(values))]
    labels = labels[: len(values)]
    
    # Determine Chart Type
    if re.search(r"revenue|growth over time|year over year|yoy|trend", combined) and len(values) >= 2:
        chart_type = "line"
    elif re.search(r"market share|percent of|% of|share.*%|breakdown", combined) or (all(0 <= v <= 100 for v in values) and len(values) <= 6):
        chart_type = "pie"
    else:
        chart_type = "bar"
        
    title_short = (slide_title or "Data Insight")[:50]
    return {"type": chart_type, "title": title_short, "labels": labels, "values": values}


async def detect_and_generate_charts(
    outline: Dict[str, Any],
    output_dir: str | Path,
    theme_hex_dict: Dict[str, str] | None = None,
    model_name: str = "gemini-2.0-flash",
) -> Dict[int, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    theme = theme_hex_dict or {}
    slides = outline.get("slides") or []
    result: Dict[int, Path] = {}

    for idx, s in enumerate(slides):
        title = s.get("title") or ""
        content = s.get("content")
        if isinstance(content, str):
            bullets = [content] if content.strip() else []
        else:
            bullets = list(content) if content else []
        bullets = [str(b).strip() for b in bullets if str(b).strip()]

        data_points = _count_data_points(bullets)
        if data_points < 2:
            continue
            
        spec = _extract_chart_spec_heuristic(title, bullets)
        if not spec or not spec.get("type"):
            continue
            
        save_path = (output_dir / f"slide_chart_{idx}.png").resolve()
        try:
            out = render_dynamic_chart(save_path, spec.get("type", "bar"), spec, theme=theme)
            if out is not None and save_path.exists():
                result[idx] = save_path
        except Exception as e:
            logger.warning("ChartMaster: failed to generate chart for slide %d: %s", idx, e)
            
    return result