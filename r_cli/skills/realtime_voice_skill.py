"""
Realtime Voice Skill for R CLI.

Real-time voice conversation using:
- Supertonic TTS (167x faster than realtime, local)
- Whisper STT (local speech recognition)
- sounddevice for audio I/O

100% local and offline voice interaction.
"""

import json
import logging
import os
import tempfile
import threading
import time
import wave
from datetime import datetime
from pathlib import Path
from queue import Queue
from typing import Optional

import numpy as np

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool

logger = logging.getLogger(__name__)

# Audio settings
SAMPLE_RATE = 24000  # Supertonic uses 24kHz
WHISPER_SAMPLE_RATE = 16000  # Whisper expects 16kHz
CHANNELS = 1
DTYPE = np.float32


class RealtimeVoiceSkill(Skill):
    """
    Real-time voice interaction skill.

    Features:
    - Voice-to-text with Whisper (local)
    - Text-to-voice with Supertonic (167x realtime)
    - Real-time recording and playback
    - Multiple voice styles (M1-M5, F1-F5)
    """

    name = "realtime_voice"
    description = "Real-time voice: Whisper STT + Supertonic TTS (local, fast)"

    # Supertonic voice styles
    VOICE_STYLES = {
        "M1": "Male voice 1",
        "M2": "Male voice 2",
        "M3": "Male voice 3",
        "M4": "Male voice 4",
        "M5": "Male voice 5",
        "F1": "Female voice 1",
        "F2": "Female voice 2",
        "F3": "Female voice 3 (default - natural, clear)",
        "F4": "Female voice 4",
        "F5": "Female voice 5",
    }

    def __init__(self, config=None):
        super().__init__(config)
        self._tts = None
        self._tts_style = None
        self._whisper_model = None
        self._is_recording = False
        self._audio_queue = Queue()

        # Check dependencies
        self._supertonic_available = self._check_supertonic()
        self._whisper_available = self._check_whisper()
        self._sounddevice_available = self._check_sounddevice()

    def _check_supertonic(self) -> bool:
        """Check if Supertonic TTS is available."""
        try:
            from supertonic import TTS

            return True
        except ImportError:
            return False

    def _check_whisper(self) -> bool:
        """Check if Whisper is available."""
        try:
            import whisper

            return True
        except ImportError:
            try:
                from faster_whisper import WhisperModel

                return True
            except ImportError:
                return False

    def _check_sounddevice(self) -> bool:
        """Check if sounddevice is available."""
        try:
            import sounddevice

            return True
        except ImportError:
            return False

    def _get_tts(self, voice: str = "F3"):
        """Get or initialize TTS engine."""
        if not self._supertonic_available:
            raise RuntimeError("Supertonic not installed. Run: pip install supertonic")

        from supertonic import TTS

        if self._tts is None:
            self._tts = TTS(auto_download=True)

        if self._tts_style is None or voice != getattr(self, "_current_voice", None):
            self._tts_style = self._tts.get_voice_style(voice)
            self._current_voice = voice

        return self._tts, self._tts_style

    def _get_whisper(self, model_size: str = "base"):
        """Get or initialize Whisper model."""
        if not self._whisper_available:
            raise RuntimeError("Whisper not installed. Run: pip install openai-whisper")

        if self._whisper_model is None:
            try:
                # Try faster-whisper first
                from faster_whisper import WhisperModel

                self._whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
                self._whisper_type = "faster"
            except ImportError:
                # Fall back to openai-whisper
                import whisper

                self._whisper_model = whisper.load_model(model_size)
                self._whisper_type = "openai"

        return self._whisper_model

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="voice_speak",
                description="Convert text to speech and play it (Supertonic TTS)",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to speak",
                        },
                        "voice": {
                            "type": "string",
                            "description": "Voice style: M1-M5 (male), F1-F5 (female). Default: F3",
                        },
                        "speed": {
                            "type": "number",
                            "description": "Speech speed (0.5-2.0, default: 1.05)",
                        },
                        "save_path": {
                            "type": "string",
                            "description": "Optional: Save audio to file instead of playing",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.voice_speak,
            ),
            Tool(
                name="voice_listen",
                description="Record audio from microphone and transcribe to text (Whisper STT)",
                parameters={
                    "type": "object",
                    "properties": {
                        "duration": {
                            "type": "number",
                            "description": "Recording duration in seconds (default: 5)",
                        },
                        "language": {
                            "type": "string",
                            "description": "Language code (en, es, de, etc.). Default: en",
                        },
                        "model": {
                            "type": "string",
                            "description": "Whisper model: tiny, base, small, medium, large",
                        },
                    },
                },
                handler=self.voice_listen,
            ),
            Tool(
                name="voice_transcribe",
                description="Transcribe an audio file to text",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to audio file (wav, mp3, etc.)",
                        },
                        "language": {
                            "type": "string",
                            "description": "Language code (en, es, de, etc.)",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.voice_transcribe,
            ),
            Tool(
                name="voice_conversation",
                description="Start a voice conversation loop (listen -> process -> speak)",
                parameters={
                    "type": "object",
                    "properties": {
                        "voice": {
                            "type": "string",
                            "description": "Voice style for responses",
                        },
                        "language": {
                            "type": "string",
                            "description": "Language for transcription",
                        },
                    },
                },
                handler=self.voice_conversation,
            ),
            Tool(
                name="voice_status",
                description="Check voice system status and available features",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.voice_status,
            ),
            Tool(
                name="voice_list_styles",
                description="List available voice styles",
                parameters={
                    "type": "object",
                    "properties": {},
                },
                handler=self.voice_list_styles,
            ),
        ]

    def voice_speak(
        self,
        text: str,
        voice: str = "F3",
        speed: float = 1.05,  # Supertonic default for natural voice
        save_path: str | None = None,
    ) -> str:
        """Convert text to speech using Supertonic TTS."""
        if not self._supertonic_available:
            return "Error: Supertonic not installed. Run: pip install supertonic"

        try:
            import soundfile as sf

            # Validate voice
            if voice not in self.VOICE_STYLES:
                voice = "M1"

            # Clamp speed
            speed = max(0.5, min(2.0, speed))

            # Get TTS engine
            tts, style = self._get_tts(voice)

            # Synthesize (using default total_steps=5 for natural voice quality)
            start_time = time.time()
            audio, duration = tts.synthesize(text, style, speed=speed)
            synth_time = time.time() - start_time

            # Squeeze audio from (1, N) to (N,)
            audio = audio.squeeze()
            actual_duration = len(audio) / SAMPLE_RATE

            if save_path:
                # Save to file
                path = Path(save_path).expanduser()
                path.parent.mkdir(parents=True, exist_ok=True)
                sf.write(str(path), audio, SAMPLE_RATE)
                return json.dumps(
                    {
                        "success": True,
                        "saved_to": str(path),
                        "duration": f"{actual_duration:.2f}s",
                        "synthesis_time": f"{synth_time:.3f}s",
                        "realtime_factor": f"{synth_time / actual_duration:.3f}x",
                        "voice": voice,
                    }
                )
            # Play audio
            elif not self._sounddevice_available:
                # Save to temp and use system player
                temp_path = Path(tempfile.gettempdir()) / "r_cli_voice.wav"
                sf.write(str(temp_path), audio, SAMPLE_RATE)
                os.system(
                    f"afplay '{temp_path}' 2>/dev/null || aplay '{temp_path}' 2>/dev/null || play '{temp_path}' 2>/dev/null &"
                )
                return json.dumps(
                    {
                        "success": True,
                        "played": True,
                        "duration": f"{actual_duration:.2f}s",
                        "synthesis_time": f"{synth_time:.3f}s",
                        "voice": voice,
                    }
                )
            else:
                import sounddevice as sd

                sd.play(audio, SAMPLE_RATE)
                sd.wait()
                return json.dumps(
                    {
                        "success": True,
                        "played": True,
                        "duration": f"{actual_duration:.2f}s",
                        "synthesis_time": f"{synth_time:.3f}s",
                        "realtime_factor": f"{synth_time / actual_duration:.3f}x",
                        "voice": voice,
                    }
                )

        except Exception as e:
            logger.error(f"TTS error: {e}")
            return json.dumps({"error": str(e)})

    def voice_listen(
        self,
        duration: float = 5.0,
        language: str = "en",
        model: str = "base",
    ) -> str:
        """Record audio and transcribe with Whisper."""
        if not self._whisper_available:
            return "Error: Whisper not installed. Run: pip install openai-whisper"

        if not self._sounddevice_available:
            return "Error: sounddevice not installed. Run: pip install sounddevice"

        try:
            import sounddevice as sd

            # Record audio
            print(f"🎤 Recording for {duration}s... (speak now)")
            audio = sd.rec(
                int(duration * WHISPER_SAMPLE_RATE),
                samplerate=WHISPER_SAMPLE_RATE,
                channels=1,
                dtype=np.float32,
            )
            sd.wait()
            print("✅ Recording complete")

            # Squeeze to 1D
            audio = audio.squeeze()

            # Transcribe
            return self._transcribe_audio(audio, language, model)

        except Exception as e:
            logger.error(f"Recording error: {e}")
            return json.dumps({"error": str(e)})

    def voice_transcribe(
        self,
        file_path: str,
        language: str = "en",
        model: str = "base",
    ) -> str:
        """Transcribe an audio file."""
        if not self._whisper_available:
            return "Error: Whisper not installed. Run: pip install openai-whisper"

        try:
            import librosa

            path = Path(file_path).expanduser()
            if not path.exists():
                return json.dumps({"error": f"File not found: {file_path}"})

            # Load audio (resample to 16kHz for Whisper)
            audio, sr = librosa.load(str(path), sr=WHISPER_SAMPLE_RATE, mono=True)

            return self._transcribe_audio(audio, language, model)

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return json.dumps({"error": str(e)})

    def _transcribe_audio(
        self,
        audio: np.ndarray,
        language: str = "en",
        model_size: str = "base",
    ) -> str:
        """Internal: transcribe audio array."""
        try:
            whisper_model = self._get_whisper(model_size)

            start_time = time.time()

            if self._whisper_type == "faster":
                # faster-whisper
                segments, info = whisper_model.transcribe(
                    audio,
                    language=language,
                    beam_size=5,
                )
                text = " ".join([seg.text for seg in segments])
                detected_lang = info.language
            else:
                # openai-whisper
                result = whisper_model.transcribe(
                    audio,
                    language=language,
                    fp16=False,
                )
                text = result["text"]
                detected_lang = result.get("language", language)

            transcribe_time = time.time() - start_time
            audio_duration = len(audio) / WHISPER_SAMPLE_RATE

            return json.dumps(
                {
                    "success": True,
                    "text": text.strip(),
                    "language": detected_lang,
                    "audio_duration": f"{audio_duration:.2f}s",
                    "transcribe_time": f"{transcribe_time:.2f}s",
                    "realtime_factor": f"{transcribe_time / audio_duration:.2f}x",
                }
            )

        except Exception as e:
            return json.dumps({"error": str(e)})

    def voice_conversation(
        self,
        voice: str = "M1",
        language: str = "en",
    ) -> str:
        """
        Start interactive voice conversation mode.

        This is a simplified version - for full conversation,
        the agent would need to process the transcribed text
        and generate responses.
        """
        return json.dumps(
            {
                "mode": "conversation",
                "instructions": [
                    "Voice conversation mode ready.",
                    "Use voice_listen to capture user speech",
                    "Process the transcribed text with the LLM",
                    "Use voice_speak to respond",
                ],
                "voice": voice,
                "language": language,
                "example_flow": [
                    "1. result = voice_listen(duration=5)",
                    "2. user_text = result['text']",
                    "3. response = llm.generate(user_text)",
                    "4. voice_speak(response)",
                ],
            }
        )

    def voice_status(self) -> str:
        """Check voice system status."""
        status = {
            "supertonic_tts": {
                "available": self._supertonic_available,
                "description": "167x realtime TTS, 10 voice styles",
                "install": "pip install supertonic",
            },
            "whisper_stt": {
                "available": self._whisper_available,
                "description": "Local speech recognition",
                "install": "pip install openai-whisper",
            },
            "sounddevice": {
                "available": self._sounddevice_available,
                "description": "Audio recording/playback",
                "install": "pip install sounddevice",
            },
            "ready": self._supertonic_available and self._whisper_available,
        }

        if status["ready"]:
            status["message"] = "Voice system ready for real-time conversation"
        else:
            missing = []
            if not self._supertonic_available:
                missing.append("supertonic")
            if not self._whisper_available:
                missing.append("openai-whisper")
            if not self._sounddevice_available:
                missing.append("sounddevice")
            status["message"] = f"Missing: {', '.join(missing)}"

        return json.dumps(status, indent=2)

    def voice_list_styles(self) -> str:
        """List available voice styles."""
        return json.dumps(
            {
                "voices": self.VOICE_STYLES,
                "default": "M1",
                "categories": {
                    "male": ["M1", "M2", "M3", "M4", "M5"],
                    "female": ["F1", "F2", "F3", "F4", "F5"],
                },
            },
            indent=2,
        )

    def execute(self, **kwargs) -> str:
        """Direct execution - check status by default."""
        if "text" in kwargs:
            return self.voice_speak(kwargs["text"], kwargs.get("voice", "M1"))
        return self.voice_status()
