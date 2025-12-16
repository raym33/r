"""
QR Code Skill for R CLI.

QR code generation and reading:
- Generate QR codes
- Read QR codes from images
- Create QR codes with logos
"""

import json
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class QRSkill(Skill):
    """Skill for QR code operations."""

    name = "qr"
    description = "QR: generate and read QR codes"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="qr_generate",
                description="Generate a QR code image",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "Data to encode (URL, text, etc.)",
                        },
                        "output": {
                            "type": "string",
                            "description": "Output file path (PNG)",
                        },
                        "size": {
                            "type": "integer",
                            "description": "Size in pixels (default: 300)",
                        },
                    },
                    "required": ["data", "output"],
                },
                handler=self.qr_generate,
            ),
            Tool(
                name="qr_read",
                description="Read QR code from an image",
                parameters={
                    "type": "object",
                    "properties": {
                        "image_path": {
                            "type": "string",
                            "description": "Path to image with QR code",
                        },
                    },
                    "required": ["image_path"],
                },
                handler=self.qr_read,
            ),
            Tool(
                name="qr_text",
                description="Generate QR code as ASCII art",
                parameters={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "string",
                            "description": "Data to encode",
                        },
                    },
                    "required": ["data"],
                },
                handler=self.qr_text,
            ),
        ]

    def qr_generate(
        self,
        data: str,
        output: str,
        size: int = 300,
    ) -> str:
        """Generate QR code image."""
        try:
            import qrcode
            from qrcode.constants import ERROR_CORRECT_H

            qr = qrcode.QRCode(
                version=1,
                error_correction=ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            # Resize if needed
            if size != 300:
                img = img.resize((size, size))

            path = Path(output).expanduser()
            img.save(str(path))

            return f"QR code saved to {output}"

        except ImportError:
            return "Error: qrcode not installed. Run: pip install qrcode[pil]"
        except Exception as e:
            return f"Error: {e}"

    def qr_read(self, image_path: str) -> str:
        """Read QR code from image."""
        try:
            from PIL import Image
            import pyzbar.pyzbar as pyzbar

            path = Path(image_path).expanduser()
            if not path.exists():
                return f"File not found: {image_path}"

            img = Image.open(path)
            decoded = pyzbar.decode(img)

            if not decoded:
                return "No QR code found in image"

            results = []
            for obj in decoded:
                results.append({
                    "type": obj.type,
                    "data": obj.data.decode("utf-8"),
                })

            return json.dumps(results, indent=2)

        except ImportError:
            return "Error: pyzbar not installed. Run: pip install pyzbar pillow"
        except Exception as e:
            return f"Error: {e}"

    def qr_text(self, data: str) -> str:
        """Generate QR as ASCII art."""
        try:
            import qrcode

            qr = qrcode.QRCode(
                version=1,
                box_size=1,
                border=1,
            )
            qr.add_data(data)
            qr.make(fit=True)

            # Get matrix
            matrix = qr.get_matrix()
            lines = []

            for row in matrix:
                line = ""
                for cell in row:
                    line += "██" if cell else "  "
                lines.append(line)

            return "\n".join(lines)

        except ImportError:
            return "Error: qrcode not installed"
        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "generate")
        if action == "generate":
            return self.qr_generate(
                kwargs.get("data", ""),
                kwargs.get("output", "qr.png"),
            )
        elif action == "read":
            return self.qr_read(kwargs.get("image", ""))
        return f"Unknown action: {action}"
