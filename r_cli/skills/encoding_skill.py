"""
Encoding Skill for R CLI.

Text encoding utilities:
- Convert between encodings
- Detect encoding
- Handle Unicode
- Escape sequences
"""

import codecs
import json
import unicodedata
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class EncodingSkill(Skill):
    """Skill for text encoding operations."""

    name = "encoding"
    description = "Encoding: convert, detect, unicode, escape sequences"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="encoding_convert",
                description="Convert text between encodings",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to convert",
                        },
                        "from_encoding": {
                            "type": "string",
                            "description": "Source encoding (default: utf-8)",
                        },
                        "to_encoding": {
                            "type": "string",
                            "description": "Target encoding",
                        },
                    },
                    "required": ["text", "to_encoding"],
                },
                handler=self.encoding_convert,
            ),
            Tool(
                name="encoding_detect",
                description="Detect text encoding",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to analyze",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.encoding_detect,
            ),
            Tool(
                name="encoding_list",
                description="List available encodings",
                parameters={
                    "type": "object",
                    "properties": {
                        "filter": {
                            "type": "string",
                            "description": "Filter by name (optional)",
                        },
                    },
                },
                handler=self.encoding_list,
            ),
            Tool(
                name="unicode_info",
                description="Get Unicode information for character(s)",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Character(s) to analyze",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.unicode_info,
            ),
            Tool(
                name="unicode_from_codepoint",
                description="Get character from Unicode codepoint",
                parameters={
                    "type": "object",
                    "properties": {
                        "codepoint": {
                            "type": "string",
                            "description": "Codepoint (e.g., U+0041, 0x41, 65)",
                        },
                    },
                    "required": ["codepoint"],
                },
                handler=self.unicode_from_codepoint,
            ),
            Tool(
                name="escape_unicode",
                description="Escape text to Unicode escape sequences",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to escape",
                        },
                        "format": {
                            "type": "string",
                            "description": "Format: python, json, html, css",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.escape_unicode,
            ),
            Tool(
                name="unescape_unicode",
                description="Unescape Unicode sequences to text",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text with escape sequences",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.unescape_unicode,
            ),
            Tool(
                name="hex_encode",
                description="Encode text to hexadecimal",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to encode",
                        },
                        "encoding": {
                            "type": "string",
                            "description": "Text encoding (default: utf-8)",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.hex_encode,
            ),
            Tool(
                name="hex_decode",
                description="Decode hexadecimal to text",
                parameters={
                    "type": "object",
                    "properties": {
                        "hex_string": {
                            "type": "string",
                            "description": "Hex string to decode",
                        },
                        "encoding": {
                            "type": "string",
                            "description": "Text encoding (default: utf-8)",
                        },
                    },
                    "required": ["hex_string"],
                },
                handler=self.hex_decode,
            ),
        ]

    def encoding_convert(
        self,
        text: str,
        to_encoding: str,
        from_encoding: str = "utf-8",
    ) -> str:
        """Convert text between encodings."""
        try:
            # Encode to bytes, then decode to target
            encoded = text.encode(to_encoding, errors="replace")

            return json.dumps({
                "original": text,
                "from_encoding": from_encoding,
                "to_encoding": to_encoding,
                "bytes": encoded.hex(),
                "length": len(encoded),
            }, indent=2)

        except LookupError:
            return f"Unknown encoding: {to_encoding}"
        except Exception as e:
            return f"Error: {e}"

    def encoding_detect(self, text: str) -> str:
        """Detect text encoding characteristics."""
        try:
            # Check if ASCII
            try:
                text.encode("ascii")
                is_ascii = True
            except UnicodeEncodeError:
                is_ascii = False

            # Analyze characters
            has_unicode = any(ord(c) > 127 for c in text)
            has_bom = text.startswith("\ufeff")

            # Get unique scripts/categories
            categories = set()
            scripts = set()
            for char in text:
                categories.add(unicodedata.category(char))
                try:
                    scripts.add(unicodedata.name(char).split()[0])
                except ValueError:
                    pass

            return json.dumps({
                "is_ascii": is_ascii,
                "has_unicode": has_unicode,
                "has_bom": has_bom,
                "length_chars": len(text),
                "length_bytes_utf8": len(text.encode("utf-8")),
                "categories": sorted(categories),
                "likely_encoding": "ASCII" if is_ascii else "UTF-8",
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def encoding_list(self, filter: Optional[str] = None) -> str:
        """List available encodings."""
        # Common encodings
        encodings = [
            "utf-8", "utf-16", "utf-32", "ascii",
            "latin-1", "iso-8859-1", "iso-8859-15",
            "cp1252", "cp437", "cp850",
            "mac-roman", "big5", "gb2312", "gbk", "gb18030",
            "euc-jp", "shift-jis", "iso-2022-jp",
            "euc-kr", "iso-2022-kr",
            "koi8-r", "koi8-u",
        ]

        if filter:
            encodings = [e for e in encodings if filter.lower() in e.lower()]

        return json.dumps({
            "count": len(encodings),
            "encodings": encodings,
        }, indent=2)

    def unicode_info(self, text: str) -> str:
        """Get Unicode information for characters."""
        try:
            chars = []
            for char in text[:20]:  # Limit to 20 chars
                try:
                    name = unicodedata.name(char)
                except ValueError:
                    name = "UNKNOWN"

                chars.append({
                    "char": char,
                    "codepoint": f"U+{ord(char):04X}",
                    "decimal": ord(char),
                    "name": name,
                    "category": unicodedata.category(char),
                })

            return json.dumps({
                "count": len(chars),
                "characters": chars,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def unicode_from_codepoint(self, codepoint: str) -> str:
        """Get character from codepoint."""
        try:
            # Parse various formats
            cp = codepoint.strip()

            if cp.upper().startswith("U+"):
                code = int(cp[2:], 16)
            elif cp.lower().startswith("0x"):
                code = int(cp, 16)
            elif cp.startswith("\\u"):
                code = int(cp[2:], 16)
            else:
                code = int(cp)

            char = chr(code)
            try:
                name = unicodedata.name(char)
            except ValueError:
                name = "UNKNOWN"

            return json.dumps({
                "input": codepoint,
                "character": char,
                "codepoint": f"U+{code:04X}",
                "decimal": code,
                "name": name,
            }, indent=2)

        except (ValueError, OverflowError) as e:
            return f"Invalid codepoint: {e}"

    def escape_unicode(self, text: str, format: str = "python") -> str:
        """Escape to Unicode sequences."""
        try:
            if format == "python":
                escaped = text.encode("unicode_escape").decode("ascii")
            elif format == "json":
                escaped = "".join(
                    f"\\u{ord(c):04x}" if ord(c) > 127 else c
                    for c in text
                )
            elif format == "html":
                escaped = "".join(
                    f"&#x{ord(c):x};" if ord(c) > 127 else c
                    for c in text
                )
            elif format == "css":
                escaped = "".join(
                    f"\\{ord(c):06x}" if ord(c) > 127 else c
                    for c in text
                )
            else:
                return f"Unknown format: {format}"

            return json.dumps({
                "original": text,
                "format": format,
                "escaped": escaped,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def unescape_unicode(self, text: str) -> str:
        """Unescape Unicode sequences."""
        try:
            # Try Python unicode_escape
            try:
                unescaped = codecs.decode(text, "unicode_escape")
            except Exception:
                unescaped = text

            # Handle HTML entities
            import html
            unescaped = html.unescape(unescaped)

            return json.dumps({
                "escaped": text,
                "unescaped": unescaped,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def hex_encode(self, text: str, encoding: str = "utf-8") -> str:
        """Encode text to hex."""
        try:
            encoded = text.encode(encoding)
            hex_string = encoded.hex()

            return json.dumps({
                "original": text,
                "encoding": encoding,
                "hex": hex_string,
                "hex_spaced": " ".join(hex_string[i:i+2] for i in range(0, len(hex_string), 2)),
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def hex_decode(self, hex_string: str, encoding: str = "utf-8") -> str:
        """Decode hex to text."""
        try:
            # Remove spaces and common prefixes
            hex_clean = hex_string.replace(" ", "").replace("0x", "").replace("\\x", "")

            decoded = bytes.fromhex(hex_clean).decode(encoding)

            return json.dumps({
                "hex": hex_string,
                "encoding": encoding,
                "decoded": decoded,
            }, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "detect")
        if action == "detect":
            return self.encoding_detect(kwargs.get("text", ""))
        elif action == "unicode":
            return self.unicode_info(kwargs.get("text", ""))
        return f"Unknown action: {action}"
