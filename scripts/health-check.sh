#!/bin/bash
# Quick health check for both frontend and backend services
# Run after code changes to verify services are responsive

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

BACKEND_URL="${BACKEND_URL:-http://localhost:8001}"
FRONTEND_URL="${FRONTEND_URL:-http://localhost:8877}"

check() {
    local name=$1
    local url=$2
    local status
    status=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 "$url")
    if [ "$status" = "200" ]; then
        echo -e "${GREEN}✓${NC} $name ($url) — OK"
        return 0
    else
        echo -e "${RED}✗${NC} $name ($url) — FAILED (status: $status)"
        return 1
    fi
}

echo "Health check:"
be_ok=true
fe_ok=true

check "Backend  /api/styles" "$BACKEND_URL/api/styles" || be_ok=false
check "Backend  /api/layouts" "$BACKEND_URL/api/layouts" || be_ok=false
check "Frontend /" "$FRONTEND_URL" || fe_ok=false

if [ "$be_ok" = false ]; then
    echo -e "\n${RED}Backend is down. Restarting...${NC}"
    lsof -ti:8001 | xargs kill -9 2>/dev/null
    sleep 1
    cd "$(dirname "$0")/../backend"
    /opt/homebrew/bin/uvicorn main:app --reload --port 8001 > /tmp/ppt-backend.log 2>&1 &
    sleep 2
    check "Backend  /api/styles" "$BACKEND_URL/api/styles"
fi

if [ "$fe_ok" = false ]; then
    echo -e "\n${RED}Frontend is down. Restarting...${NC}"
    lsof -ti:8877 | xargs kill -9 2>/dev/null
    sleep 1
    cd "$(dirname "$0")/../frontend"
    npm run dev > /tmp/ppt-frontend.log 2>&1 &
    sleep 3
    check "Frontend /" "$FRONTEND_URL"
fi

echo ""
