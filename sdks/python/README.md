# R SDK for Python

Official Python SDK for the R CLI API - Your Local AI Agent Runtime.

## Installation

```bash
pip install r-sdk
```

Or install from source:
```bash
cd sdks/python
pip install -e .
```

## Quick Start

```python
from r_sdk import RClient

# Connect to local R CLI server
client = RClient(base_url="http://localhost:8000")

# Check server status
status = client.status()
print(f"Server: {status.status}, Skills: {status.skills_loaded}")

# Chat with AI
response = client.chat("Generate a Python hello world")
print(response.message)
```

## Authentication

### API Key (Recommended)
```python
client = RClient(
    base_url="http://localhost:8000",
    api_key="your-api-key"
)
```

### Username/Password
```python
client = RClient(base_url="http://localhost:8000")
client.login("admin", "password")
```

### JWT Token
```python
client = RClient(
    base_url="http://localhost:8000",
    token="your-jwt-token"
)
```

## Usage Examples

### Chat

```python
from r_sdk import RClient, ChatMessage

client = RClient(api_key="your-key")

# Simple chat
response = client.chat("What is 2 + 2?")
print(response.message)

# With conversation history
history = [
    ChatMessage(role="user", content="My name is Alice"),
    ChatMessage(role="assistant", content="Hello Alice!"),
]
response = client.chat("What's my name?", history=history)

# Force a specific skill
response = client.chat("Generate SQL query", skill="sql")
print(f"Used skill: {response.skill_used}")
print(f"Tools called: {response.tools_called}")

# Streaming
for chunk in client.chat("Write a poem", stream=True):
    print(chunk, end="", flush=True)
```

### Skills

```python
# List all skills
skills = client.list_skills()
for skill in skills:
    print(f"{skill.name}: {skill.description}")
    for tool in skill.tools:
        print(f"  - {tool.name}")

# Get specific skill
skill = client.get_skill("code")
print(skill.description)
```

### API Keys Management

```python
# List your API keys
keys = client.list_api_keys()
for key in keys:
    print(f"{key.name} - {key.scopes}")

# Create new API key
key_value, key_info = client.create_api_key(
    name="My App",
    scopes=["read", "write", "chat"]
)
print(f"Save this key: {key_value}")  # Only shown once!

# Delete an API key
client.delete_api_key(key_info.key_id)
```

### Audit Logs (Admin)

```python
# Get recent audit logs
logs = client.get_audit_logs(limit=100)
for log in logs:
    print(f"[{log.severity}] {log.action}: {log.success}")

# Filter by action
chat_logs = client.get_audit_logs(action="chat.request")

# Filter by success/failure
failures = client.get_audit_logs(success=False)
```

## Async Client

```python
import asyncio
from r_sdk import AsyncRClient

async def main():
    async with AsyncRClient(api_key="your-key") as client:
        # All methods are async
        status = await client.status()
        response = await client.chat("Hello!")
        skills = await client.list_skills()

asyncio.run(main())
```

## Error Handling

```python
from r_sdk import RClient, AuthError, RateLimitError, APIError

client = RClient()

try:
    response = client.chat("Hello")
except AuthError as e:
    print(f"Auth failed: {e.message}")
except RateLimitError as e:
    print(f"Rate limited. Retry after: {e.retry_after}s")
except APIError as e:
    print(f"API error {e.status_code}: {e.message}")
```

## Context Manager

```python
# Client closes automatically
with RClient(api_key="your-key") as client:
    response = client.chat("Hello!")
```

## Type Safety

All responses are typed dataclasses:

```python
from r_sdk import StatusResponse, ChatResponse, SkillInfo

status: StatusResponse = client.status()
response: ChatResponse = client.chat("Hi")
skills: list[SkillInfo] = client.list_skills()
```

## License

MIT
