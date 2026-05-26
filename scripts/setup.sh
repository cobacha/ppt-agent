#!/bin/bash
set -e

echo ""
echo "============================================"
echo "  PPT Agent - Interactive Setup Wizard"
echo "============================================"
echo ""

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# --- Step 1: Backend Python environment ---
echo "[1/3] Setting up backend Python environment..."
cd "$PROJECT_DIR/backend"

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "  Created virtual environment: backend/venv"
else
    echo "  Virtual environment already exists, skipping creation."
fi

source venv/bin/activate
pip install -q -r requirements.txt
echo "  Dependencies installed."
echo ""

# --- Step 2: LLM Provider configuration ---
echo "[2/3] Configure LLM Provider"
echo ""
echo "  Choose your LLM provider:"
echo "    1) Anthropic Claude (recommended)"
echo "    2) OpenAI / GPT-4o"
echo "    3) OpenAI-compatible (DeepSeek, Ollama, vLLM, etc.)"
echo ""
read -p "  Enter choice [1/2/3] (default: 1): " provider_choice
provider_choice="${provider_choice:-1}"

ENV_FILE="$PROJECT_DIR/backend/.env"

case "$provider_choice" in
    1)
        echo ""
        echo "  -- Anthropic Claude --"
        read -s -p "  API Key (sk-ant-...): " api_key
        echo ""
        read -p "  Model ID (default: claude-sonnet-4-6): " model_id
        model_id="${model_id:-claude-sonnet-4-6}"
        read -p "  Base URL (leave empty for default api.anthropic.com): " base_url

        cat > "$ENV_FILE" <<EOF
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=${api_key}
MODEL_ID=${model_id}
EOF
        if [ -n "$base_url" ]; then
            echo "ANTHROPIC_BASE_URL=${base_url}" >> "$ENV_FILE"
        fi
        echo "CORS_ORIGINS=http://localhost:3000,http://localhost:8877" >> "$ENV_FILE"
        ;;
    2)
        echo ""
        echo "  -- OpenAI / GPT-4o --"
        read -s -p "  API Key (sk-...): " api_key
        echo ""
        read -p "  Model (default: gpt-4o): " model_id
        model_id="${model_id:-gpt-4o}"

        cat > "$ENV_FILE" <<EOF
LLM_PROVIDER=openai
OPENAI_API_KEY=${api_key}
OPENAI_MODEL=${model_id}
OPENAI_BASE_URL=https://api.openai.com/v1
CORS_ORIGINS=http://localhost:3000,http://localhost:8877
EOF
        ;;
    3)
        echo ""
        echo "  -- OpenAI-compatible provider --"
        read -s -p "  API Key: " api_key
        echo ""
        read -p "  Base URL (e.g., http://localhost:11434/v1): " base_url
        if [ -z "$base_url" ]; then
            echo "  Error: Base URL is required for OpenAI-compatible providers."
            exit 1
        fi
        read -p "  Model name (e.g., deepseek-chat, llama3): " model_id
        if [ -z "$model_id" ]; then
            echo "  Error: Model name is required."
            exit 1
        fi

        cat > "$ENV_FILE" <<EOF
LLM_PROVIDER=openai
OPENAI_API_KEY=${api_key}
OPENAI_BASE_URL=${base_url}
OPENAI_MODEL=${model_id}
CORS_ORIGINS=http://localhost:3000,http://localhost:8877
EOF
        ;;
    *)
        echo "  Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "  Wrote backend/.env"

# --- Step 3: Frontend setup ---
echo ""
echo "[3/3] Setting up frontend..."
cd "$PROJECT_DIR/frontend"

npm install --silent 2>/dev/null || npm install
echo "  Dependencies installed."

if [ ! -f ".env.local" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env.local
    else
        cat > .env.local <<EOF
NEXT_PUBLIC_API_URL=http://localhost:8001
PORT=8877
EOF
    fi
    echo "  Created frontend/.env.local"
else
    echo "  frontend/.env.local already exists, skipping."
fi

# --- Done ---
echo ""
echo "============================================"
echo "  Setup complete!"
echo "============================================"
echo ""
echo "  Next steps:"
echo "    cd backend && source venv/bin/activate && uvicorn main:app --reload --port 8001"
echo "    cd frontend && npm run dev"
echo ""
echo "  Or use: make dev"
echo ""
