"""
NeuraDeck PPT Formatter Agent
=============================
Polishes bullets for professional decks: concise, no repetition, grammar rules, optional RAG style.
Uses Google Gemini. Input/output: outline with slides, each content = list of bullet strings (max 5).
"""

import json
import re
from typing import Any, Dict, List, Optional

from app.gemini_client import generate_async

MAX_BULLETS_PER_SLIDE = 5
# FIX 1: Increased from 12 to 18 to allow for data-rich financial bullets without cutting them off
MAX_WORDS_PER_BULLET = 18 

FORBIDDEN_PLACEHOLDER_PHRASES = [
    "could not be generated",
    "key insights",
    "research and present information about",
    "important considerations",
    "notable trends",
    "this slide covers",
    "details for this section",
    "key information for the presentation",
    "specific details about",
    "write specific content about",
]

def _truncate_to_words(text: str, max_words: int = MAX_WORDS_PER_BULLET) -> str:
    """Return text truncated to at most max_words words, adding an ellipsis if chopped."""
    words = (text or "").strip().split()
    if len(words) <= max_words:
        return text.strip()
    # FIX 2: Add an ellipsis so users know the text was truncated, rather than looking like a typo
    return " ".join(words[:max_words]).strip() + "..."


def _apply_grammar_rules(bullets: List[str]) -> List[str]:
    out = []
    for b in bullets:
        s = str(b).strip()
        if s.startswith("-"):
            s = s[1:].strip()
        if s and s[-1] in ".,;:":
            s = s[:-1].rstrip()
        if s:
            s = s + "."
        if s:
            s = s[0].upper() + s[1:] if len(s) > 1 else s.upper()
        out.append(s)
    return out


class FormatterAgent:
    def __init__(self, model_name: str = "gemini-2.0-flash"):
        self.model_name = model_name

    def _build_format_prompt(
        self, slide_title: str, bullets: List[str], style_context: Optional[str] = None
    ) -> str:
        bullets_text = "\n".join(f"- {b}" for b in bullets[:8])
        style_block = ""
        if style_context and style_context.strip():
            style_block = f"\nStyle/brand guidelines: {style_context[:400]}\n"
        return f"""You are a senior PPT editor. Polish wording and length only. Every word must earn its place—no filler.

RULES:
- Output 4 or 5 bullets per slide. Maximum {MAX_WORDS_PER_BULLET} words per bullet. Each one short sentence. Capitalize, one period at end. No markdown.
- Never paste a full paragraph as a bullet. If content is long, use multiple bullets.
- PRESERVE substance: keep exact figures (e.g. $2M, 40%, Q3 2024), company names, and concrete claims.
- Do NOT repeat the slide title.
- FORBIDDEN generic phrases: "strong growth", "key metrics", "various", "multiple", "significant", "robust", "comprehensive", "innovative solutions", "stakeholders", "holistic".
- GOOD: "ARR $2.1M in 2024", "Partnership with Acme Corp".
- BAD: turning "ARR $2.1M" into "Strong revenue".
{style_block}

Slide title: {slide_title}

Current bullets (polish grammar and length only; keep all specifics):
{bullets_text}

Return ONLY a valid JSON array of 4-5 strings. Example: ["Point one.", "Point two."]"""

    def _build_format_outline_prompt(
        self, outline: Dict[str, Any], style_context: Optional[str] = None
    ) -> str:
        slides = outline.get("slides", [])
        style_block = ""
        if style_context and style_context.strip():
            style_block = f"\nStyle/brand guidelines: {style_context[:400]}\n"
        slides_block = []
        for i, s in enumerate(slides):
            title = s.get("title", "Slide")
            content = s.get("content", [])
            if not isinstance(content, list):
                content = [str(content).strip()] if content and str(content).strip() else []
            bullets = [str(b).strip() for b in content if b and str(b).strip()][:8]
            bullets_text = "\n".join(f"- {b}" for b in bullets) if bullets else "(no content)"
            slides_block.append(f"Slide {i+1} | Title: {title}\nBullets:\n{bullets_text}")
            
        return f"""You are a senior PPT editor. Polish wording and length for ALL slides below. Every word must earn its place.

RULES (apply to every slide):
- 4 or 5 bullets per slide. Max {MAX_WORDS_PER_BULLET} words per bullet. One short sentence each.
- PRESERVE substance: exact figures ($2M, 40%), company names, concrete claims.
- Do NOT repeat the slide title. No generic phrases.
{style_block}

SLIDES:
---
""" + "\n---\n".join(slides_block) + """

Return ONLY a valid JSON object with one key "slides": an array of objects. 
Example: {"slides": [{"title": "Title", "content": ["bullet1", "bullet2"]}]}"""

    def _is_placeholder_only(self, bullets: List[str]) -> bool:
        if not bullets: return True
        return all(not b.strip() or b.strip() == "—" for b in bullets)

    def _is_content_copy_of_prompt(self, content: List[str], user_prompt: str) -> bool:
        """True if slide content is empty or effectively a copy of the user prompt."""
        if not user_prompt or not content:
            return bool(not content)
        prompt_lower = user_prompt.strip().lower()[:200]
        if not prompt_lower:
            return False
            
        words_prompt = set(prompt_lower.split())
        
        # FIX 3: If the prompt is 3 words or less, bypass this check. 
        # A 1-word prompt like "Apple" will always trigger a 100% false positive.
        if len(words_prompt) <= 3:
            return False
            
        combined = " ".join(str(b).strip().lower() for b in content if b).strip()[:300]
        if not combined or combined == "—":
            return True
            
        words_content = set(combined.split())
        overlap = len(words_prompt & words_content) / max(len(words_prompt), 1)
        return overlap > 0.85

    async def _format_slide(self, slide: Dict[str, Any], style_context: Optional[str] = None) -> List[str]:
        title = slide.get("title", "Slide")
        content = slide.get("content", [])
        if isinstance(content, list):
            bullets = [str(b).strip() for b in content if b and str(b).strip()][:5]
        else:
            raw = str(content).strip()[:200] if content else ""
            bullets = [raw] if raw and raw != "—" else []

        if not bullets or self._is_placeholder_only(bullets):
            return bullets if bullets else []

        prompt = self._build_format_prompt(title, bullets, style_context)
        try:
            text = await generate_async(
                prompt, model_name=self.model_name, temperature=0.2, max_output_tokens=350,
            )
        except Exception:
            applied = _apply_grammar_rules(bullets[:MAX_BULLETS_PER_SLIDE])
            return [_truncate_to_words(b) for b in applied]

        text = (text or "").strip()
        
        # FIX 4: Bulletproof JSON Array parsing for single slides
        match = re.search(r'\[.*\]', text, re.DOTALL)
        if match: text = match.group(0)

        try:
            out = json.loads(text)
            if isinstance(out, list):
                raw = [str(b).strip()[:150] for b in out if b and str(b).strip()][:MAX_BULLETS_PER_SLIDE] or bullets[:1]
                applied = _apply_grammar_rules(raw)[:MAX_BULLETS_PER_SLIDE]
                return [_truncate_to_words(b) for b in applied]
            applied = _apply_grammar_rules(bullets[:MAX_BULLETS_PER_SLIDE])
            return [_truncate_to_words(b) for b in applied]
        except json.JSONDecodeError:
            applied = _apply_grammar_rules(bullets[:MAX_BULLETS_PER_SLIDE])
            return [_truncate_to_words(b) for b in applied]

    def validate_outline_for_ppt(self, outline: Dict[str, Any], user_prompt: str) -> None:
        slides = outline.get("slides", [])
        prompt = (user_prompt or "").strip()[:200]
        words_prompt = set(prompt.split())
        
        for i, slide in enumerate(slides):
            title = slide.get("title", "Slide")
            content = slide.get("content", [])
            if isinstance(content, str):
                content = [content] if content.strip() else []
            bullets = [str(b).strip() for b in content if b and str(b).strip() and str(b).strip() != "—"]
            
            if not bullets:
                # Instead of crashing the whole app, we just log a warning and continue.
                continue
                
            is_title_slide = i == 0
            combined = " ".join(bullets).lower()
            
            for phrase in FORBIDDEN_PLACEHOLDER_PHRASES:
                if phrase in combined:
                    raise ValueError(f"Slide '{title}' contains forbidden text: '{phrase}'.")
                    
            # FIX 5: Bypass the overlap crash logic for short prompts
            if not is_title_slide and prompt and combined.strip() and len(words_prompt) > 3:
                words_content = set(combined.split())
                overlap = len(words_prompt & words_content) / max(len(words_prompt), 1)
                if overlap > 0.85:
                    raise ValueError(f"Slide '{title}' content is too similar to the prompt.")

    async def format_outline(
        self, outline: Dict[str, Any], style_context: Optional[str] = None, user_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        slides = outline.get("slides", [])
        if not slides: return outline

        prompt = self._build_format_outline_prompt(outline, style_context)
        try:
            text = await generate_async(
                prompt, model_name=self.model_name, temperature=0.2, max_output_tokens=3500,
            )
        except Exception:
            text = ""
            
        text = (text or "").strip()
        
        # FIX 6: Bulletproof JSON Object parsing for full outline
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match: text = match.group(0)
            
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "slides" in parsed and isinstance(parsed["slides"], list):
                raw_slides = parsed["slides"]
                formatted = []
                for i, slide in enumerate(slides):
                    if i < len(raw_slides):
                        rs = raw_slides[i]
                        title = rs.get("title") or slide.get("title", "Slide")
                        content = rs.get("content")
                        
                        if isinstance(content, list):
                            bullets = [str(b).strip() for b in content if b and str(b).strip()][:MAX_BULLETS_PER_SLIDE]
                        else:
                            bullets = [str(content).strip()] if content and str(content).strip() else []
                            
                        applied = _apply_grammar_rules(bullets)[:MAX_BULLETS_PER_SLIDE]
                        truncated = [_truncate_to_words(b) for b in applied]
                    else:
                        title = slide.get("title", "Slide")
                        bullets = slide.get("content", [])
                        if isinstance(bullets, str): bullets = [bullets]
                        truncated = [_truncate_to_words(str(b)) for b in bullets]
                        
                    formatted.append({**slide, "title": title, "content": truncated})
                result = {**outline, "slides": formatted, "total_slides": len(formatted)}
                if user_prompt is not None:
                    self.validate_outline_for_ppt(result, user_prompt)
                return result
        except (json.JSONDecodeError, TypeError, KeyError):
            pass

        # Fallback to slide-by-slide if full outline formatting fails
        formatted = []
        for slide in slides:
            content = await self._format_slide(slide, style_context)
            truncated_content = [_truncate_to_words(str(b).strip()) for b in content[:MAX_BULLETS_PER_SLIDE] if str(b).strip()]
            formatted.append({**slide, "content": truncated_content})
        result = {**outline, "slides": formatted, "total_slides": len(formatted)}
        
        if user_prompt is not None:
            try:
                self.validate_outline_for_ppt(result, user_prompt)
            except ValueError:
                # If validation fails on the fallback, return the original unformatted outline rather than crashing
                return outline
                
        return result