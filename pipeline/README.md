# KEAM Cutoff Rank OCR Processing System

An offline, local web application that extracts KEAM engineering admission cutoff rank tables from PDF documents using AI vision (Ollama + minicpm-v:8b).

---

## System Requirements

| Component | Requirement |
|---|---|
| Python | 3.12+ |
| GPU | NVIDIA RTX 3050 6GB (or better) |
| RAM | 8GB+ |
| Ollama | Running locally with `minicpm-v:8b` pulled |
| PostgreSQL | Existing Supabase or local instance |

---

## Quick Start

### 1. Install Ollama model (if not already done)
```bash
ollama pull minicpm-v:8b
```

### 2. Set up Python environment
```bash
cd pipeline
python -m venv .venv

# Windows
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure environment
Copy `.env.example` to `.env` and fill in your credentials:
```bash
copy .env.example .env
```

The `.env` file already contains your Supabase credentials. Verify:
```
DB_HOST=aws-0-ap-southeast-1.pooler.supabase.com
DB_USER=postgres.ewautejpvfuhwpjjqxag
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=minicpm-v:8b
```

### 4. Run the application
```bash
python run.py
```

Open your browser: **http://127.0.0.1:8000**

---

## Usage Flow

```
1. Upload   →  Drag PDF or images onto the upload page
2. Process  →  Watch real-time OCR progress (15-30s per page)
3. Review   →  Search, sort, edit, or delete records in the preview table
4. Insert   →  Click "Insert Approved Data" → confirm → done
```

---

## Project Structure

```
pipeline/
├── app/
│   ├── main.py              # FastAPI app factory + lifespan
│   ├── config.py            # Pydantic settings (reads .env)
│   ├── dependencies.py      # DI providers
│   ├── api/                 # Route handlers
│   │   ├── health.py        # GET /api/health
│   │   ├── upload.py        # POST /api/upload
│   │   ├── process.py       # POST /api/process/{job_id}  (SSE stream)
│   │   ├── preview.py       # GET/PUT/DELETE /api/preview/{job_id}
│   │   └── insert.py        # POST /api/insert/{job_id}
│   ├── core/                # Business logic
│   │   ├── pdf_splitter.py  # PyMuPDF: PDF → PNG pages
│   │   ├── ocr_engine.py    # Ollama REST client + retry logic
│   │   ├── prompt_templates.py  # minicpm-v prompts
│   │   ├── data_cleaner.py  # Normalize OCR output
│   │   ├── validator.py     # Business rule validation
│   │   └── ocr_pipeline.py  # Pipeline orchestrator + SSE events
│   ├── db/
│   │   ├── database.py      # SQLAlchemy engine + session
│   │   ├── models.py        # ORM models (mirrors existing table)
│   │   └── repository.py    # All DB operations
│   ├── schemas/             # Pydantic request/response models
│   ├── templates/           # Jinja2 HTML templates
│   ├── static/              # CSS + JS
│   └── utils/               # Logging, file ops, image processing
├── data/
│   ├── uploads/             # Uploaded files (auto-cleaned after insert)
│   ├── images/              # Extracted page images
│   └── results/             # Job JSON results
├── sample/
│   └── lastrank_p1.pdf      # Sample KEAM 2026 PDF for testing
├── tests/
│   ├── conftest.py
│   ├── test_data_cleaner.py
│   └── test_validator.py
├── .env                     # Your credentials (gitignored)
├── .env.example             # Template
├── requirements.txt
├── pyproject.toml
└── run.py                   # Entrypoint
```

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | System health check |
| `POST` | `/api/upload` | Upload PDF/image files |
| `POST` | `/api/process/{job_id}` | Validate job is ready |
| `GET` | `/api/process/{job_id}/stream` | SSE progress stream |
| `GET` | `/api/process/{job_id}/status` | Check processing status |
| `GET` | `/api/preview/{job_id}` | Paginated record list |
| `GET` | `/api/preview/{job_id}/stats` | Summary statistics |
| `PUT` | `/api/preview/{job_id}/records/{idx}` | Edit a record |
| `DELETE` | `/api/preview/{job_id}/records/{idx}` | Delete a record |
| `POST` | `/api/insert/{job_id}` | Insert approved records |

---

## Running Tests

```bash
# From the pipeline/ directory
pytest tests/ -v
```

Unit tests (no external deps needed):
- `test_data_cleaner.py` — rank value parsing, comma removal, dash→null
- `test_validator.py` — required fields, format checks, duplicate detection

---

## Business Rules

- Only **Government (G)** colleges are inserted into the database
- Self-financing (S) records are extracted but skipped at insert time
- `"-"` → `null` in rank values
- Commas removed from numbers: `"8,302"` → `8302`
- "Other Categories" column parsed: `"FW:7355 SD:13549"` → `{"FW": 7355, "SD": 13549}`
- Upsert on conflict: `(year, round, course, college_code)` — existing records are updated, not duplicated

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `Cannot connect to database` | Check DB credentials in `.env`. Ensure Supabase is accessible. |
| `Cannot connect to Ollama` | Run `ollama serve` and ensure it's listening on port 11434 |
| `minicpm-v:8b not found` | Run `ollama pull minicpm-v:8b` |
| `keam_cutoff_ranks not found` | The Go backend must be set up and have run the import at least once |
| OCR returns empty JSON | Enable `APP_DEBUG=true` and check the raw response in logs |
| Very slow processing | Expected: ~15-30s per page on RTX 3050. Reduce image DPI in `.env` if needed. |

---

## Notes

- The app listens on `127.0.0.1:8000` only — it is not exposed to the network
- Temporary files are automatically deleted after successful database insertion
- The Go backend (port 8080) and this pipeline (port 8000) share the same PostgreSQL database but are independent processes
- The pipeline never modifies the schema of `keam_cutoff_ranks`
