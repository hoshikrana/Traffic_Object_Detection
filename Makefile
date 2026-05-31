.PHONY: setup db-up migrate backend inference frontend up down test lint clean

MODEL ?= artifacts/best_openvino_model/
VIDEO ?= sample.mp4

setup:
	cp -n .env.example .env || true
	pip install -r backend/requirements.txt
	cd frontend && npm install

db-up:
	docker compose up -d postgres redis
	@echo "Waiting for postgres..." && timeout /t 5 /nobreak >nul 2>&1 || sleep 5

migrate:
	cd backend && alembic upgrade head

backend:
	cd backend && uvicorn main:app --reload --port 8000

inference:
	python -m inference.engine --model $(MODEL) --video $(VIDEO) \
	  --output outputs/annotated.mp4 --job-id local-test --api-url http://localhost:8000

frontend:
	cd frontend && npm run dev

down:
	docker compose down

test:
	cd backend && pytest tests/ -v --cov=. --cov-report=term-missing

lint:
	ruff check . && ruff format --check .

clean:
	del /s /q __pycache__ 2>nul || true
	rd /s /q backend\.pytest_cache 2>nul || true
	rd /s /q frontend\dist 2>nul || true
