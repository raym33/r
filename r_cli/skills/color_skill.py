"""
Color Skill for R CLI.

Color utilities:
- Convert between formats (HEX, RGB, HSL)
- Generate palettes
- Check contrast
- Color names
"""

import json
import re
from typing import Optional, Tuple

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class ColorSkill(Skill):
    """Skill for color operations."""

    name = "color"
    description = "Color: convert HEX/RGB/HSL, palettes, contrast"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="color_convert",
                description="Convert color between formats",
                parameters={
                    "type": "object",
                    "properties": {
                        "color": {
                            "type": "string",
                            "description": "Color value (#FF0000, rgb(255,0,0), hsl(0,100%,50%))",
                        },
                    },
                    "required": ["color"],
                },
                handler=self.color_convert,
            ),
            Tool(
                name="color_palette",
                description="Generate color palette",
                parameters={
                    "type": "object",
                    "properties": {
                        "base_color": {
                            "type": "string",
                            "description": "Base color (HEX)",
                        },
                        "type": {
                            "type": "string",
                            "description": "Palette type: complementary, analogous, triadic, split, shades",
                        },
                    },
                    "required": ["base_color"],
                },
                handler=self.color_palette,
            ),
            Tool(
                name="color_contrast",
                description="Check contrast ratio between two colors (WCAG)",
                parameters={
                    "type": "object",
                    "properties": {
                        "color1": {
                            "type": "string",
                            "description": "First color (HEX)",
                        },
                        "color2": {
                            "type": "string",
                            "description": "Second color (HEX)",
                        },
                    },
                    "required": ["color1", "color2"],
                },
                handler=self.color_contrast,
            ),
            Tool(
                name="color_blend",
                description="Blend two colors",
                parameters={
                    "type": "object",
                    "properties": {
                        "color1": {
                            "type": "string",
                            "description": "First color (HEX)",
                        },
                        "color2": {
                            "type": "string",
                            "description": "Second color (HEX)",
                        },
                        "ratio": {
                            "type": "number",
                            "description": "Blend ratio 0-1 (default: 0.5)",
                        },
                    },
                    "required": ["color1", "color2"],
                },
                handler=self.color_blend,
            ),
            Tool(
                name="color_lighten",
                description="Lighten a color",
                parameters={
                    "type": "object",
                    "properties": {
                        "color": {
                            "type": "string",
                            "description": "Color (HEX)",
                        },
                        "amount": {
                            "type": "number",
                            "description": "Amount 0-1 (default: 0.2)",
                        },
                    },
                    "required": ["color"],
                },
                handler=self.color_lighten,
            ),
            Tool(
                name="color_darken",
                description="Darken a color",
                parameters={
                    "type": "object",
                    "properties": {
                        "color": {
                            "type": "string",
                            "description": "Color (HEX)",
                        },
                        "amount": {
                            "type": "number",
                            "description": "Amount 0-1 (default: 0.2)",
                        },
                    },
                    "required": ["color"],
                },
                handler=self.color_darken,
            ),
            Tool(
                name="color_random",
                description="Generate random color(s)",
                parameters={
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "description": "Number of colors (default: 1)",
                        },
                    },
                },
                handler=self.color_random,
            ),
        ]

    def _hex_to_rgb(self, hex_color: str) -> Tuple[int, int, int]:
        """Convert HEX to RGB."""
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 3:
            hex_color = ''.join(c * 2 for c in hex_color)
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    def _rgb_to_hex(self, r: int, g: int, b: int) -> str:
        """Convert RGB to HEX."""
        return f"#{r:02x}{g:02x}{b:02x}".upper()

    def _rgb_to_hsl(self, r: int, g: int, b: int) -> Tuple[int, int, int]:
        """Convert RGB to HSL."""
        r, g, b = r / 255, g / 255, b / 255
        max_c = max(r, g, b)
        min_c = min(r, g, b)
        l = (max_c + min_c) / 2

        if max_c == min_c:
            h = s = 0
        else:
            d = max_c - min_c
            s = d / (2 - max_c - min_c) if l > 0.5 else d / (max_c + min_c)

            if max_c == r:
                h = (g - b) / d + (6 if g < b else 0)
            elif max_c == g:
                h = (b - r) / d + 2
            else:
                h = (r - g) / d + 4
            h /= 6

        return int(h * 360), int(s * 100), int(l * 100)

    def _hsl_to_rgb(self, h: int, s: int, l: int) -> Tuple[int, int, int]:
        """Convert HSL to RGB."""
        h, s, l = h / 360, s / 100, l / 100

        if s == 0:
            r = g = b = l
        else:
            def hue_to_rgb(p, q, t):
                if t < 0:
                    t += 1
                if t > 1:
                    t -= 1
                if t < 1/6:
                    return p + (q - p) * 6 * t
                if t < 1/2:
                    return q
                if t < 2/3:
                    return p + (q - p) * (2/3 - t) * 6
                return p

            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q
            r = hue_to_rgb(p, q, h + 1/3)
            g = hue_to_rgb(p, q, h)
            b = hue_to_rgb(p, q, h - 1/3)

        return int(r * 255), int(g * 255), int(b * 255)

    def _parse_color(self, color: str) -> Tuple[int, int, int]:
        """Parse color string to RGB."""
        color = color.strip()

        # HEX
        if color.startswith('#'):
            return self._hex_to_rgb(color)

        # RGB
        rgb_match = re.match(r'rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', color, re.I)
        if rgb_match:
            return int(rgb_match.group(1)), int(rgb_match.group(2)), int(rgb_match.group(3))

        # HSL
        hsl_match = re.match(r'hsl\s*\(\s*(\d+)\s*,\s*(\d+)%?\s*,\s*(\d+)%?\s*\)', color, re.I)
        if hsl_match:
            h, s, l = int(hsl_match.group(1)), int(hsl_match.group(2)), int(hsl_match.group(3))
            return self._hsl_to_rgb(h, s, l)

        # Named colors
        named_colors = {
            "red": (255, 0, 0), "green": (0, 128, 0), "blue": (0, 0, 255),
            "white": (255, 255, 255), "black": (0, 0, 0), "yellow": (255, 255, 0),
            "cyan": (0, 255, 255), "magenta": (255, 0, 255), "orange": (255, 165, 0),
            "purple": (128, 0, 128), "pink": (255, 192, 203), "gray": (128, 128, 128),
        }
        if color.lower() in named_colors:
            return named_colors[color.lower()]

        raise ValueError(f"Cannot parse color: {color}")

    def color_convert(self, color: str) -> str:
        """Convert color between formats."""
        try:
            r, g, b = self._parse_color(color)
            h, s, l = self._rgb_to_hsl(r, g, b)

            return json.dumps({
                "hex": self._rgb_to_hex(r, g, b),
                "rgb": f"rgb({r}, {g}, {b})",
                "hsl": f"hsl({h}, {s}%, {l}%)",
                "values": {
                    "r": r, "g": g, "b": b,
                    "h": h, "s": s, "l": l,
                },
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def color_palette(
        self,
        base_color: str,
        type: str = "complementary",
    ) -> str:
        """Generate color palette."""
        try:
            r, g, b = self._parse_color(base_color)
            h, s, l = self._rgb_to_hsl(r, g, b)

            colors = []
            type_lower = type.lower()

            if type_lower == "complementary":
                colors = [
                    (h, s, l),
                    ((h + 180) % 360, s, l),
                ]
            elif type_lower == "analogous":
                colors = [
                    ((h - 30) % 360, s, l),
                    (h, s, l),
                    ((h + 30) % 360, s, l),
                ]
            elif type_lower == "triadic":
                colors = [
                    (h, s, l),
                    ((h + 120) % 360, s, l),
                    ((h + 240) % 360, s, l),
                ]
            elif type_lower == "split":
                colors = [
                    (h, s, l),
                    ((h + 150) % 360, s, l),
                    ((h + 210) % 360, s, l),
                ]
            elif type_lower == "shades":
                colors = [
                    (h, s, max(0, l - 30)),
                    (h, s, max(0, l - 15)),
                    (h, s, l),
                    (h, s, min(100, l + 15)),
                    (h, s, min(100, l + 30)),
                ]
            else:
                return f"Unknown palette type: {type}"

            palette = []
            for hue, sat, light in colors:
                rgb = self._hsl_to_rgb(hue, sat, light)
                palette.append(self._rgb_to_hex(*rgb))

            return json.dumps({
                "base": self._rgb_to_hex(r, g, b),
                "type": type,
                "palette": palette,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def color_contrast(self, color1: str, color2: str) -> str:
        """Check WCAG contrast ratio."""
        try:
            def luminance(r, g, b):
                rgb = []
                for c in [r, g, b]:
                    c = c / 255
                    if c <= 0.03928:
                        c = c / 12.92
                    else:
                        c = ((c + 0.055) / 1.055) ** 2.4
                    rgb.append(c)
                return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]

            r1, g1, b1 = self._parse_color(color1)
            r2, g2, b2 = self._parse_color(color2)

            l1 = luminance(r1, g1, b1)
            l2 = luminance(r2, g2, b2)

            lighter = max(l1, l2)
            darker = min(l1, l2)
            ratio = (lighter + 0.05) / (darker + 0.05)

            # WCAG levels
            aa_normal = ratio >= 4.5
            aa_large = ratio >= 3
            aaa_normal = ratio >= 7
            aaa_large = ratio >= 4.5

            return json.dumps({
                "color1": self._rgb_to_hex(r1, g1, b1),
                "color2": self._rgb_to_hex(r2, g2, b2),
                "ratio": round(ratio, 2),
                "wcag": {
                    "AA_normal": "Pass" if aa_normal else "Fail",
                    "AA_large": "Pass" if aa_large else "Fail",
                    "AAA_normal": "Pass" if aaa_normal else "Fail",
                    "AAA_large": "Pass" if aaa_large else "Fail",
                },
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def color_blend(
        self,
        color1: str,
        color2: str,
        ratio: float = 0.5,
    ) -> str:
        """Blend two colors."""
        try:
            r1, g1, b1 = self._parse_color(color1)
            r2, g2, b2 = self._parse_color(color2)

            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)

            return json.dumps({
                "color1": self._rgb_to_hex(r1, g1, b1),
                "color2": self._rgb_to_hex(r2, g2, b2),
                "ratio": ratio,
                "result": self._rgb_to_hex(r, g, b),
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def color_lighten(self, color: str, amount: float = 0.2) -> str:
        """Lighten color."""
        try:
            r, g, b = self._parse_color(color)
            h, s, l = self._rgb_to_hsl(r, g, b)
            new_l = min(100, l + int(amount * 100))
            new_r, new_g, new_b = self._hsl_to_rgb(h, s, new_l)

            return json.dumps({
                "original": self._rgb_to_hex(r, g, b),
                "lightened": self._rgb_to_hex(new_r, new_g, new_b),
                "amount": amount,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def color_darken(self, color: str, amount: float = 0.2) -> str:
        """Darken color."""
        try:
            r, g, b = self._parse_color(color)
            h, s, l = self._rgb_to_hsl(r, g, b)
            new_l = max(0, l - int(amount * 100))
            new_r, new_g, new_b = self._hsl_to_rgb(h, s, new_l)

            return json.dumps({
                "original": self._rgb_to_hex(r, g, b),
                "darkened": self._rgb_to_hex(new_r, new_g, new_b),
                "amount": amount,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def color_random(self, count: int = 1) -> str:
        """Generate random colors."""
        import random
        colors = []
        for _ in range(count):
            r = random.randint(0, 255)
            g = random.randint(0, 255)
            b = random.randint(0, 255)
            colors.append(self._rgb_to_hex(r, g, b))

        if count == 1:
            return colors[0]
        return json.dumps(colors, indent=2)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "convert")
        if action == "convert":
            return self.color_convert(kwargs.get("color", "#FF0000"))
        elif action == "random":
            return self.color_random()
        return f"Unknown action: {action}"
