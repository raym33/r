# R OS - Terminal UI for Edge Devices (Experimental)

R OS is a terminal-based interface (TUI) for R CLI, designed for Raspberry Pi and edge devices. It provides an Android-like visual experience in the terminal using [Textual](https://textual.textualize.io/).

**Note:** This is NOT an operating system. It's a TUI that runs on top of your existing OS and provides a visual interface to R CLI's skills.

## Features

### Hardware Skills (5 new skills)

| Skill | Description | Platforms |
|-------|-------------|-----------|
| `gpio` | Raspberry Pi GPIO control, PWM, servo | Pi |
| `bluetooth` | Device scanning, pairing, connection | Pi, Android |
| `wifi` | Network scanning, connection, hotspot | Pi, Android |
| `power` | Shutdown, reboot, brightness, volume | Pi, Android |
| `android` | SMS, calls, camera, notifications | Android |

### Voice Interface

Complete hands-free assistant with:
- **Wake Word Detection**: Porcupine, OpenWakeWord, or simple keyword
- **Speech-to-Text**: Whisper.cpp (optimized for Pi), faster-whisper
- **Text-to-Speech**: Piper TTS, espeak

### Android-style TUI

Terminal-based interface that mimics Android's look:

```
┌─────────────────────────────────────────────────────────┐
│ ▁▂▄█ 📶 R OS          12:45          🔋 85%             │
├─────────────────────────────────────────────────────────┤
│   💬 Messages   📞 Phone     📧 Email     🌐 Browser   │
│   📷 Camera     🖼️ Gallery   🎵 Music     🎬 Video     │
│   📁 Files      📅 Calendar  ⏰ Clock     🔢 Calculator │
│   🤖 R Chat     🎤 Voice     🌍 Translate 📝 Notes     │
│   ⚙️ Settings   📶 WiFi      🔵 Bluetooth 🔋 Battery   │
│   💡 GPIO       💻 Terminal  🔌 Network   📊 System    │
├─────────────────────────────────────────────────────────┤
│           ◀ Back      ● Home      ▢ Recent             │
└─────────────────────────────────────────────────────────┘
```

## Installation

### Standard Installation

```bash
pip install r-cli-ai[simulator]
```

### Raspberry Pi Installation

```bash
# One-command installer
curl -sSL https://raw.githubusercontent.com/raym33/r/main/r_os/rpi/install.sh | bash

# Or manual installation
pip install r-cli-ai[all-rpi]
```

### Android (via Termux)

```bash
pkg install python
pip install r-cli-ai[simulator]
```

## Usage

### Launch

```bash
r-os                    # Default Material theme
r-os --theme amoled     # AMOLED black theme
r-os --theme light      # Light theme
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `t` | Cycle themes |
| `n` | Toggle notifications |
| `h` | Go home |
| `Esc` | Go back |
| `q` | Quit |

### Voice Assistant

```bash
# Start voice interface (requires audio hardware)
r voice start

# Or in Python
from r_cli.core.voice_interface import create_voice_interface

voice = create_voice_interface(
    config={
        "wake_word": "hey_r",
        "stt": "whisper",
        "tts": "piper",
    }
)
voice.run()
```

### GPIO Control (Raspberry Pi)

```bash
# Setup pin as output
r gpio setup 17 out

# Write HIGH
r gpio write 17 1

# PWM control
r gpio pwm 18 50  # 50% duty cycle

# Servo control
r gpio servo 12 90  # 90 degrees
```

### Bluetooth

```bash
# Scan for devices
r bluetooth scan

# Pair device
r bluetooth pair AA:BB:CC:DD:EE:FF

# Connect
r bluetooth connect AA:BB:CC:DD:EE:FF
```

### WiFi

```bash
# Scan networks
r wifi scan

# Connect to network
r wifi connect "MyNetwork" "password123"

# Create hotspot
r wifi hotspot "R-OS-AP" "password123"
```

### Power Management

```bash
# Battery status
r power battery

# Set brightness (0-100)
r power brightness 70

# Set volume (0-100)
r power volume 50

# Shutdown/Reboot
r power shutdown
r power reboot
```

### Android Control (via ADB)

```bash
# Send SMS
r android sms "+1234567890" "Hello from R OS!"

# Take photo
r android photo ~/photo.jpg

# Get location
r android location

# Show notification
r android notify "Title" "Message"
```

## Architecture

```
r_os/
├── simulator/          # Android-like TUI
│   ├── app.py         # Main Textual application
│   └── __main__.py    # CLI entry point
├── rpi/               # Raspberry Pi configs
│   ├── install.sh     # One-command installer
│   ├── r-os.service   # Systemd service
│   └── config.yaml    # Pi-specific settings
└── android/           # Android configs
    └── config.yaml    # Android-specific settings
```

## Hardware Requirements

### Raspberry Pi

- Raspberry Pi 3B+ or newer (4GB+ RAM recommended)
- MicroSD card (32GB+)
- USB microphone (for voice)
- Speaker/headphones (for TTS)

### Android

- Android 7.0+ with Termux
- ADB debugging enabled (for full features)
- Microphone access (for voice)

## Edge LLM Options

For fully offline operation, use lightweight models:

| Model | Size | Platform | Performance |
|-------|------|----------|-------------|
| Qwen2.5-0.5B | 500MB | Pi 4/5 | Fast |
| Qwen2.5-1.5B | 1.5GB | Pi 5 8GB | Good |
| Gemma-2B | 2GB | Android | Good |
| Phi-3-mini | 2.3GB | Pi 5/Android | Best |

### Setup with Ollama

```bash
# On Raspberry Pi
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:0.5b

# Configure R CLI
export R_MODEL="qwen2.5:0.5b"
export OPENAI_API_BASE="http://localhost:11434/v1"
```

## Systemd Service (Raspberry Pi)

R OS can run as a system service for always-on operation:

```bash
# Enable and start
sudo systemctl enable r-os
sudo systemctl start r-os

# Check status
sudo systemctl status r-os

# View logs
journalctl -u r-os -f
```

## Themes

### Material (Default)
- Background: #121212
- Primary: #bb86fc
- Secondary: #03dac6

### AMOLED
- Background: #000000
- Primary: #00ff88
- Secondary: #00d4ff

### Light
- Background: #f5f5f5
- Primary: #6200ee
- Secondary: #03dac6

## Contributing

Contributions welcome! Areas of interest:

- Additional hardware drivers
- New TUI widgets
- Voice model integrations
- Platform-specific optimizations

## License

MIT License - See [LICENSE](../LICENSE)
