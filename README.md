# HEXA — Sovereign Industrial AI Workbench

<p align="center">
  <img src="static/assets/hexa-logo.png" alt="HEXA Logo" width="120" style="border-radius:50%; box-shadow:0 4px 20px rgba(16,185,129,0.3);">
</p>

<p align="center">
  <b>Air-Gapped · Local-First · Agentic AI · Zero Data Egress</b>
</p>

<p align="center">
  <i>Engineered for Refineries, PSUs, Defence Units, and High-Security Enterprise Environments</i>
</p>

---

## The Idea

Refineries, public sector undertakings (PSUs), defence-linked manufacturing units, and government institutions generate massive volumes of sensitive knowledge work — P&ID diagrams, audit reports, vendor negotiation notes, engineering schematics, and internal correspondence.

**The problem**: Cloud AI assistants (ChatGPT, Claude, Gemini) are prohibited in these environments. Sending proprietary data across public networks violates data sovereignty policies and air-gap mandates. Engineers either spend thousands of hours on manual work, or risk policy violations by quietly using cloud models.

**HEXA solves this** by delivering a fully self-hosted AI workspace that runs entirely on the organization's own hardware. No internet connection required. No data ever leaves the premises. Engineers get the full power of modern AI — document understanding, reasoning, code generation, research — with verifiable zero network egress.

---

## Key Features

### Verifiable Zero-Egress Air-Gap Security
- Operates completely offline without external API keys, telemetry, or cloud calls
- Compatible with air-gapped networks — no outbound traffic during operation
- No login required — single-user local deployment, just open and use

### Multi-Model Auto-Routing
- Automatically classifies prompt intent and routes to the best available model:
  - **Coding & Automation** → Qwen-2.5-Coder
  - **Math & Complex Reasoning** → DeepSeek-R1
  - **Multimodal / Image / OCR** → Qwen2-VL / LLaVA
  - **General Knowledge** → Llama-3.3 / Qwen-2.5
- Supports any OpenAI-compatible endpoint: Ollama, vLLM, LM Studio, llama.cpp, SGLang

### Full Document Intelligence
- Upload `.docx`, `.pdf`, `.xlsx`, `.pptx`, `.txt`, `.csv`, `.md` — the AI reads and understands the actual content
- Multi-layer extraction: `markitdown` → `python-docx` → native ZIP/XML fallback ensures Word documents are always processed
- PDF extraction with page-by-page text and image OCR via vision model
- 24,000-character shared context budget with smart proportional allocation across multiple attachments

### Corporate Deliverable Engine
- Generates structured downloadable files from AI output:
  - **Word (`.docx`)** — Approval notes, inspection summaries, memos
  - **Excel (`.xlsx`)** — Calculation sheets with native formulas
  - **PowerPoint (`.pptx`)** — Board presentations, technical review decks

### Agentic Multi-Step Autonomy
- Extended agent loop powered by Model Context Protocol (MCP v1)
- Decomposes complex tasks, runs Python scripts, searches documents, validates results
- Web search, shell execution, memory management, scheduled tasks

### On-Premises RAG & Knowledge Base
- Index internal SOPs, manuals, standards, and correspondence locally
- FastEmbed (ONNX local embeddings) + ChromaDB vector store
- Exact citation: document name, page, and paragraph text

### Email, Calendar, Notes, Tasks
- Full email client (IMAP/SMTP, Gmail OAuth)
- CalDAV calendar sync
- Markdown notes with AI assistance
- Task management with scheduling

---

## System Architecture & Data Flow

```
User Input (text + documents)
         │
         ▼
  HEXA Web Interface (Vanilla JS ES Modules)
         │
         ▼
  FastAPI Async Core (Python 3.11+)
         │
    ┌────┴────┐
    │         │
    ▼         ▼
Document   Intent Router
Processor  & Task Classifier
    │         │
    │    ┌────┼─────────────┐
    │    ▼    ▼             ▼
    │  Ollama  OpenAI   Anthropic
    │  vLLM    Groq     (any OpenAI-
    │  llama.cpp         compatible)
    │    │
    ▼    ▼
MCP Agent Loop
(tool calls, script execution, web search, memory)
    │
    ▼
Response + Optional Deliverable
(DOCX / XLSX / PPTX / Markdown)
    │
    ▼
Real-time SSE Stream → Browser
```

**Attachment Processing Flow:**
```
Upload .docx / .pdf / .xlsx
         │
         ▼
   UploadHandler (saves to data/uploads/, UUID filename)
         │
         ▼
   DocumentProcessor.build_user_content()
         │
         ├─ .docx → markitdown (if installed)
         │           → python-docx via multimodal_parser
         │           → native ZIP+XML extractor (always works)
         │
         ├─ .pdf  → pypdf text extraction
         │           → vision model for image-only pages
         │
         ├─ image → base64 inline → vision model
         │
         └─ .txt/.py/.csv → direct text read
         │
         ▼
   Content appended to LLM message (up to 24,000 chars inline)
   Full text saved as Document in DB (accessible via manage_documents)
         │
         ▼
   AI model receives actual document content and responds
```

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| **Backend** | Python 3.11+, FastAPI, Uvicorn | Async REST + SSE streaming |
| **Frontend** | Vanilla HTML5/CSS3/ES6 Modules | No build step, zero npm required |
| **Database** | SQLite (default) / PostgreSQL | File-based SQLite for standalone |
| **Vector Search** | ChromaDB Client + FastEmbed | Local ONNX embeddings, offline |
| **LLM Inference** | Ollama, vLLM, llama.cpp, LM Studio | Any OpenAI-compatible endpoint |
| **Cloud LLMs** | OpenAI, Anthropic, Groq, Gemini, Mistral | Optional, when internet available |
| **Document Extraction** | python-docx, pypdf, markitdown, PyMuPDF | DOCX/PDF/XLSX/PPTX processing |
| **Agent Protocol** | MCP SDK v1 | Tool calls, multi-step autonomy |
| **Audio** | faster-whisper (STT), Kokoro-82M (TTS) | Fully local, no cloud |
| **Search** | SearXNG (self-hosted), DuckDuckGo, Brave | Pluggable search providers |
| **Email** | IMAP/SMTP + Gmail OAuth | Full email client |
| **Calendar** | CalDAV + icalendar | Sync with Nextcloud, Apple, etc. |
| **Rendering** | Mermaid.js, KaTeX, Highlight.js | Diagrams, math, code highlighting |

---

## Setup & Installation

### Prerequisites

- Python 3.11 or 3.12
- Git
- At least one LLM backend (Ollama recommended for local use)

### 1. Clone the Repository

```bash
git clone https://github.com/AsHwIn00000/SIH.git
cd SIH
```

### 2. Create and Activate a Virtual Environment

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
# Core dependencies (required)
pip install -r requirements.txt

# Optional — for full Office document support, local STT/TTS, DuckDuckGo search
pip install -r requirements-optional.txt
```

Key optional packages and what they unlock:
- `markitdown[docx,pptx,xlsx,xls]` — higher-fidelity Office document extraction
- `faster-whisper` — local microphone speech-to-text
- `kokoro` — local text-to-speech (Python 3.11–3.12 only)
- `ddgs` — DuckDuckGo search provider
- `PyMuPDF` — PDF form-filling (AGPL-3.0 license)

> **Note**: Even without optional packages, `.docx` files are fully readable — the built-in `python-docx` and native ZIP/XML extractor always work.

### 4. Configure the Environment

```bash
cp .env.example .env
```

Edit `.env` and set the values relevant to your setup:

```env
# Authentication — disabled by default, no login required
AUTH_ENABLED=false

# Point to your Ollama instance (or any OpenAI-compatible LLM)
LLM_HOST=localhost
# OLLAMA_BASE_URL=http://localhost:11434/v1

# Optional: OpenAI API key (only needed for cloud models)
# OPENAI_API_KEY=sk-...

# SearXNG for web search (optional, self-hosted)
# SEARXNG_INSTANCE=http://localhost:8080
```

### 5. Set Up a Local LLM (Ollama)

```bash
# Install Ollama from https://ollama.com
# Pull recommended models
ollama pull llama3.2
ollama pull qwen2.5-coder
ollama pull llava   # for image/document OCR
```

### 6. Run the Application

```bash
python -m uvicorn app:app --host 0.0.0.0 --port 7000 --reload
```

Or use the provided launcher:

```bash
python launcher.py
```

Windows users can double-click `launch-windows.ps1`.

Open your browser at **http://localhost:7000**

---

## Docker Setup (Recommended for Production)

```bash
# Start all services (app + SearXNG + ChromaDB)
docker compose up -d

# View logs
docker compose logs -f
```

The app will be available at **http://localhost:7000**.

---

## Directory Structure

```
HEXA/
├── app.py                  # Main FastAPI application entry point
├── launcher.py             # Windows/Mac desktop launcher
├── requirements.txt        # Core Python dependencies
├── requirements-optional.txt  # Optional feature dependencies
├── .env                    # Your local configuration (not committed)
├── .env.example            # Configuration template
│
├── core/                   # Core modules
│   ├── auth.py             # Authentication manager (bcrypt, sessions, TOTP)
│   ├── database.py         # SQLAlchemy models and DB setup
│   ├── middleware.py        # Security headers, admin checks
│   ├── models.py           # Pydantic models
│   └── session_manager.py  # Chat session lifecycle
│
├── routes/                 # FastAPI route handlers
│   ├── chat_routes.py      # Chat + streaming SSE
│   ├── upload_routes.py    # File upload handling
│   ├── auth_routes.py      # Login/logout/user management
│   ├── session_routes.py   # Session CRUD
│   ├── research_routes.py  # Deep research agent
│   ├── note_routes.py      # Notes management
│   ├── email_routes.py     # Email client
│   └── ...                 # 30+ more route files
│
├── src/                    # Business logic
│   ├── document_processor.py   # Attachment → LLM content pipeline
│   ├── markitdown_runtime.py   # DOCX/XLSX/PPTX extraction chain
│   ├── multimodal_parser.py    # python-docx/openpyxl/pptx parsers
│   ├── llm_core.py             # LLM API calls, provider detection
│   ├── upload_handler.py       # File storage, MIME detection
│   ├── owner_identity.py       # Auth mode detection
│   └── ...
│
├── static/                 # Frontend (no build step needed)
│   ├── index.html          # SPA shell
│   ├── style.css           # All styles
│   └── js/                 # ES6 modules (~60 files)
│
├── data/                   # Runtime data (auto-created, git-ignored)
│   ├── app.db              # SQLite database
│   ├── uploads/            # Uploaded files
│   ├── settings.json       # App settings
│   └── logs/               # Application logs
│
├── mcp_servers/            # MCP tool servers
│   ├── memory_server.py    # Memory/context tools
│   ├── email_server.py     # Email tools
│   └── image_gen_server.py # Image generation tools
│
└── config/
    └── searxng/
        └── settings.yml    # SearXNG search engine config
```

---

## Configuration Reference

### Key Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AUTH_ENABLED` | `false` | Enable login page (`true`) or open access (`false`) |
| `LLM_HOST` | `localhost` | Primary LLM host for model discovery |
| `OLLAMA_BASE_URL` | auto | Explicit Ollama URL |
| `OPENAI_API_KEY` | — | OpenAI API key (optional) |
| `DATABASE_URL` | `sqlite:///./data/app.db` | Database URL |
| `ODYSSEUS_DATA_DIR` | `./data` | Move all data to a custom path |
| `SEARXNG_INSTANCE` | `http://localhost:8080` | SearXNG search URL |
| `LOCALHOST_BYPASS` | `false` | Skip auth for loopback requests |
| `APP_PORT` | `7000` | Server port |
| `REQUEST_HARD_TIMEOUT` | `45` | Per-request timeout in seconds |

### Adding LLM Models

1. Open the app → Settings → Models
2. Click "Add Endpoint"
3. Enter your endpoint URL (e.g. `http://localhost:11434/v1`) and API key if needed
4. HEXA auto-discovers available models from the endpoint

---

## Document Upload — How It Works

When you upload a `.docx` Word document (or any supported file) in chat:

1. **File is saved** to `data/uploads/` with a UUID filename
2. **Extraction runs** using the multi-layer pipeline:
   - `markitdown` (if installed) — best quality
   - `python-docx` — full paragraphs and tables
   - Native ZIP+XML — always available, no external deps
3. **Full text is saved** as a Document in the database (viewable in the Document panel)
4. **Up to 24,000 characters** are included inline in the chat message
5. **The AI model receives** the actual document text and can answer questions, summarize, extract data, or take action based on the content

Supported upload formats: `.docx`, `.pdf`, `.xlsx`, `.pptx`, `.epub`, `.txt`, `.py`, `.csv`, `.json`, `.md`, `.log`, images (PNG/JPG/WebP/GIF), audio (MP3/WAV/M4A)

---

## Authentication

By default (`AUTH_ENABLED=false`), no login is required. Just open the app and start working.

To enable multi-user authentication (useful for shared deployments):

```env
AUTH_ENABLED=true
```

On first run with auth enabled, you'll be prompted to create an admin account. Features include bcrypt password hashing, session tokens, optional TOTP 2FA, per-user privilege controls, and API tokens for integrations.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines, commit conventions, and the PR process.

---

## Acknowledgments

See [ACKNOWLEDGMENTS.md](ACKNOWLEDGMENTS.md) for third-party licenses and credits.

---

## License

This project is licensed under the MIT License — see the LICENSE file for details.
