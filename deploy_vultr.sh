#!/bin/bash
# =============================================================================
# FrenzAI Cloud Deployment — Vultr GH200 (ARM64) / Any NVIDIA GPU Server
# =============================================================================
# Usage: bash deploy_vultr.sh
# After: Access http://<server-ip>:8111
# =============================================================================

set -e

echo "============================================"
echo "  FrenzAI Cloud Deployment"
echo "============================================"

export DEBIAN_FRONTEND=noninteractive
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# ─── 1. System Dependencies ────────────────────────────────────────────────
echo "[1/8] Installing system dependencies..."
apt-get update -qq
apt-get install -y -qq python3.12 python3.12-venv python3.12-dev python3-pip \
    nodejs npm ffmpeg git curl sox libsox-dev espeak-ng \
    build-essential pkg-config libsndfile1 2>/dev/null || {
    # If python3.12 not available, add deadsnakes PPA
    apt-get install -y -qq software-properties-common
    add-apt-repository -y ppa:deadsnakes/ppa
    apt-get update -qq
    apt-get install -y -qq python3.12 python3.12-venv python3.12-dev
}

# Check Node.js version (need 18+)
NODE_VER=$(node -v 2>/dev/null | sed 's/v//' | cut -d. -f1)
if [ -z "$NODE_VER" ] || [ "$NODE_VER" -lt 18 ]; then
    echo "  Installing Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
    apt-get install -y -qq nodejs
fi

echo "  Python: $(python3.12 --version)"
echo "  Node: $(node -v)"
echo "  ffmpeg: $(ffmpeg -version 2>&1 | head -1)"

# ─── 2. Python Virtual Environment ─────────────────────────────────────────
echo "[2/8] Setting up Python virtual environment..."
if [ ! -d "venv" ]; then
    python3.12 -m venv venv
fi
source venv/bin/activate

pip install --upgrade pip wheel setuptools -q

# ─── 3. PyTorch with CUDA ──────────────────────────────────────────────────
echo "[3/8] Installing PyTorch with CUDA support..."
ARCH=$(uname -m)
echo "  Architecture: $ARCH"

if [ "$ARCH" = "aarch64" ]; then
    # ARM64 (GH200) — use NVIDIA's PyTorch for Jetson/Grace
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124 -q 2>/dev/null || \
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121 -q 2>/dev/null || \
    pip install torch torchaudio -q
else
    # x86_64 — standard CUDA 12.1 build
    pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu121 -q
fi

python3 -c "import torch; print(f'  PyTorch {torch.__version__} CUDA={torch.cuda.is_available()} Device={torch.cuda.get_device_name(0) if torch.cuda.is_available() else \"CPU\"}')"

# ─── 4. Python Dependencies ────────────────────────────────────────────────
echo "[4/8] Installing Python dependencies..."
cd "$PROJECT_DIR/backend"
pip install -r requirements.txt -q

# Core TTS engine packages
pip install kokoro>=0.9 kokoro-onnx 2>/dev/null || true
pip install edge-tts -q
pip install espeakng-loader -q
pip install chatterbox-tts resemble-perth -q 2>/dev/null || true

# Additional engines for cloud (96GB VRAM — run them all!)
pip install --no-deps f5-tts -q 2>/dev/null || true
pip install accelerate safetensors transformers vocos torchdiffeq einops \
    x_transformers cached_path pypinyin rjieba unidecode tomli librosa \
    hydra-core omegaconf ema_pytorch bitsandbytes -q 2>/dev/null || true

pip install --no-deps qwen-tts -q 2>/dev/null || true
pip install onnxruntime -q 2>/dev/null || true

pip install --no-deps parler-tts descript-audio-codec descript-audiotools -q 2>/dev/null || true
pip install flatten-dict julius argbind tensorboard ffmpy -q 2>/dev/null || true

pip install --no-deps fish-speech -q 2>/dev/null || true
pip install bark -q 2>/dev/null || true

# Audio pipeline
pip install pyloudnorm pedalboard noisereduce -q 2>/dev/null || true

# spaCy for text processing
pip install spacy -q 2>/dev/null || true
python3 -m spacy download en_core_web_sm -q 2>/dev/null || true

cd "$PROJECT_DIR"

# ─── 5. Frontend Build ─────────────────────────────────────────────────────
echo "[5/8] Building frontend for production..."
cd "$PROJECT_DIR/frontend"
npm install --silent 2>/dev/null
npm run build

cd "$PROJECT_DIR"

# ─── 6. Create Data Directories ────────────────────────────────────────────
echo "[6/8] Setting up data directories..."
mkdir -p data/voices/samples data/voices/embeddings data/voices/import data/voices/staging
mkdir -p data/projects data/exports data/temp
mkdir -p backend/models

# ─── 7. Configure for Cloud ────────────────────────────────────────────────
echo "[7/8] Configuring for cloud access..."

# Create cloud environment file
cat > .env << 'ENVEOF'
VOICEFORGE_HOST=0.0.0.0
VOICEFORGE_PORT=8111
VOICEFORGE_DEVICE=cuda
FRENZAI_CLOUD=1
ENVEOF

# ─── 8. Create systemd Service ─────────────────────────────────────────────
echo "[8/8] Creating systemd service..."

cat > /etc/systemd/system/frenzai.service << SVCEOF
[Unit]
Description=FrenzAI TTS Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$PROJECT_DIR/backend
Environment=PATH=$PROJECT_DIR/venv/bin:/usr/local/bin:/usr/bin:/bin
Environment=VOICEFORGE_HOST=0.0.0.0
Environment=VOICEFORGE_PORT=8111
Environment=VOICEFORGE_DEVICE=cuda
Environment=FRENZAI_CLOUD=1
ExecStart=$PROJECT_DIR/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8111 --workers 1
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable frenzai

echo ""
echo "============================================"
echo "  FrenzAI Deployment Complete!"
echo "============================================"
echo ""
echo "  Start:   systemctl start frenzai"
echo "  Stop:    systemctl stop frenzai"
echo "  Logs:    journalctl -u frenzai -f"
echo "  Status:  systemctl status frenzai"
echo ""
echo "  Access:  http://$(curl -s ifconfig.me 2>/dev/null || echo '<server-ip>'):8111"
echo ""
echo "  To import voices:"
echo "  1. Upload .opus/.wav/.mp3 files to: $PROJECT_DIR/data/voices/import/"
echo "  2. Use the Clone page -> Import from Folder"
echo ""

# Start it now
systemctl start frenzai
sleep 3
echo "  Server status:"
systemctl is-active frenzai && echo "  RUNNING!" || echo "  Check logs: journalctl -u frenzai -f"
