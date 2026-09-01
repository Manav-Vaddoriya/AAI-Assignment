# P13 — Typed Read-Only Agent Tools
# -------------------------------------------
# Targets:
#   make install        — install all Python dependencies
#   make seed           — create and seed the demo database
#   make test           — run the full pytest suite
#   make lint           — run ruff linter
#   make manifest       — regenerate manifests/tools.json and diff against committed
#   make manifest-check — compare generated manifest with committed (CI mode)
#   make run-api        — start the FastAPI server
#   make run-ui         — start the Streamlit UI
#   make all            — install + seed + test + manifest-check
#   make ci             — test + lint + manifest-check (CI pipeline)

PYTHON        ?= python
MANIFEST_DIR   = manifests
MANIFEST_FILE  = $(MANIFEST_DIR)/tools.json
MANIFEST_TMP   = $(MANIFEST_DIR)/tools.json.new

.PHONY: install seed test lint manifest manifest-check run-api run-ui all ci clean

install:
	$(PYTHON) -m pip install -e ".[dev]"

seed:
	$(PYTHON) scripts/seed_database.py

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	$(PYTHON) -m ruff check app/ tests/ scripts/ ui/ --ignore E501

manifest:
	@echo "Generating tool manifest from registry..."
	@mkdir -p $(MANIFEST_DIR)
	$(PYTHON) scripts/generate_manifest.py --output $(MANIFEST_FILE)
	@echo "OK — manifest written to $(MANIFEST_FILE)"

manifest-check:
	@echo "Checking manifest for drift..."
	$(PYTHON) scripts/generate_manifest.py --check --output $(MANIFEST_FILE)
	@echo "PASS — manifest matches registry"

run-api:
	uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

run-ui:
	streamlit run ui/streamlit_app.py

all: install seed test manifest-check
	@echo "All checks passed."

ci: lint test manifest-check
	@echo "CI checks passed."

clean:
	@rm -f $(MANIFEST_TMP)
	@if exist data\demo.db del /f data\demo.db 2>nul || true
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
