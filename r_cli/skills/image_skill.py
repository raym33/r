"""
Image Skill for R CLI.

Image manipulation using Pillow:
- Resize, crop, rotate
- Format conversion
- Filters and effects
- Image info
"""

import json
from pathlib import Path
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class ImageSkill(Skill):
    """Skill for image manipulation."""

    name = "image"
    description = "Image: resize, crop, rotate, convert, filters"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="image_info",
                description="Get image information",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to image file",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.image_info,
            ),
            Tool(
                name="image_resize",
                description="Resize an image",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input image path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output image path",
                        },
                        "width": {
                            "type": "integer",
                            "description": "Target width (0 for auto)",
                        },
                        "height": {
                            "type": "integer",
                            "description": "Target height (0 for auto)",
                        },
                    },
                    "required": ["input_path", "output_path"],
                },
                handler=self.image_resize,
            ),
            Tool(
                name="image_crop",
                description="Crop an image",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input image path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output image path",
                        },
                        "left": {"type": "integer", "description": "Left coordinate"},
                        "top": {"type": "integer", "description": "Top coordinate"},
                        "right": {"type": "integer", "description": "Right coordinate"},
                        "bottom": {"type": "integer", "description": "Bottom coordinate"},
                    },
                    "required": ["input_path", "output_path", "left", "top", "right", "bottom"],
                },
                handler=self.image_crop,
            ),
            Tool(
                name="image_rotate",
                description="Rotate an image",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input image path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output image path",
                        },
                        "angle": {
                            "type": "number",
                            "description": "Rotation angle in degrees",
                        },
                    },
                    "required": ["input_path", "output_path", "angle"],
                },
                handler=self.image_rotate,
            ),
            Tool(
                name="image_convert",
                description="Convert image format",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input image path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output path (format from extension)",
                        },
                        "quality": {
                            "type": "integer",
                            "description": "Quality 1-100 for JPEG",
                        },
                    },
                    "required": ["input_path", "output_path"],
                },
                handler=self.image_convert,
            ),
            Tool(
                name="image_filter",
                description="Apply filter to image",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input image path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output image path",
                        },
                        "filter": {
                            "type": "string",
                            "description": "Filter: grayscale, blur, sharpen, contour, emboss, invert",
                        },
                    },
                    "required": ["input_path", "output_path", "filter"],
                },
                handler=self.image_filter,
            ),
            Tool(
                name="image_thumbnail",
                description="Create thumbnail",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input image path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output image path",
                        },
                        "size": {
                            "type": "integer",
                            "description": "Max dimension (default: 128)",
                        },
                    },
                    "required": ["input_path", "output_path"],
                },
                handler=self.image_thumbnail,
            ),
            Tool(
                name="image_flip",
                description="Flip image horizontally or vertically",
                parameters={
                    "type": "object",
                    "properties": {
                        "input_path": {
                            "type": "string",
                            "description": "Input image path",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output image path",
                        },
                        "direction": {
                            "type": "string",
                            "description": "Direction: horizontal, vertical",
                        },
                    },
                    "required": ["input_path", "output_path", "direction"],
                },
                handler=self.image_flip,
            ),
        ]

    def _load_image(self, path: str):
        """Load image with Pillow."""
        try:
            from PIL import Image
            p = Path(path).expanduser()
            if not p.exists():
                return None, f"File not found: {path}"
            return Image.open(p), None
        except ImportError:
            return None, "Pillow not installed. Run: pip install Pillow"
        except Exception as e:
            return None, str(e)

    def image_info(self, file_path: str) -> str:
        """Get image information."""
        img, error = self._load_image(file_path)
        if error:
            return f"Error: {error}"

        try:
            info = {
                "filename": Path(file_path).name,
                "format": img.format,
                "mode": img.mode,
                "width": img.width,
                "height": img.height,
                "size_pixels": img.width * img.height,
            }

            # File size
            path = Path(file_path).expanduser()
            info["file_size"] = f"{path.stat().st_size / 1024:.1f} KB"

            # EXIF data if available
            if hasattr(img, "_getexif") and img._getexif():
                exif = img._getexif()
                if exif:
                    info["has_exif"] = True

            img.close()
            return json.dumps(info, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def image_resize(
        self,
        input_path: str,
        output_path: str,
        width: int = 0,
        height: int = 0,
    ) -> str:
        """Resize image."""
        img, error = self._load_image(input_path)
        if error:
            return f"Error: {error}"

        try:
            from PIL import Image

            if width == 0 and height == 0:
                return "Specify width or height"

            orig_w, orig_h = img.size

            if width == 0:
                width = int(orig_w * height / orig_h)
            elif height == 0:
                height = int(orig_h * width / orig_w)

            resized = img.resize((width, height), Image.Resampling.LANCZOS)
            resized.save(Path(output_path).expanduser())
            img.close()

            return f"Resized to {width}x{height}, saved to {output_path}"

        except Exception as e:
            return f"Error: {e}"

    def image_crop(
        self,
        input_path: str,
        output_path: str,
        left: int,
        top: int,
        right: int,
        bottom: int,
    ) -> str:
        """Crop image."""
        img, error = self._load_image(input_path)
        if error:
            return f"Error: {error}"

        try:
            cropped = img.crop((left, top, right, bottom))
            cropped.save(Path(output_path).expanduser())
            img.close()

            return f"Cropped to {right-left}x{bottom-top}, saved to {output_path}"

        except Exception as e:
            return f"Error: {e}"

    def image_rotate(
        self,
        input_path: str,
        output_path: str,
        angle: float,
    ) -> str:
        """Rotate image."""
        img, error = self._load_image(input_path)
        if error:
            return f"Error: {error}"

        try:
            rotated = img.rotate(angle, expand=True)
            rotated.save(Path(output_path).expanduser())
            img.close()

            return f"Rotated {angle}°, saved to {output_path}"

        except Exception as e:
            return f"Error: {e}"

    def image_convert(
        self,
        input_path: str,
        output_path: str,
        quality: int = 85,
    ) -> str:
        """Convert image format."""
        img, error = self._load_image(input_path)
        if error:
            return f"Error: {error}"

        try:
            out_path = Path(output_path).expanduser()

            # Handle RGBA to RGB for JPEG
            if out_path.suffix.lower() in [".jpg", ".jpeg"] and img.mode == "RGBA":
                img = img.convert("RGB")

            if out_path.suffix.lower() in [".jpg", ".jpeg"]:
                img.save(out_path, quality=quality)
            else:
                img.save(out_path)

            img.close()
            return f"Converted to {out_path.suffix}, saved to {output_path}"

        except Exception as e:
            return f"Error: {e}"

    def image_filter(
        self,
        input_path: str,
        output_path: str,
        filter: str,
    ) -> str:
        """Apply filter to image."""
        img, error = self._load_image(input_path)
        if error:
            return f"Error: {error}"

        try:
            from PIL import Image, ImageFilter, ImageOps

            filter_lower = filter.lower()

            if filter_lower == "grayscale":
                result = ImageOps.grayscale(img)
            elif filter_lower == "blur":
                result = img.filter(ImageFilter.BLUR)
            elif filter_lower == "sharpen":
                result = img.filter(ImageFilter.SHARPEN)
            elif filter_lower == "contour":
                result = img.filter(ImageFilter.CONTOUR)
            elif filter_lower == "emboss":
                result = img.filter(ImageFilter.EMBOSS)
            elif filter_lower == "invert":
                if img.mode == "RGBA":
                    r, g, b, a = img.split()
                    rgb = Image.merge("RGB", (r, g, b))
                    inverted = ImageOps.invert(rgb)
                    r, g, b = inverted.split()
                    result = Image.merge("RGBA", (r, g, b, a))
                else:
                    result = ImageOps.invert(img.convert("RGB"))
            else:
                return f"Unknown filter: {filter}. Available: grayscale, blur, sharpen, contour, emboss, invert"

            result.save(Path(output_path).expanduser())
            img.close()

            return f"Applied {filter} filter, saved to {output_path}"

        except Exception as e:
            return f"Error: {e}"

    def image_thumbnail(
        self,
        input_path: str,
        output_path: str,
        size: int = 128,
    ) -> str:
        """Create thumbnail."""
        img, error = self._load_image(input_path)
        if error:
            return f"Error: {error}"

        try:
            img.thumbnail((size, size))
            img.save(Path(output_path).expanduser())

            return f"Thumbnail {img.width}x{img.height} saved to {output_path}"

        except Exception as e:
            return f"Error: {e}"

    def image_flip(
        self,
        input_path: str,
        output_path: str,
        direction: str,
    ) -> str:
        """Flip image."""
        img, error = self._load_image(input_path)
        if error:
            return f"Error: {error}"

        try:
            from PIL import ImageOps

            if direction.lower() == "horizontal":
                result = ImageOps.mirror(img)
            elif direction.lower() == "vertical":
                result = ImageOps.flip(img)
            else:
                return f"Unknown direction: {direction}. Use: horizontal, vertical"

            result.save(Path(output_path).expanduser())
            img.close()

            return f"Flipped {direction}, saved to {output_path}"

        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "info")
        if action == "info":
            return self.image_info(kwargs.get("file", ""))
        return f"Unknown action: {action}"
