"""
Video Skill for R CLI.

Video manipulation using ffmpeg:
- Get video info
- Convert formats
- Extract audio
- Create thumbnails
- Trim/cut videos
"""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class VideoSkill(Skill):
    """Skill for video manipulation."""

    name = "video"
    description = "Video: convert, extract audio, thumbnails, trim (requires ffmpeg)"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="video_info",
                description="Get video file information",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to video file",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.video_info,
            ),
            Tool(
                name="video_convert",
                description="Convert video to another format",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input video path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output path (format determined by extension)",
                        },
                        "quality": {
                            "type": "string",
                            "description": "Quality: low, medium, high (default: medium)",
                        },
                    },
                    "required": ["input_path", "output_path"],
                },
                handler=self.video_convert,
            ),
            Tool(
                name="video_extract_audio",
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
                            "description": "Output audio path (mp3, wav, etc.)",
                        },
                    },
                    "required": ["input_path", "output_path"],
                },
                handler=self.video_extract_audio,
            ),
            Tool(
                name="video_thumbnail",
                description="Create thumbnail from video",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input video path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output image path",
                        },
                        "timestamp": {
                            "type": "string",
                            "description": "Timestamp (e.g., '00:00:05' or '5')",
                        },
                    },
                    "required": ["input_path", "output_path"],
                },
                handler=self.video_thumbnail,
            ),
            Tool(
                name="video_trim",
                description="Trim video to specified duration",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input video path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output video path",
                        },
                        "start": {
                            "type": "string",
                            "description": "Start time (e.g., '00:00:30')",
                        },
                        "duration": {
                            "type": "string",
                            "description": "Duration (e.g., '00:01:00')",
                        },
                    },
                    "required": ["input_path", "output_path", "start"],
                },
                handler=self.video_trim,
            ),
            Tool(
                name="video_resize",
                description="Resize video",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input video path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output video path",
                        },
                        "width": {
                            "type": "integer",
                            "description": "Target width (-1 for auto)",
                        },
                        "height": {
                            "type": "integer",
                            "description": "Target height (-1 for auto)",
                        },
                    },
                    "required": ["input_path", "output_path", "width", "height"],
                },
                handler=self.video_resize,
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
                capture_output=True,
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

    def video_info(self, file_path: str) -> str:
        """Get video information."""
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
                capture_output=True,
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
                if stream.get("codec_type") == "video":
                    info["video"] = {
                        "codec": stream.get("codec_name"),
                        "width": stream.get("width"),
                        "height": stream.get("height"),
                        "fps": stream.get("r_frame_rate"),
                    }
                elif stream.get("codec_type") == "audio":
                    info["audio"] = {
                        "codec": stream.get("codec_name"),
                        "channels": stream.get("channels"),
                        "sample_rate": stream.get("sample_rate"),
                    }

            return json.dumps(info, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def video_convert(
        self,
        input_path: str,
        output_path: str,
        quality: str = "medium",
    ) -> str:
        """Convert video format."""
        path = Path(input_path).expanduser()
        if not path.exists():
            return f"File not found: {input_path}"

        crf = {"low": "28", "medium": "23", "high": "18"}.get(quality, "23")

        success, msg = self._run_ffmpeg([
            "-i", str(path),
            "-c:v", "libx264",
            "-crf", crf,
            "-c:a", "aac",
            str(Path(output_path).expanduser()),
        ])

        return f"Converted to {output_path}" if success else f"Error: {msg}"

    def video_extract_audio(self, input_path: str, output_path: str) -> str:
        """Extract audio from video."""
        path = Path(input_path).expanduser()
        if not path.exists():
            return f"File not found: {input_path}"

        success, msg = self._run_ffmpeg([
            "-i", str(path),
            "-vn",
            "-acodec", "libmp3lame" if output_path.endswith(".mp3") else "copy",
            str(Path(output_path).expanduser()),
        ])

        return f"Audio extracted to {output_path}" if success else f"Error: {msg}"

    def video_thumbnail(
        self,
        input_path: str,
        output_path: str,
        timestamp: str = "00:00:01",
    ) -> str:
        """Create thumbnail from video."""
        path = Path(input_path).expanduser()
        if not path.exists():
            return f"File not found: {input_path}"

        success, msg = self._run_ffmpeg([
            "-i", str(path),
            "-ss", timestamp,
            "-vframes", "1",
            str(Path(output_path).expanduser()),
        ])

        return f"Thumbnail saved to {output_path}" if success else f"Error: {msg}"

    def video_trim(
        self,
        input_path: str,
        output_path: str,
        start: str,
        duration: Optional[str] = None,
    ) -> str:
        """Trim video."""
        path = Path(input_path).expanduser()
        if not path.exists():
            return f"File not found: {input_path}"

        args = ["-i", str(path), "-ss", start]
        if duration:
            args.extend(["-t", duration])
        args.extend(["-c", "copy", str(Path(output_path).expanduser())])

        success, msg = self._run_ffmpeg(args)
        return f"Trimmed video saved to {output_path}" if success else f"Error: {msg}"

    def video_resize(
        self,
        input_path: str,
        output_path: str,
        width: int,
        height: int,
    ) -> str:
        """Resize video."""
        path = Path(input_path).expanduser()
        if not path.exists():
            return f"File not found: {input_path}"

        scale = f"scale={width}:{height}"

        success, msg = self._run_ffmpeg([
            "-i", str(path),
            "-vf", scale,
            "-c:a", "copy",
            str(Path(output_path).expanduser()),
        ])

        return f"Resized video saved to {output_path}" if success else f"Error: {msg}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "info")
        if action == "info":
            return self.video_info(kwargs.get("file", ""))
        return f"Unknown action: {action}"
