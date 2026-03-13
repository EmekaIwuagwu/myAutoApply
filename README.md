# AutoApply — AI-Powered Job Application Agent

AutoApply is a fully automated job application agent built in Python. It searches for jobs across multiple platforms, uses a local LLM (via Ollama) to score each job for fit, tailors your resume, generates cover letters, and submits applications automatically — like a human would.

## Features

- **Multi-platform scraping**: Indeed, LinkedIn, Greenhouse/Lever, Remote.co / We Work Remotely
- **LLM-powered fit analysis**: Scores each job 0–1 using Ollama (llama3 or mistral)
- **Automated applications**: Fills and submits forms, uploads resume, generates cover letters
- **Human simulation**: Random delays, character-by-character typing, mouse movements
- **Anti-bot hardening**: Stealth mode, rotating user agents, session persistence
- **Resume tailoring**: LLM suggests edits to match each job description
- **Dark web dashboard**: Real-time status, activity feed, log streaming via SSE
- **Daily limits**: Configurable max applications/day and min fit score threshold
- **APScheduler**: Auto-run every N hours in the background

## Tech Stack

| Layer | Technology |
|---|---|
| Web Framework | Flask 3.x |
| Database | SQLite via SQLAlchemy |
| Browser Automation | Playwright (async) |
| HTML Parsing | BeautifulSoup4 + lxml |
| Computer Vision | OpenCV + Pillow |
| OCR (fallback) | Tesseract + pytesseract |
| LLM Backend | Ollama (llama3 / mistral) |
| Human Simulation | fake-useragent + random delays |
| Resume Editing | python-docx + pdfplumber |
| Task Queue | Python threading + APScheduler |
| Frontend | Tailwind CSS (CDN) + Vanilla JS |

## Setup

### 1. Clone and install

```bash
git clone <repo-url>
cd myAutoApply
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Install Playwright browsers

```bash
playwright install chromium
```

### 3. Install and start Ollama

Download from [https://ollama.ai](https://ollama.ai), then:

```bash
ollama pull llama3
ollama serve  # starts on http://localhost:11434
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env with your preferences
```

### 5. Initialize the database

```bash
python -c "
from autoapply.app import create_app
app = create_app()
print('Database initialized!')
"
```

### 6. Run AutoApply

```bash
python run.py
# Visit http://localhost:5000
```

## Usage

1. **Upload your resume** at `/resume` (PDF or DOCX)
2. **Fill in your profile** at `/settings` — name, skills, experience, desired role
3. **Configure the agent** — search keywords, min fit score, max daily applications
4. **Click "Start Agent"** on the dashboard and watch it work
5. **Monitor activity** in real-time at `/logs`
6. **Review applications** with fit scores and screenshots at `/applications`

## Project Structure

```
autoapply/
├── app.py                  # Flask routes and app factory
├── config.py               # All configuration
├── database/
│   ├── models.py           # SQLAlchemy models (7 tables)
│   └── db.py               # DB init and config helpers
├── agents/
│   ├── orchestrator.py     # Master pipeline controller
│   ├── search_agent.py     # Finds jobs on all platforms
│   ├── analysis_agent.py   # LLM fit scoring
│   ├── apply_agent.py      # Fills and submits applications
│   └── resume_agent.py     # Resume tailoring per job
├── browser/
│   ├── playwright_engine.py # Async browser controller
│   ├── human_simulator.py  # Delays, typing, scrolling
│   └── session_manager.py  # Cookie persistence
├── scrapers/
│   ├── indeed_scraper.py
│   ├── linkedin_scraper.py
│   ├── greenhouse_scraper.py
│   └── remoteco_scraper.py
├── llm/
│   ├── ollama_client.py    # Ollama HTTP client
│   ├── prompts.py          # LLM prompt templates
│   └── analyzer.py         # Job analysis logic
├── resume/
│   ├── parser.py           # Parse PDF/DOCX resumes
│   └── tailorer.py         # LLM-powered tailoring
├── vision/
│   ├── screenshot.py       # Playwright screenshot capture
│   ├── ocr.py              # Tesseract OCR fallback
│   └── detector.py         # OpenCV button detection
├── scheduler/
│   └── job_scheduler.py    # APScheduler integration
└── templates/              # Jinja2 HTML templates
```

## Running Tests

```bash
# Database tests
python tests/test_db.py

# Browser tests (requires Playwright)
python tests/test_browser.py

# Ollama tests (requires Ollama running)
python tests/test_ollama.py

# Indeed scraper test
python tests/test_scraper_indeed.py

# Full pipeline dry run (no actual job submission)
python tests/test_full_pipeline.py
```

## Configuration

All settings can be managed via the **Settings UI** at `/settings` or via environment variables in `.env`:

| Setting | Default | Description |
|---|---|---|
| `MIN_FIT_SCORE` | 0.65 | Minimum LLM fit score to auto-apply |
| `MAX_DAILY_APPLICATIONS` | 20 | Daily application cap |
| `SEARCH_INTERVAL_MINUTES` | 60 | Auto-run interval |
| `HEADLESS` | false | Run browser headless |
| `OLLAMA_MODEL` | llama3 | Which Ollama model to use |

## Anti-Bot Measures

- Random delays (0.5–3s) between every action
- Character-by-character typing with variable speed
- Rotate user agents via `fake-useragent`
- Disable `navigator.webdriver` flag
- Scroll into view before clicking
- Session cookie persistence (avoids repeated logins)
- Daily application rate limiting

## Notes

- LinkedIn requires valid credentials — set in Settings → Platform Credentials
- Greenhouse/Lever forms are the most reliable (structured HTML)
- If Ollama is offline, the dashboard shows a warning but does not crash
- The Stop button sends a graceful shutdown signal between pipeline steps
- All screenshots are saved in `uploads/screenshots/`

## License

MIT
