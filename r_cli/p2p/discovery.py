"""
P2P Discovery for R CLI.

Handles peer discovery via mDNS/Bonjour and manual configuration.
Uses zeroconf library for mDNS.
"""

import asyncio
import logging
import socket
from datetime import datetime
from typing import Callable, Optional

from r_cli.p2p.peer import Peer, PeerCapability, PeerStatus
from r_cli.p2p.registry import PeerRegistry
from r_cli.p2p.security import P2PSecurity

logger = logging.getLogger(__name__)

# Check if zeroconf is available
try:
    from zeroconf import ServiceInfo, ServiceStateChange, Zeroconf
    from zeroconf.asyncio import AsyncServiceBrowser, AsyncZeroconf

    ZEROCONF_AVAILABLE = True
except ImportError:
    ZEROCONF_AVAILABLE = False
    logger.debug("zeroconf not installed - mDNS discovery disabled")


class P2PDiscoveryService:
    """
    Handles peer discovery via mDNS/Bonjour and manual configuration.

    mDNS Service Type: _r-cli._tcp.local.

    Features:
    - Automatic LAN discovery via mDNS
    - Manual peer addition for internet peers
    - Service advertisement
    - Peer validation
    """

    SERVICE_TYPE = "_r-cli._tcp.local."
    SERVICE_NAME_PREFIX = "R-CLI-"

    def __init__(
        self,
        registry: PeerRegistry,
        security: P2PSecurity,
        service_name: Optional[str] = None,
        port: int = 8765,
    ):
        self.registry = registry
        self.security = security
        self.service_name = service_name or f"{self.SERVICE_NAME_PREFIX}{security.instance_id[:8]}"
        self.port = port

        self._zeroconf: Optional[AsyncZeroconf] = None
        self._browser: Optional[AsyncServiceBrowser] = None
        self._service_info: Optional[ServiceInfo] = None
        self._running = False
        self._on_peer_discovered: Optional[Callable[[Peer], None]] = None
        self._pending_tasks: set = set()

    # =========================================================================
    # mDNS Discovery
    # =========================================================================

    async def start_discovery(self) -> bool:
        """
        Start mDNS browser for peer discovery.

        Returns True if started successfully.
        """
        if not ZEROCONF_AVAILABLE:
            logger.warning("zeroconf not available - install with: pip install zeroconf")
            return False

        if self._running:
            logger.warning("Discovery already running")
            return False

        try:
            self._zeroconf = AsyncZeroconf()

            # Create service browser
            self._browser = AsyncServiceBrowser(
                self._zeroconf.zeroconf,
                [self.SERVICE_TYPE],
                handlers=[self._on_service_state_change],
            )

            self._running = True
            logger.info(f"Started mDNS discovery for {self.SERVICE_TYPE}")
            return True

        except Exception as e:
            logger.error(f"Failed to start discovery: {e}")
            return False

    async def stop_discovery(self) -> None:
        """Stop mDNS discovery."""
        if self._browser:
            await self._browser.async_cancel()
            self._browser = None

        if self._zeroconf:
            await self._zeroconf.async_close()
            self._zeroconf = None

        self._running = False
        logger.info("Stopped mDNS discovery")

    def _on_service_state_change(
        self,
        zeroconf: "Zeroconf",
        service_type: str,
        name: str,
        state_change: "ServiceStateChange",
    ) -> None:
        """Handle mDNS service state changes."""
        if state_change.name == "Added":
            task = asyncio.create_task(self._handle_service_added(zeroconf, service_type, name))
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)
        elif state_change.name == "Removed":
            self._handle_service_removed(name)

    async def _handle_service_added(
        self,
        zeroconf: "Zeroconf",
        service_type: str,
        name: str,
    ) -> None:
        """Handle a newly discovered service."""
        try:
            info = zeroconf.get_service_info(service_type, name, timeout=3000)
            if not info:
                return

            # Extract peer info
            addresses = info.parsed_addresses()
            if not addresses:
                return

            host = addresses[0]
            port = info.port

            # Parse properties
            properties = {}
            if info.properties:
                for key, value in info.properties.items():
                    if isinstance(key, bytes):
                        key = key.decode()
                    if isinstance(value, bytes):
                        value = value.decode()
                    properties[key] = value

            peer_id = properties.get("peer_id", "")
            peer_name = properties.get("name", name)
            skills = properties.get("skills", "").split(",") if properties.get("skills") else []
            version = properties.get("version", "")

            # Skip if it's us
            if peer_id == self.security.instance_id:
                return

            # Check if we already know this peer
            existing = self.registry.get_peer(peer_id)
            if existing:
                # Update last seen
                existing.last_seen = datetime.now()
                existing.host = host
                existing.port = port
                return

            # Create new peer
            peer = Peer(
                peer_id=peer_id or f"mdns-{host}-{port}",
                name=peer_name,
                host=host,
                port=port,
                status=PeerStatus.DISCOVERED,
                discovered_via="mdns",
                skills=skills,
                version=version,
                capabilities=[PeerCapability.TASK_EXECUTION, PeerCapability.SKILL_SHARING],
            )

            # Add to registry
            try:
                self.registry.add_peer(peer)
                logger.info(f"Discovered peer via mDNS: {peer.name} ({host}:{port})")

                # Notify callback
                if self._on_peer_discovered:
                    self._on_peer_discovered(peer)

            except Exception as e:
                logger.warning(f"Failed to add discovered peer: {e}")

        except Exception as e:
            logger.error(f"Error handling discovered service: {e}")

    def _handle_service_removed(self, name: str) -> None:
        """Handle a removed service."""
        # Mark peer as offline if we can find it
        for peer in self.registry.list_peers():
            if peer.name == name or f"{self.SERVICE_NAME_PREFIX}{peer.peer_id[:8]}" == name:
                self.registry.set_offline(peer.peer_id)
                logger.info(f"Peer went offline: {peer.name}")
                break

    def on_peer_discovered(self, callback: Callable[[Peer], None]) -> None:
        """Register callback for new peer discovery."""
        self._on_peer_discovered = callback

    # =========================================================================
    # mDNS Advertisement
    # =========================================================================

    async def advertise_service(self, skills: Optional[list[str]] = None) -> bool:
        """
        Advertise this instance via mDNS.

        Args:
            skills: List of skill names to advertise

        Returns True if started successfully.
        """
        if not ZEROCONF_AVAILABLE:
            logger.warning("zeroconf not available")
            return False

        if not self._zeroconf:
            self._zeroconf = AsyncZeroconf()

        try:
            # Get local IP
            local_ip = self._get_local_ip()
            if not local_ip:
                logger.error("Could not determine local IP")
                return False

            # Build properties
            properties = {
                b"peer_id": self.security.instance_id.encode(),
                b"name": self.service_name.encode(),
                b"version": b"1.0.0",
            }
            if skills:
                properties[b"skills"] = ",".join(skills).encode()

            # Create service info
            self._service_info = ServiceInfo(
                self.SERVICE_TYPE,
                f"{self.service_name}.{self.SERVICE_TYPE}",
                port=self.port,
                properties=properties,
                addresses=[socket.inet_aton(local_ip)],
            )

            # Register service
            await self._zeroconf.async_register_service(self._service_info)
            logger.info(f"Advertising service: {self.service_name} on {local_ip}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"Failed to advertise service: {e}")
            return False

    async def stop_advertising(self) -> None:
        """Stop mDNS advertisement."""
        if self._service_info and self._zeroconf:
            await self._zeroconf.async_unregister_service(self._service_info)
            self._service_info = None
            logger.info("Stopped advertising service")

    def _get_local_ip(self) -> Optional[str]:
        """Get local IP address."""
        try:
            # Create a socket to determine the local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    # =========================================================================
    # Manual Peer Addition
    # =========================================================================

    def add_manual_peer(
        self,
        host: str,
        port: int = 8765,
        name: Optional[str] = None,
    ) -> Peer:
        """
        Add a peer manually (for internet peers).

        The peer will be in DISCOVERED status until validated and approved.
        """
        peer = Peer(
            name=name or f"Peer at {host}",
            host=host,
            port=port,
            status=PeerStatus.DISCOVERED,
            discovered_via="manual",
        )

        self.registry.add_peer(peer)
        logger.info(f"Added manual peer: {peer.name} ({host}:{port})")
        return peer

    # =========================================================================
    # Peer Validation
    # =========================================================================

    async def validate_peer(self, peer: Peer, timeout: float = 5.0) -> bool:
        """
        Validate that a peer is reachable and running R CLI.

        Attempts to connect to the peer's health endpoint.
        Returns True if valid.
        """
        import httpx

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(f"{peer.url}/health")
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "ok":
                        peer.last_seen = datetime.now()
                        return True
        except Exception as e:
            logger.debug(f"Peer validation failed for {peer.host}:{peer.port}: {e}")
            peer.last_error = str(e)

        return False

    async def validate_and_update_peer(self, peer_id: str) -> bool:
        """Validate a peer and update its status."""
        peer = self.registry.get_peer(peer_id)
        if not peer:
            return False

        is_valid = await self.validate_peer(peer)

        if is_valid:
            if peer.status == PeerStatus.OFFLINE:
                self.registry.set_online(peer_id)
        elif peer.status == PeerStatus.APPROVED:
            self.registry.set_offline(peer_id)

        return is_valid

    # =========================================================================
    # Network Scan
    # =========================================================================

    async def scan_network(self, timeout: float = 5.0) -> list[Peer]:
        """
        Actively scan for peers on the network.

        Triggers mDNS query and waits for responses.
        Returns list of discovered peers.
        """
        if not ZEROCONF_AVAILABLE:
            return []

        discovered = []

        def on_discovered(peer: Peer) -> None:
            discovered.append(peer)

        # Temporarily set callback
        old_callback = self._on_peer_discovered
        self._on_peer_discovered = on_discovered

        # Start discovery if not running
        was_running = self._running
        if not was_running:
            await self.start_discovery()

        # Wait for responses
        await asyncio.sleep(timeout)

        # Restore state
        self._on_peer_discovered = old_callback
        if not was_running:
            await self.stop_discovery()

        return discovered

    @property
    def is_running(self) -> bool:
        """Check if discovery is running."""
        return self._running
