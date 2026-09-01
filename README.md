# P13 — Typed Read-Only Agent Tools

> **P13 · A typed tool set and a manifest**
>
> Build three read-only tools with `extra="forbid"` input models, pattern-constrained identifiers, row limits with truncation flags, and a decorator performing five checks at import. Generate a manifest from the registry and make CI fail when the committed manifest differs from the generated manifest.

---

## Why This Project Exists

Large Language Models (LLMs) can produce malformed tool arguments:
- Wrong types, missing fields, extra fields
- Unicode digits that pass `\d` but should be rejected (`P१२३`)
- Requests for unlimited rows that overwhelm context
- Arbitrary fields that attempt to bypass logic

This project solves these problems with **server-side Pydantic validation** that is *authoritative* — the LLM cannot bypass it, no matter what it sends.

---

## Architecture

```
                     USER
                       |
                       v
                  OLLAMA LLM
                (qwen3:8b etc.)
                       |
               Tool call request
                       |
                       v
                 TOOL REGISTRY
                (TOOL_REGISTRY)
                       |
                       v
            PYDANTIC VALIDATION
            (extra="forbid", [0-9])
                       |
         +-------------+-------------+
         |             |             |
         v             v             v
     get_product   get_user   get_user_orders
      Handler       Handler      Handler
         |             |             |
         +-------------+-------------+
                       |
                       v
                    SQLite
                  (read-only)
```

```
Registry → Manifest → CI
```

---

## The Three Tools

| Tool | Input Model | Identifier Pattern | Row Limit |
|------|-------------|-------------------|-----------|
| `get_product` | `ProductInput` | `^P[0-9]+$` | 1 |
| `get_user` | `UserInput` | `^U[0-9]+$` | 1 |
| `get_user_orders` | `UserOrdersInput` | `^U[0-9]+$` | 100 (default 20) |

**Valid examples:**
- `P1001`, `U1001` ✅
- `P१२३`, `U१२३` ❌ (Devanagari digits — rejected by `[0-9]`)
- `P１２３` ❌ (fullwidth digits — rejected)
- `PABC` ❌ (letters — rejected)

---

## The Five Registration Checks

The `@read_tool` decorator runs these at **import time**. Any failure raises `ToolRegistrationError` and the process cannot start:

| # | Check |
|---|-------|
| 1 | Description must be a non-empty string |
| 2 | `row_limit` must be a positive integer |
| 3 | First parameter must be annotated with a Pydantic `BaseModel` subclass |
| 4 | Input model must have `extra="forbid"` |
| 5 | Tool name must be unique — no duplicates allowed |

---

## The `\d` Trap

**Never use `\d` in identifier patterns.** Python's `re` and Pydantic's `pattern` validator use Unicode `\d`, which matches:
- Devanagari digits: `१२३` (U+0967–U+096F)
- Fullwidth digits: `１２３` (U+FF11–U+FF19)
- Arabic-Indic digits, and many others

Use `[0-9]` to restrict to strict ASCII digits only.

---

## Setup

### 1. Install Python 3.11+

Download from [python.org](https://www.python.org/downloads/)

### 2. Install Ollama

Download from [ollama.com](https://ollama.com) or on Windows:
```powershell
winget install Ollama.Ollama
```

### 3. Pull a model (recommended for i7 + 16GB + RTX 4050)

```bash
# Recommended — best tool-calling, ~5GB VRAM
ollama pull qwen3:8b

# Alternative
ollama pull llama3.1:8b
ollama pull mistral-small3.2

# Note: gpt-oss:20b requires ~12GB+ VRAM — not recommended for 16GB systems
```

### 4. Install Python dependencies

```bash
pip install pydantic fastapi "uvicorn[standard]" httpx ollama streamlit python-dotenv pytest pytest-cov pytest-asyncio ruff
```

### 5. Copy environment config

```bash
cp .env.example .env
# Edit .env if needed (defaults work out of the box)
```

### 6. Seed the database

```bash
python scripts/seed_database.py
```

Output: 20 products, 10 users, 52 orders (U1001 has 25 orders — enough for truncation demo)

### 7. Run tests

```bash
python -m pytest tests/ -v
```

### 8. Start the API

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### 9. Start the Streamlit UI

```bash
streamlit run ui/streamlit_app.py
```

---

## PowerShell One-Liners (Windows)

```powershell
# Install deps
python -m pip install pydantic fastapi "uvicorn[standard]" httpx ollama streamlit python-dotenv pytest ruff

# Seed DB
python scripts/seed_database.py

# Run tests
python -m pytest tests/ -v

# Start API
uvicorn app.main:app --reload

# Start UI
streamlit run ui/streamlit_app.py
```

---

## Ollama Setup

```bash
# Start Ollama server (runs in background)
ollama serve

# Check running models
ollama list

# Pull models (one at a time — each takes a few GB)
ollama pull qwen3:8b          # recommended first
ollama pull llama3.1:8b       # alternative
ollama pull mistral-small3.2  # alternative
```

---

## Manifest

The manifest is **generated from the live registry** — never manually written.

```bash
# Generate/update the committed manifest
python scripts/generate_manifest.py --output manifests/tools.json

# Drift check (exits nonzero if mismatch — used in CI)
python scripts/generate_manifest.py --check --output manifests/tools.json

# Via Makefile
make manifest        # generate
make manifest-check  # check
```

---

## Makefile Targets

| Target | Action |
|--------|--------|
| `make install` | Install all dependencies |
| `make seed` | Seed the SQLite demo database |
| `make test` | Run pytest suite |
| `make lint` | Run ruff linter |
| `make manifest` | Regenerate manifest.json |
| `make manifest-check` | Drift detection (CI mode) |
| `make run-api` | Start FastAPI server |
| `make run-ui` | Start Streamlit UI |
| `make all` | install + seed + test + manifest-check |
| `make ci` | lint + test + manifest-check |

---

## CI

GitHub Actions runs on every push/PR:
1. **Install** dependencies
2. **Lint** with Ruff
3. **Seed** database
4. **Test** with pytest (227+ tests)
5. **Manifest check** — fails if drift detected

See [`.github/workflows/ci.yml`](.github/workflows/ci.yml).

---

## Project Structure

```
p13-agentic-tools/
├── app/
│   ├── __init__.py
│   ├── config.py         # Central configuration
│   ├── database.py       # Read-only SQLite access
│   ├── models.py         # DB row dataclasses
│   ├── schemas.py        # Pydantic input/output models
│   ├── errors.py         # Custom exception hierarchy
│   ├── decorators.py     # @read_tool (5 checks)
│   ├── registry.py       # TOOL_REGISTRY
│   ├── handlers.py       # get_product, get_user, get_user_orders
│   ├── manifest.py       # Manifest generator + drift detection
│   ├── tools.py          # Ollama tool definitions
│   ├── agent.py          # Agentic loop
│   ├── ollama_client.py  # Ollama connectivity
│   ├── api.py            # FastAPI endpoints
│   └── main.py           # Uvicorn entry point
│
├── ui/
│   └── streamlit_app.py  # 8-page Streamlit console
│
├── tests/
│   ├── conftest.py
│   ├── test_app_models.py     # Schema validation
│   ├── test_app_registry.py   # 5-check decorator
│   ├── test_security.py       # test_malformed_arguments_never_reach_handler
│   ├── test_app_handlers.py   # Handler + DB integration
│   ├── test_app_manifest.py   # Manifest + drift detection
│   ├── test_app_agent.py      # Agent loop (mocked Ollama)
│   ├── test_models.py         # Original tools/ models
│   ├── test_registry.py       # Original tools/ registry
│   ├── test_tools.py          # Original tools/ handlers
│   └── test_manifest.py       # Original manifest
│
├── scripts/
│   ├── seed_database.py        # Create and seed demo.db
│   ├── generate_manifest.py    # CLI: generate or --check
│   └── demo_scenarios.py       # 7 presentation scenarios
│
├── data/
│   └── demo.db                 # SQLite demo database
│
├── manifests/
│   └── tools.json              # Committed manifest (source of truth)
│
├── tools/                      # Original P13 implementation (kept)
│   ├── models.py
│   ├── registry.py
│   ├── handlers.py
│   └── manifest.py
│
├── .github/workflows/ci.yml
├── .env.example
├── Makefile
├── pyproject.toml
└── README.md
```

---

## Security Guarantees

| Guarantee | Mechanism |
|-----------|-----------|
| Typed inputs | Pydantic v2 models on every tool |
| `extra="forbid"` | Unknown fields rejected before handler |
| ASCII-only identifiers | `[0-9]` patterns, not `\d` |
| Server-side row limits | Pydantic `ge`/`le` + double-enforcement in handler |
| Truncation reporting | `truncated=True` flag always set truthfully |
| Read-only handlers | SQLite opened in `mode=ro` URI mode |
| No arbitrary SQL | Parameterized queries only |
| Import-time validation | `@read_tool` fails at startup |
| Registry source of truth | Single `TOOL_REGISTRY` dict |
| Manifest consistency | CI drift check |

---

## Known Limitations

- Ollama tool calling quality varies by model. `qwen3:8b` works best.
- `gpt-oss:20b` is not recommended for systems with ≤16GB RAM.
- The UI's AI Chat requires Ollama to be running; all other pages work without it.
- Manifest check in CI does not install Ollama — agent tests use mocks.
MIT License — see [LICENSE](LICENSE).
