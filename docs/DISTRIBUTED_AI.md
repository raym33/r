# Distributed AI with R CLI

Run large language models (70B+) across multiple Apple Silicon Macs using MLX. Similar to [exo](https://github.com/exo-explore/exo), but integrated with R CLI's 74 skills ecosystem.

---

## Table of Contents

1. [Overview](#overview)
2. [Requirements](#requirements)
3. [Quick Start](#quick-start)
4. [Cluster Setup Guide](#cluster-setup-guide)
5. [Example: 70B Model on 5 Macs](#example-70b-model-on-5-macs)
6. [API Reference](#api-reference)
7. [Skill Reference](#skill-reference)
8. [Performance Tuning](#performance-tuning)
9. [Comparison with exo](#comparison-with-exo)
10. [Troubleshooting](#troubleshooting)

---

## Overview

R CLI's Distributed AI system enables multiple Apple Silicon Macs to collaborate on AI inference by:

- **Ring-weighted partitioning**: Distributes model layers proportionally based on available memory
- **MLX optimization**: Native Apple Silicon acceleration via [mlx-lm](https://github.com/ml-explore/mlx-lm)
- **P2P integration**: Automatic node discovery via mDNS or manual configuration
- **Unified API**: Same REST endpoints work for single-node or distributed inference

### Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Distributed Cluster                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐           │
│   │  Mac Mini 1  │   │  Mac Mini 2  │   │  Mac Mini 3  │           │
│   │   M4 16GB    │   │   M4 16GB    │   │   M4 16GB    │           │
│   │ Layers 0-13  │──▶│ Layers 14-27 │──▶│ Layers 28-41 │──┐        │
│   └──────────────┘   └──────────────┘   └──────────────┘  │        │
│                                                           │        │
│   ┌──────────────┐   ┌──────────────┐                     │        │
│   │  Mac Mini 4  │   │   MacBook    │◀────────────────────┘        │
│   │   M4 16GB    │   │   M4 24GB    │                              │
│   │ Layers 42-55 │──▶│ Layers 56-79 │──▶ Output                    │
│   └──────────────┘   └──────────────┘                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Requirements

### Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| Chip | Apple M1 | Apple M2/M3/M4 |
| RAM per node | 8GB | 16GB+ |
| Network | 1 Gbps | 10 Gbps / Thunderbolt |
| Nodes for 70B | 3-4 nodes | 5+ nodes |

### Software

```bash
# Install R CLI with MLX support
pip install r-cli-ai[mlx]

# Or with all features
pip install r-cli-ai[all-mac]
```

### Memory Requirements by Model

| Model | Parameters | 4-bit | FP16 | Min Nodes (16GB) |
|-------|------------|-------|------|------------------|
| Llama 3.2 | 1B | 1 GB | 3 GB | 1 |
| Qwen 2.5 | 3B | 2 GB | 6 GB | 1 |
| Mistral | 7B | 4 GB | 14 GB | 1 |
| Llama 3.1 | 8B | 4 GB | 16 GB | 1 |
| Llama 2 | 13B | 7 GB | 26 GB | 1 |
| Mixtral | 8x7B | 26 GB | 90 GB | 3 |
| Llama 2 | 70B | 35 GB | 140 GB | 4 |
| Llama 3.1 | 70B | 35 GB | 140 GB | 4 |
| Llama 3.1 | 405B | 200 GB | 800 GB | 20+ |

---

## Quick Start

### Single Node (Local)

```bash
# Start R CLI server
r serve --port 8765

# Check cluster status
curl http://localhost:8765/v1/distributed/status

# Check if your Mac can run a model
curl "http://localhost:8765/v1/distributed/models/requirements?model_name=llama-70b"
```

### Multi-Node Cluster

**On each Mac:**

```bash
# Install R CLI
pip install r-cli-ai[mlx,p2p]

# Start server (use same port on all nodes)
r serve --host 0.0.0.0 --port 8765
```

**On the coordinator Mac:**

```bash
# Add nodes manually
curl -X POST http://localhost:8765/v1/distributed/nodes \
  -H "Content-Type: application/json" \
  -d '{"host": "192.168.1.101", "port": 8765, "name": "mac-mini-1"}'

# Or discover P2P peers automatically
curl -X POST http://localhost:8765/v1/distributed/discover

# Load model across cluster
curl -X POST http://localhost:8765/v1/distributed/models/load \
  -H "Content-Type: application/json" \
  -d '{"model_name": "mlx-community/Meta-Llama-3.1-70B-Instruct-4bit", "quantization": "4bit"}'

# Generate text
curl -X POST http://localhost:8765/v1/distributed/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Explain quantum computing:", "max_tokens": 500}'
```

---

## Cluster Setup Guide

### Step 1: Network Configuration

All Macs must be on the same network. For best performance:

```
Recommended Network Topology:

┌─────────────┐
│   Router    │
│ (10 Gbps)   │
└──────┬──────┘
       │
  ┌────┴────┐
  │ Switch  │ (10 Gbps or Thunderbolt bridge)
  └────┬────┘
       │
   ┌───┴───┬───────┬───────┬───────┐
   │       │       │       │       │
┌──┴──┐ ┌──┴──┐ ┌──┴──┐ ┌──┴──┐ ┌──┴──┐
│Mac 1│ │Mac 2│ │Mac 3│ │Mac 4│ │Mac 5│
└─────┘ └─────┘ └─────┘ └─────┘ └─────┘
```

**Network options (sorted by speed):**

| Connection | Bandwidth | Latency | Best For |
|------------|-----------|---------|----------|
| Thunderbolt 4 Bridge | 40 Gbps | <1ms | 2 Macs |
| 10 GbE | 10 Gbps | <1ms | 3-10 Macs |
| 2.5 GbE | 2.5 Gbps | <1ms | 3-5 Macs |
| 1 GbE | 1 Gbps | <1ms | Budget setup |
| WiFi 6 | 1.2 Gbps | 2-5ms | Not recommended |

### Step 2: Assign Static IPs

Edit `/etc/hosts` on each Mac or use your router's DHCP reservation:

```
192.168.1.100  mac-coordinator
192.168.1.101  mac-mini-1
192.168.1.102  mac-mini-2
192.168.1.103  mac-mini-3
192.168.1.104  mac-mini-4
```

### Step 3: Install R CLI on All Nodes

```bash
# On each Mac
pip install r-cli-ai[mlx,p2p]

# Verify MLX is working
python3 -c "import mlx.core as mx; print(f'MLX version: {mx.__version__}')"
```

### Step 4: Start Servers

**On each node:**

```bash
# Start R CLI server
r serve --host 0.0.0.0 --port 8765

# Or run in background
nohup r serve --host 0.0.0.0 --port 8765 > r-cli.log 2>&1 &
```

### Step 5: Build the Cluster

**From the coordinator Mac:**

```bash
# Add all nodes
for ip in 192.168.1.101 192.168.1.102 192.168.1.103 192.168.1.104; do
  curl -X POST http://localhost:8765/v1/distributed/nodes \
    -H "Content-Type: application/json" \
    -d "{\"host\": \"$ip\", \"port\": 8765}"
done

# Verify cluster
curl http://localhost:8765/v1/distributed/cluster
```

---

## Example: 70B Model on 5 Macs

This example shows how to run **Llama 3.1 70B** on a cluster of:
- 4x Mac Mini M4 (16GB each)
- 1x MacBook Pro M4 (24GB)

### Cluster Specifications

| Node | Device | RAM | Available | Est. TFLOPS |
|------|--------|-----|-----------|-------------|
| mac-coordinator | MacBook Pro M4 | 24 GB | ~16.8 GB | 4.5 |
| mac-mini-1 | Mac Mini M4 | 16 GB | ~11.2 GB | 4.5 |
| mac-mini-2 | Mac Mini M4 | 16 GB | ~11.2 GB | 4.5 |
| mac-mini-3 | Mac Mini M4 | 16 GB | ~11.2 GB | 4.5 |
| mac-mini-4 | Mac Mini M4 | 16 GB | ~11.2 GB | 4.5 |
| **Total** | | **88 GB** | **~61.6 GB** | **22.5** |

### Model Requirements

| Model | 4-bit | Layers | Memory/Layer |
|-------|-------|--------|--------------|
| Llama 3.1 70B | 35 GB | 80 | 0.44 GB |

**Cluster has 61.6 GB available > 42 GB needed (35 GB × 1.2 overhead) ✓**

### Layer Distribution

The ring-weighted partitioner assigns layers proportionally to available memory:

```
┌────────────────────────────────────────────────────────────────────┐
│                    Llama 3.1 70B (80 layers)                       │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  mac-mini-1     mac-mini-2     mac-mini-3     mac-mini-4          │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐        │
│  │ Layers   │   │ Layers   │   │ Layers   │   │ Layers   │        │
│  │  0 - 13  │──▶│ 14 - 27  │──▶│ 28 - 41  │──▶│ 42 - 55  │        │
│  │ (14)     │   │ (14)     │   │ (14)     │   │ (14)     │        │
│  │ 6.2 GB   │   │ 6.2 GB   │   │ 6.2 GB   │   │ 6.2 GB   │        │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘        │
│                                                      │             │
│                                                      ▼             │
│                                              ┌──────────────┐      │
│                                              │  MacBook M4  │      │
│                                              │ Layers 56-79 │      │
│                                              │    (24)      │      │
│                                              │   10.6 GB    │      │
│                                              └──────────────┘      │
│                                                      │             │
│                                                      ▼             │
│                                                   Output           │
└────────────────────────────────────────────────────────────────────┘
```

### Setup Commands

```bash
# 1. On mac-mini-1 (192.168.1.101)
pip install r-cli-ai[mlx,p2p]
r serve --host 0.0.0.0 --port 8765

# 2. On mac-mini-2 (192.168.1.102)
pip install r-cli-ai[mlx,p2p]
r serve --host 0.0.0.0 --port 8765

# 3. On mac-mini-3 (192.168.1.103)
pip install r-cli-ai[mlx,p2p]
r serve --host 0.0.0.0 --port 8765

# 4. On mac-mini-4 (192.168.1.104)
pip install r-cli-ai[mlx,p2p]
r serve --host 0.0.0.0 --port 8765

# 5. On MacBook (coordinator, 192.168.1.100)
pip install r-cli-ai[mlx,p2p]
r serve --host 0.0.0.0 --port 8765
```

### Build Cluster and Load Model

```bash
# From MacBook (coordinator)

# Add all Mac Minis to cluster
curl -X POST http://localhost:8765/v1/distributed/nodes \
  -H "Content-Type: application/json" \
  -d '{"host": "192.168.1.101", "port": 8765, "name": "mac-mini-1"}'

curl -X POST http://localhost:8765/v1/distributed/nodes \
  -H "Content-Type: application/json" \
  -d '{"host": "192.168.1.102", "port": 8765, "name": "mac-mini-2"}'

curl -X POST http://localhost:8765/v1/distributed/nodes \
  -H "Content-Type: application/json" \
  -d '{"host": "192.168.1.103", "port": 8765, "name": "mac-mini-3"}'

curl -X POST http://localhost:8765/v1/distributed/nodes \
  -H "Content-Type: application/json" \
  -d '{"host": "192.168.1.104", "port": 8765, "name": "mac-mini-4"}'

# Check cluster status
curl http://localhost:8765/v1/distributed/cluster | jq

# Verify we can run 70B
curl "http://localhost:8765/v1/distributed/models/requirements?model_name=llama-70b" | jq

# Load the model (this will download ~35GB on first run)
curl -X POST http://localhost:8765/v1/distributed/models/load \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "mlx-community/Meta-Llama-3.1-70B-Instruct-4bit",
    "quantization": "4bit"
  }' | jq

# Check layer assignments
curl http://localhost:8765/v1/distributed/layers | jq
```

### Generate Text

```bash
# Simple generation
curl -X POST http://localhost:8765/v1/distributed/generate \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Write a haiku about distributed computing:",
    "max_tokens": 100,
    "temperature": 0.7
  }' | jq

# Streaming generation
curl -X POST http://localhost:8765/v1/distributed/generate/stream \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain the theory of relativity in simple terms:",
    "max_tokens": 500
  }'
```

### Using the Chat Interface

```bash
# Start interactive chat with distributed inference
r chat

# The agent can now use the distributed_ai skill
> Check the cluster status
> Load llama-70b model
> Generate a story about AI
```

### Using Python SDK

```python
import httpx

BASE_URL = "http://localhost:8765"

# Check cluster
response = httpx.get(f"{BASE_URL}/v1/distributed/cluster")
print(response.json())

# Load model
response = httpx.post(
    f"{BASE_URL}/v1/distributed/models/load",
    json={
        "model_name": "mlx-community/Meta-Llama-3.1-70B-Instruct-4bit",
        "quantization": "4bit"
    }
)
print(response.json())

# Generate
response = httpx.post(
    f"{BASE_URL}/v1/distributed/generate",
    json={
        "prompt": "Hello, I am a 70B model running on",
        "max_tokens": 100
    },
    timeout=120.0
)
result = response.json()
print(f"Generated: {result['text']}")
print(f"Speed: {result['tokens_per_second']:.1f} tokens/sec")
```

---

## Expected Performance

### Tokens per Second (Estimates)

Performance depends on network speed, model size, and quantization:

| Cluster | Model | Network | Est. Tokens/sec |
|---------|-------|---------|-----------------|
| 1x M4 Max 128GB | 70B 4-bit | Local | 15-25 |
| 2x M4 Pro 48GB | 70B 4-bit | 10 GbE | 10-18 |
| 5x M4 16-24GB | 70B 4-bit | 10 GbE | 8-15 |
| 5x M4 16-24GB | 70B 4-bit | 1 GbE | 5-10 |
| 5x M4 16-24GB | 70B 4-bit | WiFi 6 | 2-5 |

### Bottlenecks

1. **Network latency**: Activations must pass between nodes for each token
2. **Synchronization**: Nodes must coordinate for each forward pass
3. **Memory bandwidth**: Unified memory is fast but shared with GPU

### Optimization Tips

- Use 10 GbE or Thunderbolt bridge for best performance
- Place nodes with more layers at the end of the pipeline
- Disable WiFi and use wired connections only
- Close other applications to maximize available memory

---

## Comparison with exo

| Feature | R CLI Distributed | exo |
|---------|-------------------|-----|
| **Focus** | Tool orchestration + inference | Pure distributed inference |
| **Skills** | 74 integrated skills | None (inference only) |
| **Partitioning** | Ring-weighted by memory | Ring-weighted by memory |
| **Framework** | MLX (Apple Silicon) | MLX, tinygrad |
| **Hardware** | Apple Silicon only | Apple, NVIDIA, AMD |
| **Discovery** | mDNS + manual | UDP broadcast, Tailscale |
| **Communication** | HTTP/REST | gRPC |
| **API** | OpenAI-compatible | OpenAI-compatible |
| **Installation** | `pip install r-cli-ai[mlx]` | `pip install exo` |
| **Python** | 3.10+ | 3.12+ |
| **Chat UI** | CLI + Web UI | Web UI |
| **RAG** | Built-in (ChromaDB) | Not included |
| **Voice** | Whisper + Piper TTS | Not included |

### When to Use R CLI

- You need integrated tools (PDF, SQL, git, docker, etc.)
- You want RAG/semantic search capabilities
- You prefer REST API integration
- You're building an AI agent system

### When to Use exo

- You only need distributed inference
- You have mixed hardware (NVIDIA + Apple)
- You want gRPC for lower latency
- You need Tailscale for remote clusters

---

## API Reference

### Cluster Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/distributed/status` | Full system status |
| GET | `/v1/distributed/cluster` | Cluster info summary |
| GET | `/v1/distributed/nodes` | List all nodes |
| GET | `/v1/distributed/nodes/{id}` | Get node details |
| POST | `/v1/distributed/nodes` | Add a node |
| DELETE | `/v1/distributed/nodes/{id}` | Remove a node |
| POST | `/v1/distributed/discover` | Discover P2P peers |
| POST | `/v1/distributed/sync-from-p2p` | Sync from P2P |

### Model Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/distributed/models/requirements` | Check model requirements |
| GET | `/v1/distributed/models/info` | Current model info |
| POST | `/v1/distributed/models/load` | Load model |
| POST | `/v1/distributed/models/unload` | Unload model |

### Inference

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/v1/distributed/generate` | Generate text |
| POST | `/v1/distributed/generate/stream` | Stream generation |

### Layer Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/v1/distributed/layers` | Current assignments |
| POST | `/v1/distributed/layers/reassign` | Reassign layers |

---

## Skill Reference

The `distributed_ai` skill provides 10 tools:

| Tool | Description |
|------|-------------|
| `cluster_status` | Get cluster status |
| `add_node` | Add a remote node |
| `remove_node` | Remove a node |
| `list_nodes` | List all nodes |
| `check_model` | Check model requirements |
| `load_model` | Load distributed model |
| `unload_model` | Unload model |
| `generate` | Generate text |
| `assign_layers` | View/reassign layers |
| `sync_p2p` | Sync from P2P peers |

### Example Usage in Chat

```
User: Check if we can run llama-70b
Agent: [calls check_model(model_name="llama-70b")]
       The cluster has 61.6GB available. Llama-70B requires 35GB at 4-bit.
       ✓ The cluster can run this model.

User: Add a new Mac at 192.168.1.105
Agent: [calls add_node(host="192.168.1.105", port=8765, name="mac-mini-5")]
       Node 'mac-mini-5' added to cluster.

User: Load the 70B model
Agent: [calls load_model(model_name="mlx-community/Meta-Llama-3.1-70B-Instruct-4bit")]
       Model loaded across 5 nodes:
       - mac-mini-1: layers 0-13 (14 layers)
       - mac-mini-2: layers 14-27 (14 layers)
       - mac-mini-3: layers 28-41 (14 layers)
       - mac-mini-4: layers 42-55 (14 layers)
       - mac-coordinator: layers 56-79 (24 layers)
```

---

## Troubleshooting

### Node Not Connecting

```bash
# Check if server is running
curl http://192.168.1.101:8765/health

# Check firewall
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate

# Allow R CLI through firewall
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add /usr/bin/python3
```

### MLX Not Available

```bash
# Install MLX
pip install mlx-lm

# Verify
python3 -c "import mlx.core as mx; print(mx.__version__)"
```

### Out of Memory

```bash
# Check available memory
python3 -c "
from r_cli.distributed.cluster import NodeCapabilities
caps = NodeCapabilities.detect_local()
print(f'Available: {caps.available_memory_gb:.1f} GB')
"

# Try a smaller model or add more nodes
```

### Slow Performance

1. Check network speed: `iperf3 -c <other-node-ip>`
2. Use wired connection instead of WiFi
3. Close other applications
4. Try a smaller quantization (4-bit instead of FP16)

### Model Download Failed

```bash
# Download manually
huggingface-cli download mlx-community/Meta-Llama-3.1-70B-Instruct-4bit

# Then load from cache
curl -X POST http://localhost:8765/v1/distributed/models/load \
  -d '{"model_name": "mlx-community/Meta-Llama-3.1-70B-Instruct-4bit"}'
```

---

## Further Reading

- [MLX Documentation](https://ml-explore.github.io/mlx/)
- [mlx-lm GitHub](https://github.com/ml-explore/mlx-lm)
- [MLX Community Models](https://huggingface.co/mlx-community)
- [exo GitHub](https://github.com/exo-explore/exo)
- [R CLI Complete Guide](COMPLETE_GUIDE.md)
- [P2P Distributed Agents](P2P_AGENTS.md)
