#!/bin/bash
# R OS Installer for Raspberry Pi
# https://github.com/raym33/r

set -e

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║     ██████╗        ██████╗██╗     ██╗                        ║"
echo "║     ██╔══██╗      ██╔════╝██║     ██║                        ║"
echo "║     ██████╔╝█████╗██║     ██║     ██║                        ║"
echo "║     ██╔══██╗╚════╝██║     ██║     ██║                        ║"
echo "║     ██║  ██║      ╚██████╗███████╗██║                        ║"
echo "║     ╚═╝  ╚═╝       ╚═════╝╚══════╝╚═╝                        ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""
echo "R OS Installer for Raspberry Pi"
echo "================================"
echo ""

# Check if running on Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "Warning: This doesn't appear to be a Raspberry Pi"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Detect Pi model
PI_MODEL=$(cat /proc/cpuinfo | grep "Model" | cut -d: -f2 | xargs)
PI_RAM=$(free -m | awk '/^Mem:/{print $2}')
echo "Detected: $PI_MODEL"
echo "RAM: ${PI_RAM}MB"
echo ""

# Update system
echo "[1/8] Updating system..."
sudo apt-get update
sudo apt-get upgrade -y

# Install dependencies
echo "[2/8] Installing dependencies..."
sudo apt-get install -y \
    python3 python3-pip python3-venv \
    git curl wget \
    portaudio19-dev python3-pyaudio \
    espeak-ng \
    libopenblas-dev \
    ffmpeg

# Install Ollama
echo "[3/8] Installing Ollama..."
if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.ai/install.sh | sh
fi

# Pull appropriate model based on RAM
echo "[4/8] Pulling LLM model..."
if [ "$PI_RAM" -ge 7000 ]; then
    MODEL="qwen2.5:1.5b"
else
    MODEL="qwen2.5:0.5b"
fi
echo "Selected model: $MODEL"
ollama pull $MODEL

# Create virtual environment
echo "[5/8] Setting up Python environment..."
python3 -m venv ~/.r-cli-venv
source ~/.r-cli-venv/bin/activate

# Install R CLI
echo "[6/8] Installing R CLI..."
pip install --upgrade pip
pip install r-cli-ai[all]

# Create config
echo "[7/8] Creating configuration..."
mkdir -p ~/.r-cli

cat > ~/.r-cli/config.yaml << EOF
# R OS Configuration for Raspberry Pi
llm:
  backend: ollama
  model: $MODEL
  base_url: http://localhost:11434/v1
  temperature: 0.7
  max_tokens: 2048
  request_timeout: 120.0

ui:
  theme: minimal
  show_thinking: false
  show_tool_calls: true

voice:
  enabled: true
  wake_word:
    type: simple
    phrase: "hey r"
  stt:
    type: whisper-cpp
    model: base.en
  tts:
    type: espeak
    voice: en
    speed: 150

gpio:
  enabled: true
  default_pins:
    led: 17
    button: 27
    buzzer: 22
    servo: 18

skills:
  mode: blacklist
  disabled: []
  require_confirmation:
    - power
EOF

# Create systemd service
echo "[8/8] Setting up systemd service..."
sudo tee /etc/systemd/system/r-os.service > /dev/null << EOF
[Unit]
Description=R OS - Local AI Assistant
After=network.target ollama.service

[Service]
Type=simple
User=$USER
Environment="PATH=$HOME/.r-cli-venv/bin:/usr/local/bin:/usr/bin"
ExecStart=$HOME/.r-cli-venv/bin/r serve --host 0.0.0.0 --port 8765
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable r-os
sudo systemctl enable ollama

# Add user to gpio group
sudo usermod -aG gpio $USER

# Create alias
echo "" >> ~/.bashrc
echo "# R CLI" >> ~/.bashrc
echo "alias r='$HOME/.r-cli-venv/bin/r'" >> ~/.bashrc
echo "source $HOME/.r-cli-venv/bin/activate" >> ~/.bashrc

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  R OS Installation Complete!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "  Model: $MODEL"
echo "  Config: ~/.r-cli/config.yaml"
echo "  Service: r-os.service"
echo ""
echo "  Next steps:"
echo "  1. Reboot: sudo reboot"
echo "  2. After reboot, R OS will start automatically"
echo "  3. Access via: http://$(hostname -I | cut -d' ' -f1):8765"
echo "  4. Or use terminal: r chat 'Hello!'"
echo ""
echo "  To start voice assistant:"
echo "    r voice"
echo ""
echo "  Documentation: https://github.com/raym33/r"
echo ""
