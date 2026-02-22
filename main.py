"""
NeuraDeck FastAPI Backend – Research-to-deck in 60 seconds
==========================================================
7 agents: Planning -> (News + Projects in parallel) -> Research -> RAG -> Formatter -> ChartMaster -> build_ppt.
One prompt, one .pptx. Uses Google Gemini and Tavily. 
"""

import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv  # type: ignore[reportMissingImports]

_backend_dir = Path(__file__).resolve().parent
_env_path = _backend_dir / ".env"
if _env_path.exists():
    load_dotenv(str(_env_path), override=True)
else:
    load_dotenv(str(_backend_dir.parent / ".env"), override=True)
    
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, Form, HTTPException, BackgroundTasks, UploadFile  # type: ignore[reportMissingImports]
from fastapi.middleware.cors import CORSMiddleware  # type: ignore[reportMissingImports]
from fastapi.responses import FileResponse  # type: ignore[reportMissingImports]
from pydantic import BaseModel, field_validator  # type: ignore[reportMissingImports]
import uvicorn  # type: ignore[reportMissingImports]

from app.jobs import create_job, get_job, update_job, JobStatus
from app.agents import generate_research_and_outline
from app.research_agent import _fetch_tavily_multistep
from app.news_research_agent import NewsResearchAgent
from app.projects_research_agent import ProjectsResearchAgent

# Graceful import for RAG in case the user hasn't uploaded local files yet
try:
    from app.rag_agent import RAGAgent
except ImportError:
    RAGAgent = None

from app.formatter_agent import FormatterAgent
from app.chart_master_agent import ChartMasterAgent
from app.ppt_builder import build_ppt, get_template_accent_hex, get_template_theme_hex

OUTPUT_DIR = Path(__file__).resolve().parent / "output"

TEMPLATE_ID_ALIASES = {
    "1": "builtin_1", "2": "builtin_2", "3": "builtin_3",
    "4": "builtin_4", "5": "builtin_5", "6": "builtin_6",
    "builtin 1": "builtin_1", "builtin 2": "builtin_2", "builtin 3": "builtin_3",
    "theme_1": "builtin_1", "theme_2": "builtin_2", "theme_3": "builtin_3",
    "theme1": "builtin_1", "theme2": "builtin_2", "theme3": "builtin_3",
}

def normalize_template_id(template_id: str | None) -> str:
    tid = (template_id or "").strip().lower()
    if not tid: return "builtin_1"
    if tid in TEMPLATE_ID_ALIASES: return TEMPLATE_ID_ALIASES[tid]
    if tid in ("builtin_1", "builtin_2", "builtin_3", "builtin_4", "builtin_5", "builtin_6", "corporate", "pitch"):
        return tid
    for alias, canonical in TEMPLATE_ID_ALIASES.items():
        if alias.replace(" ", "_") == tid or tid.replace("_", " ") == alias:
            return canonical
    return "builtin_1"


def _find_slide_index_by_title(slides: List[Dict[str, Any]], title: str) -> Optional[int]:
    t = title.strip().lower()
    for i, s in enumerate(slides):
        if (s.get("title") or "").strip().lower() == t:
            return i
    return None


def _inject_slide_content(outline: Dict[str, Any], title: str, content: List[str]) -> None:
    if not content or not isinstance(content, list): return
    cleaned = [str(b).strip() for b in content if b and str(b).strip()][:5]
    if not cleaned: return
    slides = outline.get("slides", [])
    idx = _find_slide_index_by_title(slides, title)
    if idx is not None:
        slides[idx]["content"] = cleaned


app = FastAPI(
    title="NeuraDeck API",
    version="1.0.0",
    description="Research-to-deck platform: one prompt → 7 research agents → outline → research → charts → one .pptx.",
)

_CORS_ORIGINS = [
    "http://localhost:8501", "http://127.0.0.1:8501",
    "http://localhost:5500", "http://127.0.0.1:5500",
    "http://localhost:8080", "http://127.0.0.1:8080",
    "http://localhost:3000", "http://127.0.0.1:3000",
    "http://localhost:5173", "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _require_api_keys() -> None:
    missing = []
    if not (os.environ.get("GROQ_API_KEY") or "").strip():
        missing.append("GROQ_API_KEY")
    if not (os.environ.get("TAVILY_API_KEY") or "").strip():
        missing.append("TAVILY_API_KEY")
    if missing:
        raise RuntimeError("NeuraDeck cannot start: missing required API key(s): " + ", ".join(missing))


@app.on_event("startup")
def _startup_validate_env() -> None:
    _require_api_keys()


class GenerateRequest(BaseModel):
    prompt: str
    templateId: str = "builtin_1"
    charts: bool = True
    brandColor: str | None = None 

    @field_validator("prompt")
    @classmethod
    def prompt_not_empty(cls, v: str) -> str:
        cleaned = (v or "").strip()
        if not cleaned: raise ValueError("Prompt cannot be empty")
        return cleaned


class GenerateResponse(BaseModel):
    jobId: str

class StatusResponse(BaseModel):
    status: str
    progress_message: str


async def run_generation_pipeline(job_id: str, prompt: str, template_id: str, charts: bool = True, brand_color: str | None = None):
    try:
        update_job(job_id=job_id, status=JobStatus.PENDING, message="Initializing...")
        template_id = normalize_template_id(template_id)
        topic_short = prompt[:120]

        # 1) Gather raw research
        update_job(job_id=job_id, status=JobStatus.PENDING, message="Gathering raw research...")
        try:
            raw_snippets = await _fetch_tavily_multistep(topic_short)
            raw_research = "\n\n---\n\n".join(raw_snippets)
        except Exception:
            raw_research = ""
            
        news_agent = NewsResearchAgent()
        projects_agent = ProjectsResearchAgent()
        
        market_bullets, success_bullets = await asyncio.gather(
            news_agent.fetch_market_context(topic_short),
            projects_agent.fetch_success_stories(topic_short),
        )
        
        if market_bullets or success_bullets:
            raw_research += "\n\n## Market & News\n" + "\n".join(f"- {b}" for b in (market_bullets or []))
            raw_research += "\n\n## Success Stories\n" + "\n".join(f"- {b}" for b in (success_bullets or []))
        if not raw_research.strip():
            raw_research = f"Topic: {topic_short}. No web research retrieved."

        # 2) Generate Outline
        update_job(job_id=job_id, status=JobStatus.PENDING, message="Generating outline from research...")
        outline_json = await generate_research_and_outline(
            raw_research, prompt, template_id=template_id, charts_enabled=charts
        )

        _inject_slide_content(outline_json, "Market Context", market_bullets)
        _inject_slide_content(outline_json, "Success Stories", success_bullets)

        # 3) RAG / Style Context
        style_context = None
        if RAGAgent:
            update_job(job_id=job_id, status=JobStatus.PENDING, message="RAG Agent loading brand guidelines...")
            try:
                rag_agent = RAGAgent()
                style_context = await rag_agent.get_style_context(prompt[:120])
            except Exception:
                pass # Fail silently if user hasn't setup local documents

        # 4) Formatting
        update_job(job_id=job_id, status=JobStatus.PENDING, message="Formatter Agent polishing slides...")
        formatter_agent = FormatterAgent()
        outline_json = await formatter_agent.format_outline(
            outline_json, style_context=style_context, user_prompt=prompt
        )

        job_dir = OUTPUT_DIR / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        chart_paths = []
        chart_data: dict = {}
        slide_chart_paths = {}

        # 5) Charts
        if charts:
            update_job(job_id=job_id, status=JobStatus.BUILDING_PPT, message="ChartMaster generating business charts...")
            chart_agent = ChartMasterAgent()
            chart_dir = job_dir / "charts"
            chart_accent = brand_color or get_template_accent_hex(template_id)
            theme_hex = get_template_theme_hex(template_id, brand_color)
            
            try:
                chart_paths, chart_data = await chart_agent.generate_charts(
                    topic=prompt[:80], output_dir=chart_dir, accent_color=chart_accent, research_context=raw_research[:3000]
                )
                chart_paths = list(chart_paths)[:4]
            except Exception:
                pass
                
            try:
                slide_chart_paths = await chart_agent.detect_and_generate_charts(
                    outline_json, chart_dir, theme_hex_dict=theme_hex
                )
            except Exception:
                pass

        # 6) Build PPT
        update_job(job_id=job_id, status=JobStatus.BUILDING_PPT, message="Building PowerPoint...")
        ppt_path = job_dir / f"NeuraDeck_{job_id}.pptx"
        template_path = job_dir / "template.pptx" if (job_dir / "template.pptx").exists() else None
        
        await asyncio.to_thread(
            build_ppt,
            outline=outline_json, chart_paths=chart_paths, output_path=ppt_path, user_prompt=prompt[:80],
            template_id=template_id, brand_color=brand_color, template_path=template_path,
            chart_data=chart_data, slide_chart_paths=slide_chart_paths,
        )

        update_job(
            job_id=job_id, status=JobStatus.COMPLETED,
            message="Done. Generated deck." + (" Includes business charts." if charts else ""),
            result_path=str(ppt_path),
        )
        
    except Exception as e:
        error_msg = str(e)
        if "Failed to parse JSON" in error_msg or "JSONDecodeError" in error_msg:
            error_msg = f"Outline JSON error: {error_msg[:500]}"
        update_job(job_id=job_id, status=JobStatus.FAILED, message=error_msg, error=error_msg)


def _handle_generate(request: GenerateRequest, background_tasks: BackgroundTasks):
    job = create_job()
    background_tasks.add_task(
        run_generation_pipeline, job_id=job.id, prompt=request.prompt,
        template_id=request.templateId, charts=request.charts, brand_color=request.brandColor,
    )
    return GenerateResponse(jobId=job.id)

@app.post("/api/generate", response_model=GenerateResponse)
async def generate_ppt(request: GenerateRequest, background_tasks: BackgroundTasks):
    return _handle_generate(request, background_tasks)

@app.get("/api/generate/{job_id}/status", response_model=StatusResponse)
async def get_job_status(job_id: str):
    job = get_job(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job not found")
    return StatusResponse(status=job.status.value, progress_message=job.message or job.status.value)

@app.get("/api/generate/{job_id}/result")
async def get_job_result(job_id: str):
    job = get_job(job_id)
    if not job or job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=404, detail="Job not found or not completed")
    if not job.result_path or not Path(job.result_path).exists():
        raise HTTPException(status_code=404, detail="Result file not found")
    return FileResponse(
        path=job.result_path, filename=f"NeuraDeck_{job_id}.pptx",
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)