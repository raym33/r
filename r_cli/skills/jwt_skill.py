"""
JWT Skill for R CLI.

JWT token utilities:
- Decode tokens
- Encode/create tokens
- Verify signatures
- Inspect claims
"""

import base64
import hashlib
import hmac
import json
from datetime import datetime
from typing import Optional

from r_cli.core.agent import Skill
from r_cli.core.llm import Tool


class JWTSkill(Skill):
    """Skill for JWT operations."""

    name = "jwt"
    description = "JWT: decode, encode, verify tokens"

    def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="jwt_decode",
                description="Decode a JWT token (without verification)",
                parameters={
                    "type": "object",
                    "properties": {
                        "token": {
                            "type": "string",
                            "description": "JWT token string",
                        },
                    },
                    "required": ["token"],
                },
                handler=self.jwt_decode,
            ),
            Tool(
                name="jwt_encode",
                description="Create a JWT token",
                parameters={
                    "type": "object",
                    "properties": {
                        "payload": {
                            "type": "object",
                            "description": "Token payload (claims)",
                        },
                        "secret": {
                            "type": "string",
                            "description": "Secret key for signing",
                        },
                        "algorithm": {
                            "type": "string",
                            "description": "Algorithm: HS256, HS384, HS512 (default: HS256)",
                        },
                        "expires_in": {
                            "type": "integer",
                            "description": "Expiration in seconds from now",
                        },
                    },
                    "required": ["payload", "secret"],
                },
                handler=self.jwt_encode,
            ),
            Tool(
                name="jwt_verify",
                description="Verify a JWT token signature",
                parameters={
                    "type": "object",
                    "properties": {
                        "token": {
                            "type": "string",
                            "description": "JWT token string",
                        },
                        "secret": {
                            "type": "string",
                            "description": "Secret key for verification",
                        },
                        "algorithm": {
                            "type": "string",
                            "description": "Algorithm: HS256, HS384, HS512",
                        },
                    },
                    "required": ["token", "secret"],
                },
                handler=self.jwt_verify,
            ),
            Tool(
                name="jwt_inspect",
                description="Inspect JWT token details and validity",
                parameters={
                    "type": "object",
                    "properties": {
                        "token": {
                            "type": "string",
                            "description": "JWT token string",
                        },
                    },
                    "required": ["token"],
                },
                handler=self.jwt_inspect,
            ),
        ]

    def _base64url_decode(self, data: str) -> bytes:
        """Decode base64url."""
        padding = 4 - len(data) % 4
        if padding != 4:
            data += "=" * padding
        return base64.urlsafe_b64decode(data)

    def _base64url_encode(self, data: bytes) -> str:
        """Encode to base64url."""
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")

    def jwt_decode(self, token: str) -> str:
        """Decode JWT without verification."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return "Invalid JWT format: expected 3 parts separated by dots"

            header = json.loads(self._base64url_decode(parts[0]))
            payload = json.loads(self._base64url_decode(parts[1]))

            return json.dumps({
                "header": header,
                "payload": payload,
            }, indent=2)

        except Exception as e:
            return f"Error decoding JWT: {e}"

    def jwt_encode(
        self,
        payload: dict,
        secret: str,
        algorithm: str = "HS256",
        expires_in: Optional[int] = None,
    ) -> str:
        """Create JWT token."""
        try:
            # Add timestamps
            now = int(datetime.now().timestamp())
            payload = dict(payload)
            payload["iat"] = now

            if expires_in:
                payload["exp"] = now + expires_in

            # Header
            header = {"alg": algorithm, "typ": "JWT"}

            # Encode parts
            header_b64 = self._base64url_encode(json.dumps(header).encode())
            payload_b64 = self._base64url_encode(json.dumps(payload).encode())

            # Sign
            message = f"{header_b64}.{payload_b64}"

            if algorithm == "HS256":
                signature = hmac.new(
                    secret.encode(), message.encode(), hashlib.sha256
                ).digest()
            elif algorithm == "HS384":
                signature = hmac.new(
                    secret.encode(), message.encode(), hashlib.sha384
                ).digest()
            elif algorithm == "HS512":
                signature = hmac.new(
                    secret.encode(), message.encode(), hashlib.sha512
                ).digest()
            else:
                return f"Unsupported algorithm: {algorithm}"

            signature_b64 = self._base64url_encode(signature)
            token = f"{message}.{signature_b64}"

            return json.dumps({
                "token": token,
                "algorithm": algorithm,
                "expires_at": datetime.fromtimestamp(payload["exp"]).isoformat() if "exp" in payload else None,
            }, indent=2)

        except Exception as e:
            return f"Error encoding JWT: {e}"

    def jwt_verify(
        self,
        token: str,
        secret: str,
        algorithm: str = "HS256",
    ) -> str:
        """Verify JWT signature."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return json.dumps({"valid": False, "error": "Invalid format"}, indent=2)

            message = f"{parts[0]}.{parts[1]}"
            signature = self._base64url_decode(parts[2])

            # Calculate expected signature
            if algorithm == "HS256":
                expected = hmac.new(
                    secret.encode(), message.encode(), hashlib.sha256
                ).digest()
            elif algorithm == "HS384":
                expected = hmac.new(
                    secret.encode(), message.encode(), hashlib.sha384
                ).digest()
            elif algorithm == "HS512":
                expected = hmac.new(
                    secret.encode(), message.encode(), hashlib.sha512
                ).digest()
            else:
                return json.dumps({"valid": False, "error": f"Unsupported algorithm: {algorithm}"}, indent=2)

            valid = hmac.compare_digest(signature, expected)

            # Check expiration
            payload = json.loads(self._base64url_decode(parts[1]))
            expired = False
            if "exp" in payload:
                expired = datetime.now().timestamp() > payload["exp"]

            return json.dumps({
                "valid": valid,
                "signature_valid": valid,
                "expired": expired,
                "algorithm": algorithm,
            }, indent=2)

        except Exception as e:
            return json.dumps({"valid": False, "error": str(e)}, indent=2)

    def jwt_inspect(self, token: str) -> str:
        """Inspect JWT details."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return "Invalid JWT format"

            header = json.loads(self._base64url_decode(parts[0]))
            payload = json.loads(self._base64url_decode(parts[1]))

            result = {
                "header": header,
                "payload": payload,
                "analysis": {},
            }

            # Analyze claims
            now = datetime.now().timestamp()

            if "exp" in payload:
                exp_time = datetime.fromtimestamp(payload["exp"])
                result["analysis"]["expires"] = exp_time.isoformat()
                result["analysis"]["expired"] = now > payload["exp"]
                result["analysis"]["expires_in"] = f"{int(payload['exp'] - now)} seconds" if now < payload["exp"] else "already expired"

            if "iat" in payload:
                iat_time = datetime.fromtimestamp(payload["iat"])
                result["analysis"]["issued_at"] = iat_time.isoformat()

            if "nbf" in payload:
                nbf_time = datetime.fromtimestamp(payload["nbf"])
                result["analysis"]["not_before"] = nbf_time.isoformat()
                result["analysis"]["not_yet_valid"] = now < payload["nbf"]

            if "sub" in payload:
                result["analysis"]["subject"] = payload["sub"]

            if "iss" in payload:
                result["analysis"]["issuer"] = payload["iss"]

            if "aud" in payload:
                result["analysis"]["audience"] = payload["aud"]

            return json.dumps(result, indent=2)

        except Exception as e:
            return f"Error: {e}"

    def execute(self, **kwargs) -> str:
        """Direct skill execution."""
        action = kwargs.get("action", "decode")
        if action == "decode":
            return self.jwt_decode(kwargs.get("token", ""))
        return f"Unknown action: {action}"
