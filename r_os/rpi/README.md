# R OS for Raspberry Pi

Build and deploy R CLI as a complete AI operating system for Raspberry Pi.

## Supported Hardware

| Model | RAM | LLM Support | Notes |
|-------|-----|-------------|-------|
| Pi 4 | 2GB | Qwen2.5-0.5B | Basic, limited context |
| Pi 4 | 4GB | Qwen2.5-0.5B | Recommended minimum |
| Pi 4 | 8GB | Qwen2.5-1.5B | Good performance |
| Pi 5 | 8GB | Qwen2.5-1.5B | Best performance |

## Quick Start

### 1. Flash Base Image

Use Raspberry Pi Imager to flash Raspberry Pi OS Lite (64-bit).

### 2. Install R OS

```bash
# SSH into your Pi
ssh pi@raspberrypi.local

# Run installer
curl -fsSL https://raw.githubusercontent.com/raym33/r/main/r_os/rpi/install.sh | bash
```

### 3. Configure

```bash
# Edit config
nano ~/.r-cli/config.yaml

# Set up voice (optional)
r-os setup-voice
```

## Building Custom Image

### Prerequisites

- Docker
- QEMU for ARM emulation
- 16GB+ SD card

### Build

```bash
# Clone repo
git clone https://github.com/raym33/r.git
cd r/r_os/rpi

# Build image
./build-image.sh

# Flash to SD card
./flash-image.sh /dev/sdX
```

## Features

### Voice Assistant

- Wake word: "Hey R"
- Local Whisper transcription
- Piper TTS
- Hands-free operation

### GPIO Control

```bash
r chat "Turn on the LED on pin 17"
r chat "Read the button on pin 27"
r chat "Set servo to 90 degrees"
```

### System Control

```bash
r chat "What's the CPU temperature?"
r chat "Show memory usage"
r chat "Connect to WiFi network 'MyNetwork'"
```

## Configuration

### config.yaml

```yaml
llm:
  backend: ollama
  model: qwen2.5:0.5b
  base_url: http://localhost:11434/v1

voice:
  enabled: true
  wake_word: "hey r"
  stt: whisper-cpp
  tts: piper

gpio:
  default_pins:
    led: 17
    button: 27
    servo: 18
```

### Systemd Service

R OS runs as a systemd service:

```bash
sudo systemctl status r-os
sudo systemctl restart r-os
sudo journalctl -u r-os -f
```

## Peripherals

### Supported Hardware

- LEDs, buttons, relays
- Servo motors, DC motors
- I2C sensors (temperature, humidity, etc.)
- SPI displays
- Camera module
- USB microphone
- USB/Bluetooth speakers

### Example: LED Control

```python
# Via chat
r chat "Blink the LED 5 times"

# Via API
curl -X POST http://localhost:8765/v1/skills/call \
  -H "Content-Type: application/json" \
  -d '{"skill": "gpio", "tool": "gpio_blink", "arguments": {"pin": 17, "times": 5}}'
```

## Troubleshooting

### No audio output

```bash
# Check audio devices
aplay -l

# Test audio
speaker-test -c2 -t wav
```

### GPIO permission error

```bash
# Add user to gpio group
sudo usermod -aG gpio $USER
```

### Out of memory

```bash
# Reduce model size
ollama rm qwen2.5:1.5b
ollama pull qwen2.5:0.5b
```

## License

MIT License
