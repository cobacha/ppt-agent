.PHONY: dev backend frontend test lint clean docker

dev:
	@echo "Starting backend (port 8001) and frontend (port 8877)..."
	@cd backend && uvicorn main:app --reload --port 8001 &
	@cd frontend && npm run dev &
	@wait

backend:
	cd backend && uvicorn main:app --reload --port 8001

frontend:
	cd frontend && npm run dev

test:
	cd backend && python -m pytest tests/ -v

lint:
	cd backend && ruff check .
	cd frontend && npm run lint

clean:
	rm -rf backend/__pycache__ backend/**/__pycache__
	rm -rf backend/.pytest_cache
	rm -rf frontend/.next

docker:
	docker compose up --build
