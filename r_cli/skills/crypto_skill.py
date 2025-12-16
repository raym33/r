"""
Crypto Skill for R CLI.

Cryptographic utilities:
- Hash generation (MD5, SHA256, etc.)
- Password generation
- Base64 encoding/decoding
- UUID generation
"""

import base64
import hashlib
import secrets
import string
import uuid
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class CryptoSkill(Skill):
    """Skill for cryptographic operations."""

    name = "crypto"
    description = "Crypto: hashing, passwords, encoding, UUIDs"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="hash",
                description="Generate hash of text",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to hash",
                        },
                        "algorithm": {
                            "type": "string",
                            "description": "Algorithm: md5, sha1, sha256, sha512 (default: sha256)",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.hash_text,
            ),
            Tool(
                name="hash_file",
                description="Generate hash of a file",
                parameters={
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Path to file",
                        },
                        "algorithm": {
                            "type": "string",
                            "description": "Algorithm: md5, sha1, sha256, sha512",
                        },
                    },
                    "required": ["file_path"],
                },
                handler=self.hash_file,
            ),
            Tool(
                name="password_generate",
                description="Generate secure random password",
                parameters={
                    "type": "object",
                    "properties": {
                        "length": {
                            "type": "integer",
                            "description": "Password length (default: 16)",
                        },
                        "include_symbols": {
                            "type": "boolean",
                            "description": "Include special characters",
                        },
                        "exclude_ambiguous": {
                            "type": "boolean",
                            "description": "Exclude ambiguous chars (0, O, l, 1)",
                        },
                    },
                },
                handler=self.password_generate,
            ),
            Tool(
                name="base64_encode",
                description="Encode text to Base64",
                parameters={
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to encode",
                        },
                    },
                    "required": ["text"],
                },
                handler=self.base64_encode,
            ),
            Tool(
                name="base64_decode",
                description="Decode Base64 to text",
                parameters={
                    "type": "object",
                    "properties": {
                        "encoded": {
                            "type": "string",
                            "description": "Base64 string to decode",
                        },
                    },
                    "required": ["encoded"],
                },
                handler=self.base64_decode,
            ),
            Tool(
                name="uuid_generate",
                description="Generate UUID",
                parameters={
                    "type": "object",
                    "properties": {
                        "version": {
                            "type": "integer",
                            "description": "UUID version: 1 (time-based) or 4 (random, default)",
                        },
                        "count": {
                            "type": "integer",
                            "description": "Number of UUIDs to generate",
                        },
                    },
                },
                handler=self.uuid_generate,
            ),
            Tool(
                name="random_hex",
                description="Generate random hex string",
                parameters={
                    "type": "object",
                    "properties": {
                        "length": {
                            "type": "integer",
                            "description": "Number of bytes (output will be 2x in hex chars)",
                        },
                    },
                },
                handler=self.random_hex,
            ),
            Tool(
                name="random_token",
                description="Generate URL-safe random token",
                parameters={
                    "type": "object",
                    "properties": {
                        "length": {
                            "type": "integer",
                            "description": "Number of bytes",
                        },
                    },
                },
                handler=self.random_token,
            ),
        ]

    def hash_text(self, text: str, algorithm: str = "sha256") -> str:
        """Generate hash of text."""
        try:
            algo = algorithm.lower()
            if algo == "md5":
                h = hashlib.md5(text.encode()).hexdigest()
            elif algo == "sha1":
                h = hashlib.sha1(text.encode()).hexdigest()
            elif algo == "sha256":
                h = hashlib.sha256(text.encode()).hexdigest()
            elif algo == "sha512":
                h = hashlib.sha512(text.encode()).hexdigest()
            else:
                return f"Unknown algorithm: {algorithm}"

            return f"{algo.upper()}: {h}"

        except Exception as e:
            return f"Error: {e}"

    def hash_file(self, file_path: str, algorithm: str = "sha256") -> str:
        """Generate hash of file."""
        try:
            from pathlib import Path
            path = Path(file_path).expanduser()

            if not path.exists():
                return f"File not found: {file_path}"

            algo = algorithm.lower()
            if algo == "md5":
                h = hashlib.md5()
            elif algo == "sha1":
                h = hashlib.sha1()
            elif algo == "sha256":
                h = hashlib.sha256()
            elif algo == "sha512":
                h = hashlib.sha512()
            else:
                return f"Unknown algorithm: {algorithm}"

            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)

            return f"{algo.upper()}: {h.hexdigest()}"

        except Exception as e:
            return f"Error: {e}"

    def password_generate(
        self,
        length: int = 16,
        include_symbols: bool = True,
        exclude_ambiguous: bool = False,
    ) -> str:
        """Generate secure password."""
        chars = string.ascii_letters + string.digits
        if include_symbols:
            chars += "!@#$%^&*()_+-=[]{}|;:,.<>?"

        if exclude_ambiguous:
            for c in "0O1lI":
                chars = chars.replace(c, "")

        password = "".join(secrets.choice(chars) for _ in range(length))
        return password

    def base64_encode(self, text: str) -> str:
        """Encode to Base64."""
        try:
            encoded = base64.b64encode(text.encode()).decode()
            return encoded
        except Exception as e:
            return f"Error: {e}"

    def base64_decode(self, encoded: str) -> str:
        """Decode from Base64."""
        try:
            decoded = base64.b64decode(encoded).decode()
            return decoded
        except Exception as e:
            return f"Error: {e}"

    def uuid_generate(self, version: int = 4, count: int = 1) -> str:
        """Generate UUIDs."""
        uuids = []
        for _ in range(count):
            if version == 1:
                uuids.append(str(uuid.uuid1()))
            else:
                uuids.append(str(uuid.uuid4()))

        return "\n".join(uuids)

    def random_hex(self, length: int = 16) -> str:
        """Generate random hex string."""
        return secrets.token_hex(length)

    def random_token(self, length: int = 32) -> str:
        """Generate URL-safe token."""
        return secrets.token_urlsafe(length)

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "hash")
        if action == "hash":
            return self.hash_text(kwargs.get("text", ""))
        elif action == "password":
            return self.password_generate()
        elif action == "uuid":
            return self.uuid_generate()
        return f"Unknown action: {action}"
