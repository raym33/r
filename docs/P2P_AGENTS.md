# P2P Distributed Agents

Enable multiple R CLI instances to discover each other, share skills, distribute tasks, and synchronize context.

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Discovery Methods](#discovery-methods)
4. [Security Model](#security-model)
5. [Skill Reference](#skill-reference)
6. [API Reference](#api-reference)
7. [Configuration](#configuration)
8. [Examples](#examples)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The P2P system allows R CLI instances to:

- **Discover peers** automatically on local network (mDNS/Bonjour)
- **Add remote peers** manually for internet connections
- **Execute tasks** on remote peers
- **Invoke remote skills** (PDF generation, SQL, etc.)
- **Synchronize context** and conversation memory
- **Share documents** across instances

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         P2P Network                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────────┐         mDNS          ┌──────────────┐          │
│   │  R CLI (A)   │◀──────────────────────▶│  R CLI (B)   │          │
│   │  MacBook     │                        │  Mac Mini    │          │
│   │  Skills: *   │       HTTPS + JWT      │  Skills: *   │          │
│   └──────┬───────┘◀──────────────────────▶└──────┬───────┘          │
│          │                                       │                  │
│          │              Manual IP                │                  │
│          │         ┌──────────────┐              │                  │
│          └────────▶│  R CLI (C)   │◀─────────────┘                  │
│                    │  Cloud VPS   │                                 │
│                    │  Skills: *   │                                 │
│                    └──────────────┘                                 │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### 1. Install with P2P Support

```bash
pip install r-cli-ai[p2p]
```

### 2. Start the Server

```bash
# On each R CLI instance
r serve --host 0.0.0.0 --port 8765
```

### 3. Discover Peers

```bash
# Using chat interface
r chat "discover peers on the network"

# Using API
curl -X POST http://localhost:8765/v1/p2p/discover
```

### 4. Approve Peers

```bash
# List pending peers
curl http://localhost:8765/v1/p2p/pending

# Approve a peer
curl -X POST http://localhost:8765/v1/p2p/approve/peer-abc123
```

### 5. Collaborate

```bash
# Execute task on remote peer
r chat "ask office-mac to convert report.docx to PDF"

# Invoke remote skill
r chat "use the SQL skill on database-server to query sales data"
```

---

## Discovery Methods

### mDNS (Local Network)

Automatic discovery using Bonjour/mDNS. Works on the same LAN without configuration.

```bash
# Start discovery (5 second scan)
curl -X POST http://localhost:8765/v1/p2p/discover \
  -d '{"timeout": 5}'

# Response
{
  "discovered": 3,
  "peers": [
    {"name": "office-mac", "host": "192.168.1.101", "port": 8765},
    {"name": "server-room", "host": "192.168.1.102", "port": 8765},
    {"name": "laptop", "host": "192.168.1.103", "port": 8765}
  ]
}
```

### Manual (Internet)

Add peers by IP address or hostname for internet connections.

```bash
# Add peer manually
curl -X POST http://localhost:8765/v1/p2p/peers \
  -H "Content-Type: application/json" \
  -d '{
    "host": "my-server.example.com",
    "port": 8765,
    "name": "cloud-server"
  }'
```

---

## Security Model

### Trust Levels

| Level | Value | Capabilities |
|-------|-------|--------------|
| Unknown | 0 | None |
| Pending | 10 | None (awaiting approval) |
| Basic | 50 | Execute tasks |
| Trusted | 75 | Skills + context sync |
| Full | 100 | Everything |

### Approval Flow

```
1. Peer A discovers Peer B (mDNS or manual)
         │
         ▼
2. Peer A requests connection
         │
         ▼
3. Peer B marks A as "pending"
         │
         ▼
4. User on Peer B approves/rejects
         │
         ▼
5. If approved: Challenge-response authentication
         │
         ▼
6. JWT tokens for subsequent requests
```

### Authentication

- **Challenge-Response**: Initial handshake with HMAC
- **JWT Tokens**: Short-lived tokens for API calls
- **Mutual TLS** (optional): For high-security environments

---

## Skill Reference

The `p2p` skill provides 12 tools:

### Discovery

| Tool | Description |
|------|-------------|
| `discover_peers` | Scan network for R CLI instances |
| `add_peer` | Add peer manually by IP/hostname |

### Management

| Tool | Description |
|------|-------------|
| `list_peers` | List all known peers |
| `approve_peer` | Approve pending peer |
| `reject_peer` | Reject pending peer |
| `peer_status` | Get detailed peer status |

### Remote Operations

| Tool | Description |
|------|-------------|
| `remote_task` | Execute task on remote peer |
| `remote_skill` | Invoke specific skill on peer |
| `find_skill` | Find peers with a specific skill |

### Synchronization

| Tool | Description |
|------|-------------|
| `sync_context` | Sync conversation context |
| `share_document` | Share document with peers |
| `p2p_status` | Get P2P system status |

### Chat Examples

```
User: discover peers
Agent: [calls discover_peers(timeout=5)]
       Found 3 peers on the network:
       - office-mac (192.168.1.101) - Online
       - server-room (192.168.1.102) - Online
       - laptop (192.168.1.103) - Offline

User: approve office-mac
Agent: [calls approve_peer(peer_id="abc123")]
       Peer 'office-mac' approved with trust level: Trusted

User: ask server-room to run SQL query "SELECT * FROM users LIMIT 10"
Agent: [calls remote_skill(peer_id="xyz789", skill="sql", tool="query", args={...})]
       Query executed on server-room. Results:
       | id | name    | email           |
       |----|---------|-----------------|
       | 1  | Alice   | alice@example.com |
       | 2  | Bob     | bob@example.com   |
       ...
```

---

## API Reference

### Status & Discovery

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/p2p/status` | P2P system status |
| POST | `/v1/p2p/discover` | Start mDNS discovery |

### Peer Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/p2p/peers` | List all peers |
| POST | `/v1/p2p/peers` | Add peer manually |
| GET | `/v1/p2p/peers/{id}` | Get peer details |
| DELETE | `/v1/p2p/peers/{id}` | Remove peer |

### Approval

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/p2p/pending` | List pending peers |
| POST | `/v1/p2p/approve/{id}` | Approve peer |
| POST | `/v1/p2p/reject/{id}` | Reject peer |

### Remote Operations

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/p2p/task` | Receive task from peer |
| POST | `/v1/p2p/skill` | Receive skill invocation |
| POST | `/v1/p2p/sync` | Receive context sync |

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/p2p/auth/handshake` | Initial authentication |

---

## Configuration

Add to `~/.r-cli/config.yaml`:

```yaml
p2p:
  # Enable P2P functionality
  enabled: true

  # Port for P2P server
  listen_port: 8765

  # Advertise via mDNS
  advertise_mdns: true

  # Require approval for new peers
  require_approval: true

  # Auto-discover peers on startup
  auto_discover: true

  # Maximum number of peers
  max_peers: 20

  # Task timeout in seconds
  task_timeout: 120

  # Skills to expose (empty = all)
  expose_skills: []

  # Skills to hide from peers
  hide_skills:
    - ssh  # Don't expose SSH to peers
```

---

## Examples

### Distributed Document Processing

```bash
# On your laptop
r chat "
I have 100 PDF files to process.
Distribute the work across office-mac and server-room.
Extract text from each PDF and combine into a single report.
"

# R CLI will:
# 1. Split the files into batches
# 2. Send batches to each peer
# 3. Each peer uses OCR/PDF skills
# 4. Collect and merge results
```

### Remote Database Queries

```bash
# From any R CLI instance
r chat "
Connect to database-server peer and run:
SELECT customer_name, total_orders
FROM customers
WHERE total_orders > 100
"
```

### Collaborative RAG

```bash
# Sync knowledge bases
r chat "sync my RAG documents with research-mac"

# Query across peers
r chat "search all peers for information about quantum computing"
```

### Task Delegation

```bash
# Delegate heavy computation
r chat "
Ask gpu-server to:
1. Load the image generation model
2. Generate 10 variations of 'sunset over mountains'
3. Send the results back
"
```

---

## Troubleshooting

### Peer Not Found

```bash
# Check if peer is online
ping 192.168.1.101

# Check if R CLI server is running
curl http://192.168.1.101:8765/health

# Try manual add instead of mDNS
curl -X POST http://localhost:8765/v1/p2p/peers \
  -d '{"host": "192.168.1.101", "port": 8765}'
```

### Authentication Failed

```bash
# Check peer status
curl http://localhost:8765/v1/p2p/peers

# Re-approve peer if needed
curl -X POST http://localhost:8765/v1/p2p/approve/peer-id
```

### mDNS Not Working

```bash
# Check if zeroconf is installed
pip install zeroconf

# Check firewall allows mDNS (port 5353)
# macOS: System Preferences > Security > Firewall

# Fallback to manual discovery
curl -X POST http://localhost:8765/v1/p2p/peers \
  -d '{"host": "192.168.1.x", "port": 8765}'
```

### Timeout on Remote Operations

```bash
# Increase timeout in config
# ~/.r-cli/config.yaml
p2p:
  task_timeout: 300  # 5 minutes

# Or check network latency
ping peer-hostname
```

---

## Further Reading

- [Distributed AI Documentation](DISTRIBUTED_AI.md)
- [R CLI Complete Guide](COMPLETE_GUIDE.md)
- [Security Best Practices](SECURITY.md)
