"""
P2P Security for R CLI.

Handles peer authentication, key management, and secure tokens.
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from pydantic import BaseModel

from r_cli.p2p.peer import Peer, ApprovalRequest
from r_cli.p2p.exceptions import PeerAuthenticationError

logger = logging.getLogger(__name__)


class PeerToken(BaseModel):
    """Token for authenticated peer communication."""

    token: str
    peer_id: str
    scopes: list[str]
    created_at: datetime
    expires_at: datetime

    @property
    def is_valid(self) -> bool:
        return datetime.now() < self.expires_at


class ChallengeData(BaseModel):
    """Challenge for peer authentication."""

    challenge: str
    created_at: datetime
    expires_at: datetime
    peer_id: str


class P2PSecurity:
    """
    Handles peer authentication and secure communication.

    Security Model:
    1. Each instance has a unique key (generated on first run)
    2. Peers exchange keys during discovery
    3. User must approve new peers before communication
    4. Communication uses HMAC-signed requests
    5. Tokens are short-lived and regularly rotated
    """

    KEYS_DIR = "~/.r-cli/p2p"
    KEY_FILE = "instance_key.json"
    TOKEN_EXPIRY_SECONDS = 3600  # 1 hour
    CHALLENGE_EXPIRY_SECONDS = 300  # 5 minutes

    def __init__(self, keys_dir: Optional[str] = None):
        self.keys_dir = Path(keys_dir or self.KEYS_DIR).expanduser()
        self._instance_key: Optional[str] = None
        self._instance_id: Optional[str] = None
        self._peer_tokens: dict[str, PeerToken] = {}
        self._pending_challenges: dict[str, ChallengeData] = {}
        self._initialize_keys()

    # =========================================================================
    # Key Management
    # =========================================================================

    def _initialize_keys(self) -> None:
        """Generate or load instance key."""
        self.keys_dir.mkdir(parents=True, exist_ok=True)
        key_file = self.keys_dir / self.KEY_FILE

        if key_file.exists():
            try:
                with open(key_file) as f:
                    data = json.load(f)
                    self._instance_key = data["key"]
                    self._instance_id = data["id"]
                    logger.debug(f"Loaded instance key: {self._instance_id[:8]}...")
                    return
            except Exception as e:
                logger.warning(f"Failed to load key, generating new: {e}")

        # Generate new key
        self._instance_key = secrets.token_hex(32)  # 256-bit key
        self._instance_id = self._generate_instance_id(self._instance_key)

        try:
            with open(key_file, "w") as f:
                json.dump({"key": self._instance_key, "id": self._instance_id}, f)
            os.chmod(key_file, 0o600)  # Restrict permissions
            logger.info(f"Generated new instance key: {self._instance_id[:8]}...")
        except Exception as e:
            logger.error(f"Failed to save key: {e}")

    def _generate_instance_id(self, key: str) -> str:
        """Generate a deterministic instance ID from the key."""
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    @property
    def instance_id(self) -> str:
        """Get this instance's unique ID."""
        if not self._instance_id:
            self._initialize_keys()
        return self._instance_id or ""

    @property
    def instance_key(self) -> str:
        """Get this instance's secret key."""
        if not self._instance_key:
            self._initialize_keys()
        return self._instance_key or ""

    def get_fingerprint(self) -> str:
        """Get a human-readable fingerprint for verification."""
        h = hashlib.sha256(self.instance_id.encode()).hexdigest()
        # Format as XX:XX:XX:XX:XX:XX:XX:XX
        return ":".join(h[i : i + 2].upper() for i in range(0, 16, 2))

    # =========================================================================
    # Peer Authentication
    # =========================================================================

    def create_challenge(self, peer_id: str) -> ChallengeData:
        """Create a challenge for peer authentication."""
        challenge = secrets.token_hex(32)
        now = datetime.now()

        data = ChallengeData(
            challenge=challenge,
            created_at=now,
            expires_at=now + timedelta(seconds=self.CHALLENGE_EXPIRY_SECONDS),
            peer_id=peer_id,
        )

        self._pending_challenges[peer_id] = data
        return data

    def respond_to_challenge(self, challenge: str, peer_key: str) -> str:
        """
        Respond to a challenge from another peer.

        Signs the challenge with our key combined with their key.
        """
        # Create response using HMAC
        combined_key = f"{self.instance_key}:{peer_key}"
        response = hmac.new(
            combined_key.encode(),
            challenge.encode(),
            hashlib.sha256,
        ).hexdigest()
        return response

    def verify_challenge_response(
        self,
        peer_id: str,
        response: str,
        peer_key: str,
    ) -> bool:
        """
        Verify a peer's response to our challenge.

        Returns True if the response is valid.
        """
        pending = self._pending_challenges.get(peer_id)
        if not pending:
            logger.warning(f"No pending challenge for peer {peer_id}")
            return False

        if datetime.now() > pending.expires_at:
            logger.warning(f"Challenge expired for peer {peer_id}")
            del self._pending_challenges[peer_id]
            return False

        # Calculate expected response
        combined_key = f"{peer_key}:{self.instance_key}"
        expected = hmac.new(
            combined_key.encode(),
            pending.challenge.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Remove challenge regardless of result
        del self._pending_challenges[peer_id]

        if hmac.compare_digest(response, expected):
            logger.info(f"Challenge verified for peer {peer_id}")
            return True
        else:
            logger.warning(f"Invalid challenge response from peer {peer_id}")
            return False

    # =========================================================================
    # Token Management
    # =========================================================================

    def create_peer_token(
        self,
        peer_id: str,
        peer_key: str,
        scopes: Optional[list[str]] = None,
        expiry_seconds: Optional[int] = None,
    ) -> PeerToken:
        """
        Create a short-lived token for peer communication.

        The token is signed with a shared secret derived from both keys.
        """
        if scopes is None:
            scopes = ["p2p:task", "p2p:skill", "p2p:sync"]

        expiry = expiry_seconds or self.TOKEN_EXPIRY_SECONDS
        now = datetime.now()
        expires_at = now + timedelta(seconds=expiry)

        # Create token payload
        payload = {
            "peer_id": peer_id,
            "scopes": scopes,
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "nonce": secrets.token_hex(16),
        }

        # Sign with shared secret
        shared_secret = self._derive_shared_secret(peer_key)
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        signature = hmac.new(shared_secret, payload_bytes, hashlib.sha256).hexdigest()

        # Combine payload and signature
        token_data = base64.urlsafe_b64encode(payload_bytes).decode()
        token = f"{token_data}.{signature}"

        peer_token = PeerToken(
            token=token,
            peer_id=peer_id,
            scopes=scopes,
            created_at=now,
            expires_at=expires_at,
        )

        self._peer_tokens[peer_id] = peer_token
        return peer_token

    def validate_peer_token(
        self,
        token: str,
        peer_key: str,
    ) -> Optional[dict]:
        """
        Validate and decode a peer token.

        Returns the payload if valid, None otherwise.
        """
        try:
            parts = token.split(".")
            if len(parts) != 2:
                return None

            token_data, signature = parts

            # Decode payload
            payload_bytes = base64.urlsafe_b64decode(token_data)
            payload = json.loads(payload_bytes)

            # Verify signature
            shared_secret = self._derive_shared_secret(peer_key)
            expected_sig = hmac.new(shared_secret, payload_bytes, hashlib.sha256).hexdigest()

            if not hmac.compare_digest(signature, expected_sig):
                logger.warning("Invalid token signature")
                return None

            # Check expiry
            expires_at = datetime.fromisoformat(payload["expires_at"])
            if datetime.now() > expires_at:
                logger.warning("Token expired")
                return None

            return payload

        except Exception as e:
            logger.warning(f"Token validation failed: {e}")
            return None

    def revoke_peer_token(self, peer_id: str) -> bool:
        """Revoke all tokens for a peer."""
        if peer_id in self._peer_tokens:
            del self._peer_tokens[peer_id]
            return True
        return False

    def get_peer_token(self, peer_id: str) -> Optional[PeerToken]:
        """Get existing token for a peer if valid."""
        token = self._peer_tokens.get(peer_id)
        if token and token.is_valid:
            return token
        return None

    def _derive_shared_secret(self, peer_key: str) -> bytes:
        """Derive a shared secret from both keys."""
        combined = f"{self.instance_key}:{peer_key}"
        return hashlib.sha256(combined.encode()).digest()

    # =========================================================================
    # Request Signing
    # =========================================================================

    def sign_request(self, data: dict, peer_key: str) -> str:
        """Sign a request payload for a peer."""
        shared_secret = self._derive_shared_secret(peer_key)
        payload_bytes = json.dumps(data, sort_keys=True).encode()
        return hmac.new(shared_secret, payload_bytes, hashlib.sha256).hexdigest()

    def verify_request(self, data: dict, signature: str, peer_key: str) -> bool:
        """Verify a signed request from a peer."""
        expected = self.sign_request(data, peer_key)
        return hmac.compare_digest(signature, expected)

    # =========================================================================
    # Approval Workflow
    # =========================================================================

    def create_approval_request(
        self,
        peer: Peer,
        discovery_method: str = "manual",
        expiry_hours: int = 24,
    ) -> ApprovalRequest:
        """Create an approval request for a new peer."""
        now = datetime.now()

        # Generate fingerprint for display
        if peer.public_key:
            fingerprint = hashlib.sha256(peer.public_key.encode()).hexdigest()[:16]
            fingerprint = ":".join(fingerprint[i : i + 2].upper() for i in range(0, 16, 2))
        else:
            fingerprint = "Unknown"

        return ApprovalRequest(
            peer=peer,
            requested_at=now,
            expires_at=now + timedelta(hours=expiry_hours),
            fingerprint=fingerprint,
            discovery_method=discovery_method,
        )
