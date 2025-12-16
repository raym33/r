"""
Voice Interface for R CLI / R OS.

Always-listening voice assistant with:
- Wake word detection ("Hey R")
- Speech-to-text (Whisper)
- Text-to-speech (Piper)
- Continuous conversation mode
"""

import asyncio
import json
import logging
import queue
import shutil
import subprocess
import tempfile
import threading
import wave
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Wake Word Detection
# ============================================================================


class WakeWordDetector(ABC):
    """Base class for wake word detection."""

    @abstractmethod
    def start(self, callback: Callable[[], None]) -> None:
        """Start listening for wake word."""

    @abstractmethod
    def stop(self) -> None:
        """Stop listening."""


class PorcupineWakeWord(WakeWordDetector):
    """Wake word detection using Picovoice Porcupine."""

    def __init__(
        self,
        keyword: str = "hey google",  # Use built-in, or custom .ppn
        sensitivity: float = 0.5,
        access_key: Optional[str] = None,
    ):
        self.keyword = keyword
        self.sensitivity = sensitivity
        self.access_key = access_key
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._porcupine = None
        self._audio = None

    def start(self, callback: Callable[[], None]) -> None:
        """Start wake word detection."""
        try:
            import pvporcupine
            import pyaudio

            self._porcupine = pvporcupine.create(
                access_key=self.access_key,
                keywords=[self.keyword],
                sensitivities=[self.sensitivity],
            )

            self._audio = pyaudio.PyAudio()
            self._stream = self._audio.open(
                rate=self._porcupine.sample_rate,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=self._porcupine.frame_length,
            )

            self._running = True
            self._thread = threading.Thread(
                target=self._listen_loop,
                args=(callback,),
                daemon=True,
            )
            self._thread.start()
            logger.info(f"Wake word detection started: '{self.keyword}'")

        except ImportError:
            logger.error("pvporcupine not installed. pip install pvporcupine")
            raise
        except Exception as e:
            logger.error(f"Failed to start wake word detection: {e}")
            raise

    def _listen_loop(self, callback: Callable[[], None]) -> None:
        """Main listening loop."""
        while self._running:
            try:
                pcm = self._stream.read(
                    self._porcupine.frame_length,
                    exception_on_overflow=False,
                )
                pcm = [
                    int.from_bytes(pcm[i : i + 2], "little", signed=True)
                    for i in range(0, len(pcm), 2)
                ]

                keyword_index = self._porcupine.process(pcm)

                if keyword_index >= 0:
                    logger.info("Wake word detected!")
                    callback()

            except Exception as e:
                logger.error(f"Wake word error: {e}")
                break

    def stop(self) -> None:
        """Stop wake word detection."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
        if self._stream:
            self._stream.close()
        if self._audio:
            self._audio.terminate()
        if self._porcupine:
            self._porcupine.delete()


class OpenWakeWord(WakeWordDetector):
    """Open-source wake word detection using openWakeWord."""

    def __init__(
        self,
        model: str = "hey_jarvis",  # Built-in models
        threshold: float = 0.5,
    ):
        self.model = model
        self.threshold = threshold
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self, callback: Callable[[], None]) -> None:
        """Start wake word detection."""
        try:
            import pyaudio
            from openwakeword import Model

            self._oww = Model(wakeword_models=[self.model])
            self._audio = pyaudio.PyAudio()
            self._stream = self._audio.open(
                rate=16000,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=1280,
            )

            self._running = True
            self._thread = threading.Thread(
                target=self._listen_loop,
                args=(callback,),
                daemon=True,
            )
            self._thread.start()
            logger.info(f"OpenWakeWord started: '{self.model}'")

        except ImportError:
            logger.error("openwakeword not installed. pip install openwakeword")
            raise

    def _listen_loop(self, callback: Callable[[], None]) -> None:
        """Main listening loop."""
        import numpy as np

        while self._running:
            try:
                audio_data = self._stream.read(1280, exception_on_overflow=False)
                audio_array = np.frombuffer(audio_data, dtype=np.int16)

                prediction = self._oww.predict(audio_array)

                for model_name, score in prediction.items():
                    if score > self.threshold:
                        logger.info(f"Wake word detected: {model_name} ({score:.2f})")
                        callback()
                        break

            except Exception as e:
                logger.error(f"Wake word error: {e}")
                break

    def stop(self) -> None:
        """Stop detection."""
        self._running = False
        if hasattr(self, "_stream"):
            self._stream.close()
        if hasattr(self, "_audio"):
            self._audio.terminate()


class SimpleWakeWord(WakeWordDetector):
    """Simple wake word using Vosk (fully offline, no API key)."""

    def __init__(self, wake_phrase: str = "hey r"):
        self.wake_phrase = wake_phrase.lower()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self, callback: Callable[[], None]) -> None:
        """Start listening."""
        try:
            import pyaudio
            from vosk import KaldiRecognizer, Model

            # Download model if needed
            model_path = Path.home() / ".r-cli" / "models" / "vosk-model-small-en-us-0.15"
            if not model_path.exists():
                logger.warning(f"Vosk model not found at {model_path}")
                logger.info("Download from: https://alphacephei.com/vosk/models")
                return

            self._model = Model(str(model_path))
            self._recognizer = KaldiRecognizer(self._model, 16000)

            self._audio = pyaudio.PyAudio()
            self._stream = self._audio.open(
                rate=16000,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=4000,
            )

            self._running = True
            self._thread = threading.Thread(
                target=self._listen_loop,
                args=(callback,),
                daemon=True,
            )
            self._thread.start()
            logger.info(f"Simple wake word started: '{self.wake_phrase}'")

        except ImportError:
            logger.error("vosk not installed. pip install vosk")
            raise

    def _listen_loop(self, callback: Callable[[], None]) -> None:
        """Listen for wake phrase."""
        while self._running:
            try:
                data = self._stream.read(4000, exception_on_overflow=False)

                if self._recognizer.AcceptWaveform(data):
                    result = json.loads(self._recognizer.Result())
                    text = result.get("text", "").lower()

                    if self.wake_phrase in text:
                        logger.info(f"Wake phrase detected in: {text}")
                        callback()

            except Exception as e:
                logger.error(f"Wake word error: {e}")
                break

    def stop(self) -> None:
        """Stop listening."""
        self._running = False


# ============================================================================
# Speech-to-Text
# ============================================================================


class SpeechToText(ABC):
    """Base class for speech-to-text."""

    @abstractmethod
    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file to text."""

    @abstractmethod
    def transcribe_stream(self, audio_data: bytes) -> str:
        """Transcribe audio data to text."""


class WhisperSTT(SpeechToText):
    """Speech-to-text using OpenAI Whisper (local)."""

    def __init__(
        self,
        model: str = "base",  # tiny, base, small, medium, large
        device: str = "auto",  # cpu, cuda, auto
    ):
        self.model_name = model
        self.device = device
        self._model = None

    def _load_model(self):
        """Lazy load the model."""
        if self._model is None:
            try:
                import torch
                import whisper

                device = self.device
                if device == "auto":
                    device = "cuda" if torch.cuda.is_available() else "cpu"

                logger.info(f"Loading Whisper model '{self.model_name}' on {device}")
                self._model = whisper.load_model(self.model_name, device=device)

            except ImportError:
                logger.error("whisper not installed. pip install openai-whisper")
                raise

    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file."""
        self._load_model()

        result = self._model.transcribe(audio_path)
        return result["text"].strip()

    def transcribe_stream(self, audio_data: bytes) -> str:
        """Transcribe audio data."""
        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name

        try:
            return self.transcribe(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)


class WhisperCppSTT(SpeechToText):
    """Speech-to-text using whisper.cpp (optimized for Pi)."""

    def __init__(
        self,
        model_path: Optional[str] = None,
        executable: str = "whisper-cpp",
    ):
        self.model_path = model_path or str(Path.home() / ".r-cli" / "models" / "ggml-base.en.bin")
        self.executable = shutil.which(executable) or executable

    def transcribe(self, audio_path: str) -> str:
        """Transcribe audio file."""
        try:
            result = subprocess.run(
                [
                    self.executable,
                    "-m",
                    self.model_path,
                    "-f",
                    audio_path,
                    "-nt",  # No timestamps
                    "-np",  # No progress
                ],
                check=False,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.error(f"whisper.cpp error: {result.stderr}")
                return ""

        except FileNotFoundError:
            logger.error(f"whisper.cpp not found: {self.executable}")
            return ""
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return ""

    def transcribe_stream(self, audio_data: bytes) -> str:
        """Transcribe audio data."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name

        try:
            return self.transcribe(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)


# ============================================================================
# Text-to-Speech
# ============================================================================


class TextToSpeech(ABC):
    """Base class for text-to-speech."""

    @abstractmethod
    def speak(self, text: str, output_path: Optional[str] = None) -> Optional[str]:
        """Convert text to speech. Returns audio path or plays directly."""


class PiperTTS(TextToSpeech):
    """Text-to-speech using Piper (fast, local)."""

    def __init__(
        self,
        model: str = "en_US-lessac-medium",
        executable: str = "piper",
    ):
        self.model = model
        self.executable = shutil.which(executable) or executable
        self._model_path = Path.home() / ".r-cli" / "models" / "piper" / f"{model}.onnx"

    def speak(self, text: str, output_path: Optional[str] = None) -> Optional[str]:
        """Convert text to speech."""
        if not output_path:
            output_path = tempfile.mktemp(suffix=".wav")

        try:
            # Piper reads from stdin
            result = subprocess.run(
                [
                    self.executable,
                    "--model",
                    str(self._model_path),
                    "--output_file",
                    output_path,
                ],
                check=False,
                input=text,
                text=True,
                capture_output=True,
                timeout=30,
            )

            if result.returncode == 0 and Path(output_path).exists():
                # Play the audio
                self._play_audio(output_path)
                return output_path
            else:
                logger.error(f"Piper error: {result.stderr}")
                return None

        except FileNotFoundError:
            logger.error(f"Piper not found: {self.executable}")
            return None
        except Exception as e:
            logger.error(f"TTS error: {e}")
            return None

    def _play_audio(self, path: str) -> None:
        """Play audio file."""
        try:
            # Try different players
            for player in ["aplay", "afplay", "play", "paplay"]:
                if shutil.which(player):
                    subprocess.run([player, path], check=True)
                    return

            logger.warning("No audio player found")
        except Exception as e:
            logger.error(f"Audio playback error: {e}")


class EspeakTTS(TextToSpeech):
    """Text-to-speech using espeak-ng (lightweight)."""

    def __init__(
        self,
        voice: str = "en",
        speed: int = 175,
    ):
        self.voice = voice
        self.speed = speed
        self.executable = shutil.which("espeak-ng") or shutil.which("espeak")

    def speak(self, text: str, output_path: Optional[str] = None) -> Optional[str]:
        """Convert text to speech."""
        if not self.executable:
            logger.error("espeak not found. Install espeak-ng.")
            return None

        try:
            cmd = [self.executable, "-v", self.voice, "-s", str(self.speed)]

            if output_path:
                cmd.extend(["-w", output_path])
                subprocess.run(cmd + [text], check=True)
                return output_path
            else:
                # Speak directly
                subprocess.run(cmd + [text], check=True)
                return None

        except Exception as e:
            logger.error(f"TTS error: {e}")
            return None


# ============================================================================
# Voice Interface
# ============================================================================


class VoiceInterface:
    """
    Complete voice interface for R CLI.

    Integrates wake word detection, speech-to-text, and text-to-speech
    for a hands-free AI assistant experience.
    """

    def __init__(
        self,
        wake_word: Optional[WakeWordDetector] = None,
        stt: Optional[SpeechToText] = None,
        tts: Optional[TextToSpeech] = None,
        on_command: Optional[Callable[[str], str]] = None,
    ):
        self.wake_word = wake_word or SimpleWakeWord("hey r")
        self.stt = stt or WhisperCppSTT()
        self.tts = tts or EspeakTTS()
        self.on_command = on_command

        self._running = False
        self._listening_for_command = False
        self._audio_queue: queue.Queue = queue.Queue()

    def start(self) -> None:
        """Start the voice interface."""
        logger.info("Starting voice interface...")

        # Start wake word detection
        self.wake_word.start(self._on_wake_word)
        self._running = True

        logger.info("Voice interface ready. Say 'Hey R' to activate.")

    def stop(self) -> None:
        """Stop the voice interface."""
        self._running = False
        self.wake_word.stop()
        logger.info("Voice interface stopped.")

    def _on_wake_word(self) -> None:
        """Handle wake word detection."""
        if self._listening_for_command:
            return

        self._listening_for_command = True

        # Play acknowledgment sound
        self.tts.speak("Yes?")

        # Record command
        audio_data = self._record_command()

        if audio_data:
            # Transcribe
            text = self.stt.transcribe_stream(audio_data)
            logger.info(f"Transcribed: {text}")

            if text and self.on_command:
                # Process command
                response = self.on_command(text)

                # Speak response
                if response:
                    self.tts.speak(response)

        self._listening_for_command = False

    def _record_command(
        self,
        duration: float = 5.0,
        silence_threshold: int = 500,
        silence_duration: float = 1.5,
    ) -> Optional[bytes]:
        """Record audio until silence or max duration."""
        try:
            import audioop

            import pyaudio

            audio = pyaudio.PyAudio()
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024,
            )

            frames = []
            silent_chunks = 0
            max_silent_chunks = int(silence_duration * 16000 / 1024)
            max_chunks = int(duration * 16000 / 1024)

            for _ in range(max_chunks):
                data = stream.read(1024, exception_on_overflow=False)
                frames.append(data)

                # Check for silence
                rms = audioop.rms(data, 2)
                if rms < silence_threshold:
                    silent_chunks += 1
                    if silent_chunks > max_silent_chunks:
                        break
                else:
                    silent_chunks = 0

            stream.close()
            audio.terminate()

            # Create WAV data
            import io

            buffer = io.BytesIO()
            with wave.open(buffer, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(b"".join(frames))

            return buffer.getvalue()

        except Exception as e:
            logger.error(f"Recording error: {e}")
            return None

    async def run_async(self) -> None:
        """Run the voice interface asynchronously."""
        self.start()

        try:
            while self._running:
                await asyncio.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def run(self) -> None:
        """Run the voice interface (blocking)."""
        self.start()

        try:
            while self._running:
                import time

                time.sleep(0.1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


# ============================================================================
# Factory
# ============================================================================


def create_voice_interface(
    config: Optional[dict] = None,
    on_command: Optional[Callable[[str], str]] = None,
) -> VoiceInterface:
    """
    Create a voice interface with the given configuration.

    Config options:
        wake_word:
            type: "simple" | "porcupine" | "openwakeword"
            phrase: "hey r"
            sensitivity: 0.5

        stt:
            type: "whisper" | "whisper-cpp"
            model: "base"

        tts:
            type: "piper" | "espeak"
            voice: "en_US-lessac-medium"
    """
    config = config or {}

    # Wake word
    ww_config = config.get("wake_word", {})
    ww_type = ww_config.get("type", "simple")

    if ww_type == "porcupine":
        wake_word = PorcupineWakeWord(
            keyword=ww_config.get("keyword", "hey google"),
            sensitivity=ww_config.get("sensitivity", 0.5),
            access_key=ww_config.get("access_key"),
        )
    elif ww_type == "openwakeword":
        wake_word = OpenWakeWord(
            model=ww_config.get("model", "hey_jarvis"),
            threshold=ww_config.get("threshold", 0.5),
        )
    else:
        wake_word = SimpleWakeWord(
            wake_phrase=ww_config.get("phrase", "hey r"),
        )

    # STT
    stt_config = config.get("stt", {})
    stt_type = stt_config.get("type", "whisper-cpp")

    if stt_type == "whisper":
        stt = WhisperSTT(
            model=stt_config.get("model", "base"),
            device=stt_config.get("device", "auto"),
        )
    else:
        stt = WhisperCppSTT(
            model_path=stt_config.get("model_path"),
        )

    # TTS
    tts_config = config.get("tts", {})
    tts_type = tts_config.get("type", "espeak")

    if tts_type == "piper":
        tts = PiperTTS(
            model=tts_config.get("model", "en_US-lessac-medium"),
        )
    else:
        tts = EspeakTTS(
            voice=tts_config.get("voice", "en"),
            speed=tts_config.get("speed", 175),
        )

    return VoiceInterface(
        wake_word=wake_word,
        stt=stt,
        tts=tts,
        on_command=on_command,
    )
