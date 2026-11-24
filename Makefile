.PHONY: install test run docker up ui-install ui ui-build dev
install:
	pip install -r requirements-dev.txt
test:
	pytest -q

# --- API only (http://localhost:8000, docs at /docs) ---
run:
	TRIAGE_BACKEND=local TRIAGE_MIN_GROUNDING_SCORE=0.1 uvicorn app.main:app --reload --port 8000

# --- UI ---
ui-install:
	cd frontend && npm install
ui:                      # Vite dev server on :5173, proxies /v1 to :8000
	cd frontend && npm run dev
ui-build:                # compile the UI into app/static so `make run` serves it too
	cd frontend && npm run build && rm -rf ../app/static && cp -r dist ../app/static
dev:                     # API + UI together (hot reload on both)
	$(MAKE) -j2 run ui

# --- Docker (UI + API in one image) ---
docker:
	docker build -t support-triage-copilot .
up:
	docker compose up --build
