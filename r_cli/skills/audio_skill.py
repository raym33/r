"""
Audio Skill for R CLI.

Audio manipulation using ffmpeg/pydub:
- Convert formats
- Trim and merge
- Volume adjustment
- Audio info
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class AudioSkill(Skill):
    """Skill for audio manipulation."""

    name = "audio"
    description = "Audio: convert, trim, merge, volume, info"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="audio_info",
                description="Get audio file information",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to audio file",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.audio_info,
            ),
            Tool(
                name="audio_convert",
                description="Convert audio format",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input audio path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output path (format from extension)",
                        },
                        "bitrate": {
                            "type": "string",
                            "description": "Bitrate (e.g., '192k')",
                        },
                    },
                    "required": ["input_path", "output_path"],
                },
                handler=self.audio_convert,
            ),
            Tool(
                name="audio_trim",
                description="Trim audio to specified duration",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input audio path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output audio path",
                        },
                        "start": {
                            "type": "string",
                            "description": "Start time (e.g., '00:00:30' or '30')",
                        },
                        "duration": {
                            "type": "string",
                            "description": "Duration (e.g., '00:01:00' or '60')",
                        },
                    },
                    "required": ["input_path", "output_path", "start"],
                },
                handler=self.audio_trim,
            ),
            Tool(
                name="audio_volume",
                description="Adjust audio volume",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input audio path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output audio path",
                        },
                        "volume": {
                            "type": "number",
                            "description": "Volume multiplier (0.5 = half, 2.0 = double)",
                        },
                    },
                    "required": ["input_path", "output_path", "volume"],
                },
                handler=self.audio_volume,
            ),
            Tool(
                name="audio_merge",
                description="Merge multiple audio files",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_paths": {
                            "type": "string",
                            "description": "Comma-separated list of input files",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output audio path",
                        },
                    },
                    "required": ["input_paths", "output_path"],
                },
                handler=self.audio_merge,
            ),
            Tool(
                name="audio_extract",
                description="Extract audio from video",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input video path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output audio path",
                        },
                    },
                    "required": ["input_path", "output_path"],
                },
                handler=self.audio_extract,
            ),
            Tool(
                name="audio_normalize",
                description="Normalize audio volume",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input audio path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output audio path",
                        },
                    },
                    "required": ["input_path", "output_path"],
                },
                handler=self.audio_normalize,
            ),
            Tool(
                name="audio_speed",
                description="Change audio speed/tempo",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input audio path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output audio path",
                        },
                        "speed": {
                            "type": "number",
                            "description": "Speed multiplier (0.5 = half, 2.0 = double)",
                        },
                    },
                    "required": ["input_path", "output_path", "speed"],
                },
                handler=self.audio_speed,
            ),
        ]

    def _check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available."""
        return shutil.which("ffmpeg") is not None

    def _run_ffmpeg(self, args: list[str]) -> tuple[bool, str]:
        """Run ffmpeg command."""
        if not self._check_ffmpeg():
            return False, "ffmpeg not found. Install with: brew install ffmpeg"

        try:
            result = subprocess.run(
                ["ffmpeg", "-y"] + args,
                check=False, capture_output=True,
                text=True,
                timeout=300,
            )
            if result.returncode != 0:
                return False, result.stderr
            return True, "Success"
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)

    def audio_info(self, file_path: str) -> str:
        """Get audio information."""
        if not shutil.which("ffprobe"):
            return "ffprobe not found. Install ffmpeg."

        path = Path(file_path).expanduser()
        if not path.exists():
            return f"File not found: {file_path}"

        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "quiet",
                    "-print_format", "json",
                    "-show_format",
                    "-show_streams",
                    str(path),
                ],
                check=False, capture_output=True,
                text=True,
            )

            data = json.loads(result.stdout)

            info = {
                "filename": path.name,
                "format": data.get("format", {}).get("format_name"),
                "duration": data.get("format", {}).get("duration"),
                "size": data.get("format", {}).get("size"),
                "bit_rate": data.get("format", {}).get("bit_rate"),
            }

            for stream in data.get("streams", []):
                if stream.get("codec_type") == "audio":
                    info["audio"] = {
                        "codec": stream.get("codec_name"),
                        "channels": stream.get("channels"),
                        "sample_rate": stream.get("sample_rate"),
                        "bit_rate": stream.get("bit_rate"),
                    }
                    break

            return json.dumps(info, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def audio_convert(
        self,
        input_path: str,
        output_path: str,
        bitrate: str = "192k",
    ) -> str:
        """Convert audio format."""
        path = Path(input_path).expanduser()
        if not path.exists():
            return f"File not found: {input_path}"

        args = ["-i", str(path)]

        out_ext = Path(output_path).suffix.lower()
        if out_ext == ".mp3":
            args.extend(["-codec:a", "libmp3lame", "-b:a", bitrate])
        elif out_ext == ".wav":
            args.extend(["-codec:a", "pcm_s16le"])
        elif out_ext == ".ogg":
            args.extend(["-codec:a", "libvorbis", "-b:a", bitrate])
        elif out_ext == ".flac":
            args.extend(["-codec:a", "flac"])
        elif out_ext == ".aac" or out_ext == ".m4a":
            args.extend(["-codec:a", "aac", "-b:a", bitrate])

        args.append(str(Path(output_path).expanduser()))

        success, msg = self._run_ffmpeg(args)
        return f"Converted to {output_path}" if success else f"Error: {msg}"

    def audio_trim(
        self,
        input_path: str,
        output_path: str,
        start: str,
        duration: Optional[str] = None,
    ) -> str:
        """Trim audio."""
        path = Path(input_path).expanduser()
        if not path.exists():
            return f"File not found: {input_path}"

        args = ["-i", str(path), "-ss", start]
        if duration:
            args.extend(["-t", duration])
        args.extend(["-c", "copy", str(Path(output_path).expanduser())])

        success, msg = self._run_ffmpeg(args)
        return f"Trimmed audio saved to {output_path}" if success else f"Error: {msg}"

    def audio_volume(
        self,
        input_path: str,
        output_path: str,
        volume: float,
    ) -> str:
        """Adjust volume."""
        path = Path(input_path).expanduser()
        if not path.exists():
            return f"File not found: {input_path}"

        args = [
            "-i", str(path),
            "-af", f"volume={volume}",
            str(Path(output_path).expanduser()),
        ]

        success, msg = self._run_ffmpeg(args)
        return f"Volume adjusted to {volume}x, saved to {output_path}" if success else f"Error: {msg}"

    def audio_merge(self, input_paths: str, output_path: str) -> str:
        """Merge audio files."""
        files = [f.strip() for f in input_paths.split(",")]

        for f in files:
            if not Path(f).expanduser().exists():
                return f"File not found: {f}"

        # Create concat file
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            for f in files:
                tmp.write(f"file '{Path(f).expanduser()}'\n")
            concat_file = tmp.name

        args = [
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            str(Path(output_path).expanduser()),
        ]

        success, msg = self._run_ffmpeg(args)

        # Cleanup
        Path(concat_file).unlink()

        return f"Merged {len(files)} files to {output_path}" if success else f"Error: {msg}"

    def audio_extract(self, input_path: str, output_path: str) -> str:
        """Extract audio from video."""
        path = Path(input_path).expanduser()
        if not path.exists():
            return f"File not found: {input_path}"

        out_ext = Path(output_path).suffix.lower()
        codec = "libmp3lame" if out_ext == ".mp3" else "copy"

        args = [
            "-i", str(path),
            "-vn",
            "-acodec", codec,
            str(Path(output_path).expanduser()),
        ]

        success, msg = self._run_ffmpeg(args)
        return f"Audio extracted to {output_path}" if success else f"Error: {msg}"

    def audio_normalize(self, input_path: str, output_path: str) -> str:
        """Normalize audio."""
        path = Path(input_path).expanduser()
        if not path.exists():
            return f"File not found: {input_path}"

        args = [
            "-i", str(path),
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
            str(Path(output_path).expanduser()),
        ]

        success, msg = self._run_ffmpeg(args)
        return f"Normalized audio saved to {output_path}" if success else f"Error: {msg}"

    def audio_speed(
        self,
        input_path: str,
        output_path: str,
        speed: float,
    ) -> str:
        """Change audio speed."""
        path = Path(input_path).expanduser()
        if not path.exists():
            return f"File not found: {input_path}"

        if speed <= 0:
            return "Speed must be positive"

        args = [
            "-i", str(path),
            "-af", f"atempo={speed}",
            str(Path(output_path).expanduser()),
        ]

        success, msg = self._run_ffmpeg(args)
        return f"Speed changed to {speed}x, saved to {output_path}" if success else f"Error: {msg}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "info")
        if action == "info":
            return self.audio_info(kwargs.get("file", ""))
        return f"Unknown action: {action}"
