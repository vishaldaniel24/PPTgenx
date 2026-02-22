# 🧠 NeuraDeck: Multi-Agent Presentation Architect

**NeuraDeck** is an autonomous, multi-agent AI system that transforms a single text prompt into a fully researched, data-rich, and professionally formatted `.pptx` presentation in under 60 seconds. 

Instead of generic text generation, NeuraDeck uses a swarm of specialized AI agents working in parallel to scrape real-time data, extract financial metrics, dynamically draw business charts, and compile everything into a sleek slide deck.

## ✨ Key Features

* **🤖 Multi-Agent Architecture:** Utilizes 5 distinct AI roles (Planner, News Researcher, Deep Dive Researcher, Formatter, and ChartMaster) working sequentially and in parallel.
* **🌍 Real-Time Web Research:** Integrates the Tavily Search API to bypass AI hallucinations, pulling current market data, financial projections, and competitor analysis up to the current year.
* **📊 Dynamic Chart Generation:** The `ChartMaster` agent uses Python's `matplotlib` to parse financial data from text and automatically draw accurate Pie, Bar, and Line charts (Revenue, Market Share, Funnels) directly onto the slides.
* **🎨 Enterprise Auto-Formatting:** Employs `python-pptx` to build slides with auto-scaling typography, intelligent text-wrapping, and strict anti-duplication logic. 
* **⚡ High-Availability Async Router:** Custom LLM dispatcher with instant failover (Groq → Cerebras → Gemini) ensuring zero downtime and lightning-fast parallel execution.
* **💎 Glassmorphism UI:** A premium, fully responsive frontend built in Streamlit featuring custom CSS, smooth animations, template selection, and a live chart gallery.

## 🛠️ Tech Stack

* **Backend:** FastAPI, Python, `asyncio`
* **Frontend:** Streamlit (with custom CSS/HTML injection)
* **AI / LLMs:** Groq (Llama 3.3 70B), Cerebras, Google Gemini
* **Data & Search:** Tavily API
* **Document & Image Generation:** `python-pptx`, `matplotlib`

## 📂 Project Structure
```text
├── backend/
│   ├── main.py          # FastAPI Server & Agent Logic
│   └── utils/           # PPTX & Chart generation scripts
├── frontend/
│   └── app.py           # Streamlit UI (Glassmorphism)
├── requirements.txt     # Project dependencies
└── README.md            # Documentation

## 🚀 How it Works (The 60-Second Pipeline)

1. **The Dispatch:** User inputs a prompt (e.g., *"Nvidia 2025 Financial Analysis vs AMD"*).
2. **Parallel Research:** The backend uses `asyncio.gather` to launch News and Project agents simultaneously, scraping the web for hard data.
3. **The Architect:** The Planning agent dynamically outlines the exact number of slides needed—no hardcoded filler.
4. **The Editor:** The Formatting agent strictly enforces grammar, tone, and a maximum word count to prevent text-heavy slides.
5. **The Artist:** The ChartMaster detects arrays of numbers, writes Python plotting code, and saves `.png` assets.
6. **The Assembler:** The Python-PPTX engine maps the text and charts to exact X/Y coordinates based on the selected corporate theme.

## 💻 Running it Locally

**1. Clone the repo and install dependencies:**
```bash
git clone [https://github.com/yourusername/neuradeck.git](https://github.com/yourusername/neuradeck.git)
cd neuradeck
pip install -r requirements.txt

Run the Backend (FastAPI):
    
Bash
cd backend
uvicorn main:app --reload

Run the Frontend (Streamlit):

Bash
cd frontend
streamlit run app.py