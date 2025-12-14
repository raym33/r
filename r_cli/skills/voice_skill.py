"""
Voice Skill for R CLI.

Audio transcription with Whisper and voice synthesis with Piper TTS.
100% local and offline.

Requirements:
- whisper or faster-whisper for transcription
- piper-tts for voice synthesis
- sounddevice/pyaudio for real-time recording
"""

import json
import logging
import shutil
import subprocess
import wave
from datetime import datetime
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool

logger = logging.getLogger(__name__)


class VoiceSkill(Skill):
    """Skill for offline voice transcription and synthesis."""

    name = "voice"
    description = "Transcribe audio with Whisper and generate voice with Piper TTS"

    # Available Whisper models
    WHISPER_MODELS = {
        "tiny": "Fastest, lower accuracy (~1GB VRAM)",
        "base": "Speed/accuracy balance (~1GB VRAM)",
        "small": "Good accuracy (~2GB VRAM)",
        "medium": "High accuracy (~5GB VRAM)",
        "large": "Maximum accuracy (~10GB VRAM)",
        "large-v3": "Latest version, best quality (~10GB VRAM)",
    }

    # Popular Piper voices (can be downloaded)
    PIPER_VOICES = {
        "en_US-amy-medium": "Amy - English US female",
        "en_US-ryan-medium": "Ryan - English US male",
        "en_GB-alan-medium": "Alan - English UK male",
        "es_ES-davefx-medium": "Dave - Spanish Spain male",
        "es_MX-ald-medium": "Ald - Spanish Mexico male",
        "de_DE-thorsten-medium": "Thorsten - German male",
        "fr_FR-upmc-medium": "UPMC - French",
        "it_IT-riccardo-x_low": "Riccardo - Italian male",
        "pt_BR-faber-medium": "Faber - Portuguese Brazil male",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._whisper_available = self._check_whisper()
        self._piper_available = self._check_piper()
        self._sounddevice_available = self._check_sounddevice()

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

    def _check_piper(self) -> bool:
        """Check if Piper TTS is available."""
        return shutil.which("piper") is not None

    def _check_sounddevice(self) -> bool:
        """Check if sounddevice is available."""
        try:
            import sounddevice

            return True
        except ImportError:
            return False

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="transcribe_audio",
                description="Transcribe an audio file to text using Whisper",
                parameters={
                    "type": "object",
                    "properties": {
                        "audio_path": {
                            "type": "string",
                            "description": "Path to audio file (mp3, wav, m4a, etc.)",
                        },
                        "model": {
                            "type": "string",
                            "enum": list(self.WHISPER_MODELS.keys()),
                            "description": "Whisper model to use (default: base)",
                        },
                        "language": {
                            "type": "string",
                            "description": "Language code (es, en, fr, etc.). Auto-detects if not specified.",
                        },
                        "output_format": {
                            "type": "string",
                            "enum": ["text", "srt", "vtt", "json"],
                            "description": "Output format (default: text)",
                        },
                    },
                    "required": ["audio_path"],
                },
                handler=self.transcribe_audio,
            ),
            Tool(
                name="text_to_speech",
                description="Convert text to audio using Piper TTS",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to convert to speech",
                        },
                        "voice": {
                            "type": "string",
                            "description": "Voice to use (see list_voices for options)",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Path to save audio (optional)",
                        },
                        "speed": {
                            "type": "number",
                            "description": "Speech speed (0.5-2.0, default: 1.0)",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.text_to_speech,
            ),
            Tool(
                name="record_audio",
                description="Record audio from the microphone",
                parameters={
                    "type": "object",
                    "properties": {
                        "duration": {
                            "type": "number",
                            "description": "Duration in seconds",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Path to save recording",
                        },
                    },
                    "required": ["duration"],
                },
                handler=self.record_audio,
            ),
            Tool(
                name="list_whisper_models",
                description="List available Whisper models",
                parameters={"type": "object", "properties": {}},
                handler=self.list_whisper_models,
            ),
            Tool(
                name="list_voices",
                description="List available Piper TTS voices",
                parameters={"type": "object", "properties": {}},
                handler=self.list_voices,
            ),
            Tool(
                name="voice_chat",
                description="Voice conversation mode (record, transcribe, respond)",
                parameters={
                    "type": "object",
                    "properties": {
                        "duration": {
                            "type": "number",
                            "description": "Recording duration in seconds",
                        },
                    },
                    "required": ["duration"],
                },
                handler=self.voice_chat,
            ),
        ]

    def transcribe_audio(
        self,
        audio_path: str,
        model: str = "base",
        language: Optional[str] = None,
        output_format: str = "text",
    ) -> str:
        """Transcribe audio using Whisper."""
        if not self._whisper_available:
            return "Error: Whisper not installed. Run: pip install openai-whisper"

        audio_file = Path(audio_path)
        if not audio_file.exists():
            return f"Error: File not found: {audio_path}"

        try:
            # Try faster-whisper first (more efficient)
            try:
                from faster_whisper import WhisperModel

                whisper_model = WhisperModel(model, device="auto", compute_type="auto")
                segments, info = whisper_model.transcribe(
                    str(audio_file),
                    language=language,
                    beam_size=5,
                )

                detected_lang = info.language
                segments_list = list(segments)

                if output_format == "text":
                    text = " ".join([seg.text.strip() for seg in segments_list])
                    return f"Transcription ({detected_lang}):\n\n{text}"

                elif output_format == "srt":
                    srt_content = self._to_srt(segments_list)
                    return f"Subtitles SRT:\n\n{srt_content}"

                elif output_format == "vtt":
                    vtt_content = self._to_vtt(segments_list)
                    return f"Subtitles VTT:\n\n{vtt_content}"

                elif output_format == "json":
                    json_content = self._to_json(segments_list, detected_lang)
                    return f"Transcription JSON:\n\n{json_content}"

            except ImportError:
                # Fallback to openai-whisper
                import whisper

                whisper_model = whisper.load_model(model)
                result = whisper_model.transcribe(
                    str(audio_file),
                    language=language,
                )

                if output_format == "text":
                    return (
                        f"Transcription ({result.get('language', 'unknown')}):\n\n{result['text']}"
                    )

                elif output_format == "srt":
                    srt_content = self._whisper_to_srt(result)
                    return f"Subtitles SRT:\n\n{srt_content}"

                elif output_format == "vtt":
                    vtt_content = self._whisper_to_vtt(result)
                    return f"Subtitles VTT:\n\n{vtt_content}"

                elif output_format == "json":
                    return (
                        f"Transcription JSON:\n\n{json.dumps(result, indent=2, ensure_ascii=False)}"
                    )

        except Exception as e:
            return f"Error transcribing audio: {e}"

    def _to_srt(self, segments) -> str:
        """Convert segments to SRT format."""
        srt_lines = []
        for i, seg in enumerate(segments, 1):
            start = self._format_timestamp_srt(seg.start)
            end = self._format_timestamp_srt(seg.end)
            srt_lines.append(f"{i}")
            srt_lines.append(f"{start} --> {end}")
            srt_lines.append(seg.text.strip())
            srt_lines.append("")
        return "\n".join(srt_lines)

    def _to_vtt(self, segments) -> str:
        """Convert segments to VTT format."""
        vtt_lines = ["WEBVTT", ""]
        for seg in segments:
            start = self._format_timestamp_vtt(seg.start)
            end = self._format_timestamp_vtt(seg.end)
            vtt_lines.append(f"{start} --> {end}")
            vtt_lines.append(seg.text.strip())
            vtt_lines.append("")
        return "\n".join(vtt_lines)

    def _to_json(self, segments, language: str) -> str:
        """Convert segments to JSON."""
        data = {
            "language": language,
            "segments": [
                {
                    "start": seg.start,
                    "end": seg.end,
                    "text": seg.text.strip(),
                }
                for seg in segments
            ],
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def _format_timestamp_srt(self, seconds: float) -> str:
        """Format timestamp for SRT (HH:MM:SS,mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _format_timestamp_vtt(self, seconds: float) -> str:
        """Format timestamp for VTT (HH:MM:SS.mmm)."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"

    def _whisper_to_srt(self, result: dict) -> str:
        """Convert whisper result to SRT."""
        srt_lines = []
        for i, seg in enumerate(result.get("segments", []), 1):
            start = self._format_timestamp_srt(seg["start"])
            end = self._format_timestamp_srt(seg["end"])
            srt_lines.append(f"{i}")
            srt_lines.append(f"{start} --> {end}")
            srt_lines.append(seg["text"].strip())
            srt_lines.append("")
        return "\n".join(srt_lines)

    def _whisper_to_vtt(self, result: dict) -> str:
        """Convert whisper result to VTT."""
        vtt_lines = ["WEBVTT", ""]
        for seg in result.get("segments", []):
            start = self._format_timestamp_vtt(seg["start"])
            end = self._format_timestamp_vtt(seg["end"])
            vtt_lines.append(f"{start} --> {end}")
            vtt_lines.append(seg["text"].strip())
            vtt_lines.append("")
        return "\n".join(vtt_lines)

    def text_to_speech(
        self,
        text: str,
        voice: str = "en_US-amy-medium",
        output_path: Optional[str] = None,
        speed: float = 1.0,
    ) -> str:
        """Convert text to speech using Piper TTS."""
        if not self._piper_available:
            return self._tts_fallback(text, output_path)

        try:
            # Determine output path
            if output_path:
                out_path = Path(output_path)
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_path = Path(self.output_dir) / f"speech_{timestamp}.wav"

            out_path.parent.mkdir(parents=True, exist_ok=True)

            # Run Piper
            # Piper expects text via stdin
            cmd = [
                "piper",
                "--model",
                voice,
                "--output_file",
                str(out_path),
            ]

            if speed != 1.0:
                cmd.extend(["--length_scale", str(1.0 / speed)])

            result = subprocess.run(
                cmd,
                check=False,
                input=text,
                capture_output=True,
                text=True,
                timeout=120,
            )

            if result.returncode != 0:
                return f"Error in Piper TTS: {result.stderr}"

            return f"Audio generated: {out_path}"

        except subprocess.TimeoutExpired:
            return "Error: Timeout generating audio (>120s)"
        except Exception as e:
            return f"Error in TTS: {e}"

    def _tts_fallback(self, text: str, output_path: Optional[str] = None) -> str:
        """Fallback using say (macOS) or espeak (Linux)."""
        try:
            # Determine output path
            if output_path:
                out_path = Path(output_path)
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_path = Path(self.output_dir) / f"speech_{timestamp}.aiff"

            out_path.parent.mkdir(parents=True, exist_ok=True)

            # Try say (macOS)
            if shutil.which("say"):
                subprocess.run(
                    ["say", "-o", str(out_path), text],
                    check=True,
                    timeout=60,
                )
                return f"Audio generated (say): {out_path}"

            # Try espeak (Linux)
            elif shutil.which("espeak"):
                wav_path = out_path.with_suffix(".wav")
                subprocess.run(
                    ["espeak", "-w", str(wav_path), text],
                    check=True,
                    timeout=60,
                )
                return f"Audio generated (espeak): {wav_path}"

            else:
                return "Error: No TTS available. Install piper-tts, or use say (macOS) / espeak (Linux)"

        except Exception as e:
            return f"Error in TTS fallback: {e}"

    def record_audio(
        self,
        duration: float,
        output_path: Optional[str] = None,
    ) -> str:
        """Record audio from the microphone."""
        if not self._sounddevice_available:
            return "Error: sounddevice not installed. Run: pip install sounddevice"

        try:
            import numpy as np
            import sounddevice as sd

            # Recording parameters
            sample_rate = 16000  # 16kHz is sufficient for voice
            channels = 1

            print(f"Recording {duration} seconds...")

            # Record
            audio_data = sd.rec(
                int(duration * sample_rate),
                samplerate=sample_rate,
                channels=channels,
                dtype=np.int16,
            )
            sd.wait()

            # Determine output path
            if output_path:
                out_path = Path(output_path)
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_path = Path(self.output_dir) / f"recording_{timestamp}.wav"

            out_path.parent.mkdir(parents=True, exist_ok=True)

            # Save as WAV
            with wave.open(str(out_path), "wb") as wf:
                wf.setnchannels(channels)
                wf.setsampwidth(2)  # 16-bit
                wf.setframerate(sample_rate)
                wf.writeframes(audio_data.tobytes())

            return f"Recording saved: {out_path}"

        except Exception as e:
            return f"Error recording audio: {e}"

    def voice_chat(self, duration: float = 5.0) -> str:
        """Conversation mode: record -> transcribe -> return text."""
        # Record audio
        record_result = self.record_audio(duration)
        if "Error" in record_result:
            return record_result

        # Extract path from recording
        audio_path = record_result.split(": ")[-1]

        # Transcribe
        transcription = self.transcribe_audio(audio_path, model="base")

        # Clean up temp file if in output_dir
        try:
            Path(audio_path).unlink()
        except Exception as e:
            logger.debug(f"Could not clean up temp audio file {audio_path}: {e}")

        return transcription

    def list_whisper_models(self) -> str:
        """List available Whisper models."""
        result = ["Available Whisper models:\n"]

        for model, desc in self.WHISPER_MODELS.items():
            result.append(f"  - {model}: {desc}")

        result.append("\nUsage: transcribe_audio(audio_path, model='medium')")
        result.append("\nInstallation: pip install openai-whisper")
        result.append("Or for more speed: pip install faster-whisper")

        return "\n".join(result)

    def list_voices(self) -> str:
        """List available Piper TTS voices."""
        result = ["Available Piper TTS voices:\n"]

        for voice, desc in self.PIPER_VOICES.items():
            result.append(f"  - {voice}: {desc}")

        result.append("\nUsage: text_to_speech(text, voice='es_ES-davefx-medium')")
        result.append("\nDownload voices: https://github.com/rhasspy/piper/releases")

        if not self._piper_available:
            result.append(
                "\nWarning: Piper not installed. Will use say (macOS) / espeak (Linux) as fallback."
            )

        return "\n".join(result)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        audio_path = kwargs.get("audio")
        text = kwargs.get("text")
        record_duration = kwargs.get("record")

        if audio_path:
            return self.transcribe_audio(
                audio_path=audio_path,
                model=kwargs.get("model", "base"),
                language=kwargs.get("language"),
                output_format=kwargs.get("format", "text"),
            )
        elif text:
            return self.text_to_speech(
                text=text,
                voice=kwargs.get("voice", "en_US-amy-medium"),
                output_path=kwargs.get("output"),
                speed=kwargs.get("speed", 1.0),
            )
        elif record_duration:
            return self.record_audio(
                duration=float(record_duration),
                output_path=kwargs.get("output"),
            )
        else:
            return "Error: Specify --audio to transcribe, --text for TTS, or --record to record"
