"""
NeuraDeck – Research-to-Deck in 60 Seconds
==========================================
One prompt → 7 research agents → outline → research → charts → one .pptx.
Frontend → Backend: POST /api/generate (prompt, templateId, charts) → poll status → GET result for PPTX download.
"""

import os
import time
from typing import Optional, Tuple

import requests  # type: ignore[reportMissingImports]
import streamlit as st  # type: ignore[reportMissingImports]

# ============================================================================
# CONFIG
# ============================================================================
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")
STREAMLIT_PAGE_TITLE = "NeuraDeck – VC-Ready Decks in 60 Seconds"

# Theme cards: id, title, description, and colors for preview gradient + strip (bg, accent, accent_secondary, text_primary)
THEMES = [
    {"id": "corporate", "title": "Corporate Navy", "desc": "15-slide deck with News, Charts, full report. Clean serif titles, trusted for board decks.", "bg": "#ffffff", "accent": "#1b3a5c", "accent_secondary": "#8b7355", "text_primary": "#0d1b2a"},
    {"id": "pitch", "title": "Midnight Pitch", "desc": "10-slide YC-style: Problem, Solution, Traction, Ask. Dark, confident investor deck.", "bg": "#1a1a1a", "accent": "#a63d2e", "accent_secondary": "#b8860b", "text_primary": "#f0f0f0"},
    {"id": "builtin_1", "title": "Warm Ivory", "desc": "Cream and terracotta. Editorial feel for thought leadership and reports.", "bg": "#faf6f0", "accent": "#9c6b4a", "accent_secondary": "#6b5344", "text_primary": "#2c1810"},
    {"id": "builtin_2", "title": "Forest", "desc": "Deep green with muted gold. Calm, credible for sustainability and strategy.", "bg": "#1e2a1e", "accent": "#a89868", "accent_secondary": "#6b8e6b", "text_primary": "#e8ebe4"},
    {"id": "builtin_3", "title": "Concrete", "desc": "Neutral grey and brick. Industrial, no-nonsense for operations and data.", "bg": "#e8e6e1", "accent": "#8b4513", "accent_secondary": "#3d3d3d", "text_primary": "#1a1a1a"},
    {"id": "builtin_4", "title": "Indigo Classic", "desc": "Deep blue and gold. Timeless finance and executive summary style.", "bg": "#1c2340", "accent": "#b89850", "accent_secondary": "#6b7a9e", "text_primary": "#e4e6ed"},
    {"id": "builtin_5", "title": "Sand & Stone", "desc": "Warm beige and olive. Approachable, editorial for workshops and proposals.", "bg": "#f5f0e8", "accent": "#5c6b4a", "accent_secondary": "#7a6b5a", "text_primary": "#2c2416"},
    {"id": "builtin_6", "title": "Slate Minimal", "desc": "Light grey and slate blue. Minimal, modern for product and design decks.", "bg": "#f5f5f5", "accent": "#3d5a6c", "accent_secondary": "#6b8a9a", "text_primary": "#111111"},
]

EXAMPLE_PROMPTS = [
    "Tesla FSD competitive landscape — key players, timelines, and differentiation",
    "SaaS startup pitch — product, traction, team, and funding ask",
    "Q4 market analysis — key trends, growth areas, and risks for board prep",
]

# ============================================================================
# PAGE CONFIG
# ============================================================================
st.set_page_config(
    page_title=STREAMLIT_PAGE_TITLE,
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============================================================================
# CSS – Dark theme, template cards, upload zone, gradient buttons
# ============================================================================
def inject_css():
    st.markdown(
        """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    :root {
        --glow-cyan: #00D4FF;
        --glow-purple: #A855F7;
        --glass: rgba(255,255,255,0.06);
        --glass-border: rgba(255,255,255,0.12);
    }

    .stApp, [data-testid="stAppViewContainer"] {
        background: linear-gradient(180deg, #0a0e1a 0%, #0f1629 50%, #0a0e1a 100%) !important;
        font-family: 'Inter', sans-serif !important;
    }

    /* Header */
    .neura-header {
        text-align: center;
        padding: 1.5rem 0 2rem;
    }
    .neura-logo {
        font-size: 2.5rem;
        font-weight: 700;
        color: var(--glow-cyan);
        text-shadow: 0 0 20px rgba(0,212,255,0.5);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
    }
    .neura-tagline {
        font-size: 0.85rem;
        color: rgba(255,255,255,0.8);
        letter-spacing: 0.15em;
        margin-top: 0.35rem;
        text-transform: uppercase;
    }

    /* Section title (Select Your Template, etc.) */
    .section-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: var(--glow-cyan);
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    /* Template card grid */
    .template-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1.25rem;
        margin-bottom: 2rem;
    }
    @media (max-width: 900px) {
        .template-grid { grid-template-columns: repeat(2, 1fr); }
    }
    .template-card {
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 16px;
        padding: 1.25rem;
        transition: border-color 0.2s, box-shadow 0.2s;
    }
    .template-card.selected {
        border-color: var(--glow-cyan);
        box-shadow: 0 0 24px rgba(0,212,255,0.25);
    }
    .template-card-preview {
        height: 80px;
        border-radius: 12px;
        margin-bottom: 0.75rem;
    }
    .template-card-strip {
        display: flex;
        height: 8px;
        border-radius: 4px;
        overflow: hidden;
        margin-bottom: 1rem;
    }
    .template-card-strip span {
        flex: 1;
        min-width: 0;
    }
    .template-card-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #fff;
        margin-bottom: 0.35rem;
    }
    .template-card-desc {
        font-size: 0.8rem;
        color: rgba(255,255,255,0.6);
        margin-bottom: 1rem;
        line-height: 1.4;
    }
    .template-card-btn {
        display: block;
        width: 100%;
        padding: 0.6rem 1rem;
        border: none;
        border-radius: 10px;
        font-size: 0.9rem;
        font-weight: 600;
        cursor: pointer;
        text-align: center;
        background: linear-gradient(90deg, #3b82f6, var(--glow-purple));
        color: white;
        transition: opacity 0.2s;
    }
    .template-card-btn:hover { opacity: 0.9; }
    .template-card-btn.selected-btn {
        background: linear-gradient(90deg, var(--glow-cyan), var(--glow-purple));
    }

    /* Upload zone */
    .upload-zone-wrap {
        background: rgba(255,255,255,0.03);
        border: 2px dashed rgba(0,212,255,0.4);
        border-radius: 16px;
        padding: 2rem;
        margin: 1.5rem 0;
        text-align: center;
    }
    .upload-zone-wrap .upload-inner {
        color: rgba(255,255,255,0.7);
        font-size: 0.95rem;
    }
    .upload-zone-wrap .upload-hint {
        font-size: 0.8rem;
        color: rgba(255,255,255,0.5);
        margin-top: 0.5rem;
    }

    /* Research section */
    .research-heading {
        font-size: 1.15rem;
        font-weight: 600;
        color: var(--glow-cyan);
        margin: 1.5rem 0 0.75rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    /* Generate button */
    .gen-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
        width: 100%;
        max-width: 420px;
        margin: 2rem auto;
        padding: 1rem 2rem;
        font-size: 1.1rem;
        font-weight: 600;
        border: none;
        border-radius: 12px;
        background: linear-gradient(90deg, #3b82f6, var(--glow-purple));
        color: white;
        cursor: pointer;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .gen-btn:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 32px rgba(59,130,246,0.4);
    }

    /* Progress / download (keep existing feel) */
    .progress-card {
        background: var(--glass);
        backdrop-filter: blur(20px);
        border: 1px solid var(--glass-border);
        border-radius: 20px;
        padding: 2rem;
        margin: 2rem auto;
        max-width: 560px;
    }
    .progress-msg { font-size: 1.1rem; color: var(--glow-cyan); margin-bottom: 0.75rem; }
    .bounce-dots::after { animation: bounceDots 1s infinite; content: ''; }
    @keyframes bounceDots {
        0%, 20% { content: '.'; }
        40% { content: '..'; }
        60%, 100% { content: '...'; }
    }
    .success-title {
        font-size: 1.75rem;
        font-weight: 700;
        color: var(--glow-cyan);
        margin: 1rem 0;
    }
    .download-zone {
        background: var(--glass);
        border: 1px solid var(--glass-border);
        border-radius: 20px;
        padding: 2rem;
        margin: 2rem auto;
        max-width: 400px;
        text-align: center;
    }

    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
    </style>
    """,
        unsafe_allow_html=True,
    )


# ============================================================================
# API HELPERS
# ============================================================================
def submit_generation(
    prompt: str, template_id: str, charts: bool, brand_color: str | None = None
) -> Optional[str]:
    """POST /api/generate → returns job_id or None. Topic→Planning, Template→outline/layout, Color→brand, Charts→ChartMaster."""
    try:
        payload = {
            "prompt": (prompt or "").strip(),
            "templateId": template_id,
            "charts": charts,
        }
        if brand_color and str(brand_color).strip():
            payload["brandColor"] = str(brand_color).strip()
        r = requests.post(
            f"{BACKEND_URL}/api/generate",
            json=payload,
            timeout=15,
        )
        r.raise_for_status()
        try:
            data = r.json()
            return data.get("jobId")
        except (ValueError, KeyError) as json_err:
            # JSON parsing failed - show raw response
            st.error(f"Backend returned invalid JSON. Response: {r.text[:500]}")
            st.error(f"JSON error: {json_err}")
            return None
    except requests.exceptions.ConnectionError:
        st.error("Cannot connect to backend. Start the API on " + BACKEND_URL)
        return None
    except requests.exceptions.HTTPError as e:
        if e.response is not None:
            try:
                if e.response.status_code == 422:
                    detail = e.response.json().get("detail", [])
                    if isinstance(detail, list) and detail and isinstance(detail[0], dict):
                        msg = detail[0].get("msg", str(e))
                    else:
                        msg = str(e)
                else:
                    # Try to parse error response, fallback to raw text
                    try:
                        error_data = e.response.json()
                        msg = error_data.get("detail", error_data.get("message", str(e)))
                    except (ValueError, KeyError):
                        msg = f"HTTP {e.response.status_code}: {e.response.text[:500]}"
                st.error(msg)
            except Exception:
                st.error(f"Request failed: {e}. Response: {e.response.text[:500] if e.response else 'No response'}")
        else:
            st.error(f"Request failed: {e}")
        return None
    except Exception as e:
        st.error(f"Request failed: {e}")
        return None


def get_status(job_id: str) -> Tuple[str, str]:
    """GET /api/generate/{job_id}/status → (status, progress_message)."""
    try:
        r = requests.get(f"{BACKEND_URL}/api/generate/{job_id}/status", timeout=10)
        r.raise_for_status()
        try:
            d = r.json()
            return d.get("status", ""), d.get("progress_message", "")
        except (ValueError, KeyError):
            # JSON parsing failed
            return "unknown", f"Invalid response: {r.text[:200]}"
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 404:
            return "failed", "Job not found or expired."
        return "unknown", ""
    except Exception:
        return "unknown", ""


def get_result_bytes(job_id: str) -> Optional[bytes]:
    """GET /api/generate/{job_id}/result → PPTX bytes or None."""
    try:
        r = requests.get(f"{BACKEND_URL}/api/generate/{job_id}/result", timeout=30)
        r.raise_for_status()
        return r.content
    except Exception:
        return None


# ============================================================================
# SESSION STATE
# ============================================================================
if "job_id" not in st.session_state:
    st.session_state.job_id = None
if "prompt" not in st.session_state:
    st.session_state.prompt = ""
if "template_id" not in st.session_state:
    st.session_state.template_id = "builtin_2"  # Neon Purple default
if "include_charts" not in st.session_state:
    st.session_state.include_charts = True
if "brand_color" not in st.session_state:
    st.session_state.brand_color = "#1E3A8A"

# ============================================================================
# RENDER
# ============================================================================
inject_css()

# ----- Header -----
st.markdown(
    '<div class="neura-header">'
    '<div class="neura-logo">🧠 NeuraDeck</div>'
    '<p class="neura-tagline">VC-READY DECKS IN 60 SECONDS</p>'
    '</div>',
    unsafe_allow_html=True,
)

# ----- Select Your Template -----
st.markdown(
    '<p class="section-title">🧠 Select Your Template</p>',
    unsafe_allow_html=True,
)

# Grid of template cards (Corporate, Pitch, + 6 builtins)
rows = [THEMES[:4], THEMES[4:8]]
for row in rows:
    if row:  # Only create columns if row has items
        cols = st.columns(len(row))
        for col, theme in zip(cols, row):
            with col:
                selected = st.session_state.template_id == theme["id"]
                card_class = "template-card selected" if selected else "template-card"
                bg, acc, text = theme["bg"], theme["accent"], theme["text_primary"]
                acc_sec = theme.get("accent_secondary", acc)
                preview_style = f"background: linear-gradient(135deg, {bg} 0%, {acc} 100%);"
                strip_html = f'<span style="background:{bg}"></span><span style="background:{acc}"></span><span style="background:{text}"></span>'
                st.markdown(
                    f'<div class="{card_class}">'
                    f'<div class="template-card-preview" style="{preview_style}"></div>'
                    f'<div class="template-card-strip">{strip_html}</div>'
                    f'<div class="template-card-title">{theme["title"]}</div>'
                    f'<div class="template-card-desc">{theme["desc"]}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                btn_label = "✓ SELECTED" if selected else "SELECT"
                if st.button(btn_label, key=f"theme_{theme['id']}", use_container_width=True, type="primary" if selected else "secondary"):
                    st.session_state.template_id = theme["id"]
                    st.rerun()

# ----- Or Upload Your Branded Template -----
st.markdown(
    '<p class="section-title">📤 Or Upload Your Branded Template</p>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="upload-zone-wrap">'
    '<p class="upload-inner">☁️ Drag and drop file here</p>'
    '<p class="upload-hint">Limit 200MB per file • PPTX</p>'
    '</div>',
    unsafe_allow_html=True,
)
uploaded_file = st.file_uploader(
    "Browse files",
    type=["pptx"],
    accept_multiple_files=False,
    key="branded_upload",
    label_visibility="collapsed",
)
if uploaded_file:
    st.caption(f"Uploaded: {uploaded_file.name} (backend template upload not yet wired)")

# ----- What Would You Like to Research? -----
st.markdown(
    '<p class="research-heading">💬 What Would You Like to Research?</p>',
    unsafe_allow_html=True,
)
example = st.selectbox(
    "Example prompts",
    options=[""] + EXAMPLE_PROMPTS,
    format_func=lambda x: x if x else "— Choose an example —",
    key="example_prompts",
    label_visibility="collapsed",
)
placeholder = (
    "Example: Tesla research - what they do, their projects, competitors, and how to contact them for business opportunities..."
)
prompt_value = st.session_state.prompt or (example if example else "")
topic = st.text_area(
    "Research prompt",
    value=prompt_value,
    placeholder=placeholder,
    height=120,
    key="topic_input",
    label_visibility="collapsed",
)
st.session_state.prompt = topic or prompt_value

include_charts = st.checkbox(
    "Include business charts (Revenue, Funnel, Team, Market)",
    value=st.session_state.include_charts,
    key="charts",
)
st.session_state.include_charts = include_charts

# Brand color picker → backend brand propagation (PPT + charts accent)
brand_color = st.color_picker(
    "Brand accent color (PPT theme + charts)",
    value=st.session_state.brand_color,
    key="brand_color_picker",
)
st.session_state.brand_color = brand_color or st.session_state.brand_color

# ----- Generate button -----
st.markdown(
    '<div style="text-align: center;">'
    '<p style="font-size:0.85rem; color: rgba(255,255,255,0.5); margin-bottom: 0.5rem;">'
    'To exit full screen, press and hold <kbd style="background:rgba(255,255,255,0.1); padding:2px 6px; border-radius:4px;">Esc</kbd>'
    '</p></div>',
    unsafe_allow_html=True,
)
generate_clicked = st.button("🚀 Generate Research Deck", type="primary", use_container_width=True)

if generate_clicked:
    if not (topic or st.session_state.prompt):
        st.warning("Enter a research prompt first.")
    else:
        job_id = submit_generation(
            prompt=topic or st.session_state.prompt,
            template_id=st.session_state.template_id,
            charts=st.session_state.include_charts,
            brand_color=st.session_state.brand_color,
        )
        if job_id:
            st.session_state.job_id = job_id
            st.rerun()

# ----- Progress / result (when job_id is set) -----
if st.session_state.job_id:
    job_id = st.session_state.job_id
    status, msg = get_status(job_id)

    st.markdown('<div class="progress-card">', unsafe_allow_html=True)

    if status == "completed":
        st.markdown('<p class="success-title">PPT READY!</p>', unsafe_allow_html=True)

        ppt_bytes = get_result_bytes(job_id)
        if ppt_bytes:
            st.markdown('<div class="download-zone">', unsafe_allow_html=True)
            st.download_button(
                label="📥 Download PowerPoint",
                data=ppt_bytes,
                file_name=f"NeuraDeck_{job_id[:8]}.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                type="primary",
                use_container_width=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.error("Download failed. Check that the backend is running and try again.")
            if st.button("Retry download"):
                st.rerun()
        if st.button("Create another"):
            st.session_state.job_id = None
            st.rerun()
    elif status == "failed":
        st.error(f"Generation failed: {msg}")
        st.session_state.job_id = None
    else:
        progress_msg = msg or "Working..."
        if "Planning" in progress_msg or "Initializing" in progress_msg:
            display_msg = "AI Planning" + '<span class="bounce-dots"></span>'
        elif "News" in progress_msg or "Projects" in progress_msg:
            display_msg = "News & Projects Research" + '<span class="bounce-dots"></span>'
        elif "RAG" in progress_msg:
            display_msg = "RAG / brand guidelines" + '<span class="bounce-dots"></span>'
        elif "Research" in progress_msg:
            display_msg = "Researching slides" + '<span class="bounce-dots"></span>'
        elif "Formatter" in progress_msg:
            display_msg = "Formatting slides" + '<span class="bounce-dots"></span>'
        elif "Chart" in progress_msg:
            display_msg = "Generating Charts" + '<span class="bounce-dots"></span>'
        elif "Building" in progress_msg:
            display_msg = "Building PPT" + '<span class="bounce-dots"></span>'
        else:
            display_msg = progress_msg + '<span class="bounce-dots"></span>'
        st.markdown(f'<p class="progress-msg">{display_msg}</p>', unsafe_allow_html=True)
        prog = (
            0.6 if "Building" in progress_msg
            else 0.55 if "Chart" in progress_msg
            else 0.5 if "Formatter" in progress_msg
            else 0.48 if "RAG" in progress_msg
            else 0.42 if "Research" in progress_msg
            else 0.35 if "News" in progress_msg or "Projects" in progress_msg
            else 0.3
        )
        st.progress(prog, text=progress_msg)

    st.markdown("</div>", unsafe_allow_html=True)

    if status not in ("completed", "failed"):
        time.sleep(1.2)
        st.rerun()
