# R OS for Android

Run R CLI as an AI assistant on Android devices.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    R OS Android App                          │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  Voice UI   │  │  Chat UI    │  │  Floating Widget    │ │
│  │  (Compose)  │  │  (Compose)  │  │  (Overlay Service)  │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
│         │                │                     │            │
│  ┌──────┴────────────────┴─────────────────────┴──────────┐ │
│  │                    R CLI Core (Python)                  │ │
│  │              via Chaquopy / Kivy-Python                 │ │
│  └──────────────────────────┬──────────────────────────────┘ │
│                             │                                │
│  ┌──────────────────────────┴──────────────────────────────┐ │
│  │              Android Bridge (Kotlin/Java)               │ │
│  │  SMS, Calls, Contacts, Camera, Sensors, Notifications  │ │
│  └─────────────────────────────────────────────────────────┘ │
│                             │                                │
│  ┌──────────────────────────┴──────────────────────────────┐ │
│  │              Edge LLM (On-Device)                       │ │
│  │  Gemma Nano / Phi-3 / Qwen2.5 via llama.cpp            │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Options for Running Python on Android

### Option 1: Chaquopy (Recommended)

Embed Python in Android app via Gradle plugin.

```gradle
plugins {
    id 'com.chaquo.python' version '14.0.2'
}

android {
    defaultConfig {
        python {
            pip {
                install "r-cli-ai"
            }
        }
    }
}
```

### Option 2: Kivy + Buildozer

Build standalone APK with Kivy framework.

```bash
# Install buildozer
pip install buildozer

# Create spec
buildozer init

# Build APK
buildozer android debug
```

### Option 3: Termux + proot

Run R CLI in Termux Linux environment.

```bash
# In Termux
pkg install python
pip install r-cli-ai
r chat "Hello from Android!"
```

## On-Device LLM

### Gemma Nano (via ML Kit)

```kotlin
// Using Google's ML Kit
val generativeModel = GenerativeModel.getGenerativeModel("gemma-nano")
val response = generativeModel.generateContent("Hello!")
```

### Llama.cpp for Android

```kotlin
// Load GGUF model
val llamaCpp = LlamaCpp()
llamaCpp.loadModel("/sdcard/models/qwen2.5-0.5b-q4.gguf")
val response = llamaCpp.complete("User: Hello!\nAssistant:")
```

## Android Bridge API

The bridge allows R CLI to control Android features:

```python
# From R CLI
from r_cli.skills.android_skill import AndroidSkill

android = AndroidSkill()

# Send SMS
android.android_sms_send("+1234567890", "Hello from R!")

# Take photo
android.android_photo(camera="back", output="/sdcard/photo.jpg")

# Get location
location = android.android_location()

# Show notification
android.android_notification("R OS", "Task completed!")
```

## Development Setup

### Prerequisites

- Android Studio Arctic Fox+
- NDK r25+
- Python 3.10+ (for development)

### Building

```bash
# Clone
git clone https://github.com/raym33/r.git
cd r/r_os/android

# Open in Android Studio
studio .

# Or build via Gradle
./gradlew assembleDebug
```

## Features

### Voice Assistant

- Always-listening mode
- Wake word: "Hey R"
- Works offline
- Low latency responses

### System Integration

- Send/read SMS
- Make calls
- Access contacts
- Camera control
- GPS location
- Sensor data
- Clipboard sync

### Widget

- Floating bubble assistant
- Quick actions
- Voice activation

## Roadmap

- [ ] Basic Chaquopy integration
- [ ] Voice interface
- [ ] Android bridge
- [ ] On-device Gemma
- [ ] Floating widget
- [ ] Launcher mode

## License

MIT License
